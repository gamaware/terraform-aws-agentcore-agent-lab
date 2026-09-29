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
