"""The calling staff member, taken from the inbound JWT.

AgentCore Runtime validates the token (signature, issuer, client) before the request reaches this container,
because the runtime is configured with a custom JWT authorizer. This module only reads the claims it needs;
it never makes an authorization decision. Authorization happens in the gateway policy engine, which validates
the same token again.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

ACTOR_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$")


class IdentityError(ValueError):
    """The request carries no usable bearer token."""


@dataclass(frozen=True)
class Caller:
    subject: str
    groups: tuple[str, ...]
    token: str

    @property
    def actor_id(self) -> str:
        """Memory actor ID: the token subject, which Cognito issues as a UUID."""
        return self.subject


def _claims(token: str) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) != 3:
        raise IdentityError("bearer token is not a JWT")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError) as err:
        raise IdentityError("bearer token payload is not JSON") from err
    if not isinstance(claims, dict):
        raise IdentityError("bearer token payload is not an object")
    return claims


def caller_from_authorization(header: str | None) -> Caller:
    if not header or not header.lower().startswith("bearer "):
        raise IdentityError("missing bearer token")
    token = header.split(" ", 1)[1].strip()
    claims = _claims(token)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not ACTOR_PATTERN.fullmatch(subject):
        raise IdentityError("token has no usable sub claim")
    raw_groups = claims.get("cognito:groups", [])
    groups = tuple(g for g in raw_groups if isinstance(g, str)) if isinstance(raw_groups, list) else ()
    return Caller(subject=subject, groups=groups, token=token)
