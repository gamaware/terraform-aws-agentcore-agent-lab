from __future__ import annotations

import base64
import json

import pytest

from harbor_agent.config import Settings
from harbor_agent.identity import IdentityError, caller_from_authorization


def token(claims: dict[str, object]) -> str:
    def part(obj: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{part({'alg': 'RS256', 'kid': 'k1'})}.{part(claims)}.signature"


def test_caller_from_cognito_access_token() -> None:
    sub = "2f4c9a61-7b1e-4d0a-9c55-3e1f0b7a8d21"
    caller = caller_from_authorization(f"Bearer {token({'sub': sub, 'cognito:groups': ['store-leads']})}")
    assert caller.actor_id == sub
    assert caller.groups == ("store-leads",)


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Basic dXNlcjpwYXNz",
        "Bearer not-a-jwt",
        f"Bearer {token({'groups': []})}",
        f"Bearer {token({'sub': '../../etc'})}",
        "Bearer a.!!!.c",
    ],
)
def test_unusable_tokens_are_rejected(header: str | None) -> None:
    with pytest.raises(IdentityError):
        caller_from_authorization(header)


def test_groups_claim_of_the_wrong_type_is_ignored() -> None:
    caller = caller_from_authorization(f"Bearer {token({'sub': 'abc', 'cognito:groups': 'store-leads'})}")
    assert caller.groups == ()


BEDROCK_ENV = {
    "MODEL_ID": "us.amazon.nova-lite-v1:0",
    "GUARDRAIL_ID": "gr-abc",
    "GUARDRAIL_VERSION": "1",
    "GATEWAY_URL": "https://example.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    "MEMORY_ID": "harbor_memory-abcdefghij",
}


def test_bedrock_mode_needs_every_setting() -> None:
    assert Settings.from_env(BEDROCK_ENV).mode == "bedrock"
    for key in BEDROCK_ENV:
        with pytest.raises(ValueError, match=key):
            Settings.from_env({k: v for k, v in BEDROCK_ENV.items() if k != key})


def test_unknown_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="HARBOR_AGENT_MODE"):
        Settings.from_env({**BEDROCK_ENV, "HARBOR_AGENT_MODE": "debug"})


def test_smoke_mode_needs_nothing() -> None:
    assert Settings.from_env({"HARBOR_AGENT_MODE": "smoke"}).max_tool_calls == 8
