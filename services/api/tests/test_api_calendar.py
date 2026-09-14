"""Integration tests for the compliance calendar and filing workflow.

Covers the parts that are easy to get subtly wrong: generation idempotency,
overdue recomputation, and the audit requirement that exemptions carry a reason.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import ObligationStatus
from app.models.lease import Lease
from app.models.obligation import LeaseObligation, Obligation

BASE = "/api/v1"


def _generate(client: TestClient, lease: Lease, **payload) -> list[dict]:
    response = client.post(f"{BASE}/leases/{lease.id}/obligations/generate", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def test_generate_materialises_calendar_entries(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    entries = _generate(client, lease)

    assert entries, "expected at least one generated entry"
    assert all(entry["lease_id"] == str(lease.id) for entry in entries)
    # Rule context is denormalised onto each entry for the calendar view.
    assert all(entry["code"] == monthly_rule.code for entry in entries)
    assert all(entry["status"] == "pending" for entry in entries)


def test_generate_offsets_due_date_from_period_end(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    entries = _generate(client, lease, window_start="2026-01-01", window_end="2026-03-31")

    by_period = {entry["period_start"]: entry for entry in entries}
    assert by_period["2026-01-01"]["period_end"] == "2026-01-31"
    assert by_period["2026-01-01"]["due_date"] == "2026-02-15"
    assert by_period["2026-02-01"]["due_date"] == "2026-03-15"
    assert by_period["2026-03-01"]["due_date"] == "2026-04-15"


def test_generate_is_idempotent(client: TestClient, lease: Lease, monthly_rule: Obligation):
    first = _generate(client, lease, window_start="2026-01-01", window_end="2026-06-30")
    second = _generate(client, lease, window_start="2026-01-01", window_end="2026-06-30")

    assert len(first) == 6
    # Re-running must not duplicate or reset anything.
    assert len(second) == len(first)


def test_regenerating_does_not_clobber_recorded_filings(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    entries = _generate(client, lease, window_start="2026-01-01", window_end="2026-03-31")
    target = entries[0]["id"]

    submitted = client.post(f"{BASE}/calendar/{target}/submit", json={"submitted_by": "Inspector"})
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    _generate(client, lease, window_start="2026-01-01", window_end="2026-03-31")

    after = client.get(
        f"{BASE}/leases/{lease.id}/obligations",
        params={"date_from": "2026-01-01", "date_to": "2026-03-31"},
    ).json()
    assert next(row for row in after["items"] if row["id"] == target)["status"] == "submitted"


def test_generate_rejects_an_inverted_window(client: TestClient, lease: Lease, monthly_rule):
    response = client.post(
        f"{BASE}/leases/{lease.id}/obligations/generate",
        json={"window_start": "2026-12-31", "window_end": "2026-01-01"},
    )
    assert response.status_code == 422


def test_generate_404s_for_an_unknown_lease(client: TestClient):
    response = client.post(
        f"{BASE}/leases/00000000-0000-0000-0000-0000000000ff/obligations/generate", json={}
    )
    assert response.status_code == 404


def test_generate_skips_rules_that_do_not_apply(client: TestClient, lease: Lease, session: Session):
    """A rule scoped to quarry leases must not land on a mining lease."""
    from app.models.enums import ObligationCategory, Recurrence

    scoped = Obligation(
        code="TEST_QUARRY_ONLY",
        title="Quarry-only filing",
        category=ObligationCategory.RETURN_FILING,
        recurrence=Recurrence.ANNUAL,
        due_days_after_period_end=30,
        fiscal_year_end_month=3,
        applies_to_lease_types=["quarry_lease"],
    )
    session.add(scoped)
    session.flush()

    entries = _generate(client, lease)
    assert all(entry["code"] != "TEST_QUARRY_ONLY" for entry in entries)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------
def test_calendar_lists_entries_with_lease_context(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    _generate(client, lease, window_start="2026-01-01", window_end="2026-03-31")

    response = client.get(f"{BASE}/calendar", params={"lease_id": str(lease.id)})
    assert response.status_code == 200

    page = response.json()
    assert page["total"] == 3
    entry = page["items"][0]
    assert entry["lease_number"] == lease.lease_number
    assert entry["district"] == lease.district
    assert entry["title"] == monthly_rule.title


def test_calendar_filters_by_date_window(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    _generate(client, lease, window_start="2026-01-01", window_end="2026-06-30")

    response = client.get(
        f"{BASE}/calendar",
        params={"date_from": "2026-03-01", "date_to": "2026-04-30"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_calendar_rejects_an_unknown_entry_state(client: TestClient):
    response = client.get(f"{BASE}/calendar", params={"entry_state": "nonsense"})
    assert response.status_code == 422


def test_calendar_window_endpoint_reports_the_default_range(client: TestClient):
    response = client.get(f"{BASE}/calendar/window")
    assert response.status_code == 200

    body = response.json()
    start = date.fromisoformat(body["window_start"])
    end = date.fromisoformat(body["window_end"])
    assert start.month == 4 and start.day == 1  # Indian fiscal year start
    assert start < end


# ---------------------------------------------------------------------------
# Overdue recomputation
# ---------------------------------------------------------------------------
def test_refresh_marks_lapsed_entries_overdue(
    client: TestClient, session: Session, lease: Lease, monthly_rule: Obligation, today: date
):
    stale = LeaseObligation(
        lease_id=lease.id,
        obligation_id=monthly_rule.id,
        period_start=today - timedelta(days=60),
        period_end=today - timedelta(days=40),
        due_date=today - timedelta(days=25),
        status=ObligationStatus.PENDING,
    )
    session.add(stale)
    session.flush()

    response = client.post(f"{BASE}/calendar/refresh")
    assert response.status_code == 200
    assert "1 obligation(s) marked overdue" in response.json()["detail"]

    listed = client.get(
        f"{BASE}/calendar", params={"lease_id": str(lease.id), "status": "overdue"}
    ).json()
    assert any(row["id"] == str(stale.id) for row in listed["items"])


def test_refresh_leaves_future_entries_pending(
    client: TestClient, session: Session, lease: Lease, monthly_rule: Obligation, today: date
):
    upcoming = LeaseObligation(
        lease_id=lease.id,
        obligation_id=monthly_rule.id,
        period_start=today,
        period_end=today + timedelta(days=30),
        due_date=today + timedelta(days=45),
        status=ObligationStatus.PENDING,
    )
    session.add(upcoming)
    session.flush()

    client.post(f"{BASE}/calendar/refresh")
    session.refresh(upcoming)
    assert upcoming.status is ObligationStatus.PENDING


# ---------------------------------------------------------------------------
# Filing workflow
# ---------------------------------------------------------------------------
def test_submit_records_a_filing(client: TestClient, lease: Lease, monthly_rule: Obligation):
    entry = _generate(client, lease, window_start="2026-01-01", window_end="2026-01-31")[0]

    response = client.post(
        f"{BASE}/calendar/{entry['id']}/submit",
        json={
            "submitted_by": "R. Kulkarni",
            "evidence_path": "acknowledgements/2026-01.pdf",
            "notes": "Filed via state portal",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "submitted"
    assert body["submitted_by"] == "R. Kulkarni"
    assert body["submitted_at"] is not None
    assert body["evidence_path"] == "acknowledgements/2026-01.pdf"


def test_submitting_a_waived_entry_is_refused(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    entry = _generate(client, lease, window_start="2026-01-01", window_end="2026-01-31")[0]

    client.patch(
        f"{BASE}/calendar/{entry['id']}",
        json={"status": "waived", "reason": "Exempted by order"},
    )

    response = client.post(f"{BASE}/calendar/{entry['id']}/submit", json={})
    assert response.status_code == 409
    assert "reopen" in response.json()["detail"]


def test_exemption_requires_a_reason(client: TestClient, lease: Lease, monthly_rule: Obligation):
    entry = _generate(client, lease, window_start="2026-01-01", window_end="2026-01-31")[0]

    missing = client.patch(f"{BASE}/calendar/{entry['id']}", json={"status": "waived"})
    assert missing.status_code == 422

    provided = client.patch(
        f"{BASE}/calendar/{entry['id']}",
        json={"status": "waived", "reason": "Exempted under state notification 12/2026"},
    )
    assert provided.status_code == 200
    assert provided.json()["waiver_reason"].startswith("Exempted under state")


def test_reopening_an_entry_clears_its_exemption_reason(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    entry = _generate(client, lease, window_start="2026-01-01", window_end="2026-01-31")[0]

    client.patch(f"{BASE}/calendar/{entry['id']}", json={"status": "waived", "reason": "Temporary"})
    reopened = client.patch(f"{BASE}/calendar/{entry['id']}", json={"status": "pending"})

    assert reopened.status_code == 200
    assert reopened.json()["waiver_reason"] is None


def test_calendar_404s_for_an_unknown_entry(client: TestClient):
    response = client.post(f"{BASE}/calendar/00000000-0000-0000-0000-0000000000ff/submit", json={})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Lease-scoped views
# ---------------------------------------------------------------------------
def test_lease_timeline_reports_days_until_due(
    client: TestClient, lease: Lease, monthly_rule: Obligation
):
    _generate(client, lease, window_start="2026-01-01", window_end="2026-03-31")

    response = client.get(f"{BASE}/leases/{lease.id}/timeline", params={"as_of": "2026-01-20"})
    assert response.status_code == 200

    rows = response.json()
    assert rows
    first = rows[0]
    # Due 15 Feb 2026, evaluated on 20 Jan 2026.
    assert first["due_date"] == "2026-02-15"
    assert first["days_until_due"] == 26
    assert first["code"] == monthly_rule.code
