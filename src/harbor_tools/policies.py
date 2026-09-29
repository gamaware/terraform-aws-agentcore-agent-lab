"""search_policies: retrieve passages from the store policy knowledge base (Amazon Bedrock Knowledge Bases).

The knowledge base is the one built in the RAG engagement; this function only calls Retrieve on it.
"""

from __future__ import annotations

import os
from typing import Any

import boto3

from harbor_tools.common import ToolInputError, expect_tool, log_call, ok, refused, text_arg

TOOL = "search_policies"
MAX_RESULTS = 4


def _client() -> Any:
    return boto3.client("bedrock-agent-runtime")


def handler(event: dict[str, Any], context: Any, client: Any = None) -> dict[str, Any]:
    try:
        expect_tool(context, TOOL)
        query = text_arg(event, "query", max_len=500)
    except ToolInputError as err:
        log_call(TOOL, "invalid_input", detail=str(err))
        return refused(str(err))
    client = client or _client()
    response = client.retrieve(
        knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": MAX_RESULTS}},
    )
    passages = []
    for result in response.get("retrievalResults", []):
        location = result.get("location", {})
        source = location.get("s3Location", {}).get("uri") or location.get("type", "unknown")
        passages.append(
            {"text": result.get("content", {}).get("text", ""), "source": source, "score": result.get("score")}
        )
    log_call(TOOL, "ok", passages=len(passages))
    return ok({"passages": passages})
