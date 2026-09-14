"""Schemas for obligation rules and their calendared instances."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    LeaseType,
    MineralCategory,
    ObligationCategory,
    ObligationStatus,
    Recurrence,
)
from app.schemas.common import ORMModel


# --------------------------------------------------------------------------
# Obligation rules
# --------------------------------------------------------------------------
class ObligationBase(BaseModel):
    code: str = Field(max_length=64)
    title: str = Field(max_length=200)
    description: str | None = None
    category: ObligationCategory
    legal_reference: str | None = Field(default=None, max_length=200)
    jurisdiction: str | None = None
    recurrence: Recurrence
    due_days_after_period_end: int = Field(default=0, ge=0, le=400)
    grace_days: int = Field(default=0, ge=0, le=120)
    fiscal_year_end_month: int = Field(default=3, ge=1, le=12)
    applies_to_lease_types: list[LeaseType] = Field(default_factory=list)
    applies_to_mineral_categories: list[MineralCategory] = Field(default_factory=list)
    requires_payment: bool = False
    penalty_note: str | None = None
    is_active: bool = True


class ObligationCreate(ObligationBase):
    pass


class ObligationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    category: ObligationCategory | None = None
    legal_reference: str | None = None
    jurisdiction: str | None = None
    recurrence: Recurrence | None = None
    due_days_after_period_end: int | None = Field(default=None, ge=0, le=400)
    grace_days: int | None = Field(default=None, ge=0, le=120)
    fiscal_year_end_month: int | None = Field(default=None, ge=1, le=12)
    applies_to_lease_types: list[LeaseType] | None = None
    applies_to_mineral_categories: list[MineralCategory] | None = None
    requires_payment: bool | None = None
    penalty_note: str | None = None
    is_active: bool | None = None


class ObligationRead(ObligationBase, ORMModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Calendared instances
# --------------------------------------------------------------------------
class LeaseObligationRead(ORMModel):
    id: uuid.UUID
    lease_id: uuid.UUID
    obligation_id: uuid.UUID
    period_start: date | None = None
    period_end: date | None = None
    due_date: date
    status: ObligationStatus
    submitted_at: datetime | None = None
    submitted_by: str | None = None
    evidence_path: str | None = None
    notes: str | None = None
    waiver_reason: str | None = None

    # Denormalised rule fields so the calendar needs no second request.
    code: str | None = None
    title: str | None = None
    category: ObligationCategory | None = None
    legal_reference: str | None = None
    requires_payment: bool | None = None
    penalty_note: str | None = None

    # Context for cross-lease calendar views.
    lease_number: str | None = None
    lease_name: str | None = None
    district: str | None = None
    state: str | None = None

    days_until_due: int | None = None


class ObligationSubmit(BaseModel):
    """Record that a filing was made."""

    submitted_by: str | None = Field(default=None, max_length=200)
    submitted_at: datetime | None = None
    evidence_path: str | None = None
    notes: str | None = None


class ObligationStatusUpdate(BaseModel):
    """Move an instance to a different state, e.g. waive it or mark it N/A."""

    model_config = ConfigDict(extra="forbid")

    status: ObligationStatus
    reason: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _reason_required_for_exemption(self) -> "ObligationStatusUpdate":
        exempt = {ObligationStatus.WAIVED, ObligationStatus.NOT_APPLICABLE}
        if self.status in exempt and not (self.reason or "").strip():
            raise ValueError(f"a reason is required when setting status to {self.status}")
        return self


class GenerateRequest(BaseModel):
    """Request to materialise obligation instances onto a lease calendar."""

    window_start: date | None = Field(
        default=None, description="Defaults to the start of the current fiscal year"
    )
    window_end: date | None = Field(
        default=None, description="Defaults to 12 months after window_start"
    )
