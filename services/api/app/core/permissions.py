"""The role/permission matrix.

A single table, so "who can do this" is answerable by reading one file rather
than by grepping routers for role checks.

Two of these rules are judgement calls about the *domain*, not just about access
control, and are worth stating plainly:

* **An operator may not waive its own obligation.** Filing is the regulated
  party's job; deciding a filing is not required is the regulator's. If the
  operator could excuse itself, the compliance calendar would record whatever the
  operator found convenient and the whole register would stop meaning anything.
* **An operator may not read the audit trail.** It spans every organisation in
  the portfolio, so it leaks competitors' filing behaviour. It is a regulator's
  view, and operators are given a per-lease view of their own records instead.

Everything else follows the shape of the three roles: admin owns the rulebook and
the user list, inspector works the whole portfolio, operator works its own leases.
"""

from __future__ import annotations

from enum import StrEnum

from app.models.enums import AppRole


class Permission(StrEnum):
    """A capability, named ``<area>:<verb>``."""

    LEASE_READ = "lease:read"
    LEASE_WRITE = "lease:write"
    LICENCE_WRITE = "licence:write"
    CALENDAR_SUBMIT = "calendar:submit"
    CALENDAR_WAIVE = "calendar:waive"
    CALENDAR_REFRESH = "calendar:refresh"
    #: Minerals, holders and obligation rules - collectively "the rulebook".
    REFERENCE_WRITE = "reference:write"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"


#: Portfolio-wide capabilities, before any per-organisation narrowing.
#:
#: ``LEASE_WRITE``, ``LICENCE_WRITE`` and ``CALENDAR_SUBMIT`` grant the *kind* of
#: action; for an operator the row itself is additionally narrowed to leases their
#: holder owns. That narrowing is applied by ``app.services.authorization``, since
#: it needs the database and this table deliberately does not.
ROLE_PERMISSIONS: dict[AppRole, frozenset[Permission]] = {
    AppRole.ADMIN: frozenset(Permission),
    AppRole.INSPECTOR: frozenset(
        {
            Permission.LEASE_READ,
            Permission.LEASE_WRITE,
            Permission.LICENCE_WRITE,
            Permission.CALENDAR_SUBMIT,
            # The regulatory judgement, which is exactly what distinguishes an
            # inspector from an operator.
            Permission.CALENDAR_WAIVE,
            Permission.CALENDAR_REFRESH,
            Permission.AUDIT_READ,
        }
    ),
    AppRole.OPERATOR: frozenset(
        {
            Permission.LEASE_READ,
            Permission.LEASE_WRITE,
            Permission.LICENCE_WRITE,
            Permission.CALENDAR_SUBMIT,
        }
    ),
}


def permissions_for(role: AppRole | None) -> frozenset[Permission]:
    """Every capability a role holds, ignoring per-row scoping.

    A ``None`` role - an authenticated user with no profile - holds nothing.
    """
    if role is None:
        return frozenset()
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has(role: AppRole | None, permission: Permission) -> bool:
    """Whether a role holds a capability at all."""
    return permission in permissions_for(role)
