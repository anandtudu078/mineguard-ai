"""Authorisation: the permission matrix plus per-row scoping.

Two layers, because a role alone is not enough:

* Does this role hold this **kind** of capability at all? (``core.permissions``)
* Is this **particular record** one the caller may touch? (here)

Only operators are narrowed at the row level, to the leases their own
organisation holds. Admins and inspectors work the whole portfolio.

Denials are recorded in the audit trail before the error is raised. That is on
purpose: "who tried to waive what, and was refused" is a question a regulator
asking for the trail should be able to answer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import Permission, permissions_for, role_has
from app.core.security import Principal
from app.models.enums import AuditAction, AuditEntity
from app.models.lease import Lease
from app.services import audit
from app.services.audit import AuditContext


@dataclass(frozen=True, slots=True)
class LeaseScope:
    """Which leases a principal may see, as a filter the query services apply.

    ``blocked`` exists so a scoped user with no organisation fails *closed* -
    they see nothing - rather than being handed the whole portfolio because the
    filter had nothing to match on. That is the failure mode worth designing
    against: a misconfigured operator account silently becoming a regulator.
    """

    holder_id: uuid.UUID | None = None
    blocked: bool = False

    @classmethod
    def unrestricted(cls) -> LeaseScope:
        return cls()

    @classmethod
    def for_holder(cls, holder_id: uuid.UUID | None) -> LeaseScope:
        if holder_id is None:
            return cls(blocked=True)
        return cls(holder_id=holder_id)

    @classmethod
    def nothing(cls) -> LeaseScope:
        return cls(blocked=True)

    @property
    def is_narrowed(self) -> bool:
        return self.blocked or self.holder_id is not None


def scope_for(principal: Principal) -> LeaseScope:
    """The read scope implied by a principal's role and organisation."""
    if not principal.is_scoped_to_holder:
        return LeaseScope.unrestricted()
    return LeaseScope.for_holder(principal.holder_id)


def may_reach_lease(principal: Principal, lease: Lease) -> bool:
    """Whether a principal may act on a specific lease."""
    if not principal.is_scoped_to_holder:
        return True
    # An operator with no organisation reaches nothing, rather than everything.
    if principal.holder_id is None:
        return False
    return lease.holder_id == principal.holder_id


class AuthorizationError(Exception):
    """A refused action.

    Deliberately not an ``HTTPException``: the denial must be written to the
    audit trail, which needs a session, and doing that at every raise site would
    be easy to forget. ``main`` maps this to a 403 response.
    """

    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def deny(
    session: Session,
    principal: Principal,
    context: AuditContext | None,
    *,
    entity_type: AuditEntity,
    summary: str,
    entity_id: uuid.UUID | str | None = None,
    entity_label: str | None = None,
    extra: dict[str, object] | None = None,
) -> NoReturn:
    """Record the refusal, then refuse.

    Note the message goes to the caller and the summary to the trail; the trail
    entry can be more specific than the response without leaking that detail.
    """
    audit.record_denied(
        session,
        principal,
        context,
        action=AuditAction.ACCESS_DENIED,
        entity_type=entity_type,
        summary=summary,
        entity_id=entity_id,
        entity_label=entity_label,
        context_extra=extra,
        http_status=status.HTTP_403_FORBIDDEN,
    )
    raise AuthorizationError(
        "Your role does not permit this action. The attempt has been recorded."
    )


def require_permission(
    session: Session,
    principal: Principal,
    context: AuditContext | None,
    permission: Permission,
    *,
    entity_type: AuditEntity,
    entity_id: uuid.UUID | str | None = None,
    entity_label: str | None = None,
) -> None:
    """Refuse unless the principal's role holds a capability."""
    if role_has(principal.role, permission):
        return
    deny(
        session,
        principal,
        context,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        summary=(
            f"Refused {permission} for role {principal.role or 'none'}: "
            f"{principal.display} does not hold this permission."
        ),
        extra={
            "permission": str(permission),
            "role": principal.role.value if principal.role else None,
        },
    )


def assert_lease_access(
    session: Session,
    principal: Principal,
    context: AuditContext | None,
    lease_id: uuid.UUID,
    *,
    action: str,
) -> Lease:
    """Load a lease, refusing if the caller may not reach it.

    A lease that does not exist is a 404 for everyone, which keeps the error the
    same whether or not the caller was allowed to know - but a lease that exists
    and is out of scope is a *403*, not a 404. Concealing existence would only
    hide the refusal from the audit trail, and mineral concessions are a matter
    of public record anyway.
    """
    lease = session.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    if not may_reach_lease(principal, lease):
        deny(
            session,
            principal,
            context,
            entity_type=AuditEntity.LEASE,
            entity_id=lease.id,
            entity_label=lease.lease_number,
            summary=(
                f"Refused {action} on lease {lease.lease_number}: held by another "
                f"organisation than {principal.display}'s."
            ),
            extra={"action": action, "lease_number": lease.lease_number},
        )
    return lease


def permission_summary(principal: Principal) -> list[str]:
    """The capabilities to report to the UI, so it can hide what would 403."""
    return sorted(str(permission) for permission in permissions_for(principal.role))
