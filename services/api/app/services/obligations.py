"""Serialisation for calendared obligation instances.

The calendar is read far more often than anything else, so instances are
flattened with their rule and lease context attached. That turns a month view
into one request instead of one per row.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import LeaseType, ObligationCategory, ObligationStatus
from app.models.lease import Lease
from app.models.obligation import LeaseObligation, Obligation


def base_instance_select() -> Select:
    """Select instances with the joins every calendar view needs loaded."""
    return select(LeaseObligation).options(
        joinedload(LeaseObligation.obligation),
        joinedload(LeaseObligation.lease),
    )


def serialize_instance(instance: LeaseObligation, as_of: date) -> dict[str, Any]:
    """Flatten an instance plus its rule and lease context."""
    rule: Obligation | None = instance.obligation
    lease: Lease | None = instance.lease

    return {
        "id": instance.id,
        "lease_id": instance.lease_id,
        "obligation_id": instance.obligation_id,
        "period_start": instance.period_start,
        "period_end": instance.period_end,
        "due_date": instance.due_date,
        "status": instance.status,
        "submitted_at": instance.submitted_at,
        "submitted_by": instance.submitted_by,
        "evidence_path": instance.evidence_path,
        "notes": instance.notes,
        "waiver_reason": instance.waiver_reason,
        "code": rule.code if rule else None,
        "title": rule.title if rule else None,
        "category": rule.category if rule else None,
        "legal_reference": rule.legal_reference if rule else None,
        "requires_payment": rule.requires_payment if rule else None,
        "penalty_note": rule.penalty_note if rule else None,
        "lease_number": lease.lease_number if lease else None,
        "lease_name": lease.name if lease else None,
        "holder_email": lease.holder.email if lease and lease.holder else None,
        "district": lease.district if lease else None,
        "state": lease.state if lease else None,
        "days_until_due": instance.days_to_due(as_of),
    }


def list_instances(
    session: Session,
    *,
    as_of: date,
    lease_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    obligation_status: list[ObligationStatus] | None = None,
    category: list[ObligationCategory] | None = None,
    lease_type: list[LeaseType] | None = None,
    state: str | None = None,
    district: str | None = None,
    overdue_only: bool = False,
    requires_payment: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return one page of calendared instances with context."""
    conditions = []

    if lease_id is not None:
        conditions.append(LeaseObligation.lease_id == lease_id)
    if date_from is not None:
        conditions.append(LeaseObligation.due_date >= date_from)
    if date_to is not None:
        conditions.append(LeaseObligation.due_date <= date_to)
    if obligation_status:
        conditions.append(LeaseObligation.status.in_(obligation_status))
    if overdue_only:
        conditions.append(LeaseObligation.status == ObligationStatus.OVERDUE)

    # Joins are added only when a filter actually needs the joined table, so the
    # common "this month's filings" query stays a single-table scan.
    joins: list = []
    if category or requires_payment is not None:
        joins.append((Obligation, Obligation.id == LeaseObligation.obligation_id))
        if category:
            conditions.append(Obligation.category.in_(category))
        if requires_payment is not None:
            conditions.append(Obligation.requires_payment == requires_payment)

    if lease_type or state or district:
        joins.append((Lease, Lease.id == LeaseObligation.lease_id))
        if lease_type:
            conditions.append(Lease.lease_type.in_(lease_type))
        if state:
            conditions.append(Lease.state.ilike(state))
        if district:
            conditions.append(Lease.district.ilike(district))

    stmt = base_instance_select()
    count_stmt = select(func.count()).select_from(LeaseObligation)
    for entity, onclause in joins:
        stmt = stmt.join(entity, onclause)
        count_stmt = count_stmt.join(entity, onclause)

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = session.scalar(count_stmt) or 0

    rows = (
        session.scalars(stmt.order_by(LeaseObligation.due_date.asc()).limit(limit).offset(offset))
        .unique()
        .all()
    )

    return [serialize_instance(row, as_of) for row in rows], total
