from __future__ import annotations

import os
import time
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber
from harness import FakeLambdaContext

from harbor_tools import orders, policies, returns, stock

GET_ORDER = FakeLambdaContext("orders___get_order")
CHECK_STOCK = FakeLambdaContext("stock___check_stock")
OPEN_RETURN = FakeLambdaContext("returns___open_return")
SEARCH = FakeLambdaContext("policies___search_policies")


def _return(**overrides: Any) -> dict[str, Any]:
    event = {"order_id": "HG-100234", "sku": "HG-TEAK-CHAIR", "quantity": 1, "refund_cents": 8900, "reason": "wobbly"}
    return {**event, **overrides}


def test_get_order_returns_lines(tables: Any) -> None:
    result = orders.handler({"order_id": "HG-100234"}, GET_ORDER)
    assert result["ok"]
    assert [ln["sku"] for ln in result["order"]["lines"]] == ["HG-TEAK-CHAIR", "HG-LINEN-RUN"]


@pytest.mark.parametrize("order_id", ["", "100234", "HG-1", "HG-100234; DROP", None, 42])
def test_get_order_rejects_malformed_ids(tables: Any, order_id: Any) -> None:
    assert not orders.handler({"order_id": order_id}, GET_ORDER)["ok"]


def test_get_order_unknown(tables: Any) -> None:
    assert orders.handler({"order_id": "HG-999999"}, GET_ORDER) == {"ok": False, "error": "order HG-999999 not found"}


def test_tool_refuses_calls_meant_for_another_tool(tables: Any) -> None:
    result = orders.handler({"order_id": "HG-100234"}, FakeLambdaContext("returns___open_return"))
    assert not result["ok"]
    assert "serves get_order" in result["error"]


def test_tool_refuses_direct_invocation_without_gateway_context(tables: Any) -> None:
    class Bare:
        client_context = None

    assert not orders.handler({"order_id": "HG-100234"}, Bare())["ok"]


def test_check_stock_subtracts_reserved(tables: Any) -> None:
    result = stock.handler({"sku": "HG-OAK-DESK", "store_id": "ST-014"}, CHECK_STOCK)
    assert result == {"ok": True, "sku": "HG-OAK-DESK", "store_id": "ST-014", "available": 0, "stocked": True}


def test_check_stock_not_stocked(tables: Any) -> None:
    result = stock.handler({"sku": "HG-DESK-LAMP", "store_id": "ST-022"}, CHECK_STOCK)
    assert result["available"] == 0
    assert not result["stocked"]


def test_open_return_writes_one_record(tables: Any) -> None:
    result = returns.handler(_return(), OPEN_RETURN)
    assert result == {"ok": True, "return_id": "HG-100234#HG-TEAK-CHAIR", "status": "OPEN", "refund_cents": 8900}
    item = tables.Table(os.environ["RETURNS_TABLE"]).get_item(Key={"return_id": "HG-100234#HG-TEAK-CHAIR"})["Item"]
    assert item["status"] == "OPEN"
    assert item["request_id"] == "req-local-0001"


def test_open_return_is_idempotent_per_line(tables: Any) -> None:
    assert returns.handler(_return(), OPEN_RETURN)["ok"]
    second = returns.handler(_return(), OPEN_RETURN)
    assert not second["ok"]
    assert "already open" in second["error"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"refund_cents": 20001}, "above the store limit"),
        ({"refund_cents": 17801}, "above the line total"),
        ({"quantity": 3}, "has only 2"),
        ({"sku": "HG-OAK-DESK"}, "not on order"),
        ({"order_id": "HG-100241", "sku": "HG-OAK-DESK", "refund_cents": 100}, "only delivered orders"),
        ({"order_id": "HG-100257", "sku": "HG-WOOL-THROW", "refund_cents": 100}, "return window has closed"),
        ({"quantity": 0}, "between 1 and 50"),
        ({"quantity": True}, "must be an integer"),
        ({"refund_cents": "8900"}, "must be an integer"),
        ({"reason": " "}, "reason is required"),
    ],
)
def test_open_return_refusals(tables: Any, overrides: dict[str, Any], message: str) -> None:
    result = returns.handler(_return(**overrides), OPEN_RETURN)
    assert not result["ok"]
    assert message in result["error"]
    assert tables.Table(os.environ["RETURNS_TABLE"]).scan(Select="COUNT")["Count"] == 0


def test_open_return_allows_full_line_at_limit(tables: Any) -> None:
    assert returns.handler(_return(quantity=2, refund_cents=17800), OPEN_RETURN)["ok"]


def test_open_return_window_uses_delivery_time(tables: Any) -> None:
    # HG-100263 was delivered 3 days ago; 28 days later it is out of the 30-day window.
    late = time.time() + 28 * 86400
    event = _return(order_id="HG-100263", sku="HG-DESK-LAMP", refund_cents=5400)
    assert "window has closed" in returns.handler(event, OPEN_RETURN, now=late)["error"]
    assert returns.handler(event, OPEN_RETURN)["ok"]


def test_search_policies_calls_retrieve_on_the_configured_knowledge_base() -> None:
    client = boto3.client("bedrock-agent-runtime", region_name="us-east-1")
    with Stubber(client) as stub:
        stub.add_response(
            "retrieve",
            {
                "retrievalResults": [
                    {
                        "content": {"text": "Returns are accepted within 30 days of delivery."},
                        "location": {"type": "S3", "s3Location": {"uri": "s3://harbor-policies/returns.md"}},
                        "score": 0.71,
                    }
                ]
            },
            {
                "knowledgeBaseId": "KBHARBOR01",
                "retrievalQuery": {"text": "return window"},
                "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 4}},
            },
        )
        result = policies.handler({"query": "return window"}, SEARCH, client=client)
    assert result == {
        "ok": True,
        "passages": [
            {
                "text": "Returns are accepted within 30 days of delivery.",
                "source": "s3://harbor-policies/returns.md",
                "score": 0.71,
            }
        ],
    }


def test_search_policies_rejects_empty_query() -> None:
    assert not policies.handler({"query": ""}, SEARCH, client=object())["ok"]
