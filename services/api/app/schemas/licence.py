"""Schemas for statutory clearances."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LicenceStatus, LicenceType
from app.schemas.common import ORMModel


class LicenceBase(BaseModel):
    licence_type: LicenceType
    status: LicenceStatus = LicenceStatus.PENDING
    authority: str = Field(max_length=160)
    reference_number: str | None = Field(default=None, max_length=120)
    issued_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    document_path: str | None = None
    notes: str | None = None
    is_mandatory: bool = True

    @model_validator(mode="after")
    def _validity_is_ordered(self) -> "LicenceBase":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not precede valid_from")
        return self


class LicenceCreate(LicenceBase):
    pass


class LicenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    licence_type: LicenceType | None = None
    status: LicenceStatus | None = None
    authority: str | None = None
    reference_number: str | None = None
    issued_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    document_path: str | None = None
    notes: str | None = None
    is_mandatory: bool | None = None


class LicenceRead(LicenceBase, ORMModel):
    id: uuid.UUID
    lease_id: uuid.UUID
    #: Signed day count to expiry: negative once lapsed, null when open-ended.
    days_until_expiry: int | None = None
    created_at: datetime
    updated_at: datetime
