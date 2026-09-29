# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The tool Lambda ZIP keeps the `harbor_tools/` package directory, so `harbor_tools.<module>.handler` imports;
  `make tf-verify` imports every handler from the Terraform-built ZIP.
- The read-tools Cedar policy names only deployed targets (no `search_policies` without a knowledge base), and
  policies are created after the gateway targets.
- The tool-call limit ends the turn after the call over the limit instead of returning an error to the model.
- The live test requires the expected return and successful turn payloads, and a failed destroy keeps the
  Terraform state and exits non-zero.
- Cost model: Nova Lite at USD 0.06 and 0.24 per million tokens, every configured guardrail safeguard priced, and
  memory retrievals and policy authorizations added.

### Added

- Store-operations agent (Strands Agents) for AgentCore Runtime: `/invocations` and `/ping` on port 8080, the
  caller's token passed to the gateway, a tool guard (lookup before return, eight calls per turn) and AgentCore
  Memory for session history and staff preferences.
- Four Lambda tools behind AgentCore Gateway as MCP targets: `get_order`, `check_stock`, `open_return` and
  `search_policies`, defined once in `tools/schemas/`.
- Cedar policies for AgentCore Policy (read tools for store staff, returns for store leads up to the refund
  limit) with a 12-case allow and deny table.
- Scripted model provider and 11 offline agent scenarios, including a model that skips a lookup, obeys an injected
  instruction and loops.
- arm64 image on a slim, non-root Python runtime without pip, bases pinned by digest, and a smoke test of the
  runtime contract.
- Terraform registry stack (ECR, KMS) and agent stack (runtime in VPC mode, gateway, targets, policy engine,
  memory, Cognito, guardrail, DynamoDB, VPC endpoints, flow logs, log and trace delivery, dashboard, alarms), with
  14 mocked `terraform test` runs.
- Cost model per 1,000 sessions, evidence report, eight ADRs, runbook and live-test guide.
- CI (a `make verify` job next to the shared checks), deploy workflow (build once, scan, push by digest, deploy),
  OpenSSF Scorecard.
- `make test-live` for a personal sandbox account, with an account check, a plan pre-flight that refuses public
  resources, and teardown on exit.

### Security

- Shared reusable workflows from `gamaware/.github` are called pinned to a full commit SHA.
