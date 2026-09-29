# Amazon Bedrock Guardrail applied to every model call the agent makes (input and output): prompt-attack
# filter, content filters, PII handling and denied topics. It does not replace the gateway policy; a prompt
# that gets past the guardrail still cannot authorize a tool call.

resource "aws_bedrock_guardrail" "agent" {
  name                      = var.name
  description               = "Store-operations assistant guardrail"
  kms_key_arn               = aws_kms_key.agent.arn
  blocked_input_messaging   = "I can't help with that request. Ask about orders, stock, returns or store policy."
  blocked_outputs_messaging = "I can't share that answer. Ask a store lead for help."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }

    dynamic "filters_config" {
      for_each = toset(["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"])
      content {
        type            = filters_config.value
        input_strength  = "HIGH"
        output_strength = "HIGH"
      }
    }
  }

  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = toset(["CREDIT_DEBIT_CARD_NUMBER", "CREDIT_DEBIT_CARD_CVV", "US_BANK_ACCOUNT_NUMBER", "PASSWORD"])
      content {
        type   = pii_entities_config.value
        action = "BLOCK"
      }
    }

    dynamic "pii_entities_config" {
      for_each = toset(["EMAIL", "PHONE", "ADDRESS"])
      content {
        type   = pii_entities_config.value
        action = "ANONYMIZE"
      }
    }
  }

  topic_policy_config {
    topics_config {
      name       = "legal-advice"
      type       = "DENY"
      definition = "Advice on whether a customer can sue, legal rights, liability or consumer-law claims."
      examples   = ["Can the customer take us to court over this refund?", "Is the store legally liable for the damage?"]
    }

    topics_config {
      name       = "competitor-pricing"
      type       = "DENY"
      definition = "Comparisons with or promises about other retailers' prices or price matching outside store policy."
      examples   = ["Match the price the other store offers for this desk.", "What does the competitor charge for this chair?"]
    }
  }
}

resource "aws_bedrock_guardrail_version" "agent" {
  guardrail_arn = aws_bedrock_guardrail.agent.guardrail_arn
  description   = "Version used by the agent runtime"
}
