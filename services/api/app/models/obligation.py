"""Statutory obligations: the reusable template and its scheduled instances.

The split matters. ``Obligation`` is a *rule* - "MCDR monthly return, due 15 days
after month end, for mining leases". ``LeaseObligation`` is a *dated calendared
event* - "lease X must file its March return by 15 April". Rules are jurisdiction
data; instances are the compliance calendar the operator actually works from.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import ObligationCategory, ObligationStatus, Recurrence

if TYPE_CHECKING:
    from app.models.lease import Lease


class Obligation(UUIDMixin, TimestampMixin, Base):
    """A recurring statutory duty, independent of any particular lease.

    Scheduling is expressed as an offset from the end of a reporting period
    rather than a fixed calendar date. That keeps the rule portable across
    jurisdictions whose fiscal years and filing deadlines differ, and it is
    pure data, so a new regime is a seed change rather than a code change.
    """

    __tablename__ = "obligations"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[ObligationCategory] = mapped_column(
        enum_column(ObligationCategory), index=True
    )
    #: Citation in the governing instrument, e.g. "MMDR Act s.9(2)".
    legal_reference: Mapped[str | None] = mapped_column(String(200))
    #: "central" or a state/region name; used to scope rule packs.
    jurisdiction: Mapped[str | None] = mapped_column(String(120), index=True)

    recurrence: Mapped[Recurrence] = mapped_column(enum_column(Recurrence))
    #: Days after the reporting period ends that the filing becomes due.
    due_days_after_period_end: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    #: Additional days before the item is treated as overdue.
    grace_days: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: Month (1-12) in which the annual reporting year ends. India uses March.
    fiscal_year_end_month: Mapped[int] = mapped_column(Integer, default=3, server_default=text("3"))

    #: Applicability filters. Empty means "applies regardless".
    applies_to_lease_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(48)), default=list, server_default=text("'{}'::varchar[]")
    )
    applies_to_mineral_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(48)), default=list, server_default=text("'{}'::varchar[]")
    )

    #: Whether a monetary payment accompanies this filing (royalty, DMFT, etc.).
    requires_payment: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    #: Consequence text shown when the item is overdue.
    penalty_note: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    instances: Mapped[list[LeaseObligation]] = relationship(back_populates="obligation")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Obligation {self.code}>"


class LeaseObligation(UUIDMixin, TimestampMixin, Base):
    """A single dated obligation owed by one lease."""

    __tablename__ = "lease_obligations"

    lease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leases.id", ondelete="CASCADE"), index=True
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("obligations.id", ondelete="RESTRICT"), index=True
    )

    #: The reporting period this instance covers. Null for one-time obligations.
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date, index=True)

    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[ObligationStatus] = mapped_column(
        enum_column(ObligationStatus),
        default=ObligationStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Free-text actor until Supabase Auth identities are wired in Feature 3.
    submitted_by: Mapped[str | None] = mapped_column(String(200))
    #: Receipt / acknowledgement object key in document storage.
    evidence_path: Mapped[str | None] = mapped_column(String(400))

    notes: Mapped[str | None] = mapped_column(Text)
    waiver_reason: Mapped[str | None] = mapped_column(Text)

    lease: Mapped[Lease] = relationship(back_populates="obligation_instances")
    obligation: Mapped[Obligation] = relationship(back_populates="instances", lazy="joined")

    __table_args__ = (
        # COALESCE keeps one-time obligations (NULL period_start) de-duplicated,
        # which plain UNIQUE would miss because NULLs compare distinct.
        Index(
            "uq_lease_obligations_lease_obligation_period",
            "lease_id",
            "obligation_id",
            text("COALESCE(period_start, DATE '0001-01-01')"),
            unique=True,
        ),
        Index("ix_lease_obligations_due_status", "due_date", "status"),
    )

    def is_open(self) -> bool:
        """Whether the obligation still requires action."""
        return self.status in {
            ObligationStatus.PENDING,
            ObligationStatus.IN_PROGRESS,
            ObligationStatus.OVERDUE,
        }

    def days_to_due(self, on: date) -> int:
        """Days remaining until the due date; negative once past.

        Named to avoid colliding with the ``days_until_due`` field on
        ``LeaseObligationRead``, which is populated from a dict rather than
        from the ORM instance for exactly this reason.
        """
        return (self.due_date - on).days

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LeaseObligation due={self.due_date} status={self.status}>"
