# Third-party notices

This repository is MIT-licensed. Parts of it are adapted from the project below, which is licensed under the
Apache License, Version 2.0. The adapted files carry an attribution comment at the top.

## awslabs/agentcore-samples

- Source: <https://github.com/awslabs/agentcore-samples>, directory
  `04-infrastructure-as-code/terraform/end-to-end-weather-agent`
- License: Apache License, Version 2.0 (<https://www.apache.org/licenses/LICENSE-2.0>)
- NOTICE: "Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved."

| File in this repository | Adapted from | Changes |
| --- | --- | --- |
| `infra/terraform/agent/runtime.tf` | `iam.tf` (agent execution role) | Trust policy kept; permissions scoped to one repository, one model, one memory, one guardrail and one key; no managed full-access policy; runtime in VPC mode with a JWT authorizer added |
| `infra/terraform/agent/observability.tf` | `observability.tf` | Log and trace delivery wiring kept; KMS-encrypted log group, stack naming, alarms and dashboard added |

Licensed under the Apache License, Version 2.0 (the "License"); you may not use these files except in compliance
with the License. Unless required by applicable law or agreed to in writing, software distributed under the License
is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations under the License.

## Runtime dependencies

The agent image includes, among others, Strands Agents, the Amazon Bedrock AgentCore SDK, the AWS Distro for
OpenTelemetry and boto3 (Apache-2.0). The full list with versions is in `uv.lock`, and the deploy workflow publishes
a CycloneDX SBOM for every image.
