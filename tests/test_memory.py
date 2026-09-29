from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from botocore.stub import ANY, Stubber
from scenarios import load_scenarios, run_scenario

from harbor_agent.memory import AgentCoreMemory, InMemoryMemory

MEMORY_ID = "harbor_memory-abcdefghij"


@pytest.fixture
def client() -> Any:
    return boto3.client("bedrock-agentcore", region_name="us-east-1")


def _event(role: str, text: str, second: int) -> dict[str, Any]:
    return {
        "memoryId": MEMORY_ID,
        "actorId": "staff-1",
        "sessionId": "s1",
        "eventId": f"0000000{second}#abc",
        "eventTimestamp": datetime(2030, 1, 1, 12, 0, second, tzinfo=UTC),
        "payload": [{"conversational": {"content": {"text": text}, "role": role}}],
    }


def test_history_is_ordered_and_starts_with_a_user_message(client: Any) -> None:
    memory = AgentCoreMemory(client=client, memory_id=MEMORY_ID)
    with Stubber(client) as stub:
        stub.add_response(
            "list_events",
            {
                "events": [
                    _event("USER", "second question", 3),
                    _event("ASSISTANT", "first answer", 2),
                    _event("ASSISTANT", "second answer", 4),
                ]
            },
            {"memoryId": MEMORY_ID, "actorId": "staff-1", "sessionId": "s1", "includePayloads": True, "maxResults": 4},
        )
        messages = memory.history("staff-1", "s1", 2)
    assert [(m["role"], m["content"][0]["text"]) for m in messages] == [
        ("user", "second question"),
        ("assistant", "second answer"),
    ]


def test_preferences_come_from_the_actor_namespace(client: Any) -> None:
    memory = AgentCoreMemory(client=client, memory_id=MEMORY_ID)
    with Stubber(client) as stub:
        stub.add_response(
            "retrieve_memory_records",
            {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "mem-staff-preference-record-0000001-harbor",
                        "content": {"text": "Prefers stock answers per store, not totals."},
                        "memoryStrategyId": "prefs-abcdefghij",
                        "namespaces": ["/users/staff-1/preferences/"],
                        "createdAt": datetime(2030, 1, 1, tzinfo=UTC),
                    }
                ]
            },
            {
                "memoryId": MEMORY_ID,
                "namespace": "/users/staff-1/preferences/",
                "searchCriteria": {"searchQuery": "desk stock", "topK": 3},
                "maxResults": 3,
            },
        )
        assert memory.preferences("staff-1", "desk stock") == ["Prefers stock answers per store, not totals."]


def test_save_turn_writes_user_then_assistant_events(client: Any) -> None:
    memory = AgentCoreMemory(client=client, memory_id=MEMORY_ID)
    with Stubber(client) as stub:
        for role, text in (("USER", "hi"), ("ASSISTANT", "hello")):
            stub.add_response(
                "create_event",
                {"event": _event(role, text, 1)},
                {
                    "memoryId": MEMORY_ID,
                    "actorId": "staff-1",
                    "sessionId": "s1",
                    "eventTimestamp": ANY,
                    "payload": [{"conversational": {"content": {"text": text}, "role": role}}],
                },
            )
        memory.save_turn("staff-1", "s1", "hi", "hello")
        stub.assert_no_pending_responses()


def test_second_turn_sees_the_first_and_preferences_reach_the_prompt(tables: Any) -> None:
    memory = InMemoryMemory(stored_preferences={"staff-1": ["Answer in one sentence."]})
    scenario = next(s for s in load_scenarios() if s["id"] == "order-status")
    run_scenario(scenario, tables, memory=memory)
    assert memory.history("staff-1", "session-order-status", 6)[0]["content"][0]["text"] == scenario["prompt"]
    follow_up = {**scenario, "prompt": "And the other one?", "steps": [{"say": "Which order?"}]}
    run = run_scenario(follow_up, tables, memory=memory)
    assert run.reply == "Which order?"
    assert len(memory.turns[("staff-1", "session-order-status")]) == 2
