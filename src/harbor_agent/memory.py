"""Conversation memory backed by AgentCore Memory.

- Short term: each turn is stored as two conversational events (user, assistant) in the staff member's
  session. The next request in the same session replays the last ``history_turns`` turns.
- Long term: the memory resource has one USER_PREFERENCE strategy that AgentCore runs asynchronously over the
  events. Its records live under ``/users/{actorId}/preferences/`` and are added to the system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from strands.types.content import Message, Messages

PREFERENCES_NAMESPACE = "/users/{actor_id}/preferences/"
MAX_EVENT_TEXT = 9000


class MemoryPort(Protocol):
    def history(self, actor_id: str, session_id: str, turns: int) -> Messages: ...

    def preferences(self, actor_id: str, query: str) -> list[str]: ...

    def save_turn(self, actor_id: str, session_id: str, user_text: str, reply: str) -> None: ...


def _message(role: str, text: str) -> Message:
    return {"role": "user" if role == "user" else "assistant", "content": [{"text": text}]}


@dataclass
class AgentCoreMemory:
    """MemoryPort over the ``bedrock-agentcore`` data plane API."""

    client: Any
    memory_id: str

    def history(self, actor_id: str, session_id: str, turns: int) -> Messages:
        response = self.client.list_events(
            memoryId=self.memory_id,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=turns * 2,
        )
        events = sorted(response.get("events", []), key=lambda e: e["eventTimestamp"])
        messages: Messages = []
        for event in events[-turns * 2 :]:
            for item in event.get("payload", []):
                conversational = item.get("conversational")
                if conversational:
                    role = "user" if conversational["role"] == "USER" else "assistant"
                    messages.append(_message(role, conversational["content"]["text"]))
        # A Bedrock conversation must start with a user message.
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        return messages

    def preferences(self, actor_id: str, query: str) -> list[str]:
        response = self.client.retrieve_memory_records(
            memoryId=self.memory_id,
            namespace=PREFERENCES_NAMESPACE.format(actor_id=actor_id),
            searchCriteria={"searchQuery": query[:1000], "topK": 3},
            maxResults=3,
        )
        return [
            summary["content"]["text"]
            for summary in response.get("memoryRecordSummaries", [])
            if summary.get("content", {}).get("text")
        ]

    def save_turn(self, actor_id: str, session_id: str, user_text: str, reply: str) -> None:
        now = datetime.now(UTC)
        for role, text in (("USER", user_text), ("ASSISTANT", reply)):
            self.client.create_event(
                memoryId=self.memory_id,
                actorId=actor_id,
                sessionId=session_id,
                eventTimestamp=now,
                payload=[{"conversational": {"content": {"text": text[:MAX_EVENT_TEXT]}, "role": role}}],
            )


@dataclass
class InMemoryMemory:
    """MemoryPort for tests and the container smoke test."""

    turns: dict[tuple[str, str], list[tuple[str, str]]] = field(default_factory=dict)
    stored_preferences: dict[str, list[str]] = field(default_factory=dict)

    def history(self, actor_id: str, session_id: str, turns: int) -> Messages:
        messages: Messages = []
        for user_text, reply in self.turns.get((actor_id, session_id), [])[-turns:]:
            messages += [_message("user", user_text), _message("assistant", reply)]
        return messages

    def preferences(self, actor_id: str, query: str) -> list[str]:
        return list(self.stored_preferences.get(actor_id, []))

    def save_turn(self, actor_id: str, session_id: str, user_text: str, reply: str) -> None:
        self.turns.setdefault((actor_id, session_id), []).append((user_text, reply))
