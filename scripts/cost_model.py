#!/usr/bin/env python3
"""Cost per 1,000 agent sessions and the fixed monthly network cost, from data/prices.yaml.

Usage: cost_model.py [--markdown]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data" / "prices.yaml"


@dataclass(frozen=True)
class Line:
    item: str
    usage: str
    usd: float


def load(path: Path = PRICES) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(path.read_text())
    return data


def per_1000_sessions(data: dict[str, Any]) -> list[Line]:
    p, s = data["prices"], data["session_profile"]
    n = 1000
    turns = n * s["turns"]
    tool_calls = turns * s["tool_calls_per_turn"]
    model_calls = turns + tool_calls
    input_tokens = model_calls * s["input_tokens_per_model_call"]
    output_tokens = model_calls * s["output_tokens_per_model_call"]
    vcpu_hours = turns * s["runtime_active_cpu_seconds_per_turn"] * s["runtime_vcpu"] / 3600
    gb_hours = n * s["runtime_session_seconds"] * s["runtime_gb"] / 3600
    events = turns * 2
    lambda_gb_s = tool_calls * s["lambda_ms_per_tool_call"] / 1000 * s["lambda_gb"]
    return [
        Line(
            "Model input (Nova Lite)",
            f"{input_tokens / 1e6:.2f}M tokens",
            input_tokens / 1e6 * p["nova_lite_input_per_1m_tokens"],
        ),
        Line(
            "Model output (Nova Lite)",
            f"{output_tokens / 1e6:.2f}M tokens",
            output_tokens / 1e6 * p["nova_lite_output_per_1m_tokens"],
        ),
        Line(
            "Guardrail",
            f"{turns * s['guardrail_text_units_per_turn']:,.0f} text units",
            turns * s["guardrail_text_units_per_turn"] / 1000 * p["guardrail_per_1k_text_units"],
        ),
        Line("Runtime CPU", f"{vcpu_hours:.2f} vCPU-hours", vcpu_hours * p["runtime_per_vcpu_hour"]),
        Line("Runtime memory", f"{gb_hours:.1f} GB-hours", gb_hours * p["runtime_per_gb_hour"]),
        Line("Gateway", f"{tool_calls:,.0f} tool calls", tool_calls / 1000 * p["gateway_per_1k_calls"]),
        Line("Memory events", f"{events:,.0f} events", events / 1000 * p["memory_per_1k_short_term_events"]),
        Line(
            "Memory preference records",
            f"{n * s['long_term_records_per_session']:,.0f} records-month",
            n * s["long_term_records_per_session"] / 1000 * p["memory_per_1k_long_term_records_stored_month"],
        ),
        Line(
            "Lambda tools",
            f"{tool_calls:,.0f} requests, {lambda_gb_s:,.0f} GB-s",
            tool_calls / 1e6 * p["lambda_per_1m_requests"] + lambda_gb_s * p["lambda_per_gb_second"],
        ),
        Line(
            "DynamoDB",
            f"{tool_calls * s['dynamodb_reads_per_tool_call']:,.0f} reads, "
            f"{n * s['dynamodb_writes_per_session']:,.0f} writes",
            tool_calls * s["dynamodb_reads_per_tool_call"] / 1e6 * p["dynamodb_per_1m_read_units"]
            + n * s["dynamodb_writes_per_session"] / 1e6 * p["dynamodb_per_1m_write_units"],
        ),
    ]


def fixed_monthly(data: dict[str, Any]) -> Line:
    f, p = data["fixed"], data["prices"]
    count = f["interface_endpoints"] * f["availability_zones"]
    return Line(
        "Interface VPC endpoints",
        f"{count} endpoint-AZs x {f['hours_per_month']} h",
        count * f["hours_per_month"] * p["interface_endpoint_per_az_hour"],
    )


def markdown(data: dict[str, Any]) -> str:
    lines = per_1000_sessions(data)
    total = sum(line.usd for line in lines)
    out = ["| Item | Usage per 1,000 sessions | USD |", "| --- | --- | --- |"]
    out += [f"| {line.item} | {line.usage} | {line.usd:.2f} |" for line in lines]
    out.append(f"| **Total** | | **{total:.2f}** |")
    fixed = fixed_monthly(data)
    out += ["", f"Fixed: {fixed.item}, {fixed.usage}: USD {fixed.usd:.2f} a month."]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--markdown", action="store_true", help="print a Markdown table")
    args = parser.parse_args(argv)
    data = load()
    if args.markdown:
        print(markdown(data))
        return 0
    lines = per_1000_sessions(data)
    for line in lines:
        print(f"{line.item:<28} {line.usage:<36} {line.usd:>8.2f}")
    print(f"{'Total per 1,000 sessions':<65} {sum(line.usd for line in lines):>8.2f}")
    fixed = fixed_monthly(data)
    print(f"{'Fixed monthly: ' + fixed.item:<65} {fixed.usd:>8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
