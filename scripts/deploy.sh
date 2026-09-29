#!/usr/bin/env bash
# Apply the agent stack with one image digest and wait until the "live" runtime endpoint serves it.
#
# Usage: scripts/deploy.sh <ecr-repo-url>@sha256:<digest>
# Env:   TF_BACKEND_CONFIG  backend config file for terraform init (optional)
#        TF_VAR_FILE        variables file (required: region, ecr_repository_arn)
#        TF_AGENT_DIR       stack directory (default infra/terraform/agent)
set -euo pipefail

IMAGE="${1:?usage: deploy.sh <repo>@sha256:<digest>}"
STACK="${TF_AGENT_DIR:-infra/terraform/agent}"
: "${TF_VAR_FILE:?TF_VAR_FILE must point to the variables file}"

if [[ "$IMAGE" != *@sha256:* ]]; then
  echo "refusing to deploy $IMAGE: deploy by digest only" >&2
  exit 1
fi

init_args=(-input=false)
if [ "${TF_BACKEND_CONFIG:-}" != "" ]; then
  init_args+=("-backend-config=$TF_BACKEND_CONFIG")
fi
terraform -chdir="$STACK" init "${init_args[@]}"
terraform -chdir="$STACK" apply -input=false -auto-approve -var-file="$TF_VAR_FILE" -var "container_uri=$IMAGE"

runtime_id="$(terraform -chdir="$STACK" output -raw agent_runtime_arn)"
runtime_id="${runtime_id##*/}"
version="$(terraform -chdir="$STACK" output -raw agent_runtime_version)"
endpoint="$(terraform -chdir="$STACK" output -raw agent_endpoint_name)"

for ((i = 0; i < 60; i++)); do
  read -r status live_version < <(aws bedrock-agentcore-control get-agent-runtime-endpoint \
    --agent-runtime-id "$runtime_id" --endpoint-name "$endpoint" \
    --query '[status, liveVersion]' --output text)
  if [ "$status" = "READY" ] && [ "$live_version" = "$version" ]; then
    echo "endpoint $endpoint serves runtime version $version ($IMAGE)"
    exit 0
  fi
  if [[ "$status" == *FAILED* ]]; then
    echo "endpoint $endpoint is $status" >&2
    exit 1
  fi
  sleep 10
done
echo "endpoint $endpoint did not reach READY on version $version within 10 minutes" >&2
exit 1
