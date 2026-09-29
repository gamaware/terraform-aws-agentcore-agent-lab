from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from harness import GATEWAY_ARN, ROOT, authorize, load_schemas, render_policies

CASES = yaml.safe_load((ROOT / "policy" / "cases.yaml").read_text())["cases"]
POLICIES = render_policies()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_policy_decision(case: dict[str, Any]) -> None:
    groups = case["groups"].split() if case["groups"] else None
    allowed = authorize(POLICIES, groups, case["action"], case["input"])
    assert allowed == (case["decision"] == "allow")


def test_limit_is_a_template_variable_not_a_literal() -> None:
    text = (ROOT / "policy" / "open_return.cedar.tftpl").read_text()
    assert "${refund_limit_cents}" in text
    lowered = render_policies(refund_limit_cents=5000)
    lead = ["store-leads"]
    assert authorize(lowered, lead, "returns___open_return", {"refund_cents": 5000})
    assert not authorize(lowered, lead, "returns___open_return", {"refund_cents": 5001})


def test_policies_only_name_tools_the_gateway_exposes() -> None:
    exposed = {f"{s['target']}___{s['tool']['name']}" for s in load_schemas()}
    named = set(re.findall(r'AgentCore::Action::"([^"]+)"', POLICIES))
    assert named, "no actions found in the policies"
    assert named <= exposed


def test_every_exposed_tool_has_an_allow_case_and_write_tools_a_deny_case() -> None:
    exposed = {f"{s['target']}___{s['tool']['name']}" for s in load_schemas()}
    allowed = {c["action"] for c in CASES if c["decision"] == "allow"}
    denied = {c["action"] for c in CASES if c["decision"] == "deny"}
    assert exposed <= allowed
    assert "returns___open_return" in denied


def test_every_policy_is_scoped_to_the_gateway() -> None:
    for path in sorted(Path(ROOT / "policy").glob("*.cedar.tftpl")):
        assert 'resource == AgentCore::Gateway::"${gateway_arn}"' in path.read_text(), path.name


def test_another_gateway_gets_nothing() -> None:
    other = GATEWAY_ARN.replace("abcdefghij", "zzzzzzzzzz")
    assert not authorize(POLICIES, ["store-leads"], "orders___get_order", {"order_id": "HG-100234"}, other)
