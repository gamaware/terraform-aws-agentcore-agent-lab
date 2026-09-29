"""Tool guard: checks that run in the agent process before every tool call.

These are workflow rules, not authorization (the gateway policy engine owns authorization):

- ``open_return`` needs a successful ``get_order`` for the same order earlier in this turn, so the refund
  is based on the order the tool returned, not on what the user typed.
- A turn may make at most ``max_tool_calls`` tool calls, which stops a looping model.

Every decision is logged as one JSON line, which ends up in the runtime's application logs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

LOG = logging.getLogger("harbor_agent.guard")


def short_name(tool_name: str) -> str:
    """``returns___open_return`` -> ``open_return`` (gateway tools are prefixed with their target)."""
    return tool_name.rsplit("___", maxsplit=1)[-1]


@dataclass
class ToolCall:
    tool: str
    input: dict[str, Any]
    outcome: str = "pending"


@dataclass
class ToolGuard(HookProvider):
    max_tool_calls: int = 8
    session_id: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    verified_orders: set[str] = field(default_factory=set)
    _pending: dict[str, ToolCall] = field(default_factory=dict)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before)
        registry.add_callback(AfterToolCallEvent, self.after)

    def _log(self, event: str, call: ToolCall, **fields: Any) -> None:
        record = {"event": event, "session_id": self.session_id, "tool": call.tool, "outcome": call.outcome, **fields}
        LOG.info(json.dumps(record, sort_keys=True))

    def before(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        call = ToolCall(tool=short_name(tool_use["name"]), input=dict(tool_use.get("input") or {}))
        self.calls.append(call)
        reason = self._block_reason(call)
        if reason:
            call.outcome = "blocked_by_guard"
            event.cancel_tool = reason
            self._log("tool_guard", call, reason=reason)
            return
        self._pending[tool_use["toolUseId"]] = call

    def _block_reason(self, call: ToolCall) -> str | None:
        if len(self.calls) > self.max_tool_calls:
            return f"tool call limit of {self.max_tool_calls} reached for this request"
        if call.tool == "open_return":
            order_id = call.input.get("order_id")
            if order_id not in self.verified_orders:
                return "look up the order with get_order before opening a return"
        return None

    def after(self, event: AfterToolCallEvent) -> None:
        call = self._pending.pop(event.tool_use["toolUseId"], None)
        if call is None:
            return
        result = event.result
        succeeded = result.get("status") == "success" and not _refused(result)
        call.outcome = "ok" if succeeded else "error"
        if succeeded and call.tool == "get_order" and isinstance(call.input.get("order_id"), str):
            self.verified_orders.add(call.input["order_id"])
        self._log("tool_call", call)


def _refused(result: Any) -> bool:
    for item in result.get("content", []):
        text = item.get("text")
        if isinstance(text, str) and text.lstrip().startswith("{"):
            try:
                if json.loads(text).get("ok") is False:
                    return True
            except (json.JSONDecodeError, AttributeError):
                continue
        payload = item.get("json")
        if isinstance(payload, dict) and payload.get("ok") is False:
            return True
    return False
