"""Endpoints for statutory clearances attached to a lease."""

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AsOfDate, DbSession, conflict, is_unique_violation
from app.models.lease import Lease
from app.models.licence import Licence
from app.schemas.licence import LicenceCreate, LicenceRead, LicenceUpdate
from app.services.reference import apply_partial_update

router = APIRouter(tags=["licences"])


def _to_read(licence: Licence, as_of) -> LicenceRead:
    payload = LicenceRead.model_validate(licence)
    payload.days_until_expiry = licence.days_to_expiry(as_of)
    return payload


@router.post(
    "/leases/{lease_id}/licences",
    response_model=LicenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a clearance against a lease",
)
def create_licence(
    lease_id: uuid.UUID, payload: LicenceCreate, session: DbSession, as_of: AsOfDate
) -> LicenceRead:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    licence = Licence(lease_id=lease_id, **payload.model_dump())
    session.add(licence)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(
                "A clearance of this type with the same reference number is already "
                "recorded for this lease"
            ) from error
        raise
    session.refresh(licence)
    return _to_read(licence, as_of)


@router.get("/licences/{licence_id}", response_model=LicenceRead, summary="Get a clearance")
def get_licence(licence_id: uuid.UUID, session: DbSession, as_of: AsOfDate) -> LicenceRead:
    licence = session.get(Licence, licence_id)
    if licence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Licence not found")
    return _to_read(licence, as_of)


@router.patch("/licences/{licence_id}", response_model=LicenceRead, summary="Update a clearance")
def update_licence(
    licence_id: uuid.UUID, payload: LicenceUpdate, session: DbSession, as_of: AsOfDate
) -> LicenceRead:
    licence = session.get(Licence, licence_id)
    if licence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Licence not found")

    apply_partial_update(licence, payload)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(
                "A clearance of this type with the same reference number is already "
                "recorded for this lease"
            ) from error
        raise
    session.refresh(licence)
    return _to_read(licence, as_of)


@router.delete(
    "/licences/{licence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a clearance",
)
def delete_licence(licence_id: uuid.UUID, session: DbSession) -> None:
    licence = session.get(Licence, licence_id)
    if licence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Licence not found")
    session.delete(licence)
    session.commit()


@router.get(
    "/clearances/expiring",
    response_model=list[LicenceRead],
    summary="Clearances expiring across the portfolio",
)
def expiring_clearances(
    session: DbSession,
    as_of: AsOfDate,
    within_days: Annotated[int, Query(ge=1, le=3650)] = 90,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[LicenceRead]:
    rows = session.scalars(
        select(Licence)
        .where(
            Licence.valid_to.is_not(None),
            Licence.valid_to >= as_of,
            Licence.valid_to <= as_of + timedelta(days=within_days),
        )
        .order_by(Licence.valid_to.asc())
        .limit(limit)
    ).all()
    return [_to_read(row, as_of) for row in rows]
