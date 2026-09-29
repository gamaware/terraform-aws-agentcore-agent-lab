from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from seed_tables import seed


@pytest.fixture(autouse=True)
def _offline_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may reach AWS: fake credentials, fixed Region, no profile."""
    for key in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("ORDERS_TABLE", "harbor-orders")
    monkeypatch.setenv("STOCK_TABLE", "harbor-stock")
    monkeypatch.setenv("RETURNS_TABLE", "harbor-returns")
    monkeypatch.setenv("REFUND_LIMIT_CENTS", "20000")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "KBHARBOR01")


@pytest.fixture
def tables() -> Iterator[Any]:
    """The three tables with the same keys as infra/terraform/agent/dynamodb.tf, seeded from data/."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        specs = {
            os.environ["ORDERS_TABLE"]: [("order_id", "HASH")],
            os.environ["STOCK_TABLE"]: [("sku", "HASH"), ("store_id", "RANGE")],
            os.environ["RETURNS_TABLE"]: [("return_id", "HASH")],
        }
        for name, keys in specs.items():
            dynamodb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in keys],
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k, _ in keys],
                BillingMode="PAY_PER_REQUEST",
            )
        seed(dynamodb, os.environ["ORDERS_TABLE"], os.environ["STOCK_TABLE"])
        yield dynamodb
