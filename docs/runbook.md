# Runbook: Harbor Goods store-operations agent

Operating guide for the platform team. Placeholders: `ACCOUNT` is the workload account (for example
111122223333), `REGION` is `us-east-1`.

## First deployment

1. Apply the registry stack (`infra/terraform/registry`) once. Note `repository_url` and `repository_arn`.
2. Set the repository variables listed at the top of `.github/workflows/deploy.yml` and the `registry` and
   `production` environments (main branch only, a reviewer on `production`).
3. Merge to main. The deploy workflow builds, scans and pushes the image, then applies `infra/terraform/agent`
   with that digest and waits for the `live` endpoint.
4. Create staff accounts in the Cognito pool (`user_pool_id` output) and add each person to `store-associates`
   or `store-leads`. Do not create other groups without reading ADR 0003 (group names must not contain one
   another).
5. To enable policy search, set `KNOWLEDGE_BASE_ID` to the knowledge base from the RAG engagement and redeploy.

## Deploy and roll back

- Every merge to main that touches the agent, tools, policies or stack deploys a new runtime version and moves the
  `live` endpoint to it.
- Roll back by re-running the deploy workflow's `deploy` job for an earlier run, or by applying the stack with the
  previous digest: `scripts/deploy.sh <repo>@sha256:<previous digest>`. ECR keeps the last 30 tagged images.
- Never deploy by tag; Terraform refuses it.

## Change a policy

1. Edit `policy/*.cedar.tftpl` and add or update cases in `policy/cases.yaml`. Run `make py-test`.
2. For a change that could deny current traffic, deploy with `policy_mode = "LOG_ONLY"` first. Decisions are
   written to the gateway's traces without blocking. Review a representative period, then switch back to
   `ENFORCE`.
3. Changing the refund limit is one variable, `refund_limit_cents`; it updates the policy and the `open_return`
   Lambda together.

## Investigate a refused or wrong action

1. Ask for the staff member's session ID (the store app shows it) and the approximate time.
2. Runtime log groups (prefix in the `runtime_log_group_prefix` output), Logs Insights:

   ```text
   fields @timestamp, event, tool, outcome, reason
   | filter session_id = "SESSION_ID"
   | sort @timestamp asc
   ```

   Each turn logs one `turn` line and one `tool_call` or `tool_guard` line per tool call. `blocked_by_guard`
   means the agent's guard stopped the call (for example a return without a lookup).
3. If the tool call reached the gateway, check the gateway trace in CloudWatch (GenAI observability, traces): a
   policy denial shows the decision and the policies evaluated.
4. If the gateway allowed it, the tool's log group (`/aws/lambda/harbor-store-ops-*`) holds one JSON line per call
   with the outcome (`refused`, `duplicate`, `ok`).
5. A wrong answer with no tool call is a model issue: collect the prompt and reply from the trace and add it to the
   evaluation set; do not "fix" it in the prompt if a control should have caught it.

## Alarms

| Alarm | Meaning | First step |
| --- | --- | --- |
| `<name>-<tool>-errors` | The tool raised an unhandled exception (not a business refusal) | Tool log group, last errors; check DynamoDB and KMS permissions |
| `<name>-<tool>-throttles` | The tool hit its reserved concurrency (20 by default) | Check the dashboard for a looping client; raise `tool_reserved_concurrency` if traffic is real |

## Rotate or change the model

Set `model_id` (a cross-Region inference profile ID) and redeploy. The runtime role's model permission follows the
variable. Run `make test-live` in the sandbox first; model changes are not covered by the offline tests.

## Hand over

The client team owns the Cognito pool membership, the refund limit and the policies. The platform team owns the
stacks, the deploy workflow and the alarms. The report (`report/REPORT.md`) lists the open risks.
