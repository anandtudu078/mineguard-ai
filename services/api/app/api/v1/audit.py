"""The audit trail, read-only.

There is no endpoint to write, amend or delete a trail entry, and the database
refuses UPDATE and DELETE on the table anyway. A trail that the application can
edit is not a trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AuditCtx, CurrentPrincipal, DbSession, PaginationDep
from app.core.permissions import Permission
from app.models.enums import AuditAction, AuditEntity, AuditOutcome
from app.schemas.common import Page
from app.schemas.identity import AuditLogRead, AuditSummary
from app.services import audit
from app.services.authorization import require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead], summary="List audit entries")
def list_audit_entries(
    session: DbSession,
    principal: CurrentPrincipal,
    context: AuditCtx,
    page: PaginationDep,
    entity_type: Annotated[AuditEntity | None, Query(description="Record kind")] = None,
    entity_id: Annotated[str | None, Query(description="Record identifier")] = None,
    actor_id: Annotated[str | None, Query(description="Who acted")] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    outcome: Annotated[AuditOutcome | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query(description="Occurred on or after")] = None,
    occurred_to: Annotated[datetime | None, Query(description="Occurred on or before")] = None,
) -> Page[AuditLogRead]:
    """Every entry is readable by regulators; operators are refused.

    The trail covers the whole portfolio, so exposing it to a leaseholder would
    disclose other organisations' filing behaviour.
    """
    require_permission(
        session,
        principal,
        context,
        Permission.AUDIT_READ,
        entity_type=AuditEntity.USER,
        entity_id=principal.user_id,
        entity_label=principal.display,
    )

    rows, total = audit.list_entries(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=page.limit,
        offset=page.offset,
    )
    return Page[AuditLogRead](
        items=[AuditLogRead.model_validate(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/summary", response_model=AuditSummary, summary="Audit counts by outcome")
def audit_summary(
    session: DbSession, principal: CurrentPrincipal, context: AuditCtx
) -> AuditSummary:
    """Outcome counts, for the header of the audit view."""
    require_permission(
        session,
        principal,
        context,
        Permission.AUDIT_READ,
        entity_type=AuditEntity.USER,
        entity_id=principal.user_id,
        entity_label=principal.display,
    )
    return AuditSummary(**audit.summarise(session))
