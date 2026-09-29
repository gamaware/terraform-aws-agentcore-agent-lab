"""get_order: read one order from the orders table."""

from __future__ import annotations

from typing import Any

from harbor_tools.common import ORDER_ID, ToolInputError, expect_tool, log_call, ok, plain, refused, table, text_arg

TOOL = "get_order"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        expect_tool(context, TOOL)
        order_id = text_arg(event, "order_id", ORDER_ID)
    except ToolInputError as err:
        log_call(TOOL, "invalid_input", detail=str(err))
        return refused(str(err))
    item = table("ORDERS_TABLE").get_item(Key={"order_id": order_id}).get("Item")
    if item is None:
        log_call(TOOL, "not_found", order_id=order_id)
        return refused(f"order {order_id} not found")
    log_call(TOOL, "ok", order_id=order_id)
    return ok({"order": plain(item)})
