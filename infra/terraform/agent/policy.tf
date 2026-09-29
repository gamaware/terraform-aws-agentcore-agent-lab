# AgentCore Policy: Cedar policies evaluated by the gateway on every tool call, outside the model and the
# agent process. Deny by default; policy/*.cedar.tftpl permit the read tools for store staff and open_return
# for store leads up to the refund limit. tests/test_policy.py evaluates the same templates offline.
# See docs/adr/0003-authorization-outside-the-prompt.md.

resource "aws_bedrockagentcore_policy_engine" "tools" {
  name               = "${local.snake}_tools"
  description        = "Authorizes Harbor Goods store tool calls"
  encryption_key_arn = aws_kms_key.agent.arn
}

resource "aws_bedrockagentcore_policy" "tools" {
  for_each = fileset(local.policy_dir, "*.cedar.tftpl")

  name             = trimsuffix(each.key, ".cedar.tftpl")
  description      = "policy/${each.key}"
  policy_engine_id = aws_bedrockagentcore_policy_engine.tools.policy_engine_id
  validation_mode  = "FAIL_ON_ANY_FINDINGS"

  definition {
    cedar {
      statement = templatefile("${local.policy_dir}/${each.key}", {
        gateway_arn        = aws_bedrockagentcore_gateway.tools.gateway_arn
        refund_limit_cents = var.refund_limit_cents
      })
    }
  }
}
