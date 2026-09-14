"""Build deterministic, provider-neutral compliance reminders."""

from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import ObligationStatus
from app.models.reminder import ReminderDelivery
from app.schemas.reminder import ReminderPreview
from app.services.obligations import list_instances


def preview_reminders(
    session: Session,
    *,
    as_of: date,
    days: int = 30,
    limit: int = 100,
) -> list[ReminderPreview]:
    """Return overdue and upcoming work as ready-to-send reminder messages."""
    overdue_rows, _ = list_instances(
        session,
        as_of=as_of,
        date_to=as_of,
        obligation_status=[ObligationStatus.OVERDUE],
        limit=limit,
    )
    upcoming_rows, _ = list_instances(
        session,
        as_of=as_of,
        date_from=as_of,
        date_to=as_of + timedelta(days=days),
        obligation_status=[ObligationStatus.PENDING, ObligationStatus.IN_PROGRESS],
        limit=limit,
    )

    reminders: list[ReminderPreview] = []
    for row in [*overdue_rows, *upcoming_rows]:
        days_until_due = int(row["days_until_due"] or 0)
        kind = "overdue" if days_until_due < 0 else "upcoming"
        site_name = row["lease_name"] or "your mining site"
        site_number = row["lease_number"] or "unknown site"
        title = row["title"] or row["code"] or "Compliance task"
        if kind == "overdue":
            message = (
                f"Reminder: {title} for {site_name} is {abs(days_until_due)} days overdue. "
                "Please complete it and upload proof."
            )
        else:
            message = (
                f"Reminder: {title} for {site_name} is due on {row['due_date']:%d %b %Y}. "
                "Please plan the work and upload proof when complete."
            )
        reminders.append(
            ReminderPreview(
                obligation_id=row["id"],
                lease_id=row["lease_id"],
                site_name=site_name,
                site_number=site_number,
                title=title,
                due_date=row["due_date"],
                days_until_due=days_until_due,
                kind=kind,
                message=message,
                recipient_email=row.get("holder_email"),
            )
        )

    return reminders


def send_reminders(
    reminders: list[ReminderPreview],
    *,
    settings: Settings,
    dry_run: bool,
    session: Session | None = None,
) -> tuple[int, int, int, list[str]]:
    """Send reminders through Resend, returning sent, skipped, failed and details."""
    if not dry_run and not settings.resend_api_key:
        raise ValueError("RESEND_API_KEY must be configured before sending reminders")
    if not dry_run and not settings.resend_from_email:
        raise ValueError("RESEND_FROM_EMAIL must be configured before sending reminders")

    sent = skipped = failed = 0
    details: list[str] = []
    for reminder in reminders:
        if not reminder.recipient_email:
            skipped += 1
            details.append(f"Skipped {reminder.site_number}: no holder email")
            _record_delivery(session, reminder, "skipped", "No holder email")
            continue
        if dry_run:
            sent += 1
            details.append(f"Prepared reminder for {reminder.recipient_email}")
            _record_delivery(session, reminder, "dry_run")
            continue
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                    "to": [reminder.recipient_email],
                    "subject": f"Compliance reminder: {reminder.title}",
                    "text": reminder.message,
                },
                timeout=20,
            )
            response.raise_for_status()
            provider_id = response.json().get("id")
            sent += 1
            details.append(f"Sent reminder to {reminder.recipient_email}")
            _record_delivery(session, reminder, "sent", provider_message_id=provider_id)
        except Exception as error:
            failed += 1
            details.append(f"Failed {reminder.recipient_email}: {error}")
            _record_delivery(session, reminder, "failed", str(error))
    return sent, skipped, failed, details


def _record_delivery(
    session: Session | None,
    reminder: ReminderPreview,
    status: str,
    error_message: str | None = None,
    provider_message_id: str | None = None,
) -> None:
    if session is None:
        return
    session.add(
        ReminderDelivery(
            obligation_id=reminder.obligation_id,
            recipient_email=reminder.recipient_email,
            provider="resend",
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            sent_at=datetime.now(UTC) if status == "sent" else None,
        )
    )
