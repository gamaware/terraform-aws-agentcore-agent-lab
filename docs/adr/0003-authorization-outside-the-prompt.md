# 0003. Authorization outside the prompt

## Status

Accepted

## Context

The agent can open returns with refunds. A system prompt that says "never refund more than USD 200" is a request to
the model, not a control: a prompt injection, a model change or a plain mistake can ignore it. Harbor Goods needs
the refund limit and the "only store leads can open returns" rule to hold whatever the model decides.

## Decision

Enforce authorization in three layers, none of which is the prompt.

1. **Gateway policy engine (the authorization decision).** AgentCore Policy evaluates Cedar policies
   (`policy/*.cedar.tftpl`) on every tool call, in `ENFORCE` mode and deny by default. Read tools are permitted
   for the `store-associates` and `store-leads` groups; `open_return` is permitted for `store-leads` only, with
   `context.input.refund_cents <= refund_limit_cents`; a `forbid` policy repeats the limit so a future `permit`
   cannot widen it. Refunds are integers in cents because Cedar compares integers.
2. **Tool guard in the agent (workflow rules).** A Strands hook blocks `open_return` unless `get_order` succeeded
   for the same order in the same turn, and stops a turn after eight tool calls.
3. **Business checks in the tool.** `open_return` repeats the limit and checks the return window, the line total
   and duplicates, so a policy mistake or a direct invocation still cannot open a bad return.

The Amazon Bedrock Guardrail on every model call (prompt attacks, PII, denied topics) is a fourth, probabilistic
layer and is not counted on for authorization.

Constraint: the policies match group names inside the token's `cognito:groups` claim with `like "*name*"`. Group
names must therefore not contain one another. Terraform creates the only two groups in the pool, and adding a
group means checking this rule.

## Consequences

- The injected-instruction scenario (`data/scenarios.yaml`) shows the point: the scripted model obeys the attacker
  and the refund still fails at the gateway.
- Policy changes are reviewed like code, tested offline and can be trialed in `LOG_ONLY` mode first.
- The limit exists in two places (policy and Lambda environment). Both come from one Terraform variable, and a
  terraform test asserts they match.

## Compliance

- `tests/test_policy.py` renders the same templates Terraform uploads and evaluates the 12 cases in
  `policy/cases.yaml` with the Cedar engine.
- `tests/test_scenarios.py` runs the agent loop against the local gateway, which applies the same policies.
- The terraform test `gateway_authenticates_and_enforces_policy` asserts `ENFORCE`, the gateway scope and the
  rendered limit.

## Notes

Alternatives considered: authorization in the agent code only (bypassed by anything that calls the tools
directly) and a Lambda interceptor on the gateway (custom code for what Cedar expresses in a few lines).
