"""ORM models for the mining governance platform.

Every model is imported here so that SQLAlchemy's mapper registry is complete
before the first query runs and so Alembic autogenerate detects all tables.
"""

from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin, UUIDMixin, enum_column
from app.models.document import DocumentStatus, DocumentType, LeaseDocument
from app.models.enums import (
    AppRole,
    AuditAction,
    AuditEntity,
    AuditOutcome,
    FindingSource,
    FindingStatus,
    HolderEntityType,
    LeaseStatus,
    LeaseType,
    LicenceStatus,
    LicenceType,
    MineralCategory,
    ObligationCategory,
    ObligationStatus,
    Recurrence,
    RiskLevel,
    RoyaltyBasis,
    ViolationSeverity,
)
from app.models.finding import InspectionFinding
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.mineral import Mineral
from app.models.obligation import LeaseObligation, Obligation
from app.models.reminder import ReminderDelivery
from app.models.user import AppUser

__all__ = [
    "AppRole",
    "AppUser",
    "AuditAction",
    "AuditEntity",
    "AuditLog",
    "AuditOutcome",
    "Base",
    "DocumentStatus",
    "DocumentType",
    "FindingSource",
    "FindingStatus",
    "HolderEntityType",
    "InspectionFinding",
    "Lease",
    "LeaseDocument",
    "LeaseHolder",
    "LeaseObligation",
    "LeaseStatus",
    "LeaseType",
    "Licence",
    "LicenceStatus",
    "LicenceType",
    "Mineral",
    "MineralCategory",
    "Obligation",
    "ObligationCategory",
    "ObligationStatus",
    "Recurrence",
    "RiskLevel",
    "ReminderDelivery",
    "RoyaltyBasis",
    "TimestampMixin",
    "UUIDMixin",
    "enum_column",
    "ViolationSeverity",
]
