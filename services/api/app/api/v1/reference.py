"""Reference data endpoints: minerals and lease holders."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, PaginationDep, conflict, is_unique_violation
from app.models.enums import HolderEntityType, MineralCategory
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.mineral import Mineral
from app.schemas.common import Page
from app.schemas.reference import (
    HolderCreate,
    HolderRead,
    HolderUpdate,
    MineralCreate,
    MineralRead,
    MineralUpdate,
)
from app.services.reference import apply_partial_update

router = APIRouter(tags=["reference"])


# --------------------------------------------------------------------------
# Minerals
# --------------------------------------------------------------------------
@router.get("/minerals", response_model=Page[MineralRead], summary="List minerals")
def list_minerals(
    session: DbSession,
    page: PaginationDep,
    q: Annotated[str | None, Query(description="Match code or name")] = None,
    category: Annotated[MineralCategory | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> Page[MineralRead]:
    stmt = select(Mineral)
    count_stmt = select(func.count()).select_from(Mineral)

    conditions = []
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(or_(Mineral.code.ilike(pattern), Mineral.name.ilike(pattern)))
    if category is not None:
        conditions.append(Mineral.category == category)
    if is_active is not None:
        conditions.append(Mineral.is_active == is_active)

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = session.scalar(count_stmt) or 0
    items = session.scalars(
        stmt.order_by(Mineral.name.asc()).limit(page.limit).offset(page.offset)
    ).all()

    return Page[MineralRead](
        items=[MineralRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/minerals",
    response_model=MineralRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a mineral",
)
def create_mineral(payload: MineralCreate, session: DbSession) -> MineralRead:
    mineral = Mineral(**payload.model_dump())
    session.add(mineral)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(f"Mineral code '{payload.code}' already exists") from error
        raise
    session.refresh(mineral)
    return MineralRead.model_validate(mineral)


@router.get("/minerals/{mineral_id}", response_model=MineralRead, summary="Get a mineral")
def get_mineral(mineral_id: uuid.UUID, session: DbSession) -> MineralRead:
    mineral = session.get(Mineral, mineral_id)
    if mineral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mineral not found")
    return MineralRead.model_validate(mineral)


@router.patch("/minerals/{mineral_id}", response_model=MineralRead, summary="Update a mineral")
def update_mineral(
    mineral_id: uuid.UUID, payload: MineralUpdate, session: DbSession
) -> MineralRead:
    mineral = session.get(Mineral, mineral_id)
    if mineral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mineral not found")

    apply_partial_update(mineral, payload)
    session.commit()
    session.refresh(mineral)
    return MineralRead.model_validate(mineral)


# --------------------------------------------------------------------------
# Lease holders
# --------------------------------------------------------------------------
@router.get("/holders", response_model=Page[HolderRead], summary="List lease holders")
def list_holders(
    session: DbSession,
    page: PaginationDep,
    q: Annotated[str | None, Query(description="Match name, registration or tax id")] = None,
    entity_type: Annotated[HolderEntityType | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
) -> Page[HolderRead]:
    stmt = select(LeaseHolder)
    count_stmt = select(func.count()).select_from(LeaseHolder)

    conditions = []
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                LeaseHolder.name.ilike(pattern),
                LeaseHolder.registration_number.ilike(pattern),
                LeaseHolder.tax_identifier.ilike(pattern),
            )
        )
    if entity_type is not None:
        conditions.append(LeaseHolder.entity_type == entity_type)
    if state:
        conditions.append(LeaseHolder.state.ilike(state))

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = session.scalar(count_stmt) or 0
    items = session.scalars(
        stmt.order_by(LeaseHolder.name.asc()).limit(page.limit).offset(page.offset)
    ).all()

    return Page[HolderRead](
        items=[HolderRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/holders",
    response_model=HolderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a lease holder",
)
def create_holder(payload: HolderCreate, session: DbSession) -> HolderRead:
    holder = LeaseHolder(**payload.model_dump())
    session.add(holder)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(
                f"Registration number '{payload.registration_number}' already exists"
            ) from error
        raise
    session.refresh(holder)
    return HolderRead.model_validate(holder)


@router.get("/holders/{holder_id}", response_model=HolderRead, summary="Get a lease holder")
def get_holder(holder_id: uuid.UUID, session: DbSession) -> HolderRead:
    holder = session.get(LeaseHolder, holder_id)
    if holder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease holder not found")
    return HolderRead.model_validate(holder)


@router.patch("/holders/{holder_id}", response_model=HolderRead, summary="Update a lease holder")
def update_holder(holder_id: uuid.UUID, payload: HolderUpdate, session: DbSession) -> HolderRead:
    holder = session.get(LeaseHolder, holder_id)
    if holder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease holder not found")

    apply_partial_update(holder, payload)
    session.commit()
    session.refresh(holder)
    return HolderRead.model_validate(holder)


@router.delete(
    "/holders/{holder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lease holder",
)
def delete_holder(holder_id: uuid.UUID, session: DbSession) -> None:
    holder = session.get(LeaseHolder, holder_id)
    if holder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease holder not found")

    # Refuse rather than orphan: a holder with concessions must be reassigned.
    lease_count = session.scalar(
        select(func.count()).select_from(Lease).where(Lease.holder_id == holder_id)
    )
    if lease_count:
        raise conflict(f"Holder is referenced by {lease_count} lease(s); reassign them first")

    session.delete(holder)
    session.commit()
