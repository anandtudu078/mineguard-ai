"""Portfolio-level aggregation for the landing dashboard.

Every figure is derived from the same primitives the rest of the system uses,
so the dashboard can never disagree with the per-lease detail views.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.enums import LeaseStatus, ObligationStatus, RiskLevel
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.obligation import LeaseObligation, Obligation
from app.services.compliance import score_leases

#: Window used for the "lease expiring soon" tile.
_LEASE_EXPIRY_WINDOW_DAYS = 90
#: Window used for the "filings due soon" tile.
_DUE_SOON_DAYS = 30

_OPEN_STATUSES = (
    ObligationStatus.PENDING,
    ObligationStatus.IN_PROGRESS,
    ObligationStatus.OVERDUE,
)


def summary(session: Session, as_of: date, warning_days: int = 90) -> dict[str, Any]:
    """Build the complete dashboard payload in a fixed number of queries."""
    lease_expiry_horizon = as_of + timedelta(days=_LEASE_EXPIRY_WINDOW_DAYS)
    due_soon_horizon = as_of + timedelta(days=_DUE_SOON_DAYS)
    licence_horizon = as_of + timedelta(days=warning_days)

    lease_totals = session.execute(
        select(
            func.count().label("total"),
            func.count().filter(Lease.status == LeaseStatus.ACTIVE).label("active"),
            func.count()
            .filter(
                and_(
                    Lease.effective_to.is_not(None),
                    Lease.effective_to >= as_of,
                    Lease.effective_to <= lease_expiry_horizon,
                )
            )
            .label("expiring"),
            func.coalesce(func.sum(Lease.area_hectares), 0).label("area"),
        ).select_from(Lease)
    ).one()

    obligation_totals = session.execute(
        select(
            func.count()
            .filter(LeaseObligation.status == ObligationStatus.OVERDUE)
            .label("overdue"),
            func.count()
            .filter(
                and_(
                    LeaseObligation.due_date >= as_of,
                    LeaseObligation.due_date <= due_soon_horizon,
                    LeaseObligation.status.in_(_OPEN_STATUSES),
                )
            )
            .label("due_soon"),
        ).select_from(LeaseObligation)
    ).one()

    licence_totals = session.execute(
        select(
            func.count()
            .filter(and_(Licence.valid_to.is_not(None), Licence.valid_to < as_of))
            .label("expired"),
            func.count()
            .filter(
                and_(
                    Licence.valid_to.is_not(None),
                    Licence.valid_to >= as_of,
                    Licence.valid_to <= licence_horizon,
                )
            )
            .label("expiring"),
        ).select_from(Licence)
    ).one()

    # Portfolio risk requires scoring every lease, but scoring is two aggregates
    # regardless of size, so this stays flat as the register grows.
    lease_ids = list(session.scalars(select(Lease.id)).all())
    scores = score_leases(session, as_of, lease_ids, warning_days)
    bucket_counts = Counter(assessment.risk_level for assessment in scores.values())
    average_score = round(sum(a.score for a in scores.values()) / len(scores), 1) if scores else 0.0

    state_rows = session.execute(
        select(
            Lease.state,
            func.count().label("lease_count"),
            func.coalesce(func.sum(Lease.area_hectares), 0).label("area"),
        )
        .group_by(Lease.state)
        .order_by(func.count().desc(), Lease.state.asc())
    ).all()

    category_rows = session.execute(
        select(
            Obligation.category,
            func.count()
            .filter(LeaseObligation.status == ObligationStatus.OVERDUE)
            .label("overdue"),
            func.count()
            .filter(
                and_(
                    LeaseObligation.due_date >= as_of,
                    LeaseObligation.due_date <= due_soon_horizon,
                    LeaseObligation.status.in_(_OPEN_STATUSES),
                )
            )
            .label("due_soon"),
        )
        .join(Obligation, Obligation.id == LeaseObligation.obligation_id)
        .group_by(Obligation.category)
        .order_by(func.count().filter(LeaseObligation.status == ObligationStatus.OVERDUE).desc())
    ).all()

    ordered_levels = [
        RiskLevel.CRITICAL,
        RiskLevel.HIGH,
        RiskLevel.MEDIUM,
        RiskLevel.LOW,
    ]

    return {
        "as_of": as_of,
        "totals": {
            "leases_total": lease_totals.total,
            "leases_active": lease_totals.active,
            "leases_expiring_within_90_days": lease_totals.expiring,
            "total_area_hectares": lease_totals.area,
            "obligations_overdue": obligation_totals.overdue,
            "obligations_due_within_30_days": obligation_totals.due_soon,
            "licences_expired": licence_totals.expired,
            "licences_expiring_soon": licence_totals.expiring,
            "average_compliance_score": average_score,
        },
        "risk_buckets": [
            {"risk_level": level, "lease_count": bucket_counts.get(level, 0)}
            for level in ordered_levels
        ],
        "by_state": [
            {
                "state": row.state,
                "lease_count": row.lease_count,
                "area_hectares": row.area,
            }
            for row in state_rows
        ],
        "overdue_by_category": [
            {
                "category": row.category,
                "overdue": row.overdue,
                "due_soon": row.due_soon,
            }
            for row in category_rows
        ],
    }
