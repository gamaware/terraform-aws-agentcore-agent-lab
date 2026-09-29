#!/usr/bin/env python3
"""Pre-flight for `make test-live`: refuse a Terraform plan that would create anything public.

Reads `terraform show -json <plan>` output and fails when a planned resource could reach or be reached from
the internet: internet or NAT gateways, Elastic IPs, public subnets, default routes, Route 53 records or zones,
an ECR repository policy, a runtime outside VPC mode, or ingress from 0.0.0.0/0.

Usage: check_live_plan.py <plan.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_TYPES = {
    "aws_internet_gateway",
    "aws_egress_only_internet_gateway",
    "aws_nat_gateway",
    "aws_eip",
    "aws_lb",
    "aws_api_gateway_rest_api",
    "aws_apigatewayv2_api",
    "aws_lambda_function_url",
    "aws_cognito_user_pool_domain",
    "aws_ecr_repository_policy",
}
OPEN_CIDRS = {"0.0.0.0/0", "::/0"}


def planned_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    resources = []
    for change in plan.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        if "create" in actions or "update" in actions:
            resources.append(
                {"address": change["address"], "type": change["type"], "after": change["change"].get("after") or {}}
            )
    return resources


def violations(plan: dict[str, Any]) -> list[str]:
    found = []
    for res in planned_resources(plan):
        rtype, after, address = res["type"], res["after"], res["address"]
        if rtype in FORBIDDEN_TYPES or rtype.startswith("aws_route53"):
            found.append(f"{address}: {rtype} is not allowed in a live test")
        if rtype == "aws_subnet" and after.get("map_public_ip_on_launch"):
            found.append(f"{address}: subnet maps public IPs")
        if rtype == "aws_route" and after.get("destination_cidr_block") in OPEN_CIDRS:
            found.append(f"{address}: default route")
        if rtype == "aws_route_table":
            for route in after.get("route") or []:
                if route.get("cidr_block") in OPEN_CIDRS or route.get("ipv6_cidr_block") in OPEN_CIDRS:
                    found.append(f"{address}: default route")
        if rtype == "aws_vpc_security_group_ingress_rule" and (
            after.get("cidr_ipv4") in OPEN_CIDRS or after.get("cidr_ipv6") in OPEN_CIDRS
        ):
            found.append(f"{address}: ingress from the internet")
        if rtype == "aws_bedrockagentcore_agent_runtime":
            modes = [n.get("network_mode") for n in after.get("network_configuration") or []]
            if modes != ["VPC"]:
                found.append(f"{address}: runtime network mode is {modes}, expected VPC")
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    found = violations(json.loads(Path(argv[1]).read_text()))
    for line in found:
        print(f"refused: {line}", file=sys.stderr)
    if found:
        return 1
    print("pre-flight: no public resources in the plan")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
