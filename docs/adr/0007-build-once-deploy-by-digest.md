# 0007. Build once, deploy by digest, registry in its own state

## Status

Accepted

## Context

The runtime pulls the agent image from ECR. Tags can be moved, so a tag does not say which image runs. The
registry must also survive the agent stack being destroyed, or a rollback target disappears with it.

## Decision

- The ECR repository and its KMS key are a separate Terraform root module (`infra/terraform/registry`) with its own
  state, immutable tags and scan on push.
- `deploy.yml` builds the arm64 image once, runs the unit and smoke tests and a Trivy scan, pushes that exact image
  (image ID checked between jobs), records the digest ECR returns and attests its provenance.
- Terraform accepts `container_uri` only as `<repo>@sha256:<digest>`. Each apply creates a new runtime version and
  moves the `live` endpoint to it; `scripts/deploy.sh` waits until the endpoint is `READY` on that version.
- The runtime role may pull only from this repository: an explicit deny covers every other repository, because
  `ecr:GetAuthorizationToken` cannot be scoped to one.

## Consequences

- What runs is exactly what was scanned. A rollback is a deploy of an earlier digest.
- Two stacks to apply in order on first setup (registry, then agent).

## Compliance

- The terraform tests `rejects_an_image_by_tag` and `runtime_is_private_pinned_and_behind_jwt` check the digest
  rule; `access_is_scoped_per_role` checks the deny.
- `infra/terraform/registry/tests/registry.tftest.hcl` checks immutability, scanning, encryption and lifecycle.

## Notes

The same pattern is used in the ECS deploy lab of this portfolio, so the platform team deploys agents the way it
deploys everything else.
