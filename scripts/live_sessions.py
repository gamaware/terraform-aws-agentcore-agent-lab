#!/usr/bin/env python3
"""Live sessions against a deployed stack (called by scripts/test-live.sh, never by make verify).

Creates two throwaway staff users (a store associate and a store lead), signs them in, and sends real prompts
to the runtime's "live" endpoint with their access tokens. Checks the outcomes that do not depend on model
wording: which returns exist afterwards, and that the runtime rejects a call without a token.

Usage: live_sessions.py <terraform-output.json>
Credentials come from the environment (AWS_PROFILE and AWS_REGION, set by test-live.sh).
"""

from __future__ import annotations

import json
import secrets
import string
import sys
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import boto3
import urllib3

HTTP = urllib3.PoolManager()

PROMPTS = [
    ("store-associates", "Where is order HG-100241 and when will it arrive?", None),
    ("store-associates", "Does store ST-022 have the oak desk HG-OAK-DESK in stock?", None),
    (
        "store-leads",
        "Customer returns one teak chair from order HG-100234, wobbly leg. Open the return.",
        "HG-100234#HG-TEAK-CHAIR",
    ),
    ("store-leads", "Refund the full oak desk on order HG-100263, the top arrived cracked.", None),
    ("store-associates", "Open a return for the linen runner on HG-100234, wrong color.", None),
]


def _password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(20))
    return f"{core}aA1!"


def _user(cognito: Any, pool_id: str, client_id: str, group: str) -> str:
    username = f"live-{group}-{uuid.uuid4().hex[:8]}"
    password = _password()
    cognito.admin_create_user(UserPoolId=pool_id, Username=username, MessageAction="SUPPRESS")
    cognito.admin_set_user_password(UserPoolId=pool_id, Username=username, Password=password, Permanent=True)
    cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=username, GroupName=group)
    auth = cognito.admin_initiate_auth(
        UserPoolId=pool_id,
        ClientId=client_id,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return str(auth["AuthenticationResult"]["AccessToken"])


def _invoke(region: str, runtime_arn: str, qualifier: str, token: str | None, prompt: str) -> tuple[int, str]:
    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{urllib.parse.quote(runtime_arn, safe='')}/invocations?qualifier={qualifier}"
    )
    headers = {
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"live-{uuid.uuid4()}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = HTTP.request("POST", url, body=json.dumps({"prompt": prompt}), headers=headers, timeout=120.0)
    return response.status, response.data.decode()


def main(argv: list[str]) -> int:
    outputs = {k: v["value"] for k, v in json.loads(Path(argv[1]).read_text()).items()}
    session = boto3.session.Session()
    region = session.region_name
    cognito = session.client("cognito-idp")
    tokens = {
        group: _user(cognito, outputs["user_pool_id"], outputs["app_client_id"], group)
        for group in ("store-associates", "store-leads")
    }
    failures = []

    status, _ = _invoke(region, outputs["agent_runtime_arn"], outputs["agent_endpoint_name"], None, "hello")
    print(f"no token -> HTTP {status}")
    if status not in (401, 403):
        failures.append(f"a call without a token returned HTTP {status}")

    expected_returns = set()
    for group, prompt, opens in PROMPTS:
        status, body = _invoke(
            region, outputs["agent_runtime_arn"], outputs["agent_endpoint_name"], tokens[group], prompt
        )
        print(f"[{group}] {prompt}\n  HTTP {status}: {body[:400]}")
        if status != 200:
            failures.append(f"{prompt!r} returned HTTP {status}")
        if opens:
            expected_returns.add(opens)

    table = session.resource("dynamodb").Table(outputs["table_names"]["returns"])
    actual = {item["return_id"] for item in table.scan(ProjectionExpression="return_id")["Items"]}
    print(f"returns table: {sorted(actual)}")
    if not actual <= expected_returns:
        failures.append(f"unexpected returns were opened: {sorted(actual - expected_returns)}")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
