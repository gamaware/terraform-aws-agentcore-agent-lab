# agent stack

Everything the agent needs except the image registry: AgentCore Runtime (VPC mode, JWT authorizer), the `live`
endpoint, AgentCore Gateway with one Lambda target per tool, AgentCore Policy, AgentCore Memory, the Cognito user
pool, the Bedrock guardrail, DynamoDB tables, the private network with VPC endpoints, and logs, traces, a dashboard
and alarms.

It reads `tools/schemas/`, `policy/` and `src/harbor_tools/` from the repository root.

```bash
terraform init -backend-config=backend.hcl   # or copy backend.tf.example to backend.tf
terraform apply -var-file=terraform.tfvars    # see terraform.tfvars.example
```

Deploys normally go through `scripts/deploy.sh` (CI). Tests run offline against a mocked provider:
`terraform test`.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
| ---- | ------- |
| terraform | >= 1.11.0, < 2.0.0 |
| archive | ~> 2.7 |
| aws | ~> 6.66 |

## Providers

| Name | Version |
| ---- | ------- |
| archive | 2.8.1 |
| aws | 6.66.0 |

## Resources

| Name | Type |
| ---- | ---- |
| [aws_bedrock_guardrail.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrock_guardrail) | resource |
| [aws_bedrock_guardrail_version.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrock_guardrail_version) | resource |
| [aws_bedrockagentcore_agent_runtime.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_agent_runtime) | resource |
| [aws_bedrockagentcore_agent_runtime_endpoint.live](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_agent_runtime_endpoint) | resource |
| [aws_bedrockagentcore_gateway.tools](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_gateway) | resource |
| [aws_bedrockagentcore_gateway_target.tool](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_gateway_target) | resource |
| [aws_bedrockagentcore_memory.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_memory) | resource |
| [aws_bedrockagentcore_memory_strategy.preferences](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_memory_strategy) | resource |
| [aws_bedrockagentcore_policy.tools](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_policy) | resource |
| [aws_bedrockagentcore_policy_engine.tools](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagentcore_policy_engine) | resource |
| [aws_cloudwatch_dashboard.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_dashboard) | resource |
| [aws_cloudwatch_log_delivery.runtime_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery) | resource |
| [aws_cloudwatch_log_delivery.runtime_traces](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery) | resource |
| [aws_cloudwatch_log_delivery_destination.runtime_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery_destination) | resource |
| [aws_cloudwatch_log_delivery_destination.runtime_traces](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery_destination) | resource |
| [aws_cloudwatch_log_delivery_source.runtime_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery_source) | resource |
| [aws_cloudwatch_log_delivery_source.runtime_traces](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_delivery_source) | resource |
| [aws_cloudwatch_log_group.flow](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_log_group.runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_log_group.tool](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_metric_alarm.tool_errors](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.tool_throttles](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cognito_user_group.staff](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_group) | resource |
| [aws_cognito_user_pool.staff](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool) | resource |
| [aws_cognito_user_pool_client.store_app](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool_client) | resource |
| [aws_default_security_group.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_security_group) | resource |
| [aws_dynamodb_table.store](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table) | resource |
| [aws_flow_log.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/flow_log) | resource |
| [aws_iam_role.flow](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.gateway](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.tool](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.flow](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.gateway](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.tool](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_kms_alias.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_alias) | resource |
| [aws_kms_key.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key) | resource |
| [aws_lambda_function.tool](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_route_table.private](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table) | resource |
| [aws_route_table_association.private](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_security_group.endpoints](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_security_group.runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_subnet.private](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_vpc.agent](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc) | resource |
| [aws_vpc_endpoint.interface](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_endpoint.s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_security_group_egress_rule.runtime_to_endpoints](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_egress_rule) | resource |
| [aws_vpc_security_group_egress_rule.runtime_to_s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_egress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.endpoints_from_runtime](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [archive_file.tools](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [aws_availability_zones.available](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/availability_zones) | data source |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_partition.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |

## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| container\_uri | Agent image in ECR, by digest: ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPOSITORY@sha256:DIGEST. | `string` | n/a | yes |
| ecr\_repository\_arn | ARN of the ECR repository the runtime pulls from (output of the registry stack). | `string` | n/a | yes |
| alarm\_actions | ARNs (for example an SNS topic) notified when an alarm fires. | `list(string)` | `[]` | no |
| availability\_zone\_ids | Two Availability Zone IDs for the private subnets. They must be zones where AgentCore Runtime supports VPC mode (see the AgentCore VPC documentation for the Region). | `list(string)` | ```[ "use1-az1", "use1-az2" ]``` | no |
| deletion\_protection | Deletion protection on the DynamoDB tables and the user pool. Keep true outside disposable test environments. | `bool` | `true` | no |
| enable\_admin\_auth\_flow | Allow ADMIN\_USER\_PASSWORD\_AUTH on the staff app client. Only the live test sets it, to get a token for a test user. | `bool` | `false` | no |
| knowledge\_base\_id | ID of the store-policy knowledge base from the RAG engagement. Empty skips the search\_policies tool. | `string` | `""` | no |
| log\_retention\_days | Retention of the agent, tool and flow log groups. | `number` | `365` | no |
| memory\_event\_expiry\_days | Days AgentCore Memory keeps short-term events. | `number` | `30` | no |
| model\_id | Amazon Bedrock inference profile ID for the agent model. | `string` | `"us.amazon.nova-lite-v1:0"` | no |
| name | Name prefix for every resource (lowercase, hyphens). AgentCore names derive from it with underscores. | `string` | `"harbor-store-ops"` | no |
| policy\_mode | Gateway policy engine mode. ENFORCE blocks denied tool calls; LOG\_ONLY only records the decision (use it to trial a policy change). | `string` | `"ENFORCE"` | no |
| refund\_limit\_cents | Largest refund, in cents, a store lead may open through the assistant. Enforced by the gateway policy and by the open\_return Lambda. | `number` | `20000` | no |
| region | AWS Region for the stack. | `string` | `"us-east-1"` | no |
| tags | Extra tags for every resource. | `map(string)` | `{}` | no |
| tool\_reserved\_concurrency | Reserved concurrency per tool Lambda. -1 leaves the functions unreserved (small sandbox accounts). | `number` | `20` | no |
| vpc\_cidr | CIDR block of the agent VPC (private subnets only, no internet gateway, no NAT). | `string` | `"10.40.0.0/16"` | no |

## Outputs

| Name | Description |
| ---- | ----------- |
| agent\_endpoint\_name | Runtime endpoint (qualifier) the store app calls. |
| agent\_runtime\_arn | ARN of the AgentCore runtime. |
| agent\_runtime\_version | Runtime version the live endpoint serves. |
| app\_client\_id | Cognito app client the store app signs in with. |
| gateway\_url | MCP endpoint of the tool gateway. |
| memory\_id | ID of the AgentCore memory. |
| runtime\_log\_group\_prefix | Prefix of the log groups with the agent container's JSON log lines (one per endpoint). |
| runtime\_vended\_log\_group | Log group receiving the runtime's vended application logs. |
| table\_names | DynamoDB table names by role (orders, stock, returns). |
| tool\_names | Gateway tool names as the agent sees them (target\_\_\_tool). |
| user\_pool\_id | Cognito user pool for store staff. |
| workload\_identity\_arn | Workload identity AgentCore created for the runtime (used for its outbound token exchanges). |
<!-- END_TF_DOCS -->
