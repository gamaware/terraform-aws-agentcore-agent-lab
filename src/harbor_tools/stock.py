"""check_stock: available units of one SKU in one store."""

from __future__ import annotations

from typing import Any

from harbor_tools.common import (
    SKU,
    STORE_ID,
    ToolInputError,
    expect_tool,
    log_call,
    ok,
    plain,
    refused,
    table,
    text_arg,
)

TOOL = "check_stock"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        expect_tool(context, TOOL)
        sku = text_arg(event, "sku", SKU)
        store_id = text_arg(event, "store_id", STORE_ID)
    except ToolInputError as err:
        log_call(TOOL, "invalid_input", detail=str(err))
        return refused(str(err))
    item = table("STOCK_TABLE").get_item(Key={"sku": sku, "store_id": store_id}).get("Item")
    if item is None:
        log_call(TOOL, "not_stocked", sku=sku, store_id=store_id)
        return ok({"sku": sku, "store_id": store_id, "available": 0, "stocked": False})
    row = plain(item)
    available = max(0, row["on_hand"] - row["reserved"])
    log_call(TOOL, "ok", sku=sku, store_id=store_id, available=available)
    return ok({"sku": sku, "store_id": store_id, "available": available, "stocked": True})
