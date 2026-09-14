"""Writing and reading the audit trail.

Two rules shape everything here:

1. **A successful change and its audit entry share one transaction.** The entry
   is added to the caller's session and committed with the mutation, so it is
   impossible to have a change recorded without its trail, or a trail entry for a
   change that rolled back.
2. **A denial is committed on its own.** A refused request leaves no mutation to
   be part of, so the entry is written and committed immediately - otherwise the
   rollback that follows the 403 would erase the evidence of the attempt.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.audit import AuditLog
from app.models.enums import AuditAction, AuditEntity, AuditOutcome


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Request metadata captured alongside a change.

    Gathered by a dependency rather than passed around by each router, so adding
    the trail to a new endpoint is one extra argument, not four.
    """

    method: str
    path: str
    ip_address: str | None = None
    user_agent: str | None = None


def build_entry(
    principal: Principal,
    context: AuditContext | None,
    *,
    action: AuditAction,
    entity_type: AuditEntity,
    summary: str,
    entity_id: uuid.UUID | str | None = None,
    entity_label: str | None = None,
    outcome: AuditOutcome = AuditOutcome.SUCCEEDED,
    changed_fields: Sequence[str] | None = None,
    context_extra: dict[str, Any] | None = None,
    http_status: int | None = None,
) -> AuditLog:
    """Build an entry without adding it to a session."""
    return AuditLog(
        actor_id=principal.user_id,
        actor_email=principal.email,
        actor_label=principal.label or None,
        actor_role=principal.role.value if principal.role else None,
        auth_method=principal.auth_method,
        action=action,
        outcome=outcome,
        summary=summary,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_label=entity_label[:240] if entity_label else None,
        changed_fields=[field[:64] for field in (changed_fields or ())],
        context=context_extra,
        http_method=context.method if context else None,
        http_path=context.path[:400] if context else None,
        http_status=http_status,
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent[:400] if context and context.user_agent else None,
    )


def record(
    session: Session,
    principal: Principal,
    context: AuditContext | None,
    *,
    action: AuditAction,
    entity_type: AuditEntity,
    summary: str,
    entity_id: uuid.UUID | str | None = None,
    entity_label: str | None = None,
    changed_fields: Sequence[str] | None = None,
    context_extra: dict[str, Any] | None = None,
) -> AuditLog:
    """Queue an entry in the caller's transaction.

    Does not commit. The caller commits once, covering both the mutation and this
    entry, which is what makes the two atomic.
    """
    entry = build_entry(
        principal,
        context,
        action=action,
        entity_type=entity_type,
        summary=summary,
        entity_id=entity_id,
        entity_label=entity_label,
        changed_fields=changed_fields,
        context_extra=context_extra,
    )
    session.add(entry)
    return entry


def record_denied(
    session: Session,
    principal: Principal,
    context: AuditContext | None,
    *,
    action: AuditAction,
    entity_type: AuditEntity,
    summary: str,
    entity_id: uuid.UUID | str | None = None,
    entity_label: str | None = None,
    context_extra: dict[str, Any] | None = None,
    http_status: int = 403,
) -> AuditLog:
    """Record and *immediately commit* a refused request.

    Committing here is the point: the handler is about to raise, which rolls the
    session back, and an uncommitted entry would vanish with it.
    """
    entry = build_entry(
        principal,
        context,
        action=action,
        entity_type=entity_type,
        summary=summary,
        entity_id=entity_id,
        entity_label=entity_label,
        outcome=AuditOutcome.DENIED,
        context_extra=context_extra,
        http_status=http_status,
    )
    session.add(entry)
    session.commit()
    return entry


def list_entries(
    session: Session,
    *,
    entity_type: AuditEntity | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    action: AuditAction | None = None,
    outcome: AuditOutcome | None = None,
    occurred_from: datetime | date | None = None,
    occurred_to: datetime | date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Return one page of the trail, newest first."""
    conditions = []
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        conditions.append(AuditLog.actor_id == actor_id)
    if action is not None:
        conditions.append(AuditLog.action == action)
    if outcome is not None:
        conditions.append(AuditLog.outcome == outcome)
    if occurred_from is not None:
        conditions.append(AuditLog.occurred_at >= occurred_from)
    if occurred_to is not None:
        conditions.append(AuditLog.occurred_at <= occurred_to)

    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = session.scalar(count_stmt) or 0
    rows = list(
        session.scalars(
            stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def summarise(session: Session) -> dict[str, int]:
    """Counts by outcome, for the audit page header."""
    rows = session.execute(
        select(AuditLog.outcome, func.count()).group_by(AuditLog.outcome)
    ).all()
    counts = {outcome.value: 0 for outcome in AuditOutcome}
    for outcome, count in rows:
        counts[outcome.value] = count
    counts["total"] = sum(counts[outcome.value] for outcome in AuditOutcome)
    return counts
