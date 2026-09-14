"""Controlled vocabularies for the mining governance domain.

All enumerations are stored as ``VARCHAR`` plus a ``CHECK`` constraint rather than
native PostgreSQL ``ENUM`` types. Native enums require an ``ALTER TYPE`` migration
for every added member, which is painful for regulatory vocabularies that grow.
"""

from enum import StrEnum


class LeaseType(StrEnum):
    """Instrument under which mineral rights are held."""

    PROSPECTING_LICENCE = "prospecting_licence"
    MINING_LEASE = "mining_lease"
    QUARRY_LEASE = "quarry_lease"
    COMPOSITE_LICENCE = "composite_licence"


class LeaseStatus(StrEnum):
    """Lifecycle state of a mineral concession."""

    PENDING = "pending"
    ACTIVE = "active"
    PENDING_RENEWAL = "pending_renewal"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    SURRENDERED = "surrendered"
    REVOKED = "revoked"


class HolderEntityType(StrEnum):
    """Legal form of the entity holding the concession."""

    COMPANY = "company"
    INDIVIDUAL = "individual"
    COOPERATIVE = "cooperative"
    JOINT_VENTURE = "joint_venture"
    GOVERNMENT_UNDERTAKING = "government_undertaking"


class MineralCategory(StrEnum):
    """Statutory classification of the mineral.

    In the Indian regime, "major" minerals are regulated by the central
    government (MMDR Act, First Schedule) and "minor" minerals by state rules.
    """

    MAJOR = "major"
    MINOR = "minor"


class RoyaltyBasis(StrEnum):
    """How royalty is levied on a mineral."""

    AD_VALOREM = "ad_valorem"
    SPECIFIC = "specific"
    EXEMPT = "exempt"


class LicenceType(StrEnum):
    """Statutory clearances and approvals attached to a concession."""

    ENVIRONMENTAL_CLEARANCE = "environmental_clearance"
    FOREST_CLEARANCE = "forest_clearance"
    CONSENT_TO_OPERATE = "consent_to_operate"
    MINING_PLAN_APPROVAL = "mining_plan_approval"
    GROUND_WATER_NTOC = "ground_water_ntoc"
    EXPLOSIVE_LICENCE = "explosive_licence"
    DRONE_SURVEY_APPROVAL = "drone_survey_approval"
    LEASE_DEED = "lease_deed"


class LicenceStatus(StrEnum):
    """Validity state of a statutory clearance."""

    PENDING = "pending"
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ObligationCategory(StrEnum):
    """Thematic grouping used for dashboards and filtering."""

    RETURN_FILING = "return_filing"
    PAYMENT = "payment"
    INSPECTION = "inspection"
    SAFETY = "safety"
    ENVIRONMENT = "environment"
    SOCIAL = "social"
    REPORTING = "reporting"


class Recurrence(StrEnum):
    """How often a statutory obligation repeats."""

    ONE_TIME = "one_time"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    ANNUAL = "annual"


class ObligationStatus(StrEnum):
    """Filing state of a single obligation instance."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    OVERDUE = "overdue"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"


class RiskLevel(StrEnum):
    """Bucketed compliance risk derived from the compliance score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AppRole(StrEnum):
    """What a signed-in user is allowed to do.

    Deliberately separate from Supabase's own ``role`` claim, which only ever
    says "authenticated". Authorisation is the application's concern, and it
    lives in ``app_users`` where it can be changed without touching Supabase and
    joined against in a single query.
    """

    #: Manages users and reference data; can do everything an inspector can.
    ADMIN = "admin"
    #: Regulator-side. Reads the whole portfolio, files and waives on any lease.
    INSPECTOR = "inspector"
    #: Leaseholder-side. Scoped to the leases their own organisation holds.
    OPERATOR = "operator"


class AuditAction(StrEnum):
    """The kind of thing that happened, from an auditor's point of view."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    #: A statutory filing was recorded against an obligation.
    SUBMIT = "submit"
    #: An obligation was excused.
    WAIVE = "waive"
    #: A previously closed obligation was put back in play.
    REOPEN = "reopen"
    #: The calendar was materialised from the obligation rules.
    GENERATE = "generate"
    #: Overdue statuses were recomputed.
    REFRESH = "refresh"
    #: A user signed in.
    LOGIN = "login"
    #: A request was refused because the role did not allow it.
    ACCESS_DENIED = "access_denied"


class AuditEntity(StrEnum):
    """The kind of record an audit entry is about."""

    LEASE = "lease"
    LICENCE = "licence"
    OBLIGATION_RULE = "obligation_rule"
    CALENDAR_ENTRY = "calendar_entry"
    MINERAL = "mineral"
    HOLDER = "holder"
    USER = "user"
    SESSION = "session"


class AuditOutcome(StrEnum):
    """Whether the recorded attempt actually took effect."""

    SUCCEEDED = "succeeded"
    #: Refused by the role check. Recorded because failed attempts to change
    #: statutory records are exactly what an audit is for.
    DENIED = "denied"
    #: Allowed, but failed for another reason (validation, conflict).
    FAILED = "failed"
