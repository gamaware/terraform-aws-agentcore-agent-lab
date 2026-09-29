#!/usr/bin/env bash
# Local smoke test of the agent image under the AgentCore Runtime contract: linux/arm64, port 8080,
# GET /ping and POST /invocations, non-root, read-only root filesystem, no Linux capabilities.
# Needs curl and jq. Runs in smoke mode (scripted model, no tools, in-process memory) with telemetry
# off: no AWS access.
#
# Usage: scripts/smoke-test.sh [image]   (default: harbor-store-ops-agent:local)
set -euo pipefail

IMAGE="${1:-harbor-store-ops-agent:local}"
NAME="harbor-agent-smoke-$$"
PORT="${SMOKE_PORT:-18090}"
SESSION="smoke-session-000000000000000000000001"

cleanup() {
  docker rm --force "$NAME" > /dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  docker logs "$NAME" >&2 || true
  exit 1
}

arch="$(docker image inspect --format '{{.Architecture}}' "$IMAGE")"
[ "$arch" = "arm64" ] || fail "image architecture is $arch, AgentCore Runtime needs arm64"
echo "ok   architecture -> arm64"

docker run --detach --name "$NAME" \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --env HARBOR_AGENT_MODE=smoke \
  --env OTEL_SDK_DISABLED=true \
  --env AWS_EC2_METADATA_DISABLED=true \
  --publish "127.0.0.1:$PORT:8080" \
  "$IMAGE" > /dev/null

user="$(docker inspect --format '{{.Config.User}}' "$NAME")"
[ "$user" = "10001:10001" ] || fail "image runs as '$user', expected 10001:10001"
echo "ok   user -> $user"

for ((i = 0; i < 60; i++)); do
  if curl --silent --fail "http://127.0.0.1:$PORT/ping" > /dev/null; then
    break
  fi
  sleep 0.5
done

ping="$(curl --silent --fail "http://127.0.0.1:$PORT/ping")" || fail "/ping did not answer"
jq -e '.status == "Healthy"' <<< "$ping" > /dev/null || fail "/ping returned $ping"
echo "ok   /ping -> $ping"

reply="$(curl --silent --fail -X POST "http://127.0.0.1:$PORT/invocations" \
  --header 'Content-Type: application/json' \
  --header "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $SESSION" \
  --data '{"prompt": "Are you up?"}')" || fail "/invocations did not answer"
jq -e --arg s "$SESSION" '.reply == "Harbor Goods assistant is up." and .session_id == $s and .tool_calls == []' \
  <<< "$reply" > /dev/null || fail "/invocations returned $reply"
echo "ok   /invocations -> $reply"

bad="$(curl --silent -X POST "http://127.0.0.1:$PORT/invocations" \
  --header 'Content-Type: application/json' --data '{"question": "hi"}')"
jq -e 'has("error") and (has("reply") | not)' <<< "$bad" > /dev/null || fail "a payload without a prompt was not rejected: $bad"
echo "ok   /invocations without a prompt -> rejected"

for ((i = 0; i < 40; i++)); do
  health="$(docker inspect --format '{{.State.Health.Status}}' "$NAME")"
  [ "$health" = "healthy" ] && break
  sleep 0.5
done
[ "$health" = "healthy" ] || fail "Docker health check is '$health'"
echo "ok   HEALTHCHECK -> healthy"

echo "smoke test passed for $IMAGE"
