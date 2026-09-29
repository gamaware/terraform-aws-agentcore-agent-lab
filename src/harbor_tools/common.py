"""Shared helpers for the tool Lambdas: input checks, tool-name checks, JSON results."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import boto3

LOG = logging.getLogger("harbor_tools")
LOG.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TOOL_NAME_KEY = "bedrockAgentCoreToolName"
ORDER_ID = re.compile(r"^HG-\d{6}$")
SKU = re.compile(r"^HG-[A-Z0-9-]{2,40}$")
STORE_ID = re.compile(r"^ST-\d{3}$")


class ToolInputError(ValueError):
    """The caller sent arguments this tool does not accept."""


def expect_tool(context: Any, expected: str) -> None:
    """Refuse calls routed to this function for another tool.

    AgentCore Gateway passes the target-prefixed tool name (``target___tool``) in the Lambda client context.
    A direct invocation without it is refused too: these functions are only for the gateway.
    """
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    name = str(custom.get(TOOL_NAME_KEY, ""))
    if name.rsplit("___", maxsplit=1)[-1] != expected:
        raise ToolInputError(f"this function serves {expected}, not {name or 'an unnamed call'}")


def text_arg(event: Mapping[str, Any], key: str, pattern: re.Pattern[str] | None = None, max_len: int = 200) -> str:
    value = event.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} is required")
    value = value.strip()
    if len(value) > max_len:
        raise ToolInputError(f"{key} is longer than {max_len} characters")
    if pattern is not None and not pattern.fullmatch(value):
        raise ToolInputError(f"{key} has an unexpected format")
    return value


def int_arg(event: Mapping[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = event.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"{key} must be an integer")
    if not minimum <= value <= maximum:
        raise ToolInputError(f"{key} must be between {minimum} and {maximum}")
    return value


def table(env_name: str) -> Any:
    """DynamoDB table named by an environment variable (set by Terraform)."""
    return boto3.resource("dynamodb").Table(os.environ[env_name])


def plain(value: Any) -> Any:
    """Convert DynamoDB Decimals to int so results serialize as JSON."""
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def ok(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, **payload}


def refused(reason: str) -> dict[str, Any]:
    """A business refusal: the call was valid but the action is not allowed."""
    return {"ok": False, "error": reason}


def log_call(tool: str, outcome: str, **fields: Any) -> None:
    LOG.info(json.dumps({"event": "tool_call", "tool": tool, "outcome": outcome, **fields}, sort_keys=True))
