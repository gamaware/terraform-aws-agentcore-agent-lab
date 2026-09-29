#!/usr/bin/env bash
# Manual end-to-end test in a personal sandbox account (make test-live). Never runs in CI.
#
# - Runs only with the "personal" AWS profile, and only when LIVE_ACCOUNT_ID matches the account that
#   profile resolves to. Any other account is refused before anything is created.
# - Creates nothing public: every plan goes through scripts/check_live_plan.py first (no internet or NAT
#   gateway, no public subnet or default route, no Route 53, runtime in VPC mode). See ADR 0008.
# - Tags everything Project=terraform-aws-agentcore-agent-lab and Ephemeral=true, destroys everything on
#   exit (success, failure or Ctrl-C), then lists anything still tagged with this run's ID.
#
# Cost: about USD 1 to 3 per run (runtime active time, seven interface endpoints for about an hour, model
# tokens, logs). Set an AWS Budget with an alert on the sandbox account before the first run.
#
# Env: LIVE_ACCOUNT_ID   12-digit ID of the sandbox account (required)
#      LIVE_REGION       default us-east-1
#      LIVE_YES=1        skip the confirmation prompt
set -euo pipefail

PROFILE="personal"
REGION="${LIVE_REGION:-us-east-1}"
EXPECTED_ACCOUNT="${LIVE_ACCOUNT_ID:?set LIVE_ACCOUNT_ID to the sandbox account ID}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_ID="$(date +%s | tail -c 7)"
NAME="hg-live-$RUN_ID"
WORK="$(mktemp -d)"
PROJECT="terraform-aws-agentcore-agent-lab"

echo "Account for this run (profile $PROFILE):"
aws sts get-caller-identity --profile "$PROFILE" --output table
ACCOUNT_ID="$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)"
if [ "$ACCOUNT_ID" != "$EXPECTED_ACCOUNT" ]; then
  echo "refusing: profile $PROFILE resolves to $ACCOUNT_ID, not LIVE_ACCOUNT_ID" >&2
  exit 1
fi
if [ "${LIVE_YES:-0}" != "1" ]; then
  read -r -p "Create and destroy $NAME in $REGION on this account? [y/N] " answer
  [ "$answer" = "y" ] || exit 1
fi

# Terraform and the Python helpers read the profile from the environment; scoped to this script.
export AWS_PROFILE="$PROFILE"
export AWS_REGION="$REGION"
export TF_IN_AUTOMATION=1

# A copy with the repository layout: the agent stack reads tools/, policy/ and src/ from three levels up.
mkdir -p "$WORK/infra"
cp -R "$REPO_ROOT/infra/terraform" "$WORK/infra/terraform"
cp -R "$REPO_ROOT/tools" "$REPO_ROOT/policy" "$REPO_ROOT/src" "$WORK/"
rm -rf "$WORK"/infra/terraform/*/.terraform "$WORK"/infra/terraform/*/terraform.tfstate* "$WORK"/infra/terraform/*/.build
REGISTRY="$WORK/infra/terraform/registry"
AGENT="$WORK/infra/terraform/agent"
TAGS="{\"Project\"=\"$PROJECT\",\"Ephemeral\"=\"true\",\"run\"=\"$RUN_ID\"}"
REGISTRY_VARS=(-var "name=$NAME" -var force_delete=true -var "region=$REGION" -var "tags=$TAGS")

teardown() {
  set +e
  echo "--- teardown"
  if [ -f "$AGENT/terraform.tfstate" ]; then
    terraform -chdir="$AGENT" destroy -input=false -auto-approve -var-file="$WORK/agent.tfvars"
  fi
  if [ -f "$REGISTRY/terraform.tfstate" ]; then
    terraform -chdir="$REGISTRY" destroy -input=false -auto-approve "${REGISTRY_VARS[@]}"
  fi
  left="$(aws resourcegroupstaggingapi get-resources --tag-filters "Key=run,Values=$RUN_ID" \
    --query 'ResourceTagMappingList[].ResourceARN' --output text)"
  if [ "$left" != "" ]; then
    echo "WARNING: still tagged run=$RUN_ID (deleted resources can stay listed for a while):" >&2
    tr '\t' '\n' <<< "$left" >&2
  fi
  rm -rf "$WORK"
}
trap teardown EXIT

preflight() {
  local stack="$1"
  shift
  terraform -chdir="$stack" init -input=false > /dev/null
  terraform -chdir="$stack" plan -input=false -out="$WORK/plan.bin" "$@" > /dev/null
  terraform -chdir="$stack" show -json "$WORK/plan.bin" > "$WORK/plan.json"
  uv run --frozen --project "$REPO_ROOT" "$REPO_ROOT/scripts/check_live_plan.py" "$WORK/plan.json"
}

echo "--- registry"
preflight "$REGISTRY" "${REGISTRY_VARS[@]}"
terraform -chdir="$REGISTRY" apply -input=false "$WORK/plan.bin"
REPO_URL="$(terraform -chdir="$REGISTRY" output -raw repository_url)"
REPO_ARN="$(terraform -chdir="$REGISTRY" output -raw repository_arn)"

echo "--- image"
docker build --platform linux/arm64 --file "$REPO_ROOT/agent/Dockerfile" --tag "$REPO_URL:$RUN_ID" "$REPO_ROOT"
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO_URL%%/*}"
docker push "$REPO_URL:$RUN_ID"
IMAGE="$(docker image inspect --format '{{index .RepoDigests 0}}' "$REPO_URL:$RUN_ID")"
echo "pushed $IMAGE"

echo "--- agent stack"
cat > "$WORK/agent.tfvars" << TFVARS
name                      = "$NAME"
region                    = "$REGION"
container_uri             = "$IMAGE"
ecr_repository_arn        = "$REPO_ARN"
deletion_protection       = false
enable_admin_auth_flow    = true
tool_reserved_concurrency = -1
log_retention_days        = 30
tags                      = $TAGS
TFVARS
preflight "$AGENT" -var-file="$WORK/agent.tfvars"
terraform -chdir="$AGENT" apply -input=false "$WORK/plan.bin"
terraform -chdir="$AGENT" output -json > "$WORK/outputs.json"

echo "--- seed data"
orders="$(jq -r '.table_names.value.orders' "$WORK/outputs.json")"
stock="$(jq -r '.table_names.value.stock' "$WORK/outputs.json")"
uv run --frozen --project "$REPO_ROOT" "$REPO_ROOT/scripts/seed_tables.py" "$orders" "$stock"

echo "--- live sessions"
uv run --frozen --project "$REPO_ROOT" "$REPO_ROOT/scripts/live_sessions.py" "$WORK/outputs.json"

echo "--- live test passed"
