# Offline: the mocked AWS provider never calls AWS and needs no credentials. `apply` against the mock fills
# computed attributes with placeholder values, so IAM documents can be decoded and checked.
mock_provider "aws" {
  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "111122223333" }
  }
  override_data {
    target = data.aws_partition.current
    values = { partition = "aws" }
  }
  override_data {
    target = data.aws_region.current
    values = { region = "us-east-1" }
  }
  override_data {
    target = data.aws_availability_zones.available
    values = { names = ["us-east-1a", "us-east-1b"], zone_ids = ["use1-az1", "use1-az2"] }
  }

  # The mock would fill ARNs and IDs with random strings; the provider validates their format.
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:us-east-1:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::111122223333:role/harbor-store-ops-mock" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:111122223333:log-group:/harbor-store-ops/mock" }
  }
  mock_resource "aws_cognito_user_pool" {
    defaults = { id = "us-east-1_AbCdEfGhI", arn = "arn:aws:cognito-idp:us-east-1:111122223333:userpool/us-east-1_AbCdEfGhI" }
  }
  mock_resource "aws_dynamodb_table" {
    defaults = { arn = "arn:aws:dynamodb:us-east-1:111122223333:table/harbor-store-ops-mock" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:us-east-1:111122223333:function:harbor-store-ops-mock" }
  }
  mock_resource "aws_bedrock_guardrail" {
    defaults = { guardrail_arn = "arn:aws:bedrock:us-east-1:111122223333:guardrail/abcdefghij12", guardrail_id = "abcdefghij12" }
  }
  mock_resource "aws_bedrock_guardrail_version" {
    defaults = { version = "1" }
  }
  mock_resource "aws_bedrockagentcore_policy_engine" {
    defaults = {
      policy_engine_arn = "arn:aws:bedrock-agentcore:us-east-1:111122223333:policy-engine/harbor_store_ops_tools-abcdefghij"
      policy_engine_id  = "harbor_store_ops_tools-abcdefghij"
    }
  }
  mock_resource "aws_bedrockagentcore_gateway" {
    defaults = {
      gateway_arn = "arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/harbor-store-ops-abcdefghij"
      gateway_id  = "harbor-store-ops-abcdefghij"
      gateway_url = "https://harbor-store-ops-abcdefghij.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
    }
  }
  mock_resource "aws_bedrockagentcore_memory" {
    defaults = {
      arn = "arn:aws:bedrock-agentcore:us-east-1:111122223333:memory/harbor_store_ops_memory-abcdefghij"
      id  = "harbor_store_ops_memory-abcdefghij"
    }
  }
  mock_resource "aws_bedrockagentcore_agent_runtime" {
    defaults = {
      agent_runtime_arn     = "arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/harbor_store_ops_agent-abcdefghij"
      agent_runtime_id      = "harbor_store_ops_agent-abcdefghij"
      agent_runtime_version = "1"
    }
  }
  mock_resource "aws_cloudwatch_log_delivery_destination" {
    defaults = { arn = "arn:aws:logs:us-east-1:111122223333:delivery-destination:harbor-store-ops-mock" }
  }
}

variables {
  container_uri      = "111122223333.dkr.ecr.us-east-1.amazonaws.com/harbor-store-ops-agent@sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
  ecr_repository_arn = "arn:aws:ecr:us-east-1:111122223333:repository/harbor-store-ops-agent"
}

