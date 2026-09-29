# 0008. Live tests run in a sandbox account, private-only

## Status

Accepted

## Context

The offline checks cannot prove IAM evaluation, AgentCore service behavior, model quality or latency. A live test
is needed, and it must not risk a shared or production account or leave anything public behind.

## Decision

`make test-live` (`scripts/test-live.sh`):

- runs only with the maintainer's `personal` profile, and only when `LIVE_ACCOUNT_ID` matches the account that
  profile resolves to;
- plans each stack first and runs `scripts/check_live_plan.py` on the plan, which refuses internet or NAT gateways,
  Elastic IPs, public subnets, default routes, Route 53, Cognito domains, ECR repository policies and a runtime
  outside VPC mode;
- tags everything `Project=terraform-aws-agentcore-agent-lab`, `Ephemeral=true` and a run ID, destroys both stacks
  on exit (success, failure or interrupt) and lists anything still tagged;
- uses throwaway Cognito users and checks outcomes that do not depend on model wording: which returns exist and
  that a call without a token is refused.

## Consequences

- A failed teardown leaves only private resources, which the run ID tag finds.
- A run costs about USD 1 to 3; a budget alert on the sandbox account is a prerequisite.
- The live test uses Amazon Nova Lite; Claude Haiku is documented as the production option.

## Compliance

- `tests/test_check_live_plan.py` (part of `make verify`) covers the pre-flight.
- The script exits before any apply when the account does not match or the pre-flight refuses the plan.

## Notes

The same private-only approach is used by the ECS deploy lab's live test.
