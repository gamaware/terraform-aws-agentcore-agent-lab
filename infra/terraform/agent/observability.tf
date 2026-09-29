# Logs, traces, a dashboard and alarms.
# The vended log and trace delivery wiring is adapted from awslabs/agentcore-samples
# (04-infrastructure-as-code/terraform/end-to-end-weather-agent/observability.tf, Apache-2.0); see
# THIRD_PARTY_NOTICES.md. Changes: KMS-encrypted log group, stack naming, alarms and a dashboard added.

# The runtime writes the container's stdout (the agent's JSON log lines) to log groups under this prefix, which
# the service creates per endpoint. The vended APPLICATION_LOGS delivery below goes to its own log group.
locals {
  runtime_log_prefix = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id}"
}

resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/vendedlogs/bedrock-agentcore/${var.name}-runtime"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.agent.arn
}

resource "aws_cloudwatch_log_delivery_source" "runtime_logs" {
  name         = "${var.name}-runtime-logs"
  log_type     = "APPLICATION_LOGS"
  resource_arn = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

resource "aws_cloudwatch_log_delivery_destination" "runtime_logs" {
  name = "${var.name}-runtime-logs"

  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.runtime.arn
  }
}

resource "aws_cloudwatch_log_delivery" "runtime_logs" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.runtime_logs.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.runtime_logs.arn
}

resource "aws_cloudwatch_log_delivery_source" "runtime_traces" {
  name         = "${var.name}-runtime-traces"
  log_type     = "TRACES"
  resource_arn = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

resource "aws_cloudwatch_log_delivery_destination" "runtime_traces" {
  name                      = "${var.name}-runtime-traces"
  delivery_destination_type = "XRAY"
}

resource "aws_cloudwatch_log_delivery" "runtime_traces" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.runtime_traces.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.runtime_traces.arn
}

# Tool errors: a failing tool is a broken promise to store staff, not a model problem.
resource "aws_cloudwatch_metric_alarm" "tool_errors" {
  for_each = local.tools

  alarm_name          = "${var.name}-${each.value.function}-errors"
  alarm_description   = "Tool ${each.value.tool.name} returned errors (unhandled exceptions, not business refusals)."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.tool[each.key].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "tool_throttles" {
  for_each = local.tools

  alarm_name          = "${var.name}-${each.value.function}-throttles"
  alarm_description   = "Tool ${each.value.tool.name} hit its reserved concurrency."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.tool[each.key].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
}

resource "aws_cloudwatch_dashboard" "agent" {
  dashboard_name = var.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "log"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Tool calls by outcome (agent guard log)"
          region = local.region
          query  = "SOURCE logGroups(namePrefix: ['${local.runtime_log_prefix}']) | filter event = 'tool_call' or event = 'tool_guard' | stats count(*) by tool, outcome"
          view   = "table"
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Refused tool calls (Lambda business checks)"
          region = local.region
          query  = join(" ", [for k, g in aws_cloudwatch_log_group.tool : "SOURCE '${g.name}'"], ["| filter event = 'tool_call' and outcome != 'ok' | stats count(*) by tool, outcome"])
          view   = "table"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Tool invocations and errors"
          region  = local.region
          stat    = "Sum"
          period  = 300
          metrics = flatten([for k, f in aws_lambda_function.tool : [["AWS/Lambda", "Invocations", "FunctionName", f.function_name], ["AWS/Lambda", "Errors", "FunctionName", f.function_name]]])
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Tool duration p90 (ms)"
          region  = local.region
          stat    = "p90"
          period  = 300
          metrics = [for k, f in aws_lambda_function.tool : ["AWS/Lambda", "Duration", "FunctionName", f.function_name]]
        }
      },
    ]
  })
}
