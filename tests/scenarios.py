"""Run one scenario from data/scenarios.yaml through the real agent loop, offline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from harness import ROOT, LocalGateway

from harbor_agent.agent import AgentDeps, TurnRequest, run_turn
from harbor_agent.identity import Caller
from harbor_agent.memory import InMemoryMemory
from harbor_agent.scripted import ScriptedModel

SCENARIOS = ROOT / "data" / "scenarios.yaml"


def load_scenarios(path: Path = SCENARIOS) -> list[dict[str, Any]]:
    return list(yaml.safe_load(path.read_text())["scenarios"])


def expand(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in steps:
        repeat = int(step.get("repeat", 1))
        out += [{k: v for k, v in step.items() if k != "repeat"}] * repeat
    return out


def fake_knowledge_base(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """search_policies replacement: the real handler needs a Bedrock knowledge base (see test_tools.py)."""
    return {
        "ok": True,
        "passages": [
            {
                "text": "Furniture and home goods can be returned within 30 days of delivery with proof of purchase.",
                "source": "s3://harbor-policies/returns-policy.md",
                "score": 0.82,
            }
        ],
    }


@dataclass
class ScenarioRun:
    reply: str
    tool_calls: list[dict[str, str]]
    gateway_decisions: list[str]
    guard_blocked: int
    model_turns: int
    input_tokens: int
    output_tokens: int


def run_scenario(scenario: dict[str, Any], dynamodb: Any, memory: InMemoryMemory | None = None) -> ScenarioRun:
    gateway = LocalGateway(groups=scenario.get("groups"), handler_overrides={"policies": fake_knowledge_base})
    model = ScriptedModel(steps=expand(scenario["steps"]))
    caller = Caller(subject="staff-1", groups=tuple(scenario.get("groups") or ()), token="")
    request = TurnRequest(prompt=scenario["prompt"], caller=caller, session_id=f"session-{scenario['id']}")
    result = run_turn(request, AgentDeps(model=model, tools=gateway.tools(), memory=memory or InMemoryMemory()))
    return ScenarioRun(
        reply=result.reply,
        tool_calls=[{"tool": c.tool, "outcome": c.outcome} for c in result.tool_calls],
        gateway_decisions=[c.decision for c in gateway.calls],
        guard_blocked=sum(1 for c in result.tool_calls if c.outcome == "blocked_by_guard"),
        model_turns=len(model.usage),
        input_tokens=sum(u.input_tokens for u in model.usage),
        output_tokens=sum(u.output_tokens for u in model.usage),
    )


def returns_count(dynamodb: Any, table: str) -> int:
    return int(dynamodb.Table(table).scan(Select="COUNT")["Count"])


def as_json(run: ScenarioRun) -> str:
    return json.dumps(run.__dict__, sort_keys=True)
