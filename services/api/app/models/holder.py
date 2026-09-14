"""Legal entities that hold mineral concessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.enums import HolderEntityType

if TYPE_CHECKING:
    from app.models.lease import Lease


class LeaseHolder(UUIDMixin, TimestampMixin, Base):
    """The lessee: a company, individual, cooperative or joint venture."""

    __tablename__ = "lease_holders"

    name: Mapped[str] = mapped_column(String(200), index=True)
    entity_type: Mapped[HolderEntityType] = mapped_column(
        enum_column(HolderEntityType),
        default=HolderEntityType.COMPANY,
        server_default=text("'company'"),
    )

    #: Corporate identity number / registration number within the jurisdiction.
    registration_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    #: Permanent account number or local tax identifier.
    tax_identifier: Mapped[str | None] = mapped_column(String(64), index=True)

    contact_person: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))

    address_line: Mapped[str | None] = mapped_column(String(300))
    district: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(
        String(80), default="India", server_default=text("'India'")
    )

    #: True when the holder also operates the mine (vs. a pure lessor).
    is_operator: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text)

    leases: Mapped[list[Lease]] = relationship(back_populates="holder")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LeaseHolder {self.name}>"
