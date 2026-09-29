variable "name" {
  description = "Name prefix for every resource (lowercase, hyphens). AgentCore names derive from it with underscores."
  type        = string
  default     = "harbor-store-ops"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.name))
    error_message = "name must be 3-25 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "region" {
  description = "AWS Region for the stack."
  type        = string
  default     = "us-east-1"
}

variable "container_uri" {
  description = "Agent image in ECR, by digest: ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPOSITORY@sha256:DIGEST."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$", var.container_uri))
    error_message = "container_uri must be an ECR image referenced by sha256 digest, never by tag."
  }
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository the runtime pulls from (output of the registry stack)."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:ecr:[a-z0-9-]+:[0-9]{12}:repository/.+$", var.ecr_repository_arn))
    error_message = "ecr_repository_arn must be an ECR repository ARN."
  }
}

variable "model_id" {
  description = "Amazon Bedrock inference profile ID for the agent model."
  type        = string
  default     = "us.amazon.nova-lite-v1:0"

  validation {
    condition     = can(regex("^(us|eu|apac|global)\\.[a-z0-9-]+\\.[a-z0-9.:-]+$", var.model_id))
    error_message = "model_id must be a cross-Region inference profile ID such as us.amazon.nova-lite-v1:0."
  }
}

variable "refund_limit_cents" {
  description = "Largest refund, in cents, a store lead may open through the assistant. Enforced by the gateway policy and by the open_return Lambda."
  type        = number
  default     = 20000

  validation {
    condition     = var.refund_limit_cents >= 100 && var.refund_limit_cents <= 100000 && floor(var.refund_limit_cents) == var.refund_limit_cents
    error_message = "refund_limit_cents must be a whole number between 100 and 100000."
  }
}

variable "policy_mode" {
  description = "Gateway policy engine mode. ENFORCE blocks denied tool calls; LOG_ONLY only records the decision (use it to trial a policy change)."
  type        = string
  default     = "ENFORCE"

  validation {
    condition     = contains(["ENFORCE", "LOG_ONLY"], var.policy_mode)
    error_message = "policy_mode must be ENFORCE or LOG_ONLY."
  }
}

variable "knowledge_base_id" {
  description = "ID of the store-policy knowledge base from the RAG engagement. Empty skips the search_policies tool."
  type        = string
  default     = ""

  validation {
    condition     = var.knowledge_base_id == "" || can(regex("^[0-9A-Za-z]{10}$", var.knowledge_base_id))
    error_message = "knowledge_base_id must be a 10-character knowledge base ID, or empty."
  }
}

variable "vpc_cidr" {
  description = "CIDR block of the agent VPC (private subnets only, no internet gateway, no NAT)."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 20
    error_message = "vpc_cidr must be a valid IPv4 CIDR of /20 or larger."
  }
}

variable "availability_zone_ids" {
  description = "Two Availability Zone IDs for the private subnets. They must be zones where AgentCore Runtime supports VPC mode (see the AgentCore VPC documentation for the Region)."
  type        = list(string)
  default     = ["use1-az1", "use1-az2"]

  validation {
    condition     = length(var.availability_zone_ids) == 2 && alltrue([for z in var.availability_zone_ids : can(regex("^[a-z]{2,4}[0-9]-az[0-9]+$", z))])
    error_message = "availability_zone_ids must list exactly two zone IDs such as use1-az1."
  }
}

variable "memory_event_expiry_days" {
  description = "Days AgentCore Memory keeps short-term events."
  type        = number
  default     = 30

  validation {
    condition     = var.memory_event_expiry_days >= 7 && var.memory_event_expiry_days <= 365
    error_message = "memory_event_expiry_days must be between 7 and 365."
  }
}

variable "log_retention_days" {
  description = "Retention of the agent, tool and flow log groups."
  type        = number
  default     = 365

  validation {
    condition     = contains([30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch Logs retention value of at least 30 days."
  }
}

variable "tool_reserved_concurrency" {
  description = "Reserved concurrency per tool Lambda. -1 leaves the functions unreserved (small sandbox accounts)."
  type        = number
  default     = 20

  validation {
    condition     = var.tool_reserved_concurrency == -1 || (var.tool_reserved_concurrency >= 1 && var.tool_reserved_concurrency <= 200)
    error_message = "tool_reserved_concurrency must be -1 or between 1 and 200."
  }
}

variable "enable_admin_auth_flow" {
  description = "Allow ADMIN_USER_PASSWORD_AUTH on the staff app client. Only the live test sets it, to get a token for a test user."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Deletion protection on the DynamoDB tables and the user pool. Keep true outside disposable test environments."
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "ARNs (for example an SNS topic) notified when an alarm fires."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Extra tags for every resource."
  type        = map(string)
  default     = {}
}
