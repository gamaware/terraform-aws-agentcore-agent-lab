from __future__ import annotations

import os
from typing import Any

import pytest
from harness import LocalGateway
from scenarios import load_scenarios, returns_count, run_scenario

from harbor_agent.agent import AgentDeps, TurnRequest, run_turn
from harbor_agent.identity import Caller
from harbor_agent.memory import InMemoryMemory
from harbor_agent.scripted import ScriptedModel

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(scenario: dict[str, Any], tables: Any) -> None:
    run = run_scenario(scenario, tables)
    expect = scenario["expect"]
    assert run.gateway_decisions == expect["gateway"]
    assert expect["reply_contains"] in run.reply
    assert run.guard_blocked == expect.get("guard_blocked", 0)
    assert returns_count(tables, os.environ["RETURNS_TABLE"]) == expect["returns_opened"]
    if "model_turns" in expect:
        assert run.model_turns == expect["model_turns"]


def test_every_denied_or_refused_return_leaves_no_record(tables: Any) -> None:
    for scenario in SCENARIOS:
        if scenario["expect"]["returns_opened"] == 0:
            run_scenario(scenario, tables)
    assert returns_count(tables, os.environ["RETURNS_TABLE"]) == 0


def test_open_return_is_never_reached_without_a_lookup(tables: Any) -> None:
    for scenario in SCENARIOS:
        run = run_scenario(scenario, tables)
        verified = False
        for call in run.tool_calls:
            if call["tool"] == "get_order" and call["outcome"] == "ok":
                verified = True
            if call["tool"] == "open_return" and call["outcome"] != "blocked_by_guard":
                assert verified, scenario["id"]


def test_tool_call_limit_terminates_inference(tables: Any) -> None:
    """A model that asks for a tool on every turn is called max_tool_calls + 1 times and never again: the call
    over the limit is cancelled and the turn ends without handing the cancellation back to the model."""
    endless = [{"call": "check_stock", "input": {"sku": "HG-TEAK-CHAIR", "store_id": "ST-014"}}] * 100
    model = ScriptedModel(steps=endless)
    gateway = LocalGateway(groups=["store-associates"])
    caller = Caller(subject="staff-1", groups=("store-associates",), token="")
    request = TurnRequest(prompt="Check the teak chair.", caller=caller, session_id="session-endless")
    deps = AgentDeps(model=model, tools=gateway.tools(), memory=InMemoryMemory(), max_tool_calls=4)
    result = run_turn(request, deps)
    assert len(model.usage) == 5
    assert len(gateway.calls) == 4
    assert [c.outcome for c in result.tool_calls] == ["ok"] * 4 + ["blocked_by_guard"]
    assert result.reply == "Stopped: tool call limit of 4 reached for this request."
