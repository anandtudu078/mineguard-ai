"""Schemas for uploaded lease documents."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentType


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lease_id: uuid.UUID
    title: str
    file_name: str
    content_type: str
    file_path: str
    document_type: DocumentType
    source: str
    status: DocumentStatus
    notes: str | None = None
    extracted_summary: str | None = None
    extracted_reference_number: str | None = None
    extracted_authority: str | None = None
    extracted_expiry_date: date | None = None
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int


class DocumentUpload(BaseModel):
    document_type: DocumentType = DocumentType.GENERAL
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    source: str = "manual"


class DocumentUpdate(BaseModel):
    status: DocumentStatus | None = None
    notes: str | None = None
