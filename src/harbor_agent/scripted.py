"""A scripted model provider for Strands Agents.

It replays a fixed list of steps instead of calling Amazon Bedrock, so the agent loop, tool routing, guards,
gateway policy and memory can be tested offline and deterministically. Each step is one model turn:

- ``{"call": "get_order", "input": {...}}`` asks for a tool call. The name is matched to the offered tool
  specs by exact name or by the ``target___tool`` suffix the gateway uses.
- ``{"say": "text"}`` ends the turn with text.
- ``{"summarize": true}`` ends the turn with text built from the last tool result, prefixed with
  ``Could not complete:`` when that result is an error. It shows how the agent reports refusals.

The model also records a rough token count per turn (characters / 4) for the cost model.
"""

from __future__ import annotations

import json
import math
from collections.abc import AsyncGenerator, AsyncIterable
from dataclasses import dataclass, field
from typing import Any

from strands.models.model import Model


def _is_business_refusal(text: str) -> bool:
    """Tool Lambdas answer ``{"ok": false, "error": ...}`` for a valid call they refuse."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and parsed.get("ok") is False


class ScriptExhaustedError(RuntimeError):
    """The agent asked the model for more turns than the script has."""


@dataclass
class TurnUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class ScriptedModel(Model):
    steps: list[dict[str, Any]]
    offered_tools: list[str] = field(default_factory=list)
    usage: list[TurnUsage] = field(default_factory=list)
    system_prompts: list[str] = field(default_factory=list)
    _cursor: int = 0

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {"model_id": "scripted", "steps": len(self.steps)}

    def structured_output(self, output_model: Any, prompt: Any, system_prompt: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("the scripted model does not produce structured output")

    def _resolve(self, name: str, tool_specs: list[dict[str, Any]]) -> str:
        for spec in tool_specs:
            offered = spec["name"]
            if offered == name or offered.endswith(f"___{name}"):
                return str(offered)
        return name

    @staticmethod
    def _last_tool_result(messages: list[dict[str, Any]]) -> tuple[str, str]:
        for message in reversed(messages):
            for block in message.get("content", []):
                if "toolResult" in block:
                    result = block["toolResult"]
                    parts = []
                    for item in result.get("content", []):
                        if "text" in item:
                            parts.append(item["text"])
                        elif "json" in item:
                            parts.append(json.dumps(item["json"], sort_keys=True))
                    status = str(result.get("status", "success"))
                    text = " ".join(parts)
                    if status == "success" and _is_business_refusal(text):
                        status = "error"
                    return status, text
        return "none", ""

    async def stream(
        self,
        messages: Any,
        tool_specs: Any = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[Any]:
        specs: list[dict[str, Any]] = list(tool_specs or [])
        self.offered_tools = sorted(str(s["name"]) for s in specs)
        self.system_prompts.append(system_prompt or "")
        if self._cursor >= len(self.steps):
            raise ScriptExhaustedError(f"script has {len(self.steps)} steps and the agent asked for another")
        step = self.steps[self._cursor]
        self._cursor += 1
        input_tokens = math.ceil((len(json.dumps(messages, default=str)) + len(system_prompt or "")) / 4)
        async for event in self._events(step, messages, specs, input_tokens):
            yield event

    async def _events(
        self, step: dict[str, Any], messages: Any, specs: list[dict[str, Any]], input_tokens: int
    ) -> AsyncGenerator[dict[str, Any]]:
        yield {"messageStart": {"role": "assistant"}}
        if "call" in step:
            name = self._resolve(str(step["call"]), specs)
            payload = json.dumps(step.get("input", {}))
            tool_use_id = f"tooluse-{self._cursor}"
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": payload}}}}
            yield {"contentBlockStop": {}}
            stop, output_tokens = "tool_use", math.ceil((len(name) + len(payload)) / 4)
        else:
            if step.get("summarize"):
                status, text = self._last_tool_result(messages)
                reply = f"Could not complete: {text}" if status == "error" else f"Done: {text}"
            else:
                reply = str(step.get("say", ""))
            yield {"contentBlockDelta": {"delta": {"text": reply}}}
            yield {"contentBlockStop": {}}
            stop, output_tokens = "end_turn", math.ceil(len(reply) / 4)
        self.usage.append(TurnUsage(input_tokens, output_tokens))
        yield {"messageStop": {"stopReason": stop}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": 0},
            }
        }
