"""The lease: the aggregate root of the compliance domain.

Every other record in the platform - clearances, obligations, filings, inspections
and violations - hangs off a lease. Removing a lease cascades to its dependants.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import LeaseStatus, LeaseType, RoyaltyBasis

if TYPE_CHECKING:
    from app.models.document import LeaseDocument
    from app.models.finding import InspectionFinding
    from app.models.holder import LeaseHolder
    from app.models.licence import Licence
    from app.models.mineral import Mineral
    from app.models.obligation import LeaseObligation


class Lease(UUIDMixin, TimestampMixin, Base):
    """A mineral concession granted over a defined area for a defined term."""

    __tablename__ = "leases"

    # --- Identity ---
    #: Official instrument number, e.g. "ML/KA/2019/0042".
    lease_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    lease_type: Mapped[LeaseType] = mapped_column(
        enum_column(LeaseType),
        default=LeaseType.MINING_LEASE,
        server_default=text("'mining_lease'"),
        index=True,
    )
    status: Mapped[LeaseStatus] = mapped_column(
        enum_column(LeaseStatus),
        default=LeaseStatus.PENDING,
        server_default=text("'pending'"),
        index=True,
    )

    # --- Parties and subject matter ---
    holder_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lease_holders.id", ondelete="RESTRICT"), index=True
    )
    mineral_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("minerals.id", ondelete="RESTRICT"), index=True
    )

    # --- Location ---
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    village: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str] = mapped_column(
        String(80), default="India", server_default=text("'India'")
    )

    #: Surveyed lease boundary in WGS84. Enables area, overlap and proximity checks.
    boundary: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=True,
    )
    #: Point used to place the site on a map when no boundary has been surveyed.
    centroid: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )

    # --- Term ---
    grant_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, index=True)

    # --- Royalty (overrides the mineral default when set) ---
    royalty_basis: Mapped[RoyaltyBasis | None] = mapped_column(enum_column(RoyaltyBasis))
    royalty_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    royalty_unit: Mapped[str | None] = mapped_column(String(48))

    #: Most recent self-reported annual production, in tonnes.
    annual_production_tonnes: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))

    notes: Mapped[str | None] = mapped_column(Text)

    # --- Relationships ---
    holder: Mapped[LeaseHolder] = relationship(back_populates="leases", lazy="joined")
    mineral: Mapped[Mineral] = relationship(back_populates="leases", lazy="joined")
    licences: Mapped[list[Licence]] = relationship(
        back_populates="lease",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Licence.valid_to",
    )
    obligation_instances: Mapped[list[LeaseObligation]] = relationship(
        back_populates="lease",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list[LeaseDocument]] = relationship(
        back_populates="lease",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LeaseDocument.created_at.desc()",
    )
    findings: Mapped[list[InspectionFinding]] = relationship(
        back_populates="lease",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InspectionFinding.detected_at.desc()",
    )

    __table_args__ = (
        # Supports "leases expiring within N days" dashboards and renewal queues.
        Index("ix_leases_effective_to_status", "effective_to", "status"),
    )

    @property
    def is_within_term(self) -> bool:
        """Whether today falls inside the granted term."""
        today = date.today()
        if today < self.effective_from:
            return False
        return self.effective_to is None or today <= self.effective_to

    def effective_royalty(self, mineral: Mineral) -> tuple[RoyaltyBasis, Decimal, str | None]:
        """Resolve the royalty treatment, preferring the lease-level override."""
        if self.royalty_basis is not None and self.royalty_rate is not None:
            return self.royalty_basis, self.royalty_rate, self.royalty_unit
        return mineral.royalty_basis, mineral.royalty_rate, mineral.royalty_unit

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Lease {self.lease_number} {self.name}>"


def lease_summary_columns() -> list[Any]:
    """Columns needed by list views, kept in one place for query consistency."""
    return [
        Lease.id,
        Lease.lease_number,
        Lease.name,
        Lease.lease_type,
        Lease.status,
        Lease.district,
        Lease.state,
        Lease.area_hectares,
        Lease.effective_from,
        Lease.effective_to,
        func.ST_Y(Lease.centroid).label("centroid_lat"),
        func.ST_X(Lease.centroid).label("centroid_lon"),
    ]
