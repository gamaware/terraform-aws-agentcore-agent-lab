# Harbor Goods store-operations agent on Amazon Bedrock AgentCore:
#   runtime (container, VPC mode, inbound JWT)  -> gateway (MCP, JWT, policy engine) -> Lambda tools -> DynamoDB
#   memory (short-term events + user preferences), guardrail on every model call, logs and traces.
# One customer managed KMS key encrypts the tables, logs, memory, gateway, policy engine and guardrail.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  partition   = data.aws_partition.current.partition
  region      = data.aws_region.current.region
  snake       = replace(var.name, "-", "_")
  agentcore   = "arn:${local.partition}:bedrock-agentcore:${local.region}:${local.account_id}"
  schema_dir  = "${path.module}/../../../tools/schemas"
  policy_dir  = "${path.module}/../../../policy"
  tools_src   = "${path.module}/../../../src/harbor_tools"
  base_model  = regex("^(?:us|eu|apac|global)\\.(.+)$", var.model_id)[0]
  discovery   = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.staff.id}/.well-known/openid-configuration"
  staff_group = ["store-associates", "store-leads"]
}

resource "aws_kms_key" "agent" {
  description             = "Encrypts ${var.name} tables, logs, memory, gateway, policies and guardrail"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdministration"
        Effect    = "Allow"
        Principal = { AWS = "arn:${local.partition}:iam::${local.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${local.region}.amazonaws.com" }
        Action    = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:*"
          }
        }
      },
    ]
  })
}

resource "aws_kms_alias" "agent" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.agent.key_id
}
