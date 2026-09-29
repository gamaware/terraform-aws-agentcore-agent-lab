# AgentCore Runtime: the agent container, pulled by digest, running in VPC mode in the private subnets.
# Inbound calls need a staff access token (custom JWT authorizer); the Authorization header is forwarded to
# the container so the agent can call the gateway as that staff member.
# The trust policy and log/trace permissions are adapted from awslabs/agentcore-samples
# (04-infrastructure-as-code/terraform/end-to-end-weather-agent/iam.tf, Apache-2.0); see THIRD_PARTY_NOTICES.md.

resource "aws_iam_role" "runtime" {
  name = "${var.name}-runtime"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnLike      = { "aws:SourceArn" = "${local.agentcore}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "runtime" {
  name = "agent-runtime"
  role = aws_iam_role.runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PullAgentImage"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = [var.ecr_repository_arn]
      },
      {
        # GetAuthorizationToken has no resource-level permissions, so the token itself cannot be scoped.
        Sid      = "EcrToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = ["*"]
      },
      {
        # What the token can be used for is scoped instead: no pulls from any other repository, even if a
        # broader policy is attached to this role later.
        Sid         = "NoOtherRepositories"
        Effect      = "Deny"
        Action      = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
        NotResource = [var.ecr_repository_arn]
      },
      {
        Sid      = "RuntimeLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
      },
      {
        # X-Ray trace APIs have no resource-level permissions.
        Sid      = "Traces"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
        Resource = ["*"]
      },
      {
        Sid       = "Metrics"
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = ["*"]
        Condition = { StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" } }
      },
      {
        Sid    = "InvokeAgentModel"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = [
          "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:inference-profile/${var.model_id}",
          "arn:${local.partition}:bedrock:*::foundation-model/${local.base_model}",
        ]
      },
      {
        Sid      = "ApplyGuardrail"
        Effect   = "Allow"
        Action   = ["bedrock:ApplyGuardrail"]
        Resource = [aws_bedrock_guardrail.agent.guardrail_arn]
      },
      {
        Sid      = "Memory"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:CreateEvent", "bedrock-agentcore:ListEvents", "bedrock-agentcore:RetrieveMemoryRecords"]
        Resource = [aws_bedrockagentcore_memory.agent.arn]
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

resource "aws_bedrockagentcore_agent_runtime" "agent" {
  agent_runtime_name = "${local.snake}_agent"
  description        = "Harbor Goods store-operations agent"
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.container_uri
    }
  }

  network_configuration {
    network_mode = "VPC"
    network_mode_config {
      subnets         = aws_subnet.private[*].id
      security_groups = [aws_security_group.runtime.id]
    }
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = local.discovery
      allowed_clients = [aws_cognito_user_pool_client.store_app.id]
    }
  }

  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  lifecycle_configuration {
    idle_runtime_session_timeout = 900
    max_lifetime                 = 28800
  }

  environment_variables = {
    HARBOR_AGENT_MODE = "bedrock"
    MODEL_ID          = var.model_id
    GUARDRAIL_ID      = aws_bedrock_guardrail.agent.guardrail_id
    GUARDRAIL_VERSION = aws_bedrock_guardrail_version.agent.version
    GATEWAY_URL       = aws_bedrockagentcore_gateway.tools.gateway_url
    MEMORY_ID         = aws_bedrockagentcore_memory.agent.id
    MAX_TOOL_CALLS    = "8"
    HISTORY_TURNS     = "6"
  }

  depends_on = [aws_iam_role_policy.runtime, aws_vpc_endpoint.interface, aws_vpc_endpoint.s3]
}

resource "aws_bedrockagentcore_agent_runtime_endpoint" "live" {
  name                  = "live"
  description           = "Endpoint the store app calls; moves to a new runtime version on each deploy"
  agent_runtime_id      = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
  agent_runtime_version = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version
}
