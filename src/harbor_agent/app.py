"""AgentCore Runtime entry point: POST /invocations and GET /ping on port 8080.

In ``bedrock`` mode each request connects to the AgentCore Gateway over MCP with the caller's own bearer
token, so the gateway's policy engine authorizes every tool call as that staff member. ``smoke`` mode
(container smoke test only) uses the scripted model, no tools and in-process memory.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient

from harbor_agent.agent import AgentDeps, PromptError, TurnRequest, prompt_from_payload, run_turn
from harbor_agent.config import Settings
from harbor_agent.identity import Caller, IdentityError, caller_from_authorization
from harbor_agent.memory import AgentCoreMemory, InMemoryMemory
from harbor_agent.scripted import ScriptedModel

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("harbor_agent.app")

SMOKE_CALLER = Caller(subject="smoke-test", groups=("store-associates",), token="")
_SMOKE_MEMORY = InMemoryMemory()

app = BedrockAgentCoreApp()


def _bedrock_turn(settings: Settings, request: TurnRequest) -> dict[str, Any]:
    model = BedrockModel(
        model_id=settings.model_id,
        region_name=settings.region,
        guardrail_id=settings.guardrail_id,
        guardrail_version=settings.guardrail_version,
        guardrail_trace="enabled",
        temperature=0.1,
        max_tokens=800,
    )
    memory = AgentCoreMemory(
        client=boto3.client("bedrock-agentcore", region_name=settings.region), memory_id=settings.memory_id
    )
    gateway = MCPClient(url=settings.gateway_url, headers={"Authorization": f"Bearer {request.caller.token}"})
    with gateway:
        deps = AgentDeps(
            model=model,
            tools=gateway.list_tools_sync(),
            memory=memory,
            max_tool_calls=settings.max_tool_calls,
            history_turns=settings.history_turns,
        )
        result = run_turn(request, deps)
    return result.as_payload(request.session_id)


def _smoke_turn(prompt: str, session_id: str) -> dict[str, Any]:
    model = ScriptedModel(steps=[{"say": "Harbor Goods assistant is up."}])
    request = TurnRequest(prompt=prompt, caller=SMOKE_CALLER, session_id=session_id)
    return run_turn(request, AgentDeps(model=model, tools=[], memory=_SMOKE_MEMORY)).as_payload(session_id)


@app.entrypoint
def invoke(payload: Any, context: RequestContext) -> dict[str, Any]:
    settings = Settings.from_env()
    session_id = context.session_id or f"local-{uuid.uuid4()}"
    try:
        prompt = prompt_from_payload(payload)
        if settings.mode == "smoke":
            return _smoke_turn(prompt, session_id)
        headers = context.request_headers or {}
        caller = caller_from_authorization(headers.get("Authorization"))
    except (PromptError, IdentityError) as err:
        LOG.warning('{"event": "rejected_request", "reason": "%s"}', type(err).__name__)
        return {"error": str(err), "session_id": session_id}
    return _bedrock_turn(settings, TurnRequest(prompt=prompt, caller=caller, session_id=session_id))


def main() -> None:
    Settings.from_env()  # fail fast on a bad configuration
    # Binds 0.0.0.0 inside a container (DOCKER_CONTAINER=1 in the image), 127.0.0.1 elsewhere.
    app.run(port=8080)


if __name__ == "__main__":
    main()
