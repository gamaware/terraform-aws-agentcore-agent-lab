"""The runtime HTTP contract (/ping, /invocations on 8080) and the scripted model's own behavior."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from starlette.testclient import TestClient

from harbor_agent import app as app_module
from harbor_agent.scripted import ScriptedModel, ScriptExhaustedError


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("HARBOR_AGENT_MODE", "smoke")
    return TestClient(app_module.app)


def test_ping(client: TestClient) -> None:
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json()["status"] == "Healthy"


def test_invocation_in_smoke_mode(client: TestClient) -> None:
    response = client.post(
        "/invocations",
        json={"prompt": "Are you up?"},
        headers={"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "smoke-session-0000000000000000000001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "reply": "Harbor Goods assistant is up.",
        "session_id": "smoke-session-0000000000000000000001",
        "tool_calls": [],
    }


@pytest.mark.parametrize("payload", [{}, {"prompt": ""}, {"prompt": "x" * 4001}, {"question": "hi"}])
def test_bad_payloads_are_rejected_without_calling_a_model(client: TestClient, payload: dict[str, Any]) -> None:
    body = client.post("/invocations", json=payload).json()
    assert "error" in body
    assert "reply" not in body


def test_bedrock_mode_requires_a_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "HARBOR_AGENT_MODE": "bedrock",
        "MODEL_ID": "us.amazon.nova-lite-v1:0",
        "GUARDRAIL_ID": "gr-abc",
        "GUARDRAIL_VERSION": "1",
        "GATEWAY_URL": "https://example.invalid/mcp",
        "MEMORY_ID": "harbor_memory-abcdefghij",
    }.items():
        monkeypatch.setenv(key, value)

    def no_bedrock(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("must not reach Bedrock without a caller")

    monkeypatch.setattr(app_module, "_bedrock_turn", no_bedrock)
    body = TestClient(app_module.app).post("/invocations", json={"prompt": "Where is HG-100241?"}).json()
    assert body["error"] == "missing bearer token"


def test_scripted_model_raises_when_the_script_runs_out() -> None:
    model = ScriptedModel(steps=[])

    async def drain() -> None:
        async for _ in model.stream([{"role": "user", "content": [{"text": "hi"}]}]):
            pass

    with pytest.raises(ScriptExhaustedError):
        asyncio.run(drain())
