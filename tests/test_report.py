"""report/REPORT.md quotes generated tables; these tests fail when the code or prices change and the report
was not regenerated (make report)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cost_model import fixed_monthly, load, markdown, per_1000_sessions
from scenario_report import table

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "report" / "REPORT.md").read_text()


def test_report_quotes_the_current_cost_model() -> None:
    assert markdown(load()) in REPORT


def test_report_quotes_the_current_scenario_results(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    generated = table()
    assert "FAIL" not in generated
    assert generated in REPORT


def test_cost_model_arithmetic() -> None:
    data = load()
    lines = {line.item: line.usd for line in per_1000_sessions(data)}
    s, p = data["session_profile"], data["prices"]
    model_calls = 1000 * s["turns"] * (1 + s["tool_calls_per_turn"])
    expected_input = model_calls * s["input_tokens_per_model_call"] / 1e6 * p["nova_lite_input_per_1m_tokens"]
    assert lines["Model input (Nova Lite)"] == pytest.approx(expected_input)
    assert lines["Gateway"] == pytest.approx(1000 * s["turns"] * s["tool_calls_per_turn"] / 1000 * 0.005)
    assert fixed_monthly(data).usd == pytest.approx(7 * 2 * 730 * p["interface_endpoint_per_az_hour"])


def test_every_price_has_a_source() -> None:
    data = load()
    assert set(data["sources"]) == {"bedrock", "agentcore", "lambda", "dynamodb", "privatelink"}
    assert all(value > 0 for value in data["prices"].values())


def test_nova_lite_prices_match_the_bedrock_pricing_page() -> None:
    """Amazon Nova Lite (v1), Standard tier, us-east-1: USD 0.06 input and 0.24 output per 1M tokens
    (https://aws.amazon.com/bedrock/pricing/). The first estimate used 0.30 and 1.20."""
    data = load()
    assert data["sources"]["bedrock"] == "https://aws.amazon.com/bedrock/pricing/"
    assert data["prices"]["nova_lite_input_per_1m_tokens"] == 0.06
    assert data["prices"]["nova_lite_output_per_1m_tokens"] == 0.24


def test_charged_memory_retrievals_and_policy_authorizations_are_modelled() -> None:
    """Both are billed by AgentCore (https://aws.amazon.com/bedrock/agentcore/pricing/) and were missing."""
    data = load()
    s, p = data["session_profile"], data["prices"]
    assert data["sources"]["agentcore"] == "https://aws.amazon.com/bedrock/agentcore/pricing/"
    assert p["memory_per_1k_long_term_retrievals"] == 0.50
    assert p["policy_per_authorization_request"] == 0.000025
    lines = {line.item: line.usd for line in per_1000_sessions(data)}
    turns, tool_calls = 1000 * s["turns"], 1000 * s["turns"] * s["tool_calls_per_turn"]
    assert lines["Memory preference retrievals"] == pytest.approx(
        turns * s["memory_records_retrieved_per_turn"] / 1000 * p["memory_per_1k_long_term_retrievals"]
    )
    assert lines["Policy authorizations"] == pytest.approx(
        tool_calls * s["policy_authorizations_per_tool_call"] * p["policy_per_authorization_request"]
    )


def test_memory_retrieval_profile_matches_the_agent_code() -> None:
    memory_src = (ROOT / "src" / "harbor_agent" / "memory.py").read_text()
    assert f'"topK": {load()["session_profile"]["memory_records_retrieved_per_turn"]}' in memory_src


def test_guardrail_prices_every_configured_safeguard() -> None:
    guardrail_tf = (ROOT / "infra" / "terraform" / "agent" / "guardrail.tf").read_text()
    prices = load()["prices"]
    for block, key in [
        ("content_policy_config", "guardrail_content_filters_per_1k_text_units"),
        ("topic_policy_config", "guardrail_denied_topics_per_1k_text_units"),
        ("sensitive_information_policy_config", "guardrail_sensitive_info_per_1k_text_units"),
    ]:
        assert block in guardrail_tf
        assert prices[key] > 0
