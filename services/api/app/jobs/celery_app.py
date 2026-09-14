"""Celery application and daily schedules."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "mineguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "send-daily-compliance-reminders": {
            "task": "app.jobs.reminders.send_daily_reminders",
            "schedule": 60 * 60 * 24,
        }
    },
)

# Register task modules when the worker starts.
celery_app.autodiscover_tasks(["app.jobs"])
import app.jobs.reminders  # noqa: E402, F401
