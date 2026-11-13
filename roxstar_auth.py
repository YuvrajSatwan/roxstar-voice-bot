"""RoxStar login check for the Simran token server.

In simple words:
  The RoxStar app already logs users in and gives them a signed "access token" (a JWT).
  Before Simran lets anyone into a voice room, we check that token here.
  We only VERIFY it. We never create or change RoxStar tokens.

What the Auth service puts inside the token (see Rox-Auth-K8s/application/helpers/jwt_helper.php):
  - algorithm: HS256, signed with the shared secret JWT_API_KEY
  - "userID": the RoxStar user id        <- note the exact spelling, it is NOT "user_id"
  - "type":   "access" (valid 2 hours)  or "refresh" (valid 365 days!)
  - "exp":    expiry time
There is no username inside the token.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt  # PyJWT

logger = logging.getLogger("sts_roxstar_auth")


class AuthError(Exception):
    """The caller could not be proven to be a real RoxStar user."""


def parse_bearer(header_value: str | None) -> str:
    """Pull the token out of an 'Authorization: Bearer <token>' header."""
    if not header_value:
        raise AuthError("missing_authorization")
    parts = header_value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthError("malformed_authorization")
    return parts[1].strip()


def verify_access_token(token: str, secret: str, *, leeway_seconds: int = 10) -> int:
    """Check a RoxStar access token and return the RoxStar user id.

    Raises AuthError for anything suspicious. The reason is only for our logs;
    the web caller always gets one generic "unauthorized" answer.
    """
    if not secret:
        # Misconfigured server: refuse everyone rather than accept everyone.
        raise AuthError("server_secret_not_configured")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            # Only HS256. Never let the token choose its own algorithm (blocks the "alg: none" trick).
            algorithms=["HS256"],
            # A token with no expiry date must be rejected, not treated as "forever".
            options={"require": ["exp"]},
            leeway=leeway_seconds,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("token_invalid") from exc

    # Refresh tokens live for a year. They must never open a voice session.
    if claims.get("type") != "access":
        raise AuthError("not_an_access_token")

    return _user_id_from_claims(claims)


def _user_id_from_claims(claims: dict[str, Any]) -> int:
    raw = claims.get("userID")
    # bool is a subclass of int in Python; a JSON `true` must not become user 1.
    if isinstance(raw, bool) or raw is None:
        raise AuthError("missing_user_id")
    try:
        user_id = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise AuthError("bad_user_id") from exc
    if user_id <= 0:
        raise AuthError("bad_user_id")
    return user_id


def room_for_user(user_id: int) -> str:
    """The ONE private room this user may enter. Decided by the server, never by the client."""
    return f"sts-simran-{user_id}"


def identity_for_user(user_id: int) -> str:
    """Stable LiveKit identity, so two users with the same display name never collide."""
    return f"rx-{user_id}"
