"""AI-detected and manually reported inspection findings against a lease.

A finding is the unit of the visual-compliance loop: a photo (or an inspector)
produces one, the compliance score weighs it while it is open, escalation chases
it if it lingers, and closing it recovers the score. Everything needed to
reconstruct "what happened after the AI spoke" lives on this row.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import FindingSource, FindingStatus, ViolationSeverity

if TYPE_CHECKING:
    from app.models.lease import Lease


class InspectionFinding(UUIDMixin, TimestampMixin, Base):
    """One detected deviation at a site, from detection through closure."""

    __tablename__ = "inspection_findings"

    lease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leases.id", ondelete="CASCADE"), index=True
    )

    #: Who produced this finding: the vision model, an operator, an inspector.
    source: Mapped[FindingSource] = mapped_column(
        enum_column(FindingSource), default=FindingSource.MANUAL, index=True
    )
    #: Path of the uploaded photo, when the finding came from one.
    image_path: Mapped[str | None] = mapped_column(String(400))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[ViolationSeverity] = mapped_column(
        enum_column(ViolationSeverity), default=ViolationSeverity.MEDIUM, index=True
    )
    status: Mapped[FindingStatus] = mapped_column(
        enum_column(FindingStatus), default=FindingStatus.OPEN, index=True
    )

    # --- Provenance (AI findings) ---
    #: Model confidence, 0..1. Absent for human-reported findings.
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    #: e.g. "gemini-2.0-flash". Absent for human-reported findings.
    ai_model: Mapped[str | None] = mapped_column(String(80))
    #: The model's full structured response, kept so borderline calls are auditable.
    ai_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # --- Alert and escalation ladder ---
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    first_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: How many times this finding has been escalated (0 = not yet).
    escalation_level: Mapped[int] = mapped_column(default=0, server_default="0")
    last_escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Corrective action and closure ---
    corrective_action: Mapped[str | None] = mapped_column(Text)
    action_owner: Mapped[str | None] = mapped_column(String(200))
    action_due_date: Mapped[date | None] = mapped_column(Date)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(320))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    lease: Mapped[Lease] = relationship(back_populates="findings")

    @property
    def is_open(self) -> bool:
        """Whether this finding currently weighs on the compliance score."""
        return self.status in (FindingStatus.OPEN, FindingStatus.IN_PROGRESS)
