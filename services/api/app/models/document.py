"""Uploaded compliance documents attached to a lease."""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column

if TYPE_CHECKING:
    from app.models.lease import Lease


class DocumentType(StrEnum):
    """Category of uploaded evidence or record."""

    LICENCE = "licence"
    OBLIGATION = "obligation"
    EVIDENCE = "evidence"
    GENERAL = "general"


class DocumentStatus(StrEnum):
    """Review state for a document in the workflow."""

    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    NEEDS_ATTENTION = "needs_attention"
    REJECTED = "rejected"


class LeaseDocument(UUIDMixin, TimestampMixin, Base):
    """A file uploaded against a lease for review or evidence."""

    __tablename__ = "lease_documents"

    lease_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leases.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    file_name: Mapped[str] = mapped_column(String(240), index=True)
    content_type: Mapped[str] = mapped_column(String(120), index=True)
    file_path: Mapped[str] = mapped_column(String(400), unique=True)
    document_type: Mapped[DocumentType] = mapped_column(
        enum_column(DocumentType), default=DocumentType.GENERAL, index=True
    )
    source: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        enum_column(DocumentStatus), default=DocumentStatus.PENDING_REVIEW, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    extracted_summary: Mapped[str | None] = mapped_column(Text)
    extracted_reference_number: Mapped[str | None] = mapped_column(String(160))
    extracted_authority: Mapped[str | None] = mapped_column(String(200))
    extracted_expiry_date: Mapped[date | None] = mapped_column(Date, index=True)

    lease: Mapped[Lease] = relationship(back_populates="documents")
