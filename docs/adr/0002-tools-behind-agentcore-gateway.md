# 0002. Tools behind AgentCore Gateway as MCP Lambda targets

## Status

Accepted

## Context

The agent needs four tools: `get_order`, `check_stock`, `open_return` and `search_policies`. They could live inside
the agent process as Python functions, which is simpler. They touch order data and can create refunds, so each one
needs its own permissions, its own audit trail and an authorization check that does not depend on the agent code.

## Decision

Expose the tools through Amazon Bedrock AgentCore Gateway as MCP tools, one Lambda target per tool.

- Each tool is a small Lambda function (`src/harbor_tools/`) with its own IAM role: `get_order` can read the
  orders table only, `open_return` can read orders and write returns only, `search_policies` can call `Retrieve` on
  one knowledge base only.
- The tool definitions live in `tools/schemas/*.json`. Terraform builds the gateway targets from those files, and
  the offline tests read the same files, so the contract cannot drift.
- The agent discovers the tools at run time over MCP (`tools/list`), with the caller's token (ADR 0004).
- `search_policies` is created only when `knowledge_base_id` is set, so this stack does not depend on the RAG
  engagement to deploy.

## Consequences

- Adding a tool is a schema file, a handler and a policy case; the agent code does not change.
- The gateway is the single place where the policy engine can see and decide every tool call (ADR 0003).
- Each tool call adds a gateway hop and a Lambda invocation. Latency is tens of milliseconds, and the gateway costs
  USD 0.005 per 1,000 calls.
- Other agents or clients that speak MCP can reuse the same tools with the same policies.

## Compliance

- `tests/test_tool_schemas.py` checks every schema, its handler and the Terraform wiring.
- `tests/test_tools.py` runs every handler against DynamoDB emulated by moto.
- The terraform test `targets_follow_the_tool_schemas` and `access_is_scoped_per_role` check the targets and roles.

## Notes

The gateway also supports OpenAPI and Smithy targets. Lambda targets were chosen because the tools are new code
with no existing API; an existing order service would be added as an OpenAPI target instead.
