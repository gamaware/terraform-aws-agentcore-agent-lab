# Architecture decision records

Architecture decision records follow the *Fundamentals of Software Architecture* (2nd ed.) format.
Records are never deleted; a replaced decision is marked Superseded and links to its successor.

| Number | Title | Status |
| --- | --- | --- |
| [0001](0001-agentcore-runtime-over-ecs.md) | AgentCore Runtime instead of an agent hosted on ECS | Accepted |
| [0002](0002-tools-behind-agentcore-gateway.md) | Tools behind AgentCore Gateway as MCP Lambda targets | Accepted |
| [0003](0003-authorization-outside-the-prompt.md) | Authorization outside the prompt | Accepted |
| [0004](0004-caller-token-reaches-the-gateway.md) | The caller's token reaches the gateway | Accepted |
| [0005](0005-strands-with-a-scripted-model.md) | Strands Agents, tested with a scripted model | Accepted |
| [0006](0006-private-runtime-with-vpc-endpoints.md) | Private runtime with VPC endpoints | Accepted |
| [0007](0007-build-once-deploy-by-digest.md) | Build once, deploy by digest, registry in its own state | Accepted |
| [0008](0008-live-tests-in-a-sandbox-account.md) | Live tests run in a sandbox account, private-only | Accepted |
