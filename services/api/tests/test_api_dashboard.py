"""Integration tests for the portfolio dashboard.

The dashboard is the first thing anyone sees, so its numbers must agree with the
per-lease views. These tests assert the rollup against known fixtures rather
than just checking the response shape.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import LeaseStatus, ObligationStatus
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.mineral import Mineral
from app.models.obligation import LeaseObligation, Obligation

BASE = "/api/v1"


def test_summary_reports_totals_consistent_with_the_register(
    client: TestClient, lease: Lease, valid_licence: Licence
):
    response = client.get(f"{BASE}/dashboard/summary")
    assert response.status_code == 200
    body = response.json()

    totals = body["totals"]
    assert totals["leases_total"] == 1
    assert totals["leases_active"] == 1
    # The fixture lease is stated at 100 hectares.
    assert float(totals["total_area_hectares"]) == 100.0
    assert totals["licences_expired"] == 0
    assert 0 <= totals["average_compliance_score"] <= 100


def test_summary_counts_lapsed_clearances(
    client: TestClient, session: Session, lease: Lease, today: date
):
    session.add(
        Licence(
            lease_id=lease.id,
            licence_type="forest_clearance",
            authority="MoEFCC",
            reference_number="FC/LAPSED",
            valid_from=today - timedelta(days=900),
            valid_to=today - timedelta(days=30),
        )
    )
    session.flush()

    totals = client.get(f"{BASE}/dashboard/summary").json()["totals"]
    assert totals["licences_expired"] == 1


def test_summary_counts_clearances_expiring_soon(
    client: TestClient, session: Session, lease: Lease, today: date
):
    session.add(
        Licence(
            lease_id=lease.id,
            licence_type="ground_water_ntoc",
            authority="CGWA",
            reference_number="GW/SOON",
            valid_to=today + timedelta(days=30),
        )
    )
    session.flush()

    # Default warning horizon is 90 days.
    totals = client.get(f"{BASE}/dashboard/summary").json()["totals"]
    assert totals["licences_expiring_soon"] == 1

    # A tighter horizon must exclude it.
    tight = client.get(f"{BASE}/dashboard/summary", params={"warning_days": 10}).json()
    assert tight["totals"]["licences_expiring_soon"] == 0


def test_summary_counts_overdue_and_due_soon_obligations(
    client: TestClient,
    session: Session,
    lease: Lease,
    monthly_rule: Obligation,
    annual_rule: Obligation,
    today: date,
):
    session.add_all(
        [
            LeaseObligation(
                lease_id=lease.id,
                obligation_id=monthly_rule.id,
                period_start=today - timedelta(days=60),
                period_end=today - timedelta(days=40),
                due_date=today - timedelta(days=20),
                status=ObligationStatus.OVERDUE,
            ),
            LeaseObligation(
                lease_id=lease.id,
                obligation_id=annual_rule.id,
                period_start=today,
                period_end=today + timedelta(days=20),
                due_date=today + timedelta(days=10),
                status=ObligationStatus.PENDING,
            ),
        ]
    )
    session.flush()

    totals = client.get(f"{BASE}/dashboard/summary").json()["totals"]
    assert totals["obligations_overdue"] == 1
    assert totals["obligations_due_within_30_days"] == 1


def test_leases_expiring_within_ninety_days_are_counted(
    client: TestClient, session: Session, holder: LeaseHolder, mineral: Mineral, today: date
):
    session.add_all(
        [
            Lease(
                lease_number="ML/TEST/EXP/1",
                name="Expiring Soon",
                holder_id=holder.id,
                mineral_id=mineral.id,
                district="D",
                state="S",
                effective_from=today - timedelta(days=3000),
                effective_to=today + timedelta(days=30),
                status=LeaseStatus.ACTIVE,
            ),
            Lease(
                lease_number="ML/TEST/EXP/2",
                name="Expiring Later",
                holder_id=holder.id,
                mineral_id=mineral.id,
                district="D",
                state="S",
                effective_from=today - timedelta(days=1000),
                effective_to=today + timedelta(days=5000),
                status=LeaseStatus.ACTIVE,
            ),
        ]
    )
    session.flush()

    totals = client.get(f"{BASE}/dashboard/summary").json()["totals"]
    assert totals["leases_expiring_within_90_days"] == 1


def test_risk_buckets_always_report_all_four_levels(client: TestClient, lease: Lease):
    buckets = client.get(f"{BASE}/dashboard/summary").json()["risk_buckets"]

    # Every band is present even at zero, so the chart does not reflow.
    assert [bucket["risk_level"] for bucket in buckets] == [
        "critical",
        "high",
        "medium",
        "low",
    ]
    assert sum(bucket["lease_count"] for bucket in buckets) >= 1


def test_by_state_groups_the_register(
    client: TestClient, session: Session, holder: LeaseHolder, mineral: Mineral, today: date
):
    session.add_all(
        [
            Lease(
                lease_number="ML/TEST/ST/1",
                name="Odisha One",
                holder_id=holder.id,
                mineral_id=mineral.id,
                district="Keonjhar",
                state="Odisha",
                effective_from=today - timedelta(days=500),
                effective_to=today + timedelta(days=5000),
            ),
            Lease(
                lease_number="ML/TEST/ST/2",
                name="Odisha Two",
                holder_id=holder.id,
                mineral_id=mineral.id,
                district="Sundargarh",
                state="Odisha",
                effective_from=today - timedelta(days=500),
                effective_to=today + timedelta(days=5000),
            ),
        ]
    )
    session.flush()

    by_state = client.get(f"{BASE}/dashboard/summary").json()["by_state"]
    odisha = next(row for row in by_state if row["state"] == "Odisha")
    assert odisha["lease_count"] == 2


def test_overdue_by_category_breaks_down_filings(
    client: TestClient,
    session: Session,
    lease: Lease,
    monthly_rule: Obligation,
    today: date,
):
    session.add(
        LeaseObligation(
            lease_id=lease.id,
            obligation_id=monthly_rule.id,
            period_start=today - timedelta(days=60),
            period_end=today - timedelta(days=40),
            due_date=today - timedelta(days=25),
            status=ObligationStatus.OVERDUE,
        )
    )
    session.flush()

    breakdown = client.get(f"{BASE}/dashboard/summary").json()["overdue_by_category"]
    filing = next(row for row in breakdown if row["category"] == "return_filing")
    assert filing["overdue"] == 1


def test_summary_reports_the_evaluation_date(client: TestClient):
    body = client.get(f"{BASE}/dashboard/summary", params={"as_of": "2026-01-15"}).json()
    assert body["as_of"] == "2026-01-15"
