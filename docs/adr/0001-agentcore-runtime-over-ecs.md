# 0001. AgentCore Runtime instead of an agent hosted on ECS

## Status

Accepted

## Context

The agent needs somewhere to run. Harbor Goods' platform team already runs containers on Amazon ECS on Fargate,
so hosting the agent as one more ECS service was the obvious option. An agent differs from the storefront in three
ways: sessions are long and mostly idle while the model thinks, each staff session should be isolated from the
others, and the team wants traces of model and tool calls without writing the plumbing.

## Decision

Run the agent as a container on Amazon Bedrock AgentCore Runtime, with the same practices the team uses on ECS:
an image built once and pulled by digest, Terraform for every resource, a private network and alarms.

- The container implements the runtime contract (`/invocations` and `/ping` on port 8080, linux/arm64) through
  the `bedrock-agentcore` SDK.
- Each staff session gets its own isolated microVM; the runtime ends idle sessions after 15 minutes
  (`idle_runtime_session_timeout`).
- The runtime has a custom JWT authorizer, so no load balancer or API layer is needed in front of it.
- Logs and traces are delivered by the service (vended log and trace delivery); the image carries the ADOT
  auto-instrumentation.

## Consequences

- No cluster, service, load balancer or autoscaling policy to own. Scaling per session is the service's job.
- CPU is billed for active processing only. The cost model (`scripts/cost_model.py`) counts memory for the whole
  session to stay conservative.
- The runtime is a newer service: provider resources and quotas change faster than ECS, and some behavior can only
  be checked live (`make test-live`).
- Portability: the container is a plain HTTP server. Moving it to ECS later means adding a load balancer and an
  authorizer, not rewriting the agent.

## Compliance

- `infra/terraform/agent/tests/agent.tftest.hcl` asserts the container is pulled by digest, the JWT authorizer is
  set and the runtime runs in VPC mode.
- `scripts/smoke-test.sh` (part of `make verify`) checks the image against the runtime contract: arm64, port 8080,
  `/ping`, `/invocations`, non-root, read-only root filesystem.

## Notes

Alternatives considered:

- ECS on Fargate: known to the team, but it needs a load balancer, an authorizer, session affinity and custom
  tracing, which AgentCore provides.
- AWS Lambda: the 15-minute limit and cold starts do not fit multi-turn sessions that call several tools.
