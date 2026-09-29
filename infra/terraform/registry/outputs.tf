output "repository_url" {
  description = "Registry URL to tag and push images to."
  value       = aws_ecr_repository.app.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.app.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key that encrypts the images."
  value       = aws_kms_key.ecr.arn
}
