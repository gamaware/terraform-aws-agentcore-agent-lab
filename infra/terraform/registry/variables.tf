variable "name" {
  description = "Repository name; also used for the KMS key alias and tags."
  type        = string
  default     = "harbor-store-ops-agent"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name))
    error_message = "name must be 3-41 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "region" {
  description = "AWS Region for the registry."
  type        = string
  default     = "us-east-1"
}

variable "keep_images" {
  description = "How many tagged images to keep; older ones expire."
  type        = number
  default     = 30

  validation {
    condition     = var.keep_images >= 5 && var.keep_images <= 1000
    error_message = "keep_images must be between 5 and 1000, so a rollback target always exists."
  }
}

variable "force_delete" {
  description = "Allow terraform destroy to delete the repository while it still holds images. Keep false outside disposable test environments."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Extra tags for every resource."
  type        = map(string)
  default     = {}
}
