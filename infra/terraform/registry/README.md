# registry stack

The ECR repository for the agent image and the KMS key that encrypts it. Apply once, before the first push. It has
its own state so that destroying the agent stack never deletes the images a rollback needs (see
[ADR 0007](../../../docs/adr/0007-build-once-deploy-by-digest.md)).

```bash
terraform init -backend-config=backend.hcl   # or copy backend.tf.example to backend.tf
terraform apply
```

Tests run offline against a mocked provider: `terraform test`.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
| ---- | ------- |
| terraform | >= 1.11.0, < 2.0.0 |
| aws | ~> 6.66 |

## Providers

| Name | Version |
| ---- | ------- |
| aws | 6.66.0 |

## Resources

| Name | Type |
| ---- | ---- |
| [aws_ecr_lifecycle_policy.app](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_lifecycle_policy) | resource |
| [aws_ecr_repository.app](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository) | resource |
| [aws_kms_alias.ecr](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_alias) | resource |
| [aws_kms_key.ecr](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_partition.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition) | data source |

## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| force\_delete | Allow terraform destroy to delete the repository while it still holds images. Keep false outside disposable test environments. | `bool` | `false` | no |
| keep\_images | How many tagged images to keep; older ones expire. | `number` | `30` | no |
| name | Repository name; also used for the KMS key alias and tags. | `string` | `"harbor-store-ops-agent"` | no |
| region | AWS Region for the registry. | `string` | `"us-east-1"` | no |
| tags | Extra tags for every resource. | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
| ---- | ----------- |
| kms\_key\_arn | ARN of the KMS key that encrypts the images. |
| repository\_arn | ARN of the ECR repository. |
| repository\_url | Registry URL to tag and push images to. |
<!-- END_TF_DOCS -->
