"""Schemas for reference data: minerals and lease holders."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import HolderEntityType, MineralCategory, RoyaltyBasis
from app.schemas.common import ORMModel


# --------------------------------------------------------------------------
# Minerals
# --------------------------------------------------------------------------
class MineralBase(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=120)
    category: MineralCategory = MineralCategory.MAJOR
    royalty_basis: RoyaltyBasis = RoyaltyBasis.AD_VALOREM
    royalty_rate: Decimal = Decimal("0")
    royalty_unit: str | None = None
    description: str | None = None
    is_active: bool = True


class MineralCreate(MineralBase):
    pass


class MineralUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    category: MineralCategory | None = None
    royalty_basis: RoyaltyBasis | None = None
    royalty_rate: Decimal | None = None
    royalty_unit: str | None = None
    description: str | None = None
    is_active: bool | None = None


class MineralRead(MineralBase, ORMModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Lease holders
# --------------------------------------------------------------------------
class HolderBase(BaseModel):
    name: str = Field(max_length=200)
    entity_type: HolderEntityType = HolderEntityType.COMPANY
    registration_number: str | None = Field(default=None, max_length=64)
    tax_identifier: str | None = Field(default=None, max_length=64)
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line: str | None = None
    district: str | None = None
    state: str | None = None
    country: str = "India"
    is_operator: bool = True
    notes: str | None = None


class HolderCreate(HolderBase):
    pass


class HolderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    entity_type: HolderEntityType | None = None
    registration_number: str | None = None
    tax_identifier: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    is_operator: bool | None = None
    notes: str | None = None


class HolderRead(HolderBase, ORMModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
