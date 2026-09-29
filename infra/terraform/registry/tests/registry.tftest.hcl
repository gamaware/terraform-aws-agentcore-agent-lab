# Offline: the mocked provider never calls AWS and needs no credentials.
mock_provider "aws" {
  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "111122223333" }
  }
  override_data {
    target = data.aws_partition.current
    values = { partition = "aws" }
  }
}

run "repository_is_immutable_scanned_and_encrypted" {
  command = plan

  assert {
    condition     = aws_ecr_repository.app.image_tag_mutability == "IMMUTABLE"
    error_message = "Tags must be immutable so a tag always names one image."
  }

  assert {
    condition     = aws_ecr_repository.app.image_scanning_configuration[0].scan_on_push
    error_message = "Images must be scanned on push."
  }

  assert {
    condition     = aws_ecr_repository.app.encryption_configuration[0].encryption_type == "KMS"
    error_message = "Images must be encrypted with the customer managed key."
  }

  assert {
    condition     = aws_kms_key.ecr.enable_key_rotation
    error_message = "The KMS key must rotate."
  }
}

run "lifecycle_keeps_rollback_targets" {
  command = plan

  variables {
    keep_images = 12
  }

  assert {
    condition     = jsondecode(aws_ecr_lifecycle_policy.app.policy).rules[1].selection.countNumber == 12
    error_message = "The lifecycle policy must keep the configured number of tagged images."
  }

  assert {
    condition     = jsondecode(aws_ecr_lifecycle_policy.app.policy).rules[0].selection.tagStatus == "untagged"
    error_message = "Only untagged images may expire by age."
  }
}

run "rejects_a_lifecycle_that_leaves_no_rollback_target" {
  command = plan

  variables {
    keep_images = 1
  }

  expect_failures = [var.keep_images]
}
