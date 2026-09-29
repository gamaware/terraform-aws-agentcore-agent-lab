# One Lambda function per tool, each with its own role: get_order and check_stock can only read their table,
# open_return can read orders and write returns, search_policies can only call Retrieve on one knowledge base.
# Tool definitions come from tools/schemas/*.json, the same files the offline tests read.

locals {
  all_tools = {
    for f in fileset(local.schema_dir, "*.json") :
    jsondecode(file("${local.schema_dir}/${f}")).target => jsondecode(file("${local.schema_dir}/${f}"))
  }
  tools = { for k, v in local.all_tools : k => v if k != "policies" || var.knowledge_base_id != "" }

  table_arn = { for k, t in aws_dynamodb_table.store : k => t.arn }

  tool_environment = {
    orders   = { ORDERS_TABLE = aws_dynamodb_table.store["orders"].name }
    stock    = { STOCK_TABLE = aws_dynamodb_table.store["stock"].name }
    returns  = { ORDERS_TABLE = aws_dynamodb_table.store["orders"].name, RETURNS_TABLE = aws_dynamodb_table.store["returns"].name, REFUND_LIMIT_CENTS = tostring(var.refund_limit_cents) }
    policies = { KNOWLEDGE_BASE_ID = var.knowledge_base_id }
  }

  tool_statements = {
    orders = [{ Sid = "ReadOrders", Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [local.table_arn["orders"]] }]
    stock  = [{ Sid = "ReadStock", Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [local.table_arn["stock"]] }]
    returns = [
      { Sid = "ReadOrders", Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [local.table_arn["orders"]] },
      { Sid = "WriteReturns", Effect = "Allow", Action = ["dynamodb:PutItem"], Resource = [local.table_arn["returns"]] },
    ]
    policies = [{
      Sid      = "RetrieveFromKnowledgeBase"
      Effect   = "Allow"
      Action   = ["bedrock:Retrieve"]
      Resource = ["arn:${local.partition}:bedrock:${local.region}:${local.account_id}:knowledge-base/${var.knowledge_base_id}"]
    }]
  }
}

# The handlers are harbor_tools.<module>.handler and the modules import harbor_tools.common, so the ZIP keeps
# the package directory: harbor_tools/__init__.py, harbor_tools/orders.py, ... (scripts/check_tool_package.py
# imports every handler from the built ZIP after `terraform test`).
data "archive_file" "tools" {
  type        = "zip"
  output_path = "${path.module}/.build/harbor_tools.zip"

  dynamic "source" {
    for_each = fileset(local.tools_src, "*.py")
    content {
      content  = file("${local.tools_src}/${source.value}")
      filename = "harbor_tools/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "tool" {
  for_each = local.tools

  name              = "/aws/lambda/${var.name}-${each.value.function}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.agent.arn
}

resource "aws_iam_role" "tool" {
  for_each = local.tools

  name = "${var.name}-tool-${each.value.function}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "tool" {
  for_each = local.tools

  name = "tool-access"
  role = aws_iam_role.tool[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.tool_statements[each.key], [
      {
        Sid      = "OwnLogGroup"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.tool[each.key].arn}:*"]
      },
      {
        Sid      = "Tracing"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = ["*"]
      },
      {
        Sid      = "StackKey"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [aws_kms_key.agent.arn]
      },
    ])
  })
}

resource "aws_lambda_function" "tool" {
  for_each = local.tools

  #checkov:skip=CKV_AWS_117:Tools call only DynamoDB and Bedrock over IAM-authenticated AWS endpoints; a VPC would add endpoints and cost without reducing exposure.
  #checkov:skip=CKV_AWS_116:The gateway invokes the tools synchronously and receives the error; a dead-letter queue applies to asynchronous invocations only.
  #checkov:skip=CKV_AWS_272:Code is deployed by Terraform from this repository after CI; signing is a production adaptation listed in the README.
  function_name                  = "${var.name}-${each.value.function}"
  description                    = "AgentCore Gateway tool ${each.value.tool.name}"
  role                           = aws_iam_role.tool[each.key].arn
  runtime                        = "python3.13"
  architectures                  = ["arm64"]
  handler                        = each.value.handler
  filename                       = data.archive_file.tools.output_path
  source_code_hash               = data.archive_file.tools.output_base64sha256
  timeout                        = 10
  memory_size                    = 256
  reserved_concurrent_executions = var.tool_reserved_concurrency
  kms_key_arn                    = aws_kms_key.agent.arn

  environment {
    variables = merge(local.tool_environment[each.key], { LOG_LEVEL = "INFO" })
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.tool[each.key].name
  }

  tracing_config {
    mode = "Active"
  }
}
