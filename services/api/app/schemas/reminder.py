"""Schemas for reminder previews and delivery preparation."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class ReminderPreview(BaseModel):
    obligation_id: uuid.UUID
    lease_id: uuid.UUID
    site_name: str
    site_number: str
    title: str
    due_date: date
    days_until_due: int
    kind: str
    message: str
    recipient_email: str | None = None


class ReminderSendRequest(BaseModel):
    dry_run: bool = True
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=100, ge=1, le=500)


class ReminderSendResult(BaseModel):
    dry_run: bool
    prepared: int
    sent: int
    skipped: int
    failed: int
    details: list[str]


class ReminderDeliveryRead(BaseModel):
    id: uuid.UUID
    obligation_id: uuid.UUID
    recipient_email: str | None
    provider: str
    status: str
    provider_message_id: str | None
    error_message: str | None
    sent_at: str | None
    created_at: str
