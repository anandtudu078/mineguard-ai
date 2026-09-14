"""Supabase Auth token verification.

Supabase issues a signed JWT to every signed-in user. The API never talks to
Supabase to validate a request - it verifies the signature locally, which keeps
authentication off the critical path and working when Supabase is unreachable.

Two signing schemes are supported, because Supabase projects differ:

* **HS256**, a shared secret. Older projects. ``SUPABASE_JWT_SECRET``.
* **ES256 / RS256**, asymmetric keys published as JWKS. What new projects
  default to, and the better option: verification needs only the public key, so
  the API never holds a secret capable of *minting* tokens.

Which one is used is decided by the token header's ``alg``, and each scheme has
its own allow-list. ``alg: none`` is never accepted, and a token cannot talk the
API into using a scheme that is not configured - the classic JWT confusion bugs
both come from letting the token choose freely.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.models.enums import AppRole

logger = logging.getLogger(__name__)

#: Accepted when verifying against the shared secret.
_SYMMETRIC_ALGORITHMS = ("HS256", "HS384", "HS512")
#: Accepted when verifying against Supabase's published public keys.
_ASYMMETRIC_ALGORITHMS = ("ES256", "ES384", "RS256", "RS384", "RS512", "PS256")

#: Without a leeway, a token can be rejected for a few seconds of clock drift
#: between Supabase and the API host, which reads to the user as a random logout.
_LEEWAY_SECONDS = 10


class TokenError(Exception):
    """A bearer token was missing, malformed, or not trusted.

    ``expired`` lets the caller answer 401 with a hint to re-authenticate rather
    than a bare failure, which is the difference between a silent bounce to the
    login page and an unexplained error.
    """

    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.expired = expired


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """The parts of a verified Supabase token the application cares about."""

    subject: str
    email: str | None = None
    #: Supabase's own role claim. Always "authenticated" for a signed-in user;
    #: application roles are separate and live in ``app_users``.
    supabase_role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str | None:
        """Best-effort human name, from whichever metadata key is populated."""
        for key in ("full_name", "name", "display_name"):
            value = self.metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


@dataclass(frozen=True, slots=True)
class Principal:
    """The caller, after their token *and* their application profile are known.

    Routers only ever see this, never a raw token, which keeps authorisation in
    one place. It is also what the audit trail attributes a change to.
    """

    #: Supabase ``sub``, or a synthetic id when auth is disabled.
    user_id: str
    email: str | None
    #: ``None`` for a user Supabase has authenticated who has no application
    #: profile yet. Such a principal holds no permissions, which is what makes
    #: an unprovisioned account harmless rather than accidentally powerful.
    role: AppRole | None = None
    #: Organisational scope. Operators are limited to leases held by this
    #: holder; admins and inspectors are not scoped.
    holder_id: uuid.UUID | None = None
    label: str = ""
    is_authenticated: bool = True
    #: "supabase" or "disabled" - recorded on every audit entry.
    auth_method: str = "supabase"

    @property
    def has_profile(self) -> bool:
        """Whether an application role has been assigned."""
        return self.role is not None

    @property
    def is_admin(self) -> bool:
        return self.role is AppRole.ADMIN

    @property
    def is_scoped_to_holder(self) -> bool:
        """Whether this caller may only touch their own organisation's leases."""
        return self.role is AppRole.OPERATOR

    @property
    def display(self) -> str:
        """Readable identity for the audit trail and the UI menu."""
        return self.label or self.email or self.user_id


#: The identity assumed while ``auth_mode`` is "disabled".
#:
#: Deliberately loud and greppable. Every audit entry written in development
#: carries this actor, so it is never mistaken for a real person's change, and
#: the same string makes the disabled state easy to find in a log.
DEV_PRINCIPAL = Principal(
    user_id="dev:anonymous",
    email=None,
    role=AppRole.ADMIN,
    label="Development administrator (authentication disabled)",
    is_authenticated=False,
    auth_method="disabled",
)


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    """Cache one JWKS client per URL.

    ``PyJWKClient`` already caches fetched keys internally; this stops it also
    re-reading them from the network once per request.
    """
    return PyJWKClient(url, cache_keys=True, lifespan=300, timeout=10)


def _decode_unverified_header(token: str) -> dict[str, Any]:
    try:
        return jwt.get_unverified_header(token)
    except jwt.DecodeError as error:
        raise TokenError("Token is not a well-formed JWT") from error


def _decode_options() -> dict[str, Any]:
    return {
        "require": ["exp", "sub"],
        "verify_exp": True,
        "verify_aud": bool(settings.supabase_jwt_audience),
        "verify_iss": bool(settings.resolved_issuers),
    }


def verify_token(token: str) -> TokenClaims:
    """Verify a Supabase access token and return its claims.

    Raises ``TokenError`` for anything untrusted. Never returns partial trust:
    a caller either gets verified claims or an exception.
    """
    if not settings.auth_configured:
        # Reached only if a request arrives with a token while auth_mode is
        # "disabled". Treated as untrusted rather than ignored, so a stale
        # browser session cannot silently downgrade into the dev principal.
        raise TokenError("Authentication is not configured on this server")

    header = _decode_unverified_header(token)
    algorithm = header.get("alg")
    if not isinstance(algorithm, str):
        raise TokenError("Token header is missing an algorithm")

    audience = settings.supabase_jwt_audience or None
    issuer = settings.resolved_issuers

    if algorithm in _SYMMETRIC_ALGORITHMS and settings.supabase_jwt_secret:
        key: Any = settings.supabase_jwt_secret
        algorithms = [algorithm]
    elif algorithm in _ASYMMETRIC_ALGORITHMS and settings.jwks_url:
        # The token's own `kid` selects the key, which is how Supabase rotates
        # signing keys without invalidating outstanding sessions.
        try:
            key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token).key
        except jwt.exceptions.PyJWKClientError as error:
            raise TokenError(f"Could not resolve the token's signing key: {error}") from error
        algorithms = [algorithm]
    else:
        # Either the scheme is not one we accept, or the deployment has no
        # material for it. Both are refusals, not fallbacks.
        raise TokenError(f"Unsupported signing scheme {algorithm!r} for this deployment")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            leeway=_LEEWAY_SECONDS,
            options=_decode_options(),
        )
    except jwt.ExpiredSignatureError as error:
        raise TokenError("Session has expired; sign in again", expired=True) from error
    except jwt.InvalidAudienceError as error:
        raise TokenError("Token was issued for a different audience") from error
    except jwt.InvalidIssuerError as error:
        raise TokenError("Token was issued by an unexpected issuer") from error
    except jwt.InvalidSignatureError as error:
        raise TokenError("Token signature is not valid") from error
    except jwt.InvalidTokenError as error:
        raise TokenError(f"Token rejected: {error}") from error

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenError("Token is missing a subject claim")

    # Supabase splits caller-owned data (user_metadata) from claims the provider
    # controls (app_metadata). Flattening them is safe here because app_metadata
    # wins on collision.
    metadata: dict[str, Any] = {}
    user_metadata = payload.get("user_metadata")
    if isinstance(user_metadata, dict):
        metadata.update(user_metadata)
    app_metadata = payload.get("app_metadata")
    if isinstance(app_metadata, dict):
        metadata.update(app_metadata)

    email = payload.get("email")
    supabase_role = payload.get("role")

    return TokenClaims(
        subject=subject,
        email=email if isinstance(email, str) else None,
        supabase_role=supabase_role if isinstance(supabase_role, str) else None,
        metadata=metadata,
    )
