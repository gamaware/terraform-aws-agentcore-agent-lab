# 0006. Private runtime with VPC endpoints

## Status

Accepted

## Context

The runtime can run in `PUBLIC` network mode, with outbound internet access managed by the service. The agent does
not need the internet: every call it makes is to an AWS service. Harbor Goods' rule for new workloads is no
internet path unless the design needs one.

## Decision

Run the runtime in `VPC` mode in two private subnets with no internet gateway, no NAT gateway and no default
route. Reach AWS services through VPC endpoints:

- Interface endpoints: `bedrock-runtime` (model), `bedrock-agentcore` (memory), `bedrock-agentcore.gateway`
  (tools), `ecr.api` and `ecr.dkr` (image), `logs` and `xray` (telemetry).
- A gateway endpoint for S3, with a policy that allows only the ECR image layer bucket.
- The runtime's security group allows HTTPS out to the endpoint security group and the S3 prefix list only; the
  endpoints accept HTTPS from the runtime only. VPC flow logs capture all traffic.
- The subnets are pinned to Availability Zone IDs where AgentCore supports VPC mode (`availability_zone_ids`).

## Consequences

- The fixed cost is about USD 102 a month for seven endpoints in two zones, more than the variable cost below
  roughly 9,000 sessions a month. Sharing the endpoints with other private workloads is the main saving.
- A new AWS service used by the agent needs a new endpoint, or the call fails; the failure is loud, not silent.
- The tool Lambdas are outside the VPC (they call DynamoDB and Bedrock over IAM-authenticated endpoints), which
  keeps the endpoint count down.

## Compliance

- The terraform test `network_has_no_path_to_the_internet` asserts no routes, no public IPs, the endpoint set, the
  S3 endpoint policy and the HTTPS-only rules.
- `scripts/check_live_plan.py` refuses a live plan with any internet path (ADR 0008).

## Notes

A NAT gateway would cost about USD 33 a month per zone before data processing, and would give the agent a path to
the internet it does not need.
