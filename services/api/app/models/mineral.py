"""Mineral reference data and statutory royalty defaults."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import MineralCategory, RoyaltyBasis

if TYPE_CHECKING:
    from app.models.lease import Lease


class Mineral(UUIDMixin, TimestampMixin, Base):
    """A mineral species recognised by the governing regime.

    Carries the default royalty treatment. An individual lease may override the
    rate, because royalties are frequently notified per-lease or per-grade.
    """

    __tablename__ = "minerals"

    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[MineralCategory] = mapped_column(enum_column(MineralCategory), index=True)

    royalty_basis: Mapped[RoyaltyBasis] = mapped_column(
        enum_column(RoyaltyBasis), default=RoyaltyBasis.AD_VALOREM
    )
    #: Percentage of sale value (ad valorem) or amount per unit (specific).
    royalty_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default=text("0")
    )
    #: Unit the rate applies to, e.g. "percent_of_sale_value" or "INR_per_tonne".
    royalty_unit: Mapped[str | None] = mapped_column(String(48))

    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    leases: Mapped[list[Lease]] = relationship(back_populates="mineral")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Mineral {self.code} ({self.name})>"
