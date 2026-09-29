#!/usr/bin/env python3
"""Seed the orders and stock tables from data/*.json.

Used by the offline tests (against moto) and by `make test-live` (against the live tables, through the
caller's AWS profile). Order fixtures carry ``delivered_days_ago``; items get an absolute ``delivered_at``.

Usage: seed_tables.py <orders-table> <stock-table>
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3

ROOT = Path(__file__).resolve().parents[1]


def order_items(now: float | None = None) -> list[dict[str, Any]]:
    now = time.time() if now is None else now
    items = []
    for order in json.loads((ROOT / "data" / "orders.json").read_text()):
        item = {k: v for k, v in order.items() if k != "delivered_days_ago"}
        days = order.get("delivered_days_ago")
        if days is not None:
            item["delivered_at"] = datetime.fromtimestamp(now - days * 86400, UTC).isoformat()
        items.append(item)
    return items


def stock_items() -> list[dict[str, Any]]:
    return list(json.loads((ROOT / "data" / "stock.json").read_text()))


def seed(dynamodb: Any, orders_table: str, stock_table: str, now: float | None = None) -> None:
    for table_name, items in ((orders_table, order_items(now)), (stock_table, stock_items())):
        with dynamodb.Table(table_name).batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    seed(boto3.resource("dynamodb"), argv[1], argv[2])
    print(f"seeded {argv[1]} and {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