run "runtime_is_private_pinned_and_behind_jwt" {
  command = apply

  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.network_configuration[0].network_mode == "VPC"
    error_message = "The runtime must run in VPC mode, never PUBLIC."
  }

  assert {
    condition     = length(aws_bedrockagentcore_agent_runtime.agent.network_configuration[0].network_mode_config[0].subnets) == 2
    error_message = "The runtime must use the two private subnets."
  }

  assert {
    condition     = strcontains(aws_bedrockagentcore_agent_runtime.agent.agent_runtime_artifact[0].container_configuration[0].container_uri, "@sha256:")
    error_message = "The runtime must pull its image by digest."
  }

  assert {
    condition     = startswith(aws_bedrockagentcore_agent_runtime.agent.authorizer_configuration[0].custom_jwt_authorizer[0].discovery_url, "https://cognito-idp.us-east-1.amazonaws.com/")
    error_message = "Inbound calls must be authorized with the staff user pool's JWTs."
  }

  assert {
    condition     = toset(aws_bedrockagentcore_agent_runtime.agent.authorizer_configuration[0].custom_jwt_authorizer[0].allowed_clients) == toset([aws_cognito_user_pool_client.store_app.id])
    error_message = "Only the store app client may call the runtime."
  }

  assert {
    condition     = toset(aws_bedrockagentcore_agent_runtime.agent.request_header_configuration[0].request_header_allowlist) == toset(["Authorization"])
    error_message = "Only the Authorization header is forwarded, so the agent can call the gateway as the caller."
  }

  assert {
    condition     = aws_bedrockagentcore_agent_runtime.agent.environment_variables["HARBOR_AGENT_MODE"] == "bedrock"
    error_message = "The deployed runtime must never run in smoke mode."
  }

  assert {
    condition     = aws_bedrockagentcore_agent_runtime_endpoint.live.agent_runtime_version == aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version
    error_message = "The live endpoint must serve the version this apply created."
  }
}

run "network_has_no_path_to_the_internet" {
  command = apply

  assert {
    condition     = length(aws_route_table.private.route) == 0
    error_message = "The private route table must hold no routes besides local and the S3 endpoint."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.private : !s.map_public_ip_on_launch])
    error_message = "Subnets must not assign public IPs."
  }

  assert {
    condition     = toset(keys(aws_vpc_endpoint.interface)) == toset(["bedrock-agentcore", "bedrock-agentcore.gateway", "bedrock-runtime", "ecr.api", "ecr.dkr", "logs", "xray"])
    error_message = "The runtime needs exactly these interface endpoints (the cost model counts seven)."
  }

  assert {
    condition     = alltrue([for e in aws_vpc_endpoint.interface : e.private_dns_enabled])
    error_message = "Interface endpoints need private DNS so the SDKs resolve to them."
  }

  assert {
    condition     = jsondecode(aws_vpc_endpoint.s3.policy).Statement[0].Resource == ["arn:aws:s3:::prod-us-east-1-starport-layer-bucket/*"]
    error_message = "The S3 endpoint must allow only ECR's image layer bucket."
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.runtime_to_endpoints.from_port == 443 && aws_vpc_security_group_egress_rule.runtime_to_s3.to_port == 443
    error_message = "The runtime may only send HTTPS."
  }

  assert {
    condition     = aws_flow_log.agent.traffic_type == "ALL"
    error_message = "VPC flow logs must capture all traffic."
  }
}

run "gateway_authenticates_and_enforces_policy" {
  command = apply

  assert {
    condition     = aws_bedrockagentcore_gateway.tools.authorizer_type == "CUSTOM_JWT"
    error_message = "The gateway must require a staff JWT."
  }

  assert {
    condition     = aws_bedrockagentcore_gateway.tools.policy_engine_configuration[0].mode == "ENFORCE"
    error_message = "The policy engine must enforce by default."
  }

  assert {
    condition     = aws_bedrockagentcore_gateway.tools.kms_key_arn == aws_kms_key.agent.arn
    error_message = "The gateway must use the stack key."
  }

  assert {
    condition     = length(aws_bedrockagentcore_policy.tools) == 3
    error_message = "Every policy/*.cedar.tftpl file becomes one policy."
  }

  assert {
    condition     = alltrue([for p in aws_bedrockagentcore_policy.tools : strcontains(p.definition[0].cedar[0].statement, "AgentCore::Gateway::\"${aws_bedrockagentcore_gateway.tools.gateway_arn}\"")])
    error_message = "Every policy must be scoped to this gateway."
  }

  assert {
    condition     = strcontains(aws_bedrockagentcore_policy.tools["open_return.cedar.tftpl"].definition[0].cedar[0].statement, "context.input.refund_cents <= 20000")
    error_message = "The open_return policy must carry the refund limit."
  }

  assert {
    condition     = alltrue([for p in aws_bedrockagentcore_policy.tools : p.validation_mode == "FAIL_ON_ANY_FINDINGS"])
    error_message = "Policies must fail on any validation finding."
  }

  assert {
    condition     = aws_bedrockagentcore_policy_engine.tools.encryption_key_arn == aws_kms_key.agent.arn
    error_message = "The policy engine must use the stack key."
  }
}

