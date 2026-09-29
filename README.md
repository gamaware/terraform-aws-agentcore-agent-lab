# AI agent on Amazon Bedrock AgentCore

A store-operations agent that looks up orders, checks stock, opens returns and searches store policy, with every
tool call authorized per staff member. It runs on Amazon Bedrock AgentCore, is defined in Terraform and is tested
offline.

[![CI](https://github.com/gamaware/terraform-aws-agentcore-agent-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/gamaware/terraform-aws-agentcore-agent-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Lab](https://img.shields.io/badge/type-lab-5b6b7f)

![AI agents on Amazon Bedrock AgentCore](docs/assets/cover.png)

> **Lab.** Harbor Goods and all data here are fictional. Each repository in this portfolio is a
> separate engagement with Harbor Goods, a fictional mid-size retailer. Account IDs are AWS documentation examples.

## What this proves

- **An agent shipped like a service:** a Strands agent in an arm64 container on AgentCore Runtime, built once,
  scanned and deployed by `sha256` digest, in private subnets with no internet path.
- **Tools with their own permissions:** four tools behind AgentCore Gateway as MCP, one Lambda function and one
  IAM role each. `get_order` can only read orders; `open_return` can only read orders and write returns.
- **Authorization that the model cannot talk its way past:** Cedar policies in AgentCore Policy decide every tool
  call as the signed-in staff member. Only store leads can open returns, and only up to USD 200. A scripted model
  that obeys an injected "refund USD 500" instruction still gets denied.
- **Memory and observability:** AgentCore Memory keeps each staff session and learns preferences; logs, traces, a
  dashboard and per-tool alarms come with the stack.
- **Tested without an AWS account:** 109 Python tests (11 scripted agent scenarios, tools on moto, 12 policy
  cases), 14 mocked `terraform test` runs, a container smoke test, Checkov, Trivy, Semgrep and hadolint, all
  behind one `make verify`.

## Inspect the deliverable

| Artifact | Why look |
| --- | --- |
| [`report/REPORT.md`](report/REPORT.md) | Scenario results, which layer stopped what, cost per 1,000 sessions, risks |
| [`policy/`](policy) | The Cedar policies the gateway enforces, and the allow and deny table they are tested against |
| [`data/scenarios.yaml`](data/scenarios.yaml) | Scripted agent sessions, including a model that misbehaves on purpose |
| [`src/harbor_agent/guards.py`](src/harbor_agent/guards.py) | Workflow rules enforced in the agent process: lookup before return, call limit |
| [`src/harbor_tools/returns.py`](src/harbor_tools/returns.py) | The write tool and the business checks it keeps even when the policy allows a call |
| [`infra/terraform/agent/`](infra/terraform/agent) | Runtime, gateway, targets, policy engine, memory, identity, guardrail, network |
| [`infra/terraform/agent/tests/`](infra/terraform/agent/tests) | What the infrastructure must guarantee, as assertions |
| [`docs/runbook.md`](docs/runbook.md) | Deploy, roll back, change a policy, investigate a refused action |

## Scenario and acceptance criteria

Harbor Goods, a fictional mid-size retailer, wants store staff to handle order questions, stock checks and returns
through one assistant instead of three back-office screens. It must do more than answer: it must act. Leadership's
conditions: every action is authorized per person, refunds above a limit never go through the assistant, it
remembers context across a shift, it can be observed, and the platform team deploys it the way it deploys
everything else. The policy knowledge base comes from the earlier RAG engagement.

| Acceptance criterion | How it is met | Checked by |
| --- | --- | --- |
| Only store leads open returns, up to USD 200 | Cedar policies in the gateway policy engine, deny by default | `tests/test_policy.py`, scenarios |
| A manipulated model cannot exceed that | Decision outside the model: policy, tool guard, Lambda checks | Injected-instruction scenario |
| A return always matches a real order line | Guard requires `get_order` first; Lambda checks window, total, duplicates | Scenarios, `tests/test_tools.py` |
| Every tool call is attributable to a person | The caller's token goes from runtime to gateway | `terraform test`, `tests/test_app.py` |
| No internet path from the agent | VPC mode, private subnets, VPC endpoints, no NAT | `terraform test`, live-test pre-flight |
| Data encrypted with a customer managed key | One KMS key for tables, logs, memory, gateway, policies, guardrail | `terraform test` |
| What runs is what was scanned | Build once, deploy by digest | `terraform test`, deploy workflow |

## Architecture

![Animated flow: per-staff tool authorization, injected refund denied](docs/diagrams/architecture-animated.svg)

```mermaid
flowchart LR
  staff["Store staff<br/>(store app)"] -->|"sign in"| cognito["Amazon Cognito<br/>user pool"]
  staff -->|"prompt + access token"| runtime
  subgraph vpc["VPC, private subnets, no internet path"]
    runtime["AgentCore Runtime<br/>Strands agent, arm64 image by digest"]
  end
  runtime -->|"Converse + guardrail"| bedrock["Amazon Bedrock<br/>Nova Lite"]
  runtime -->|"events, preferences"| memory["AgentCore Memory"]
  runtime -->|"MCP with the caller's token"| gateway["AgentCore Gateway"]
  gateway -->|"authorize each call"| policy["AgentCore Policy<br/>Cedar, deny by default"]
  gateway --> tools["Lambda tools<br/>get_order, check_stock,<br/>open_return, search_policies"]
  tools --> ddb[("DynamoDB<br/>orders, stock, returns")]
  tools --> kb["Knowledge base<br/>(RAG engagement)"]
  runtime -. "logs, traces" .-> cw["CloudWatch<br/>dashboard, alarms"]
```

A staff member signs in to Cognito and sends a prompt with their access token. The runtime validates the token and
passes it to the agent, which opens its MCP connection to the gateway with that same token. Every tool call is
authorized by the policy engine as that person before a Lambda function runs. The model call goes through an Amazon
Bedrock Guardrail. The runtime reaches Bedrock, Memory, the gateway, ECR and CloudWatch through VPC endpoints only.

## Verify locally

Prerequisites (versions used to verify this repo):

| Tool | Version |
| --- | --- |
| Python | 3.13 (installed by uv from `.python-version`) |
| uv | 0.12 or later |
| Docker | 29 (arm64 host or emulation) |
| Terraform | 1.14.5 |
| tflint | 0.61.0 (AWS ruleset 0.49.0, fetched by `tflint --init`) |
| Checkov | 3.3.19 (run through `uvx`) |
| Semgrep | run through `uvx`, `p/default` rules |
| Trivy | 0.74.0 |
| hadolint | 2.15.1 |
| jq, curl | any recent version (smoke test) |

```bash
make verify
```

The run needs no AWS credentials and makes no AWS API calls. The first run downloads Python packages, Terraform
providers, the tflint ruleset, the base images, the Trivy database and the Semgrep rules. The run ends with:

```text
verify: all checks passed
```

`make help` lists the individual targets. `make report` prints the tables that the report quotes, and a test fails
when the report and the code disagree.

A real deployment test is available as `make test-live`. It is manual, runs only in the maintainer's personal
sandbox account, creates nothing public, tags everything and tears it all down (ADR 0008). See
[docs/live-test.md](docs/live-test.md).

## Repository map

```text
src/harbor_agent/       Strands agent: runtime entry point, tool guard, memory, identity, scripted model
src/harbor_tools/       Lambda tool handlers (get_order, check_stock, open_return, search_policies)
tools/schemas/          MCP tool definitions, read by Terraform and by the tests
policy/                 Cedar policy templates and their allow and deny cases
agent/Dockerfile        arm64 image for AgentCore Runtime
infra/terraform/
  registry/             ECR repository + KMS key (own state)
  agent/                runtime, gateway, policy, memory, identity, guardrail, tools, network, observability
data/                   fixture orders and stock, scripted scenarios, price table
scripts/                smoke test, cost model, report tables, deploy, live test and its pre-flight
tests/                  pytest suites and the offline gateway harness
report/REPORT.md        evidence report for Harbor Goods
docs/                   ADRs, runbook, live-test guide
.github/workflows/      ci.yml (shared checks + verify job), deploy.yml, scorecard.yml
Makefile                one entry point for local and CI runs
```

## Decisions and trade-offs

Architecture decision records follow the *Fundamentals of Software Architecture* (2nd ed.) format.

| Number | Title | Status |
| --- | --- | --- |
| [0001](docs/adr/0001-agentcore-runtime-over-ecs.md) | AgentCore Runtime instead of an agent hosted on ECS | Accepted |
| [0002](docs/adr/0002-tools-behind-agentcore-gateway.md) | Tools behind AgentCore Gateway as MCP Lambda targets | Accepted |
| [0003](docs/adr/0003-authorization-outside-the-prompt.md) | Authorization outside the prompt | Accepted |
| [0004](docs/adr/0004-caller-token-reaches-the-gateway.md) | The caller's token reaches the gateway | Accepted |
| [0005](docs/adr/0005-strands-with-a-scripted-model.md) | Strands Agents, tested with a scripted model | Accepted |
| [0006](docs/adr/0006-private-runtime-with-vpc-endpoints.md) | Private runtime with VPC endpoints | Accepted |
| [0007](docs/adr/0007-build-once-deploy-by-digest.md) | Build once, deploy by digest, registry in its own state | Accepted |
| [0008](docs/adr/0008-live-tests-in-a-sandbox-account.md) | Live tests run in a sandbox account, private-only | Accepted |

## Security and quality gates

| Gate | Runs in | Why |
| --- | --- | --- |
| pytest: scenarios, tools, policies, memory, runtime contract, report | `make py-test`, CI `verify` job, deploy workflow | Agent behavior and controls, offline |
| ruff, mypy | `make py-lint`, pre-commit (ruff) | Python correctness and style |
| Smoke test | `make smoke`, CI `verify` job (arm64 runner), deploy workflow | The image meets the AgentCore runtime contract |
| hadolint | `make hadolint`, pre-commit, shared `container` workflow | Dockerfile practices |
| Terraform fmt, validate, tflint, `terraform test` | `make tf-verify`, shared `terraform` workflow | Syntax, AWS-specific lint, the guarantees in the acceptance table |
| Checkov | `make checkov`, shared `security` workflow | Policy checks on Terraform, the Dockerfile and workflows; skips carry reasons in the code |
| Trivy config and image | `make trivy`, shared `security` and `container` workflows, deploy workflow | Misconfigurations and fixable HIGH or CRITICAL CVEs |
| Semgrep | `make semgrep`, shared `security` workflow | Static analysis of the code, Terraform and workflows |
| gitleaks, detect-secrets | pre-commit, shared `secrets` workflow | No credentials in the history |
| actionlint, zizmor | pre-commit, shared `lint-actions` workflow | Workflow correctness and hardening |
| OpenSSF Scorecard | `scorecard.yml` | Repository supply-chain posture |

`ci.yml` is a thin caller: the shared checks come from reusable workflows in
[gamaware/.github](https://github.com/gamaware/.github). Workflows start from `permissions: {}`, pin actions by SHA and
set timeouts. Pull request jobs get no cloud access.

## Limits and production adaptations

- **Simulated:** no AWS account backs this repo's CI. The scripted model proves the control flow, not the model's
  judgment, and the mocked Terraform tests prove configuration intent, not IAM evaluation or service behavior.
  `make test-live` covers those by hand.
- **Out of scope:** the store app's sign-in screens, the GitHub OIDC provider and deploy roles (see
  `github-actions-aws-oidc-lab`), the Terraform state bucket, and the knowledge base itself (from the RAG
  engagement).
- **A real engagement adds:** confirmation in the store app before any write action, the order and inventory
  services as OpenAPI gateway targets instead of tables, code signing for the tool functions, an AWS Config rule on
  the gateway's policy mode, a retention period for session memory agreed with the privacy team, and an evaluation
  step on real traffic (AgentCore Evaluations).
- **Cost to run:** about USD 12 per 1,000 staff sessions on Amazon Nova Lite, plus about USD 102 a month for the
  seven interface endpoints in two zones, in `us-east-1` (see the report).

## Related work

Part of the [AWS DevOps portfolio](https://github.com/gamaware/aws-devops-portfolio), under the service
[AI agents on Amazon Bedrock AgentCore on Upwork](https://www.upwork.com/freelancers/~014b3520cf9e140103). The store
policy knowledge base the agent searches is built in
[terraform-aws-bedrock-rag-lab](https://github.com/gamaware/terraform-aws-bedrock-rag-lab), and the image pipeline
follows [aws-ecs-fargate-deploy-lab](https://github.com/gamaware/aws-ecs-fargate-deploy-lab).

### Credits

Built on [awslabs/agentcore-samples](https://github.com/awslabs/agentcore-samples) (Apache-2.0): the runtime role
trust policy and the log and trace delivery wiring are adapted from its Terraform samples, with attribution in the
adapted files and in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
[sample-amazon-bedrock-agentcore-onboarding](https://github.com/aws-samples/sample-amazon-bedrock-agentcore-onboarding)
(MIT-0) was a reference for the identity and gateway setup. Background reading: the AWS workshop "Diving Deep into
Bedrock AgentCore" and the AWS Machine Learning blog post on AgentOps with AgentCore. The agent uses
[Strands Agents](https://github.com/strands-agents/sdk-python) and the
[Bedrock AgentCore SDK](https://github.com/aws/bedrock-agentcore-sdk-python) (both Apache-2.0).

## License

[MIT](LICENSE)
