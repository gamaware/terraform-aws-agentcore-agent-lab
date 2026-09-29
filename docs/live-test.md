# Live test

`make test-live` deploys both stacks to a real account, runs live sessions and destroys everything. It proves what
the offline checks cannot: IAM evaluation, AgentCore service behavior, the policy engine's decisions on real tokens,
and the model's behavior with the real tools.

## Rules

- Personal sandbox account only. The script uses the `personal` profile and refuses to run unless
  `LIVE_ACCOUNT_ID` matches the account that profile resolves to.
- Nothing public. Each plan is checked by `scripts/check_live_plan.py` before apply (ADR 0008).
- Everything is tagged `Project=terraform-aws-agentcore-agent-lab`, `Ephemeral=true` and `run=<id>`, and destroyed
  on exit, including on failure or Ctrl-C.
- Set an AWS Budget with an alert (for example USD 10) on the sandbox account before the first run.

## Prerequisites

- The `make verify` toolchain, plus the AWS CLI v2 and a signed-in `personal` profile.
- Amazon Bedrock model access to Amazon Nova Lite in `us-east-1` (enabled by default in most accounts).
- Docker able to build arm64 images.

## Run

```bash
LIVE_ACCOUNT_ID=111122223333 make test-live
```

Replace the example ID with the sandbox account's ID. `LIVE_YES=1` skips the confirmation prompt, and
`LIVE_REGION` changes the Region (the default Availability Zone IDs are for `us-east-1`).

## What it does

1. Shows the caller identity and checks the account.
2. Plans and pre-flights the registry stack, applies it, builds the image and pushes it.
3. Plans and pre-flights the agent stack with test settings (no deletion protection, admin sign-in flow on,
   unreserved tool concurrency, 30-day logs), then applies it.
4. Seeds the orders and stock tables from `data/`.
5. Creates a throwaway store associate and store lead, signs them in and sends five prompts to the `live`
   endpoint. It fails if a call without a token is accepted, if any prompt gets a non-200 answer, or if a return
   exists that only the lead's under-limit request should have opened.
6. Destroys both stacks and lists anything still tagged with the run ID.

## Cost

About USD 1 to 3 per run: runtime active time, seven interface endpoints in two zones for about an hour, Nova Lite
tokens, logs and traces. The KMS keys are scheduled for deletion (30-day window) and cost nothing while pending.