run "targets_follow_the_tool_schemas" {
  command = apply

  assert {
    condition     = toset(keys(aws_bedrockagentcore_gateway_target.tool)) == toset(["orders", "returns", "stock"])
    error_message = "Without a knowledge base ID, the gateway exposes orders, stock and returns only."
  }

  assert {
    condition     = !strcontains(aws_bedrockagentcore_policy.tools["read_tools.cedar.tftpl"].definition[0].cedar[0].statement, "policies___search_policies")
    error_message = "Without a knowledge base the read policy must not name search_policies: AgentCore rejects undefined actions."
  }

  assert {
    condition     = strcontains(aws_bedrockagentcore_policy.tools["read_tools.cedar.tftpl"].definition[0].cedar[0].statement, "AgentCore::Action::\"orders___get_order\",\n    AgentCore::Action::\"stock___check_stock\"")
    error_message = "The read policy must name get_order and check_stock."
  }

  assert {
    condition     = aws_bedrockagentcore_gateway_target.tool["returns"].target_configuration[0].mcp[0].lambda[0].tool_schema[0].inline_payload[0].name == "open_return"
    error_message = "The returns target must expose open_return."
  }

  assert {
    condition     = alltrue([for p in aws_bedrockagentcore_gateway_target.tool["returns"].target_configuration[0].mcp[0].lambda[0].tool_schema[0].inline_payload[0].input_schema[0].property : p.required])
    error_message = "Every open_return argument is required."
  }

  assert {
    condition     = one([for p in aws_bedrockagentcore_gateway_target.tool["returns"].target_configuration[0].mcp[0].lambda[0].tool_schema[0].inline_payload[0].input_schema[0].property : p.type if p.name == "refund_cents"]) == "integer"
    error_message = "refund_cents must reach the policy engine as an integer."
  }

  assert {
    condition     = aws_lambda_function.tool["returns"].environment[0].variables["REFUND_LIMIT_CENTS"] == "20000"
    error_message = "open_return must enforce the same limit as the policy."
  }

  assert {
    condition     = alltrue([for f in aws_lambda_function.tool : one(f.architectures) == "arm64" && f.tracing_config[0].mode == "Active"])
    error_message = "Tools run on arm64 with active tracing."
  }
}

run "knowledge_base_adds_the_policy_search_tool" {
  command = apply

  variables {
    knowledge_base_id = "KBHARBOR01"
  }

  assert {
    condition     = contains(keys(aws_bedrockagentcore_gateway_target.tool), "policies")
    error_message = "A knowledge base ID must add the search_policies target."
  }

  assert {
    condition     = strcontains(aws_bedrockagentcore_policy.tools["read_tools.cedar.tftpl"].definition[0].cedar[0].statement, "AgentCore::Action::\"policies___search_policies\"")
    error_message = "With a knowledge base the read policy must permit search_policies."
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.tool["policies"].policy).Statement[0].Resource == ["arn:aws:bedrock:us-east-1:111122223333:knowledge-base/KBHARBOR01"]
    error_message = "search_policies may retrieve from that one knowledge base only."
  }
}

