from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from check_live_plan import main, violations


def plan(*resources: tuple[str, str, dict[str, Any]], action: str = "create") -> dict[str, Any]:
    return {
        "resource_changes": [
            {"address": address, "type": rtype, "change": {"actions": [action], "after": after}}
            for address, rtype, after in resources
        ]
    }


PRIVATE = plan(
    ("aws_subnet.private[0]", "aws_subnet", {"map_public_ip_on_launch": False}),
    ("aws_route_table.private", "aws_route_table", {"route": []}),
    (
        "aws_bedrockagentcore_agent_runtime.agent",
        "aws_bedrockagentcore_agent_runtime",
        {"network_configuration": [{"network_mode": "VPC"}]},
    ),
    (
        "aws_vpc_security_group_ingress_rule.endpoints_from_runtime",
        "aws_vpc_security_group_ingress_rule",
        {"cidr_ipv4": None, "referenced_security_group_id": "sg-1"},
    ),
)


def test_private_plan_passes() -> None:
    assert violations(PRIVATE) == []


@pytest.mark.parametrize(
    ("resource", "message"),
    [
        (("aws_internet_gateway.igw", "aws_internet_gateway", {}), "not allowed"),
        (("aws_nat_gateway.nat", "aws_nat_gateway", {}), "not allowed"),
        (("aws_route53_record.api", "aws_route53_record", {}), "not allowed"),
        (("aws_cognito_user_pool_domain.d", "aws_cognito_user_pool_domain", {}), "not allowed"),
        (("aws_subnet.public", "aws_subnet", {"map_public_ip_on_launch": True}), "public IPs"),
        (("aws_route.default", "aws_route", {"destination_cidr_block": "0.0.0.0/0"}), "default route"),
        (("aws_route_table.rt", "aws_route_table", {"route": [{"cidr_block": "0.0.0.0/0"}]}), "default route"),
        (
            ("aws_vpc_security_group_ingress_rule.any", "aws_vpc_security_group_ingress_rule", {"cidr_ipv6": "::/0"}),
            "from the internet",
        ),
        (
            (
                "aws_bedrockagentcore_agent_runtime.agent",
                "aws_bedrockagentcore_agent_runtime",
                {"network_configuration": [{"network_mode": "PUBLIC"}]},
            ),
            "expected VPC",
        ),
    ],
)
def test_public_resources_are_refused(resource: tuple[str, str, dict[str, Any]], message: str) -> None:
    found = violations(plan(resource))
    assert len(found) == 1
    assert message in found[0]


def test_deletes_are_ignored() -> None:
    assert violations(plan(("aws_internet_gateway.old", "aws_internet_gateway", {}), action="delete")) == []


def test_cli_exit_codes(tmp_path: Path) -> None:
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(PRIVATE))
    bad.write_text(json.dumps(plan(("aws_eip.ip", "aws_eip", {}))))
    assert main(["x", str(good)]) == 0
    assert main(["x", str(bad)]) == 1
    assert main(["x"]) == 2
