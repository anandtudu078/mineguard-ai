"""Pydantic schemas for the compliance API."""

from app.schemas.common import LatLon, Message, ORMModel, Page
from app.schemas.compliance import (
    CategoryBreakdown,
    ComplianceComponent,
    ComplianceScore,
    DashboardSummary,
    DashboardTotals,
    RiskBucket,
    StateBreakdown,
)
from app.schemas.lease import LeaseCreate, LeaseListItem, LeaseRead, LeaseUpdate
from app.schemas.licence import LicenceCreate, LicenceRead, LicenceUpdate
from app.schemas.obligation import (
    GenerateRequest,
    LeaseObligationRead,
    ObligationCreate,
    ObligationRead,
    ObligationStatusUpdate,
    ObligationSubmit,
    ObligationUpdate,
)
from app.schemas.reference import (
    HolderCreate,
    HolderRead,
    HolderUpdate,
    MineralCreate,
    MineralRead,
    MineralUpdate,
)

__all__ = [
    "CategoryBreakdown",
    "ComplianceComponent",
    "ComplianceScore",
    "DashboardSummary",
    "DashboardTotals",
    "GenerateRequest",
    "HolderCreate",
    "HolderRead",
    "HolderUpdate",
    "LatLon",
    "LeaseCreate",
    "LeaseListItem",
    "LeaseObligationRead",
    "LeaseRead",
    "LeaseUpdate",
    "LicenceCreate",
    "LicenceRead",
    "LicenceUpdate",
    "Message",
    "MineralCreate",
    "MineralRead",
    "MineralUpdate",
    "ORMModel",
    "ObligationCreate",
    "ObligationRead",
    "ObligationStatusUpdate",
    "ObligationSubmit",
    "ObligationUpdate",
    "Page",
    "RiskBucket",
    "StateBreakdown",
]