run "access_is_scoped_per_role" {
  command = apply

  assert {
    condition     = jsondecode(aws_iam_role_policy.tool["orders"].policy).Statement[0].Action == ["dynamodb:GetItem"] && jsondecode(aws_iam_role_policy.tool["orders"].policy).Statement[0].Resource == [aws_dynamodb_table.store["orders"].arn]
    error_message = "get_order may only read the orders table."
  }

  assert {
    condition     = jsondecode(aws_iam_role_policy.tool["returns"].policy).Statement[1].Action == ["dynamodb:PutItem"] && jsondecode(aws_iam_role_policy.tool["returns"].policy).Statement[1].Resource == [aws_dynamodb_table.store["returns"].arn]
    error_message = "open_return may only write the returns table."
  }

  assert {
    condition = alltrue(flatten([
      for p in concat([aws_iam_role_policy.runtime.policy, aws_iam_role_policy.gateway.policy], [for t in aws_iam_role_policy.tool : t.policy]) : [
        for s in jsondecode(p).Statement : !contains(flatten([s.Action]), "*") && alltrue([for a in flatten([s.Action]) : !endswith(a, ":*")])
      ]
    ]))
    error_message = "No role may be granted wildcard actions."
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_role_policy.runtime.policy).Statement : s.Resource if s.Sid == "InvokeAgentModel"]) == ["arn:aws:bedrock:us-east-1:111122223333:inference-profile/us.amazon.nova-lite-v1:0", "arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0"]
    error_message = "The runtime may invoke only the configured model."
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_role_policy.runtime.policy).Statement : s.Resource if s.Sid == "Memory"]) == [aws_bedrockagentcore_memory.agent.arn]
    error_message = "The runtime may use only its own memory."
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_role_policy.gateway.policy).Statement : s.Resource if s.Sid == "InvokeToolFunctions"]) == [for f in aws_lambda_function.tool : f.arn]
    error_message = "The gateway may invoke only the tool functions."
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_role_policy.runtime.policy).Statement : s.NotResource if s.Sid == "NoOtherRepositories" && s.Effect == "Deny"]) == ["arn:aws:ecr:us-east-1:111122223333:repository/harbor-store-ops-agent"]
    error_message = "The runtime must be denied pulls from any repository but its own."
  }

  assert {
    condition     = jsondecode(aws_iam_role.runtime.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "111122223333"
    error_message = "The runtime role trust must be limited to this account."
  }
}

run "data_is_encrypted_and_recoverable" {
  command = apply

  assert {
    condition     = alltrue([for t in aws_dynamodb_table.store : t.server_side_encryption[0].kms_key_arn == aws_kms_key.agent.arn && t.point_in_time_recovery[0].enabled && t.deletion_protection_enabled])
    error_message = "Tables use the stack key, point-in-time recovery and deletion protection."
  }

  assert {
    condition     = aws_bedrockagentcore_memory.agent.encryption_key_arn == aws_kms_key.agent.arn
    error_message = "Memory must be encrypted with the stack key."
  }

  assert {
    condition     = aws_bedrockagentcore_memory_strategy.preferences.type == "USER_PREFERENCE"
    error_message = "Memory keeps one long-term strategy: staff preferences."
  }

  assert {
    condition     = alltrue([for g in concat([aws_cloudwatch_log_group.runtime, aws_cloudwatch_log_group.flow], values(aws_cloudwatch_log_group.tool)) : g.kms_key_id == aws_kms_key.agent.arn && g.retention_in_days >= 30])
    error_message = "Every log group is encrypted and kept for at least 30 days."
  }

  assert {
    condition     = aws_kms_key.agent.enable_key_rotation
    error_message = "The stack key must rotate."
  }

  assert {
    condition     = aws_bedrock_guardrail.agent.kms_key_arn == aws_kms_key.agent.arn
    error_message = "The guardrail must use the stack key."
  }

  assert {
    condition     = one([for f in aws_bedrock_guardrail.agent.content_policy_config[0].filters_config : f.input_strength if f.type == "PROMPT_ATTACK"]) == "HIGH"
    error_message = "The guardrail must filter prompt attacks at HIGH."
  }
}

run "rejects_an_image_by_tag" {
  command = plan

  variables {
    container_uri = "111122223333.dkr.ecr.us-east-1.amazonaws.com/harbor-store-ops-agent:latest"
  }

  expect_failures = [var.container_uri]
}

run "rejects_an_unknown_policy_mode" {
  command = plan

  variables {
    policy_mode = "DISABLED"
  }

  expect_failures = [var.policy_mode]
}

run "rejects_a_fractional_refund_limit" {
  command = plan

  variables {
    refund_limit_cents = 150.5
  }

  expect_failures = [var.refund_limit_cents]
}

run "admin_auth_flow_is_off_by_default" {
  command = plan

  assert {
    condition     = !contains(aws_cognito_user_pool_client.store_app.explicit_auth_flows, "ALLOW_ADMIN_USER_PASSWORD_AUTH")
    error_message = "Only the live test may enable ADMIN_USER_PASSWORD_AUTH."
  }

  assert {
    condition     = aws_cognito_user_pool.staff.admin_create_user_config[0].allow_admin_create_user_only
    error_message = "Staff accounts are created by administrators only."
  }
}
