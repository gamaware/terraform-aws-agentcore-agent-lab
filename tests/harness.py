"""Offline stand-in for AgentCore Gateway.

LocalGateway exposes the same tools, with the same ``target___tool`` names and input schemas, as the gateway
Terraform creates from tools/schemas/. Each call is:

1. validated against the tool's input schema,
2. authorized by the Cedar policies in policy/ (rendered the way Terraform renders them) for the calling
   staff member, with the gateway's deny-by-default behavior,
3. sent to the real Lambda handler with a Lambda-like context carrying the tool name.

Handlers run against moto DynamoDB tables, so nothing leaves the machine.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cedarpy
import jsonschema
from strands.tools.tools import PythonAgentTool

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_ARN = "arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/harbor-store-ops-abcdefghij"
REFUND_LIMIT_CENTS = 20000


def load_schemas() -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted((ROOT / "tools" / "schemas").glob("*.json"))]


WRITE_TARGETS = ("returns",)


def read_actions(targets: set[str] | None = None) -> list[str]:
    """The read tools' action names, as locals.read_actions in policy.tf builds them for deployed targets."""
    return sorted(
        f"{s['target']}___{s['tool']['name']}"
        for s in load_schemas()
        if s["target"] not in WRITE_TARGETS and (targets is None or s["target"] in targets)
    )


def render_policies(
    gateway_arn: str = GATEWAY_ARN, refund_limit_cents: int = REFUND_LIMIT_CENTS, targets: set[str] | None = None
) -> str:
    """Render policy/*.cedar.tftpl exactly as Terraform's templatefile() does in policy.tf.

    ``targets`` is the set of deployed gateway targets (default: all schemas, as with a knowledge base).
    """
    actions = ",\n    ".join(f'AgentCore::Action::"{a}"' for a in read_actions(targets))
    rendered = []
    for path in sorted((ROOT / "policy").glob("*.cedar.tftpl")):
        text = path.read_text()
        text = (
            text.replace("${gateway_arn}", gateway_arn)
            .replace("${refund_limit_cents}", str(refund_limit_cents))
            .replace("${read_actions}", actions)
        )
        assert "${" not in text, f"{path.name} has a template variable the harness does not render"
        rendered.append(text)
    return "\n".join(rendered)


def authorize(
    policies: str, groups: list[str] | None, action: str, tool_input: dict[str, Any], gateway_arn: str = GATEWAY_ARN
) -> bool:
    tags = {} if groups is None else {"cognito:groups": " ".join(groups)}
    entities = [
        {"uid": {"type": "AgentCore::OAuthUser", "id": "staff-1"}, "attrs": {}, "parents": [], "tags": tags},
        {"uid": {"type": "AgentCore::Gateway", "id": gateway_arn}, "attrs": {}, "parents": []},
    ]
    request = {
        "principal": 'AgentCore::OAuthUser::"staff-1"',
        "action": f'AgentCore::Action::"{action}"',
        "resource": f'AgentCore::Gateway::"{gateway_arn}"',
        "context": {"input": tool_input},
    }
    result = cedarpy.is_authorized(request, policies, entities)
    assert not result.diagnostics.errors, result.diagnostics.errors
    return result.decision == cedarpy.Decision.Allow


@dataclass
class FakeClientContext:
    custom: dict[str, str]


@dataclass
class FakeLambdaContext:
    tool_name: str
    aws_request_id: str = "req-local-0001"

    @property
    def client_context(self) -> FakeClientContext:
        return FakeClientContext(custom={"bedrockAgentCoreToolName": self.tool_name})


@dataclass
class GatewayCall:
    action: str
    input: dict[str, Any]
    decision: str


@dataclass
class LocalGateway:
    groups: list[str] | None
    handler_overrides: dict[str, Any] = field(default_factory=dict)
    policies: str = field(default_factory=render_policies)
    calls: list[GatewayCall] = field(default_factory=list)

    def _handler(self, schema: dict[str, Any]) -> Any:
        if schema["target"] in self.handler_overrides:
            return self.handler_overrides[schema["target"]]
        module_name, func = schema["handler"].rsplit(".", 1)
        return getattr(importlib.import_module(module_name), func)

    def call(self, schema: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
        action = f"{schema['target']}___{schema['tool']['name']}"
        try:
            jsonschema.validate(tool_input, schema["tool"]["inputSchema"])
        except jsonschema.ValidationError as err:
            self.calls.append(GatewayCall(action, tool_input, "invalid"))
            raise ValueError(f"invalid arguments for {action}: {err.message}") from err
        if not authorize(self.policies, self.groups, action, tool_input):
            self.calls.append(GatewayCall(action, tool_input, "deny"))
            raise PermissionError(f"Tool call to {action} was denied by policy")
        self.calls.append(GatewayCall(action, tool_input, "allow"))
        result: dict[str, Any] = self._handler(schema)(tool_input, FakeLambdaContext(action))
        return result

    def tools(self) -> list[PythonAgentTool]:
        tools = []
        for schema in load_schemas():
            action = f"{schema['target']}___{schema['tool']['name']}"
            spec = {
                "name": action,
                "description": schema["tool"]["description"],
                "inputSchema": {"json": schema["tool"]["inputSchema"]},
            }

            def run(tool_use: Any, *_: Any, _schema: dict[str, Any] = schema, **__: Any) -> dict[str, Any]:
                try:
                    body = self.call(_schema, dict(tool_use.get("input") or {}))
                except (PermissionError, ValueError) as err:
                    return {"toolUseId": tool_use["toolUseId"], "status": "error", "content": [{"text": str(err)}]}
                return {
                    "toolUseId": tool_use["toolUseId"],
                    "status": "success",
                    "content": [{"text": json.dumps(body, sort_keys=True)}],
                }

            tools.append(PythonAgentTool(action, spec, run))
        return tools
