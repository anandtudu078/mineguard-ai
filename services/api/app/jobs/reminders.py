"""Scheduled compliance reminder jobs."""

from datetime import date

from app.core.config import settings
from app.core.db import SessionLocal
from app.jobs.celery_app import celery_app
from app.services.reminders import preview_reminders, send_reminders


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_daily_reminders(_task) -> dict[str, int | bool]:
    """Prepare and send the daily reminder batch.

    Sending stays disabled unless REMINDER_SEND_ENABLED=true. This makes a
    locally running worker useful for previews without accidentally emailing
    real recipients.
    """
    with SessionLocal() as session:
        reminders = preview_reminders(session, as_of=date.today(), days=30, limit=500)
        sent, skipped, failed, _details = send_reminders(
            reminders,
            settings=settings,
            dry_run=not settings.reminder_send_enabled,
            session=session,
        )
        session.commit()
    return {
        "dry_run": not settings.reminder_send_enabled,
        "prepared": len(reminders),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
    }
