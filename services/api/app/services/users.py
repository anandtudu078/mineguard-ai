"""Turning a verified Supabase identity into an application profile.

Supabase owns authentication; this module owns authorisation. A token proves who
someone is, and then one of three things happens:

* A profile exists - use it.
* No profile exists **and there are no profiles at all** - this is the very first
  administrator, so bootstrap one. A fresh deployment would otherwise be
  impossible to administer, since creating the first user requires being an admin.
* No profile exists but others do - refuse. A new colleague appearing in Supabase
  is not by itself a grant of access; somebody has to assign a role.

The third case is the one that matters. Auto-provisioning every unknown signup as
a viewer would mean anyone who can reach the Supabase signup form ends up inside
the compliance register.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import Principal, TokenClaims
from app.models.enums import AppRole
from app.models.user import AppUser

logger = logging.getLogger(__name__)

#: Rewriting ``last_seen_at`` on every request would make an idle page a write
#: amplifier. This keeps it useful for "is this account still in use" without
#: turning every read into an UPDATE.
_LAST_SEEN_REFRESH = timedelta(minutes=15)


class IdentityError(Exception):
    """A verified identity that this application will not accept."""

    status_code = 403

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class UnprovisionedIdentityError(IdentityError):
    """Authenticated by Supabase, but no role has been assigned here."""


class InactiveIdentityError(IdentityError):
    """The account has been disabled in this application."""


class LastAdminError(Exception):
    """An edit that would leave the system with no active administrator."""


def bootstrap_role() -> AppRole:
    """The role handed to the first user, validated against the enum."""
    try:
        return AppRole(settings.bootstrap_role)
    except ValueError:
        logger.warning(
            "BOOTSTRAP_ROLE=%r is not a known role; falling back to 'admin'",
            settings.bootstrap_role,
        )
        return AppRole.ADMIN


def _profile_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(AppUser)) or 0


def _bootstrap(session: Session, claims: TokenClaims, user_id: uuid.UUID) -> AppUser:
    """Create the first administrator.

    Two simultaneous first logins would race here. The loser gets a primary-key
    violation, which is the desired outcome - it simply re-reads the row the
    winner created rather than failing the request.
    """
    user = AppUser(
        id=user_id,
        email=claims.email,
        full_name=claims.display_name,
        role=bootstrap_role(),
        notes="Bootstrapped automatically as the first user to sign in.",
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(AppUser, user_id)
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing
    session.refresh(user)
    logger.info("Bootstrapped first user %s with role %s", user.email or user.id, user.role)
    return user


def _touch(session: Session, user: AppUser, claims: TokenClaims) -> None:
    """Refresh the mirrored profile details and last-seen stamp."""
    changed = False

    if claims.email and user.email != claims.email:
        user.email = claims.email
        changed = True
    name = claims.display_name
    if name and user.full_name != name:
        user.full_name = name
        changed = True

    now = datetime.now(UTC)
    last_seen = user.last_seen_at
    if last_seen is None or now - last_seen > _LAST_SEEN_REFRESH:
        user.last_seen_at = now
        changed = True

    if changed:
        session.commit()


def resolve_principal(session: Session, claims: TokenClaims) -> Principal:
    """Map verified token claims onto a ``Principal``.

    Raises ``IdentityError`` rather than returning an anonymous principal, so a
    caller cannot accidentally proceed without a role.
    """
    try:
        user_id = uuid.UUID(claims.subject)
    except ValueError as error:
        raise IdentityError("Token subject is not a valid user id", status_code=401) from error

    user = session.get(AppUser, user_id)

    if user is None:
        if _profile_count(session) == 0:
            user = _bootstrap(session, claims, user_id)
        else:
            raise UnprovisionedIdentityError(
                "Your account is not set up in this system yet. "
                "Ask an administrator to assign you a role."
            )

    if not user.is_active:
        raise InactiveIdentityError("This account has been disabled.")

    _touch(session, user, claims)

    return Principal(
        user_id=str(user.id),
        email=user.email or claims.email,
        role=user.role,
        holder_id=user.holder_id,
        label=user.full_name or user.email or str(user.id),
        is_authenticated=True,
        auth_method="supabase",
    )


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------
def list_users(
    session: Session, *, role: AppRole | None = None, is_active: bool | None = None
) -> list[AppUser]:
    stmt = select(AppUser).order_by(AppUser.created_at.asc())
    if role is not None:
        stmt = stmt.where(AppUser.role == role)
    if is_active is not None:
        stmt = stmt.where(AppUser.is_active.is_(is_active))
    return list(session.scalars(stmt).all())


def assert_admin_survives(session: Session, user: AppUser, new_role: AppRole, new_active: bool) -> None:
    """Refuse an edit that removes the last active administrator.

    Losing every administrator is unrecoverable through the application: nobody
    would be left with ``user:manage`` to grant it back. Cheap to check, and the
    alternative is a support incident.
    """
    if user.role is not AppRole.ADMIN or not user.is_active:
        return
    if new_role is AppRole.ADMIN and new_active:
        return

    remaining = session.scalar(
        select(func.count())
        .select_from(AppUser)
        .where(
            AppUser.role == AppRole.ADMIN,
            AppUser.is_active.is_(True),
            AppUser.id != user.id,
        )
    )
    if not remaining:
        raise LastAdminError(
            "This is the last active administrator. Promote or activate another "
            "administrator first, otherwise nobody could manage users."
        )


def validate_operator_scope(role: AppRole, holder_id: uuid.UUID | None) -> None:
    """An operator without an organisation could reach nothing.

    Refused at the point of assignment so the mistake surfaces while somebody is
    looking at the problem list, not as an inexplicably empty register later.
    """
    if role is AppRole.OPERATOR and holder_id is None:
        raise ValueError(
            "An operator must be linked to a lease holder; their access is scoped "
            "to that organisation's leases."
        )
