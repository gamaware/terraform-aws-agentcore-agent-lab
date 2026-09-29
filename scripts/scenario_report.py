#!/usr/bin/env python3
"""Print the scripted scenario results as a Markdown table (offline: moto, local gateway, scripted model).

Used to build the results section of report/REPORT.md; tests/test_report.py checks the report still matches.
Run with src, tests and scripts on PYTHONPATH (`make report` does this).
"""

from __future__ import annotations

import os

import boto3
from moto import mock_aws
from scenarios import load_scenarios, returns_count, run_scenario
from seed_tables import seed

TABLES = {
    "ORDERS_TABLE": ("harbor-orders", [("order_id", "HASH")]),
    "STOCK_TABLE": ("harbor-stock", [("sku", "HASH"), ("store_id", "RANGE")]),
    "RETURNS_TABLE": ("harbor-returns", [("return_id", "HASH")]),
}


def _fresh_tables() -> object:
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    for name, keys in TABLES.values():
        dynamodb.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in keys],
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k, _ in keys],
            BillingMode="PAY_PER_REQUEST",
        )
    seed(dynamodb, TABLES["ORDERS_TABLE"][0], TABLES["STOCK_TABLE"][0])
    return dynamodb


def table() -> str:
    # mock_aws() supplies fake credentials; nothing here can reach AWS.
    os.environ.update(
        AWS_DEFAULT_REGION="us-east-1",
        REFUND_LIMIT_CENTS="20000",
        **{env: name for env, (name, _) in TABLES.items()},
    )
    rows = [
        "| Scenario | Tool calls (outcome) | Gateway decisions | Returns opened | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scenario in load_scenarios():
        with mock_aws():
            dynamodb = _fresh_tables()
            run = run_scenario(scenario, dynamodb)
            opened = returns_count(dynamodb, TABLES["RETURNS_TABLE"][0])
        expect = scenario["expect"]
        passed = (
            run.gateway_decisions == expect["gateway"]
            and expect["reply_contains"] in run.reply
            and run.guard_blocked == expect.get("guard_blocked", 0)
            and opened == expect["returns_opened"]
        )
        calls = ", ".join(f"{c['tool']} ({c['outcome']})" for c in _collapse(run.tool_calls))
        decisions = ", ".join(_collapse_words(run.gateway_decisions)) or "none"
        rows.append(f"| {scenario['title']} | {calls} | {decisions} | {opened} | {'pass' if passed else 'FAIL'} |")
    return "\n".join(rows)


def _collapse(calls: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for call in calls:
        if out and out[-1]["tool"].split(" x")[0] == call["tool"] and out[-1]["outcome"] == call["outcome"]:
            base, _, count = out[-1]["tool"].partition(" x")
            out[-1] = {"tool": f"{base} x{int(count or 1) + 1}", "outcome": call["outcome"]}
        else:
            out.append(dict(call))
    return out


def _collapse_words(words: list[str]) -> list[str]:
    collapsed = _collapse([{"tool": w, "outcome": ""} for w in words])
    return [c["tool"] for c in collapsed]


if __name__ == "__main__":
    print(table())
