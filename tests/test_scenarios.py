from __future__ import annotations

import os
from typing import Any

import pytest
from scenarios import load_scenarios, returns_count, run_scenario

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(scenario: dict[str, Any], tables: Any) -> None:
    run = run_scenario(scenario, tables)
    expect = scenario["expect"]
    assert run.gateway_decisions == expect["gateway"]
    assert expect["reply_contains"] in run.reply
    assert run.guard_blocked == expect.get("guard_blocked", 0)
    assert returns_count(tables, os.environ["RETURNS_TABLE"]) == expect["returns_opened"]


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
