"""Obligation rule endpoints, plus per-lease calendar generation."""

import logging
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.deps import AsOfDate, DbSession, PaginationDep, conflict, is_unique_violation
from app.models.enums import ObligationCategory, ObligationStatus, Recurrence
from app.models.lease import Lease
from app.models.obligation import LeaseObligation, Obligation
from app.schemas.common import Page
from app.schemas.obligation import (
    GenerateRequest,
    LeaseObligationRead,
    ObligationCreate,
    ObligationRead,
    ObligationUpdate,
)
from app.services.calendar import default_window, generate_instances
from app.services.obligations import serialize_instance

logger = logging.getLogger(__name__)

router = APIRouter(tags=["obligations"])


@router.get("/obligations", response_model=Page[ObligationRead], summary="List obligation rules")
def list_obligations(
    session: DbSession,
    page: PaginationDep,
    q: Annotated[str | None, Query(description="Match code, title or legal reference")] = None,
    category: Annotated[list[ObligationCategory] | None, Query()] = None,
    recurrence: Annotated[list[Recurrence] | None, Query()] = None,
    jurisdiction: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> Page[ObligationRead]:
    stmt = select(Obligation)
    count_stmt = select(func.count()).select_from(Obligation)

    conditions = []
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                Obligation.code.ilike(pattern),
                Obligation.title.ilike(pattern),
                Obligation.legal_reference.ilike(pattern),
            )
        )
    if category:
        conditions.append(Obligation.category.in_(category))
    if recurrence:
        conditions.append(Obligation.recurrence.in_(recurrence))
    if jurisdiction:
        conditions.append(Obligation.jurisdiction.ilike(jurisdiction))
    if is_active is not None:
        conditions.append(Obligation.is_active == is_active)

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = session.scalar(count_stmt) or 0
    items = session.scalars(
        stmt.order_by(Obligation.category.asc(), Obligation.code.asc())
        .limit(page.limit)
        .offset(page.offset)
    ).all()

    return Page[ObligationRead](
        items=[ObligationRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/obligations",
    response_model=ObligationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Define an obligation rule",
)
def create_obligation(payload: ObligationCreate, session: DbSession) -> ObligationRead:
    data = payload.model_dump()
    # Enum lists are stored as their string values so applicability filters can
    # be compared directly against Postgres array columns.
    data["applies_to_lease_types"] = [item.value for item in payload.applies_to_lease_types]
    data["applies_to_mineral_categories"] = [
        item.value for item in payload.applies_to_mineral_categories
    ]

    obligation = Obligation(**data)
    session.add(obligation)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(f"Obligation code '{payload.code}' already exists") from error
        raise
    session.refresh(obligation)
    return ObligationRead.model_validate(obligation)


@router.get("/obligations/{obligation_id}", response_model=ObligationRead, summary="Get a rule")
def get_obligation(obligation_id: uuid.UUID, session: DbSession) -> ObligationRead:
    obligation = session.get(Obligation, obligation_id)
    if obligation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Obligation not found")
    return ObligationRead.model_validate(obligation)


@router.patch(
    "/obligations/{obligation_id}", response_model=ObligationRead, summary="Update a rule"
)
def update_obligation(
    obligation_id: uuid.UUID, payload: ObligationUpdate, session: DbSession
) -> ObligationRead:
    obligation = session.get(Obligation, obligation_id)
    if obligation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Obligation not found")

    sent = payload.model_dump(exclude_unset=True)
    for field in ("applies_to_lease_types", "applies_to_mineral_categories"):
        if field in sent and sent[field] is not None:
            sent[field] = [item.value if hasattr(item, "value") else item for item in sent[field]]

    for field, value in sent.items():
        setattr(obligation, field, value)

    session.commit()
    session.refresh(obligation)
    return ObligationRead.model_validate(obligation)


@router.get(
    "/leases/{lease_id}/obligations",
    response_model=Page[LeaseObligationRead],
    summary="Calendar entries for one lease",
)
def lease_obligations(
    lease_id: uuid.UUID,
    session: DbSession,
    page: PaginationDep,
    as_of: AsOfDate,
    date_from: Annotated[date | None, Query(description="Due on or after")] = None,
    date_to: Annotated[date | None, Query(description="Due on or before")] = None,
    obligation_status: Annotated[list[ObligationStatus] | None, Query(alias="status")] = None,
) -> Page[LeaseObligationRead]:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    stmt = (
        select(LeaseObligation)
        .where(LeaseObligation.lease_id == lease_id)
        .options(joinedload(LeaseObligation.obligation), joinedload(LeaseObligation.lease))
    )
    count_stmt = (
        select(func.count())
        .select_from(LeaseObligation)
        .where(LeaseObligation.lease_id == lease_id)
    )

    if date_from is not None:
        stmt = stmt.where(LeaseObligation.due_date >= date_from)
        count_stmt = count_stmt.where(LeaseObligation.due_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(LeaseObligation.due_date <= date_to)
        count_stmt = count_stmt.where(LeaseObligation.due_date <= date_to)
    if obligation_status:
        stmt = stmt.where(LeaseObligation.status.in_(obligation_status))
        count_stmt = count_stmt.where(LeaseObligation.status.in_(obligation_status))

    total = session.scalar(count_stmt) or 0
    rows = (
        session.scalars(
            stmt.order_by(LeaseObligation.due_date.asc()).limit(page.limit).offset(page.offset)
        )
        .unique()
        .all()
    )

    return Page[LeaseObligationRead](
        items=[LeaseObligationRead.model_validate(serialize_instance(row, as_of)) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/leases/{lease_id}/obligations/generate",
    response_model=list[LeaseObligationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Materialise calendar entries for a lease",
)
def generate_lease_obligations(
    lease_id: uuid.UUID,
    payload: GenerateRequest,
    session: DbSession,
    as_of: AsOfDate,
) -> list[LeaseObligationRead]:
    """Populate a lease's calendar from the active obligation rules.

    Safe to call repeatedly: generation only ever adds entries that do not yet
    exist, and never disturbs recorded submissions.
    """
    lease = (
        session.scalars(
            select(Lease).where(Lease.id == lease_id).options(joinedload(Lease.mineral))
        )
        .unique()
        .one_or_none()
    )
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    window_start, window_end = default_window(as_of)
    if payload.window_start is not None:
        window_start = payload.window_start
    if payload.window_end is not None:
        window_end = payload.window_end
    if window_end < window_start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "window_end must not precede window_start"
        )

    templates = session.scalars(select(Obligation).where(Obligation.is_active.is_(True))).all()

    created = generate_instances(session, lease, list(templates), window_start, window_end)
    session.commit()

    rows = (
        session.scalars(
            select(LeaseObligation)
            .where(LeaseObligation.lease_id == lease_id)
            .options(joinedload(LeaseObligation.obligation), joinedload(LeaseObligation.lease))
            .order_by(LeaseObligation.due_date.asc())
        )
        .unique()
        .all()
    )

    if created:
        logger.info("Generated %s calendar entries for lease %s", created, lease.lease_number)

    return [LeaseObligationRead.model_validate(serialize_instance(row, as_of)) for row in rows]
