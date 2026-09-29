# AgentCore Gateway: one MCP endpoint for the agent, one Lambda target per tool. Inbound calls need a staff
# access token from the Cognito pool; the policy engine then authorizes every tools/call as that staff member.
# Tool schemas are read from tools/schemas/*.json: fileset("${path.module}/../../../tools/schemas", "*.json")

resource "aws_iam_role" "gateway" {
  name = "${var.name}-gateway"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnLike      = { "aws:SourceArn" = "${local.agentcore}:gateway/*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "gateway" {
  name = "invoke-tools"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeToolFunctions"
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = [for f in aws_lambda_function.tool : f.arn]
      },
      {
        Sid      = "PolicyEngine"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:AuthorizeAction", "bedrock-agentcore:PartiallyAuthorizeActions", "bedrock-agentcore:GetPolicyEngine"]
        Resource = [aws_bedrockagentcore_policy_engine.tools.policy_engine_arn, "${local.agentcore}:gateway/*"]
      },
      {
        Sid      = "StackKey"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [aws_kms_key.agent.arn]
      },
    ]
  })
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name            = var.name
  description     = "Harbor Goods store tools for the store-operations agent"
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "CUSTOM_JWT"
  kms_key_arn     = aws_kms_key.agent.arn

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = local.discovery
      allowed_clients = [aws_cognito_user_pool_client.store_app.id]
    }
  }

  policy_engine_configuration {
    arn  = aws_bedrockagentcore_policy_engine.tools.policy_engine_arn
    mode = var.policy_mode
  }

  protocol_configuration {
    mcp {
      instructions       = "Harbor Goods store tools. Look up an order before opening a return."
      supported_versions = ["2025-06-18"]
    }
  }

  depends_on = [aws_iam_role_policy.gateway]
}

resource "aws_bedrockagentcore_gateway_target" "tool" {
  for_each = local.tools

  name               = each.key
  description        = each.value.tool.description
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.tool[each.key].arn

        tool_schema {
          inline_payload {
            name        = each.value.tool.name
            description = each.value.tool.description

            input_schema {
              type = each.value.tool.inputSchema.type

              dynamic "property" {
                for_each = each.value.tool.inputSchema.properties
                content {
                  name        = property.key
                  type        = property.value.type
                  description = property.value.description
                  required    = contains(each.value.tool.inputSchema.required, property.key)
                }
              }
            }
          }
        }
      }
    }
  }
}
