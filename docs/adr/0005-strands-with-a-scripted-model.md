# 0005. Strands Agents, tested with a scripted model

## Status

Accepted

## Context

The agent loop needs a framework, and the delivery needs tests that run in CI without an AWS account. Testing an
agent against a live model is slow, costs money and gives different answers each run, which makes it useless as a
merge gate.

## Decision

Build the agent with Strands Agents (Apache-2.0), and test it offline with a scripted model provider.

- `harbor_agent.scripted.ScriptedModel` implements the Strands model interface and replays fixed turns: call this
  tool with these arguments, say this text, or summarize the last tool result.
- The scenarios in `data/scenarios.yaml` include a model that misbehaves on purpose (skips a lookup, obeys an
  injected instruction, loops), so the tests show which layer stops what.
- The tests use the real agent loop, the real tool guard and memory code, the real Lambda handlers on moto, and the
  real Cedar policies through a local gateway stand-in (`tests/harness.py`).
- The agent code talks to three ports: the model, the tools and memory. Production uses Bedrock, the gateway over
  MCP and AgentCore Memory; tests swap each one.

## Consequences

- The whole scenario suite runs in about three seconds and gives the same result every time.
- The tests prove the control flow, not the model's judgment. Model quality is measured live (`make test-live`)
  and belongs in an evaluation step on real traffic.
- Strands is kept swappable: the tools are MCP and the policies are in the gateway, so moving to another framework
  means rewriting `harbor_agent/agent.py`, not the controls.

## Compliance

- `tests/test_scenarios.py` runs all 11 scenarios in `make verify`, and `tests/test_report.py` checks that the
  report quotes their current results.

## Notes

Alternatives considered: LangGraph (more control over the graph, more code for a four-tool agent) and recorded
Bedrock responses (brittle when prompts change, and they cannot represent a misbehaving model).
