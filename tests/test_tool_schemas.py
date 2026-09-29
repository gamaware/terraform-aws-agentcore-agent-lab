"""The MCP tool definitions in tools/schemas/ are the contract between Terraform (gateway targets),
the Lambda handlers and the policies. These tests keep the three in step."""

from __future__ import annotations

import importlib
import re
from typing import Any

import jsonschema
import pytest
from harness import ROOT, load_schemas

SCHEMAS = load_schemas()
# Property types the Terraform gateway target block builds (infra/terraform/agent/gateway.tf).
TERRAFORM_TYPES = {"string", "integer", "number", "boolean"}
NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
TARGET = re.compile(r"^[a-z][a-z0-9-]{2,30}$")


@pytest.mark.parametrize("schema", SCHEMAS, ids=[s["target"] for s in SCHEMAS])
def test_schema_shape(schema: dict[str, Any]) -> None:
    tool = schema["tool"]
    assert TARGET.fullmatch(schema["target"])
    assert NAME.fullmatch(tool["name"])
    assert len(tool["description"]) >= 20
    input_schema = tool["inputSchema"]
    jsonschema.Draft202012Validator.check_schema(input_schema)
    assert input_schema["type"] == "object"
    assert set(input_schema["required"]) <= set(input_schema["properties"])
    for name, prop in input_schema["properties"].items():
        assert prop["type"] in TERRAFORM_TYPES, name
        assert prop.get("description"), name


@pytest.mark.parametrize("schema", SCHEMAS, ids=[s["target"] for s in SCHEMAS])
def test_handler_exists_and_expects_its_tool(schema: dict[str, Any]) -> None:
    module_name, func = schema["handler"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    assert callable(getattr(module, func))
    assert schema["tool"]["name"] == module.TOOL


def test_names_are_unique() -> None:
    assert len({s["tool"]["name"] for s in SCHEMAS}) == len(SCHEMAS)
    assert len({s["target"] for s in SCHEMAS}) == len(SCHEMAS)
    assert len({s["function"] for s in SCHEMAS}) == len(SCHEMAS)


def test_refund_is_an_integer_so_cedar_can_compare_it() -> None:
    returns = next(s for s in SCHEMAS if s["tool"]["name"] == "open_return")
    assert returns["tool"]["inputSchema"]["properties"]["refund_cents"]["type"] == "integer"


def test_terraform_reads_the_schema_directory() -> None:
    gateway_tf = (ROOT / "infra" / "terraform" / "agent" / "gateway.tf").read_text()
    assert 'fileset("${path.module}/../../../tools/schemas", "*.json")' in gateway_tf
