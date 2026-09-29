# AgentCore Memory: short-term conversation events per staff session, plus one long-term USER_PREFERENCE
# strategy that extracts how each staff member likes answers. Encrypted with the stack key.

resource "aws_bedrockagentcore_memory" "agent" {
  name                  = "${local.snake}_memory"
  description           = "Session history and staff preferences for the store-operations agent"
  event_expiry_duration = var.memory_event_expiry_days
  encryption_key_arn    = aws_kms_key.agent.arn
}

resource "aws_bedrockagentcore_memory_strategy" "preferences" {
  name                = "staff_preferences"
  description         = "How each staff member prefers answers (format, store, level of detail)"
  memory_id           = aws_bedrockagentcore_memory.agent.id
  type                = "USER_PREFERENCE"
  namespace_templates = ["/users/{actorId}/preferences/"]
}
