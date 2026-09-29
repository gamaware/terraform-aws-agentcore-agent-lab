"""The live test's pass criteria, offline: an empty returns table or an error inside HTTP 200 must fail."""

from __future__ import annotations

import json
from typing import Any

from live_sessions import CASES, LiveCase, check_response, check_returns

LOOKUP = LiveCase("store-associates", "Where is order HG-100241?", "get_order")
DENIED = LiveCase("store-associates", "Open a return for the linen runner.", None, no_return=True)


def _body(reply: str = "It ships Friday.", calls: list[dict[str, Any]] | None = None) -> str:
    return json.dumps({"reply": reply, "session_id": "s", "tool_calls": calls or []})


def test_an_empty_returns_table_fails() -> None:
    assert check_returns(set(), {"HG-100234#HG-TEAK-CHAIR"}) == [
        "expected returns are missing: ['HG-100234#HG-TEAK-CHAIR']"
    ]


def test_an_unexpected_return_fails() -> None:
    failures = check_returns({"HG-100234#HG-TEAK-CHAIR", "HG-100263#HG-OAK-DESK"}, {"HG-100234#HG-TEAK-CHAIR"})
    assert failures == ["unexpected returns were opened: ['HG-100263#HG-OAK-DESK']"]


def test_exactly_the_expected_returns_pass() -> None:
    assert check_returns({"HG-100234#HG-TEAK-CHAIR"}, {"HG-100234#HG-TEAK-CHAIR"}) == []


def test_the_live_cases_expect_one_successful_return() -> None:
    assert [c.opens for c in CASES if c.opens] == ["HG-100234#HG-TEAK-CHAIR"]
    assert all(c.requires_ok == "open_return" for c in CASES if c.opens)


def test_an_application_error_inside_http_200_fails() -> None:
    body = json.dumps({"error": "payload must be a JSON object with a non-empty 'prompt'", "session_id": "s"})
    assert "application error" in check_response(LOOKUP, 200, body)[0]


def test_a_non_json_body_fails() -> None:
    assert "not JSON" in check_response(LOOKUP, 200, "<html>upstream error</html>")[0]


def test_a_non_200_status_fails() -> None:
    assert check_response(LOOKUP, 502, "") == [f"{LOOKUP.prompt!r} returned HTTP 502"]


def test_a_turn_that_never_ran_the_tool_fails() -> None:
    body = _body(calls=[{"tool": "get_order", "outcome": "error"}])
    assert "never ran get_order successfully" in check_response(LOOKUP, 200, body)[0]


def test_a_turn_without_a_reply_fails() -> None:
    assert "no reply" in check_response(LOOKUP, 200, _body(reply=" "))[0]


def test_a_successful_lookup_passes() -> None:
    assert check_response(LOOKUP, 200, _body(calls=[{"tool": "get_order", "outcome": "ok"}])) == []


def test_a_denied_return_that_succeeded_fails() -> None:
    body = _body(calls=[{"tool": "get_order", "outcome": "ok"}, {"tool": "open_return", "outcome": "ok"}])
    assert "opened a return it must not open" in check_response(DENIED, 200, body)[0]


def test_a_denied_return_passes_when_the_gateway_refuses() -> None:
    body = _body(calls=[{"tool": "get_order", "outcome": "ok"}, {"tool": "open_return", "outcome": "error"}])
    assert check_response(DENIED, 200, body) == []
