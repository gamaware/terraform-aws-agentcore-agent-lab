"""open_return: record a return for one order line.

The gateway policy engine already refuses refunds above the store limit (policy/). This function repeats the
business checks it owns, so a mistake in the policy or a direct invocation cannot open a bad return:
the order must be delivered and inside the return window, the refund cannot exceed the line total or the limit,
and one order line can be returned once (conditional write).
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from harbor_tools.common import (
    ORDER_ID,
    SKU,
    ToolInputError,
    expect_tool,
    int_arg,
    log_call,
    ok,
    plain,
    refused,
    table,
    text_arg,
)

TOOL = "open_return"
RETURN_WINDOW_DAYS = 30


def _limit_cents() -> int:
    return int(os.environ["REFUND_LIMIT_CENTS"])


def _age_days(delivered_at: str, now: float) -> float:
    delivered = datetime.fromisoformat(delivered_at)
    if delivered.tzinfo is None:
        delivered = delivered.replace(tzinfo=UTC)
    return (now - delivered.timestamp()) / 86400


def _refusal(order: dict[str, Any] | None, request: dict[str, Any], now: float) -> str | None:
    """The business reason this return cannot be opened, or None."""
    order_id, sku, quantity, refund_cents = (request[k] for k in ("order_id", "sku", "quantity", "refund_cents"))
    reason: str | None = None
    if refund_cents > _limit_cents():
        reason = "refund is above the store limit; a store manager must approve it outside the assistant"
    elif order is None:
        reason = f"order {order_id} not found"
    elif order.get("status") != "DELIVERED" or not order.get("delivered_at"):
        reason = "only delivered orders can be returned"
    elif _age_days(order["delivered_at"], now) > RETURN_WINDOW_DAYS:
        reason = f"the {RETURN_WINDOW_DAYS}-day return window has closed"
    else:
        line = next((ln for ln in order.get("lines", []) if ln.get("sku") == sku), None)
        if line is None:
            reason = f"{sku} is not on order {order_id}"
        elif quantity > line["quantity"]:
            reason = f"order {order_id} has only {line['quantity']} of {sku}"
        elif refund_cents > quantity * line["unit_price_cents"]:
            reason = f"refund {refund_cents} is above the line total {quantity * line['unit_price_cents']}"
    return reason


def _parse(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": text_arg(event, "order_id", ORDER_ID),
        "sku": text_arg(event, "sku", SKU),
        "quantity": int_arg(event, "quantity", 1, 50),
        "refund_cents": int_arg(event, "refund_cents", 1, 10_000_000),
        "reason": text_arg(event, "reason", max_len=300),
    }


def handler(event: dict[str, Any], context: Any, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    try:
        expect_tool(context, TOOL)
        request = _parse(event)
    except ToolInputError as err:
        log_call(TOOL, "invalid_input", detail=str(err))
        return refused(str(err))

    item = table("ORDERS_TABLE").get_item(Key={"order_id": request["order_id"]}).get("Item")
    refusal = _refusal(plain(item) if item is not None else None, request, now)
    if refusal:
        log_call(TOOL, "refused", order_id=request["order_id"], detail=refusal)
        return refused(refusal)

    return_id = f"{request['order_id']}#{request['sku']}"
    record = {
        **request,
        "return_id": return_id,
        "status": "OPEN",
        "opened_at": datetime.fromtimestamp(now, UTC).isoformat(),
        "request_id": getattr(context, "aws_request_id", "unknown"),
    }
    try:
        table("RETURNS_TABLE").put_item(Item=record, ConditionExpression="attribute_not_exists(return_id)")
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            log_call(TOOL, "duplicate", return_id=return_id)
            return refused(f"a return for {request['sku']} on {request['order_id']} is already open")
        raise
    log_call(TOOL, "ok", return_id=return_id, refund_cents=request["refund_cents"])
    return ok({"return_id": return_id, "status": "OPEN", "refund_cents": request["refund_cents"]})
