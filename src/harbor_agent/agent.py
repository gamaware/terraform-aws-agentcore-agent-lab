"""One agent turn: load memory, run the Strands agent with the guard, save the turn."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from strands import Agent
from strands.models.model import Model

from harbor_agent.guards import ToolCall, ToolGuard
from harbor_agent.identity import Caller
from harbor_agent.memory import MemoryPort
from harbor_agent.prompts import SYSTEM_PROMPT, with_preferences

LOG = logging.getLogger("harbor_agent")
MAX_PROMPT_CHARS = 4000


class PromptError(ValueError):
    """The request payload has no usable prompt."""


@dataclass(frozen=True)
class TurnResult:
    reply: str
    tool_calls: list[ToolCall]

    def as_payload(self, session_id: str) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "session_id": session_id,
            "tool_calls": [{"tool": c.tool, "outcome": c.outcome} for c in self.tool_calls],
        }


def prompt_from_payload(payload: Any) -> str:
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        raise PromptError("payload must be a JSON object with a non-empty 'prompt'")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise PromptError(f"prompt is longer than {MAX_PROMPT_CHARS} characters")
    return prompt.strip()


@dataclass(frozen=True)
class TurnRequest:
    prompt: str
    caller: Caller
    session_id: str


@dataclass(frozen=True)
class AgentDeps:
    model: Model
    tools: Sequence[Any]
    memory: MemoryPort
    max_tool_calls: int = 8
    history_turns: int = 6


def run_turn(request: TurnRequest, deps: AgentDeps) -> TurnResult:
    prompt, caller, session_id, memory = request.prompt, request.caller, request.session_id, deps.memory
    history = memory.history(caller.actor_id, session_id, deps.history_turns)
    preferences = memory.preferences(caller.actor_id, prompt)
    guard = ToolGuard(max_tool_calls=deps.max_tool_calls, session_id=session_id)
    agent = Agent(
        model=deps.model,
        tools=list(deps.tools),
        system_prompt=with_preferences(SYSTEM_PROMPT, preferences),
        messages=history,
        hooks=[guard],
        callback_handler=None,
    )
    result = agent(prompt)
    reply = str(result).strip()
    memory.save_turn(caller.actor_id, session_id, prompt, reply)
    LOG.info(
        json.dumps(
            {
                "event": "turn",
                "session_id": session_id,
                "tool_calls": len(guard.calls),
                "blocked": sum(1 for c in guard.calls if c.outcome == "blocked_by_guard"),
                "stop_reason": str(result.stop_reason),
            },
            sort_keys=True,
        )
    )
    return TurnResult(reply=reply, tool_calls=guard.calls)
