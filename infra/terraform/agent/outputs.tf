output "agent_runtime_arn" {
  description = "ARN of the AgentCore runtime."
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

output "agent_endpoint_name" {
  description = "Runtime endpoint (qualifier) the store app calls."
  value       = aws_bedrockagentcore_agent_runtime_endpoint.live.name
}

output "agent_runtime_version" {
  description = "Runtime version the live endpoint serves."
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version
}

output "workload_identity_arn" {
  description = "Workload identity AgentCore created for the runtime (used for its outbound token exchanges)."
  value       = try(aws_bedrockagentcore_agent_runtime.agent.workload_identity_details[0].workload_identity_arn, null)
}

output "gateway_url" {
  description = "MCP endpoint of the tool gateway."
  value       = aws_bedrockagentcore_gateway.tools.gateway_url
}

output "memory_id" {
  description = "ID of the AgentCore memory."
  value       = aws_bedrockagentcore_memory.agent.id
}

output "user_pool_id" {
  description = "Cognito user pool for store staff."
  value       = aws_cognito_user_pool.staff.id
}

output "app_client_id" {
  description = "Cognito app client the store app signs in with."
  value       = aws_cognito_user_pool_client.store_app.id
}

output "table_names" {
  description = "DynamoDB table names by role (orders, stock, returns)."
  value       = { for k, t in aws_dynamodb_table.store : k => t.name }
}

output "tool_names" {
  description = "Gateway tool names as the agent sees them (target___tool)."
  value       = sort([for k, t in local.tools : "${k}___${t.tool.name}"])
}

output "runtime_log_group_prefix" {
  description = "Prefix of the log groups with the agent container's JSON log lines (one per endpoint)."
  value       = local.runtime_log_prefix
}

output "runtime_vended_log_group" {
  description = "Log group receiving the runtime's vended application logs."
  value       = aws_cloudwatch_log_group.runtime.name
}
