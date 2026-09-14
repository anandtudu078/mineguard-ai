"""Statutory clearances and approvals attached to a lease."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import LicenceStatus, LicenceType

if TYPE_CHECKING:
    from app.models.lease import Lease


class Licence(UUIDMixin, TimestampMixin, Base):
    """A clearance, consent or approval required to operate the concession.

    A lease is only lawfully operable while every mandatory clearance is current,
    which makes this table the backbone of compliance risk assessment.
    """

    __tablename__ = "licences"

    lease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leases.id", ondelete="CASCADE"), index=True
    )

    licence_type: Mapped[LicenceType] = mapped_column(enum_column(LicenceType), index=True)
    status: Mapped[LicenceStatus] = mapped_column(
        enum_column(LicenceStatus),
        default=LicenceStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
    )

    #: Issuing body, e.g. "MoEFCC", "State Pollution Control Board", "IBM", "DGMS".
    authority: Mapped[str] = mapped_column(String(160), index=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), index=True)

    issued_date: Mapped[date | None] = mapped_column(Date)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, index=True)

    #: Object key in document storage (Supabase Storage). Populated in Feature 2.
    document_path: Mapped[str | None] = mapped_column(String(400))
    notes: Mapped[str | None] = mapped_column(Text)

    #: Whether operating without this clearance is a material breach.
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    lease: Mapped[Lease] = relationship(back_populates="licences")

    __table_args__ = (
        # The same reference number cannot be recorded twice against one lease,
        # which makes document re-ingestion idempotent.
        UniqueConstraint("lease_id", "licence_type", "reference_number"),
        Index("ix_licences_valid_to_status", "valid_to", "status"),
    )

    def is_expired_on(self, on: date) -> bool:
        """Whether the clearance has lapsed as at the given date."""
        return self.valid_to is not None and self.valid_to < on

    def days_to_expiry(self, on: date) -> int | None:
        """Days remaining before lapse; negative once expired.

        Deliberately not named ``days_until_expiry``: that is a field on
        ``LicenceRead``, and because the read schema uses ``from_attributes`` a
        same-named method here would be picked up as the field's value instead
        of the computed number.
        """
        if self.valid_to is None:
            return None
        return (self.valid_to - on).days

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Licence {self.licence_type} ref={self.reference_number}>"
