"""The compliance calendar: cross-lease view of every dated obligation."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import AsOfDate, DbSession, PaginationDep
from app.core.config import Settings, get_settings
from app.models.enums import (
    LeaseType,
    ObligationCategory,
    ObligationStatus,
)
from app.models.obligation import LeaseObligation
from app.models.reminder import ReminderDelivery
from app.schemas.common import Message, Page
from app.schemas.obligation import (
    LeaseObligationRead,
    ObligationStatusUpdate,
    ObligationSubmit,
)
from app.schemas.reminder import (
    ReminderDeliveryRead,
    ReminderPreview,
    ReminderSendRequest,
    ReminderSendResult,
)
from app.services.calendar import default_window, refresh_overdue
from app.services.obligations import list_instances, serialize_instance
from app.services.reminders import preview_reminders, send_reminders

router = APIRouter(prefix="/calendar", tags=["calendar"])

#: Horizon used by the ``due_soon`` calendar view.
_DUE_SOON_DAYS = 30


@router.get("", response_model=Page[LeaseObligationRead], summary="List calendar entries")
def list_calendar(
    session: DbSession,
    page: PaginationDep,
    as_of: AsOfDate,
    lease_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[date | None, Query(description="Due on or after")] = None,
    date_to: Annotated[date | None, Query(description="Due on or before")] = None,
    obligation_status: Annotated[list[ObligationStatus] | None, Query(alias="status")] = None,
    category: Annotated[list[ObligationCategory] | None, Query()] = None,
    lease_type: Annotated[list[LeaseType] | None, Query()] = None,
    entry_state: Annotated[str | None, Query()] = None,
    district: Annotated[str | None, Query()] = None,
    requires_payment: Annotated[bool | None, Query()] = None,
    overdue_only: Annotated[bool, Query(description="Shorthand for status=overdue")] = False,
) -> Page[LeaseObligationRead]:
    """Calendar entries across the portfolio.

    ``entry_state`` is a convenience filter over the common operator questions:
    ``overdue``, ``due_soon`` (next 30 days), ``upcoming`` (open, beyond 30 days)
    and ``filed``.
    """
    open_statuses = [
        ObligationStatus.PENDING,
        ObligationStatus.IN_PROGRESS,
        ObligationStatus.OVERDUE,
    ]
    match entry_state:
        case "overdue":
            overdue_only = True
        case "due_soon":
            # Everything still owed with a deadline in the next 30 days.
            date_from = as_of
            date_to = as_of + timedelta(days=_DUE_SOON_DAYS)
            obligation_status = open_statuses
        case "upcoming":
            date_from = as_of + timedelta(days=_DUE_SOON_DAYS)
            obligation_status = [ObligationStatus.PENDING, ObligationStatus.IN_PROGRESS]
        case "filed":
            obligation_status = [ObligationStatus.SUBMITTED]
        case None:
            pass
        case _:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "entry_state must be one of: overdue, due_soon, upcoming, filed",
            )

    items, total = list_instances(
        session,
        as_of=as_of,
        lease_id=lease_id,
        date_from=date_from,
        date_to=date_to,
        obligation_status=obligation_status,
        category=category,
        lease_type=lease_type,
        district=district,
        overdue_only=overdue_only,
        requires_payment=requires_payment,
        limit=page.limit,
        offset=page.offset,
    )

    return Page[LeaseObligationRead](
        items=[LeaseObligationRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/refresh",
    response_model=Message,
    summary="Recompute overdue status",
)
def refresh_calendar(session: DbSession, as_of: AsOfDate) -> Message:
    """Flip lapsed open obligations to overdue.

    Exposed as an endpoint so it can be called on demand or by the scheduled
    worker, and so tests can drive it deterministically.
    """
    changed = refresh_overdue(session, as_of)
    session.commit()
    return Message(detail=f"{changed} obligation(s) marked overdue")


@router.get(
    "/reminders/preview",
    response_model=list[ReminderPreview],
    summary="Preview reminders for overdue and upcoming work",
)
def reminder_preview(
    session: DbSession,
    as_of: AsOfDate,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ReminderPreview]:
    """Prepare provider-neutral messages for a scheduled email or SMS worker."""
    return preview_reminders(session, as_of=as_of, days=days, limit=limit)


@router.post(
    "/reminders/send",
    response_model=ReminderSendResult,
    summary="Send or preview compliance reminders",
)
def send_reminder_notifications(
    payload: ReminderSendRequest,
    session: DbSession,
    as_of: AsOfDate,
    settings: Settings = Depends(get_settings),
) -> ReminderSendResult:
    reminders = preview_reminders(session, as_of=as_of, days=payload.days, limit=payload.limit)
    try:
        sent, skipped, failed, details = send_reminders(
            reminders, settings=settings, dry_run=payload.dry_run, session=session
        )
        session.commit()
    except ValueError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return ReminderSendResult(
        dry_run=payload.dry_run,
        prepared=len(reminders),
        sent=sent,
        skipped=skipped,
        failed=failed,
        details=details,
    )


@router.get(
    "/reminders/history",
    response_model=list[ReminderDeliveryRead],
    summary="List recent reminder delivery attempts",
)
def reminder_history(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ReminderDeliveryRead]:
    rows = session.scalars(
        select(ReminderDelivery)
        .order_by(ReminderDelivery.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ReminderDeliveryRead(
            id=row.id,
            obligation_id=row.obligation_id,
            recipient_email=row.recipient_email,
            provider=row.provider,
            status=row.status,
            provider_message_id=row.provider_message_id,
            error_message=row.error_message,
            sent_at=row.sent_at.isoformat() if row.sent_at else None,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get(
    "/window",
    response_model=dict,
    summary="Default calendar window bounds",
)
def calendar_window(
    as_of: AsOfDate, fiscal_year_end_month: Annotated[int, Query(ge=1, le=12)] = 3
) -> dict:
    """Report the window the generator would use, so the UI can label it."""
    start, end = default_window(as_of, fiscal_year_end_month)
    return {
        "window_start": start,
        "window_end": end,
        "fiscal_year_end_month": fiscal_year_end_month,
    }


def _load_instance(session, instance_id: uuid.UUID) -> LeaseObligation:
    instance = (
        session.scalars(
            select(LeaseObligation)
            .where(LeaseObligation.id == instance_id)
            .options(joinedload(LeaseObligation.obligation), joinedload(LeaseObligation.lease))
        )
        .unique()
        .one_or_none()
    )
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar entry not found")
    return instance


@router.post(
    "/{instance_id}/submit",
    response_model=LeaseObligationRead,
    summary="Record a filing",
)
def submit_obligation(
    instance_id: uuid.UUID, payload: ObligationSubmit, session: DbSession, as_of: AsOfDate
) -> LeaseObligationRead:
    instance = _load_instance(session, instance_id)

    if instance.status in (ObligationStatus.WAIVED, ObligationStatus.NOT_APPLICABLE):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Entry is {instance.status}; reopen it before recording a filing",
        )

    instance.status = ObligationStatus.SUBMITTED
    instance.submitted_at = payload.submitted_at or datetime.now(UTC)
    if payload.submitted_by is not None:
        instance.submitted_by = payload.submitted_by
    if payload.evidence_path is not None:
        instance.evidence_path = payload.evidence_path
    if payload.notes is not None:
        instance.notes = payload.notes

    session.commit()
    session.refresh(instance)
    return LeaseObligationRead.model_validate(serialize_instance(instance, as_of))


@router.patch(
    "/{instance_id}",
    response_model=LeaseObligationRead,
    summary="Change a calendar entry's status",
)
def update_obligation_status(
    instance_id: uuid.UUID,
    payload: ObligationStatusUpdate,
    session: DbSession,
    as_of: AsOfDate,
) -> LeaseObligationRead:
    instance = _load_instance(session, instance_id)

    instance.status = payload.status
    if payload.notes is not None:
        instance.notes = payload.notes

    if payload.status in (ObligationStatus.WAIVED, ObligationStatus.NOT_APPLICABLE):
        # An exemption without a recorded reason is indefensible in an audit.
        instance.waiver_reason = payload.reason
    elif payload.status != ObligationStatus.SUBMITTED:
        # Reopening clears any previous exemption rationale.
        instance.waiver_reason = None

    if payload.status == ObligationStatus.SUBMITTED and instance.submitted_at is None:
        instance.submitted_at = datetime.now(UTC)

    session.commit()
    session.refresh(instance)
    return LeaseObligationRead.model_validate(serialize_instance(instance, as_of))
