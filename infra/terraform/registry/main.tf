# The image registry lives in its own root module and state: it changes
# rarely, it must exist before the first image is pushed, and destroying the
# agent stack must never delete the images a rollback needs.
# See docs/adr/0007-build-once-deploy-by-digest.md.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

resource "aws_kms_key" "ecr" {
  description             = "Encrypts ${var.name} container images at rest"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AccountAdministration"
      Effect    = "Allow"
      Principal = { AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root" }
      Action    = "kms:*"
      Resource  = "*"
    }]
  })
}

resource "aws_kms_alias" "ecr" {
  name          = "alias/${var.name}-ecr"
  target_key_id = aws_kms_key.ecr.key_id
}

resource "aws_ecr_repository" "app" {
  name = var.name

  # A tag, once pushed, always names the same image. Deploys use the digest
  # anyway; immutability stops a re-push from rewriting history.
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the newest ${var.keep_images} tagged images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "imageCountMoreThan"
          countNumber    = var.keep_images
        }
        action = { type = "expire" }
      },
    ]
  })
}
