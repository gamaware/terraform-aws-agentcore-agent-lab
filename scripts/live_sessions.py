#!/usr/bin/env python3
"""Live sessions against a deployed stack (called by scripts/test-live.sh, never by make verify).

Creates two throwaway staff users (a store associate and a store lead), signs them in, and sends real prompts
to the runtime's "live" endpoint with their access tokens. Checks the outcomes that do not depend on model
wording: every response is a turn payload (not an application error inside HTTP 200), each prompt's tool calls
end with the expected outcome, the returns table holds exactly the expected return, and the runtime rejects a
call without a token.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import urllib3

HTTP = urllib3.PoolManager()


@dataclass(frozen=True)
class LiveCase:
    group: str
    prompt: str
    # A tool that must have run with outcome "ok" in this turn, or None.
    requires_ok: str | None
    # open_return must not succeed in this turn (denied by policy or refused by the tool).
    no_return: bool = False
    # The return_id this turn must create.
    opens: str | None = None


CASES = [
    LiveCase("store-associates", "Where is order HG-100241 and when will it arrive?", "get_order"),
    LiveCase("store-associates", "Does store ST-022 have the oak desk HG-OAK-DESK in stock?", "check_stock"),
    LiveCase(
        "store-leads",
        "Customer returns one teak chair from order HG-100234, wobbly leg. Open the return.",
        "open_return",
        opens="HG-100234#HG-TEAK-CHAIR",
    ),
    LiveCase("store-leads", "Refund the full oak desk on order HG-100263, the top arrived cracked.", None, True),
    LiveCase("store-associates", "Open a return for the linen runner on HG-100234, wrong color.", None, True),
]


def check_response(case: LiveCase, status: int, body: str) -> list[str]:
    """Failures for one turn. HTTP 200 alone proves nothing: the runtime answers application errors with 200."""
    label = repr(case.prompt)
    if status != 200:
        return [f"{label} returned HTTP {status}"]
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return [f"{label} returned a body that is not JSON: {body[:200]!r}"]
    if not isinstance(payload, dict):
        return [f"{label} returned {type(payload).__name__}, not a turn payload"]
    if "error" in payload:
        return [f"{label} returned an application error: {payload['error']}"]
    reply, calls = payload.get("reply"), payload.get("tool_calls")
    if not isinstance(reply, str) or not reply.strip() or not isinstance(calls, list):
        return [f"{label} returned no reply or no tool_calls"]
    outcomes = [(c.get("tool"), c.get("outcome")) for c in calls if isinstance(c, dict)]
    failures: list[str] = []
    if case.requires_ok and (case.requires_ok, "ok") not in outcomes:
        failures.append(f"{label} never ran {case.requires_ok} successfully: {outcomes}")
    if case.no_return and ("open_return", "ok") in outcomes:
        failures.append(f"{label} opened a return it must not open")
    return failures


def check_returns(actual: set[str], expected: set[str]) -> list[str]:
    """The returns table must hold exactly the expected returns: an empty table is a failure, not a pass."""
    failures: list[str] = []
    if expected - actual:
        failures.append(f"expected returns are missing: {sorted(expected - actual)}")
    if actual - expected:
        failures.append(f"unexpected returns were opened: {sorted(actual - expected)}")
    return failures


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
    failures: list[str] = []

    status, _ = _invoke(region, outputs["agent_runtime_arn"], outputs["agent_endpoint_name"], None, "hello")
    print(f"no token -> HTTP {status}")
    if status not in (401, 403):
        failures.append(f"a call without a token returned HTTP {status}")

    expected_returns = set()
    for case in CASES:
        status, body = _invoke(
            region, outputs["agent_runtime_arn"], outputs["agent_endpoint_name"], tokens[case.group], case.prompt
        )
        print(f"[{case.group}] {case.prompt}\n  HTTP {status}: {body[:400]}")
        failures += check_response(case, status, body)
        if case.opens:
            expected_returns.add(case.opens)

    table = session.resource("dynamodb").Table(outputs["table_names"]["returns"])
    actual = {item["return_id"] for item in table.scan(ProjectionExpression="return_id")["Items"]}
    print(f"returns table: {sorted(actual)}")
    failures += check_returns(actual, expected_returns)

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
