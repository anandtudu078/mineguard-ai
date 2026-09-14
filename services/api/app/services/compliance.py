"""Deterministic compliance scoring.

Design notes that matter for trust:

* The score is **derived, never stored**. Nothing can drift out of sync with the
  underlying records, and re-running the scorer is always safe.
* Components with no underlying records are **excluded and their weight
  redistributed**, rather than scored as failures. A lease registered last week
  with nothing yet due should not read as non-compliant, or the number becomes
  noise operators learn to ignore.
* Validity is recomputed from dates and statuses on every evaluation, so a
  missed nightly job cannot make a lapsed clearance look current.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Date, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import FindingStatus, LicenceStatus, ObligationStatus, RiskLevel
from app.models.finding import InspectionFinding
from app.models.licence import Licence
from app.models.obligation import LeaseObligation

#: Maximum points each component can contribute. Must total 100.
#: The legacy three-component weights (40/45/15) were scaled by 0.85 to make
#: room for site safety at 15 points. Proportional scaling means a lease with
#: no open findings scores exactly as it did before the component existed:
#: the excluded component's weight renormalises back to the old ratios.
LICENCE_WEIGHT = 34.0
OBLIGATION_WEIGHT = 38.25
TIMELINESS_WEIGHT = 12.75
SAFETY_WEIGHT = 15.0

#: Open-findings penalty inside the safety component: each open finding costs
#: this share of the component, regardless of severity (severity is honoured by
#: escalation speed, not double-counted in the score).
_OPEN_FINDING_COST = 1.0 / 3.0

#: Inclusive lower bounds for each risk band.
_RISK_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (85.0, RiskLevel.LOW),
    (70.0, RiskLevel.MEDIUM),
    (50.0, RiskLevel.HIGH),
)

#: Statuses that mean "this obligation will never need action".
_EXEMPT_STATUSES = (ObligationStatus.WAIVED, ObligationStatus.NOT_APPLICABLE)

#: Statuses that mean "still owed".
_OPEN_STATUSES = (
    ObligationStatus.PENDING,
    ObligationStatus.IN_PROGRESS,
    ObligationStatus.OVERDUE,
)


@dataclass(slots=True)
class ComponentScore:
    """One weighted input, reported so the score is explainable."""

    name: str
    weight: float
    applicable: bool
    earned: float
    ratio: float | None
    detail: str


@dataclass(slots=True)
class LeaseCompliance:
    """Assessment for one lease."""

    lease_id: uuid.UUID
    score: float
    risk_level: RiskLevel
    components: list[ComponentScore] = field(default_factory=list)

    total_licences: int = 0
    valid_licences: int = 0
    expiring_licences: int = 0
    expired_licences: int = 0

    open_obligations: int = 0
    overdue_obligations: int = 0
    submitted_obligations: int = 0
    resolved_obligations: int = 0
    on_time_obligations: int = 0

    notes: list[str] = field(default_factory=list)


def _round_score(raw: float) -> float:
    """Round to one decimal, half-up.

    Python's built-in ``round`` uses banker's rounding, which would render 66.25
    as 66.2 but 66.35 as 66.4. A compliance score that appears to round in two
    directions reads as a bug, so rounding is made explicit and predictable.
    """
    return float(Decimal(str(raw)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def risk_level_for(score: float) -> RiskLevel:
    """Bucket a numeric score into a risk band."""
    for threshold, level in _RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.CRITICAL


def _licence_aggregate(session: Session, as_of: date, warning_days: int) -> dict:
    """Per-lease clearance counts, computed from dates rather than stored status."""
    warning_limit = as_of + timedelta(days=warning_days)

    lapsed = and_(Licence.valid_to.is_not(None), Licence.valid_to < as_of)
    revoked = Licence.status == LicenceStatus.REVOKED
    invalid = or_(lapsed, revoked)
    expiring = and_(
        Licence.valid_to.is_not(None),
        Licence.valid_to >= as_of,
        Licence.valid_to <= warning_limit,
        ~invalid,
    )

    rows = session.execute(
        select(
            Licence.lease_id,
            func.count().label("total"),
            func.count().filter(~invalid).label("valid"),
            func.count().filter(expiring).label("expiring"),
            func.count().filter(invalid).label("invalid"),
        ).group_by(Licence.lease_id)
    ).all()

    return {
        row.lease_id: {
            "total": row.total,
            "valid": row.valid,
            "expiring": row.expiring,
            "invalid": row.invalid,
        }
        for row in rows
    }


def _finding_aggregate(session: Session) -> dict:
    """Per-lease counts of open inspection findings (any detection date)."""
    open_statuses = (FindingStatus.OPEN, FindingStatus.IN_PROGRESS)
    rows = session.execute(
        select(
            InspectionFinding.lease_id,
            func.count().label("open_findings"),
        )
        .where(InspectionFinding.status.in_(open_statuses))
        .group_by(InspectionFinding.lease_id)
    ).all()
    return {row.lease_id: {"open_findings": row.open_findings} for row in rows}


def _obligation_aggregate(session: Session, as_of: date) -> dict:
    """Per-lease obligation counts, computed from due dates."""
    not_exempt = ~LeaseObligation.status.in_(_EXEMPT_STATUSES)
    # Come due: the obligation's deadline has passed and it has not been waived.
    come_due = and_(LeaseObligation.due_date <= as_of, not_exempt)
    compliant = and_(come_due, LeaseObligation.status == ObligationStatus.SUBMITTED)
    submitted = and_(not_exempt, LeaseObligation.status == ObligationStatus.SUBMITTED)
    # A submission with no recorded timestamp is credited as timely by default;
    # absence of a timestamp should not manufacture a breach.
    on_time = and_(
        submitted,
        or_(
            LeaseObligation.submitted_at.is_(None),
            cast(LeaseObligation.submitted_at, Date) <= LeaseObligation.due_date,
        ),
    )

    rows = session.execute(
        select(
            LeaseObligation.lease_id,
            func.count().filter(not_exempt).label("tracked"),
            func.count().filter(come_due).label("come_due"),
            func.count().filter(compliant).label("compliant"),
            func.count().filter(submitted).label("submitted"),
            func.count().filter(on_time).label("on_time"),
            func.count()
            .filter(LeaseObligation.status == ObligationStatus.OVERDUE)
            .label("overdue"),
            func.count().filter(LeaseObligation.status.in_(_OPEN_STATUSES)).label("open"),
        ).group_by(LeaseObligation.lease_id)
    ).all()

    return {
        row.lease_id: {
            "tracked": row.tracked,
            "come_due": row.come_due,
            "compliant": row.compliant,
            "submitted": row.submitted,
            "on_time": row.on_time,
            "overdue": row.overdue,
            "open": row.open,
        }
        for row in rows
    }


def _build_assessment(
    lease_id: uuid.UUID,
    licences: dict,
    obligations: dict,
    warning_days: int,
    findings: dict | None = None,
) -> LeaseCompliance:
    """Combine aggregates into a weighted, explainable assessment."""
    l_total = licences.get("total", 0)
    l_valid = licences.get("valid", 0)
    l_expiring = licences.get("expiring", 0)
    l_invalid = licences.get("invalid", 0)

    o_come_due = obligations.get("come_due", 0)
    o_compliant = obligations.get("compliant", 0)
    o_submitted = obligations.get("submitted", 0)
    o_on_time = obligations.get("on_time", 0)

    components: list[ComponentScore] = []

    # --- Clearance sufficiency ---
    licence_applicable = l_total > 0
    licence_ratio = (l_valid / l_total) if licence_applicable else None
    components.append(
        ComponentScore(
            name="clearance_validity",
            weight=LICENCE_WEIGHT,
            applicable=licence_applicable,
            earned=LICENCE_WEIGHT * licence_ratio if licence_applicable else 0.0,
            ratio=licence_ratio,
            detail=(
                f"{l_valid} of {l_total} clearance(s) currently valid"
                if licence_applicable
                else "No clearances recorded, component excluded"
            ),
        )
    )

    # --- Filing adherence ---
    obligation_applicable = o_come_due > 0
    obligation_ratio = (o_compliant / o_come_due) if obligation_applicable else None
    components.append(
        ComponentScore(
            name="filing_adherence",
            weight=OBLIGATION_WEIGHT,
            applicable=obligation_applicable,
            earned=OBLIGATION_WEIGHT * obligation_ratio if obligation_applicable else 0.0,
            ratio=obligation_ratio,
            detail=(
                f"{o_compliant} of {o_come_due} due filing(s) submitted"
                if obligation_applicable
                else "No obligations have come due yet, component excluded"
            ),
        )
    )

    # --- Timeliness ---
    timeliness_applicable = o_submitted > 0
    timeliness_ratio = (o_on_time / o_submitted) if timeliness_applicable else None
    components.append(
        ComponentScore(
            name="timeliness",
            weight=TIMELINESS_WEIGHT,
            applicable=timeliness_applicable,
            earned=TIMELINESS_WEIGHT * timeliness_ratio if timeliness_applicable else 0.0,
            ratio=timeliness_ratio,
            detail=(
                f"{o_on_time} of {o_submitted} submission(s) filed on or before the due date"
                if timeliness_applicable
                else "Nothing submitted yet, component excluded"
            ),
        )
    )

    # --- Site safety (AI + reported findings) ---
    open_findings = int((findings or {}).get("open_findings", 0))
    safety_applicable = open_findings > 0
    # Each open finding burns a third of the component; three or more floor at zero.
    safety_ratio = max(0.0, 1.0 - open_findings * _OPEN_FINDING_COST) if safety_applicable else None
    components.append(
        ComponentScore(
            name="site_safety",
            weight=SAFETY_WEIGHT,
            applicable=safety_applicable,
            earned=SAFETY_WEIGHT * safety_ratio if safety_applicable else 0.0,
            ratio=safety_ratio,
            detail=(
                f"{open_findings} open finding(s) under remediation"
                if safety_applicable
                else "No open inspection findings, component excluded"
            ),
        )
    )

    applicable_weight = sum(c.weight for c in components if c.applicable)
    if applicable_weight == 0:
        score = 100.0
    else:
        score = _round_score(sum(c.earned for c in components) / applicable_weight * 100.0)

    notes: list[str] = []
    if open_findings:
        notes.append(
            f"{open_findings} open inspection finding(s) are lowering the site-safety component."
        )
    if not licence_applicable:
        notes.append("No clearances recorded against this lease.")
    if l_invalid:
        notes.append(f"{l_invalid} clearance(s) lapsed or revoked.")
    if l_expiring:
        notes.append(f"{l_expiring} clearance(s) expire within {warning_days} days.")

    o_overdue = obligations.get("overdue", 0)
    if o_overdue:
        notes.append(f"{o_overdue} obligation(s) overdue.")

    o_open = obligations.get("open", 0)
    if o_come_due == 0 and o_open:
        notes.append(f"{o_open} obligation(s) scheduled, none yet due.")
    elif o_come_due == 0 and not o_open:
        notes.append("No filing obligations scheduled yet.")

    return LeaseCompliance(
        lease_id=lease_id,
        score=score,
        risk_level=risk_level_for(score),
        components=components,
        total_licences=l_total,
        valid_licences=l_valid,
        expiring_licences=l_expiring,
        expired_licences=l_invalid,
        open_obligations=o_open,
        overdue_obligations=o_overdue,
        submitted_obligations=o_submitted,
        resolved_obligations=o_come_due,
        on_time_obligations=o_on_time,
        notes=notes,
    )


def score_leases(
    session: Session,
    as_of: date,
    lease_ids: list[uuid.UUID] | None = None,
    warning_days: int = 90,
) -> dict[uuid.UUID, LeaseCompliance]:
    """Score many leases with a fixed number of queries.

    Two aggregates regardless of lease count, so the portfolio list view stays
    fast as the register grows.
    """
    licences = _licence_aggregate(session, as_of, warning_days)
    obligations = _obligation_aggregate(session, as_of)
    findings = _finding_aggregate(session)

    if lease_ids is None:
        lease_ids = sorted(set(licences) | set(obligations))

    return {
        lease_id: _build_assessment(
            lease_id, licences.get(lease_id, {}), obligations.get(lease_id, {}), warning_days, findings.get(lease_id, {})
        )
        for lease_id in lease_ids
    }


def score_lease(
    session: Session, lease_id: uuid.UUID, as_of: date, warning_days: int = 90
) -> LeaseCompliance:
    """Score a single lease."""
    return score_leases(session, as_of, [lease_id], warning_days)[lease_id]
