"""Schemas for derived compliance state and portfolio dashboards."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import ObligationCategory, RiskLevel


class ComplianceComponent(BaseModel):
    """One weighted input to the compliance score.

    Reported explicitly rather than collapsed into a single number so an
    operator can see *why* a lease scored as it did, which is the difference
    between a dashboard people trust and one they ignore.
    """

    name: str
    weight: float = Field(description="Maximum points this component can contribute")
    applicable: bool = Field(
        description="False when the lease has no records this component can judge"
    )
    earned: float = Field(description="Points actually awarded")
    ratio: float | None = Field(
        default=None, description="Raw 0..1 ratio before weighting; null if not applicable"
    )
    detail: str


class ComplianceScore(BaseModel):
    """Deterministic compliance assessment for a single lease."""

    lease_id: uuid.UUID
    lease_number: str
    score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    components: list[ComplianceComponent]

    total_licences: int = 0
    valid_licences: int = 0
    expiring_licences: int = 0
    expired_licences: int = 0
    open_obligations: int = 0
    overdue_obligations: int = 0
    submitted_obligations: int = 0

    notes: list[str] = Field(default_factory=list)


class DashboardTotals(BaseModel):
    """Portfolio-level rollup."""

    leases_total: int = 0
    leases_active: int = 0
    leases_expiring_within_90_days: int = 0
    total_area_hectares: Decimal = Decimal("0")
    obligations_overdue: int = 0
    obligations_due_within_30_days: int = 0
    licences_expired: int = 0
    licences_expiring_soon: int = 0
    average_compliance_score: float = 0.0


class RiskBucket(BaseModel):
    risk_level: RiskLevel
    lease_count: int


class StateBreakdown(BaseModel):
    state: str
    lease_count: int
    area_hectares: Decimal


class CategoryBreakdown(BaseModel):
    category: ObligationCategory
    overdue: int
    due_soon: int


class DashboardSummary(BaseModel):
    """Everything the landing dashboard needs, in one round trip."""

    as_of: date
    totals: DashboardTotals
    risk_buckets: list[RiskBucket]
    by_state: list[StateBreakdown]
    overdue_by_category: list[CategoryBreakdown]
