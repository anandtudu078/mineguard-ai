"""Reminder delivery history for compliance work."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.obligation import LeaseObligation


class ReminderDelivery(UUIDMixin, TimestampMixin, Base):
    """One attempted reminder delivery for a calendared obligation."""

    __tablename__ = "reminder_deliveries"

    obligation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lease_obligations.id", ondelete="CASCADE"), index=True
    )
    recipient_email: Mapped[str | None] = mapped_column(String(320), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="resend", server_default="resend")
    status: Mapped[str] = mapped_column(String(32), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    obligation: Mapped[LeaseObligation] = relationship()
