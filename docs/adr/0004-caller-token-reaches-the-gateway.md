# 0004. The caller's token reaches the gateway

## Status

Accepted

## Context

For the policy engine to decide per staff member, the gateway must see who is asking. If the agent called the
gateway with its own identity, every tool call would look like the agent, and the policies could only say what
the agent may do, not what each person may do.

## Decision

Pass the staff member's access token from the runtime to the gateway.

- Store staff sign in to a Cognito user pool (administrator-created accounts only, optional TOTP MFA).
- The runtime's custom JWT authorizer validates the access token (issuer and app client), and the runtime forwards
  the `Authorization` header to the container (`request_header_allowlist = ["Authorization"]`).
- The agent opens its MCP connection to the gateway with that same bearer token. The gateway validates it again
  with its own JWT authorizer, and the policy engine reads the principal and its `cognito:groups` claim from it.
- The agent reads the token's `sub` claim only to key memory (the actor ID). It makes no authorization decision
  from the claims.
- AgentCore creates a workload identity for the runtime (output `workload_identity_arn`); this delivery needs no
  outbound OAuth credentials, so no credential provider is configured.

## Consequences

- Every tool call in the gateway's logs and traces carries the real staff member.
- The token's lifetime bounds a session's authority: access tokens last 60 minutes.
- The agent never holds credentials to the tools; its own IAM role cannot invoke them.

## Compliance

- The terraform test `runtime_is_private_pinned_and_behind_jwt` asserts the authorizer, the allowed client and the
  header allowlist.
- `tests/test_identity_config.py` and `tests/test_app.py` check that a request without a usable bearer token is
  rejected before any model or tool call.

## Notes

The Cognito app client allows `ADMIN_USER_PASSWORD_AUTH` only when `enable_admin_auth_flow` is true, which only the
live test sets, to sign in its throwaway users.
