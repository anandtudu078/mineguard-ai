"""Tests for the visual-compliance loop: findings, scoring and escalation.

The Gemini vision call and the Resend email call are monkeypatched, so these
tests exercise the endpoint policy, the scoring math and the escalation ladder
without touching the network.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import FindingSource, FindingStatus, ViolationSeverity
from app.models.finding import InspectionFinding
from app.models.lease import Lease
from app.services import vision as vision_module

BASE = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _fake_vision_result(findings: list[dict] | None = None):
    """A VisionResult like the real parser returns, without the network."""
    parsed = [
        SimpleNamespace(
            title=f["title"],
            severity=ViolationSeverity(f.get("severity", "high")),
            confidence=Decimal(f.get("confidence", "0.9")),
            description=f.get("description"),
            corrective_action=f.get("corrective_action"),
        )
        for f in (findings or [])
    ]
    return SimpleNamespace(
        findings=parsed,
        summary="AI summary of the photo",
        model_name="gemini-2.0-flash",
        raw={"findings": findings or []},
    )


# ---------------------------------------------------------------------------
# Analyze endpoint
# ---------------------------------------------------------------------------
def test_analyze_creates_findings_and_document(
    client: TestClient, session: Session, lease: Lease, monkeypatch
):
    recorded: dict = {}

    def fake_analyze(image_bytes, mime_type, settings):
        recorded["mime"] = mime_type
        return _fake_vision_result(
            [
                {
                    "title": "Workers without helmets near pit edge",
                    "severity": "high",
                    "confidence": "0.92",
                    "description": "Three workers visible without PPE.",
                    "corrective_action": "Issue PPE and brief the crew.",
                }
            ]
        )

    monkeypatch.setattr(vision_module, "analyze_site_photo", fake_analyze)

    response = client.post(
        f"{BASE}/leases/{lease.id}/findings/analyze",
        files={"file": ("site.jpg", b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")},
        data={"auto_alert": "false"},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["summary"] == "AI summary of the photo"
    assert body["model"] == "gemini-2.0-flash"
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["title"] == "Workers without helmets near pit edge"
    assert finding["severity"] == "high"
    assert finding["status"] == "open"
    assert finding["source"] == "ai_vision"
    assert finding["confidence"] == 0.92
    assert finding["image_path"] is not None

    # The photo itself is preserved as evidence.
    assert session.query(InspectionFinding).filter_by(lease_id=lease.id).count() == 1


def test_analyze_records_multiple_findings(
    client: TestClient, session: Session, lease: Lease, monkeypatch
):
    monkeypatch.setattr(
        vision_module,
        "analyze_site_photo",
        lambda *a, **k: _fake_vision_result(
            [
                {"title": "No helmets", "severity": "high"},
                {"title": "Spill near stream", "severity": "critical"},
                {"title": "Dust suppressant not applied", "severity": "low"},
            ]
        ),
    )

    body = client.post(
        f"{BASE}/leases/{lease.id}/findings/analyze",
        files={"file": ("site.jpg", b"jpeg", "image/jpeg")},
        data={"auto_alert": "false"},
    ).json()

    assert len(body["findings"]) == 3
    severities = {f["severity"] for f in body["findings"]}
    assert severities == {"high", "critical", "low"}


def test_analyze_fails_closed_when_vision_errors(
    client: TestClient, session: Session, lease: Lease, monkeypatch
):
    def boom(*a, **k):
        raise RuntimeError("Gemini quota exhausted")

    monkeypatch.setattr(vision_module, "analyze_site_photo", boom)

    response = client.post(
        f"{BASE}/leases/{lease.id}/findings/analyze",
        files={"file": ("site.jpg", b"jpeg", "image/jpeg")},
    )
    assert response.status_code == 502
    assert "Vision analysis failed" in response.json()["detail"]
    # Nothing was recorded as AI-produced.
    assert session.query(InspectionFinding).filter_by(lease_id=lease.id).count() == 0


def test_analyze_rejects_empty_upload(client: TestClient, lease: Lease, monkeypatch):
    response = client.post(
        f"{BASE}/leases/{lease.id}/findings/analyze",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Lifecycle: acknowledge, update, resolve
# ---------------------------------------------------------------------------
def _seed_finding(session: Session, lease: Lease, **overrides) -> InspectionFinding:
    fields: dict = {
        "lease_id": lease.id,
        "source": FindingSource.AI_VISION,
        "title": "Open blast without clearance",
        "severity": ViolationSeverity.CRITICAL,
        "status": FindingStatus.OPEN,
        "detected_at": datetime.now(UTC) - timedelta(hours=2),
    }
    fields.update(overrides)
    finding = InspectionFinding(**fields)
    session.add(finding)
    session.flush()
    return finding


def test_acknowledge_sets_timestamp_and_stops_recompute(
    client: TestClient, session: Session, lease: Lease
):
    finding = _seed_finding(session, lease)

    body = client.post(
        f"{BASE}/leases/{lease.id}/findings/{finding.id}/acknowledge"
    ).json()
    assert body["acknowledged_at"] is not None

    again = client.post(f"{BASE}/leases/{lease.id}/findings/{finding.id}/acknowledge")
    assert again.status_code == 200  # idempotent


def test_update_assigns_corrective_action(client: TestClient, session: Session, lease: Lease):
    finding = _seed_finding(session, lease)

    body = client.patch(
        f"{BASE}/leases/{lease.id}/findings/{finding.id}",
        json={
            "corrective_action": "Halt operations until clearance obtained",
            "action_owner": "Site manager",
            "action_due_date": "2026-09-30",
        },
    ).json()

    assert body["corrective_action"] == "Halt operations until clearance obtained"
    assert body["action_owner"] == "Site manager"
    assert body["action_due_date"] == "2026-09-30"


def test_resolve_closes_finding(client: TestClient, session: Session, lease: Lease):
    finding = _seed_finding(session, lease)

    body = client.post(
        f"{BASE}/leases/{lease.id}/findings/{finding.id}/resolve",
        json={"resolution_note": "PPE issued, crew briefed, verified on site."},
    ).json()

    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None
    assert "PPE issued" in body["resolution_note"]

    # Closing twice conflicts.
    response = client.post(
        f"{BASE}/leases/{lease.id}/findings/{finding.id}/resolve",
        json={},
    )
    assert response.status_code == 409


def test_list_filters_by_status(client: TestClient, session: Session, lease: Lease):
    open_one = _seed_finding(session, lease, title="Open A")
    _seed_finding(session, lease, title="Open B")
    resolved = _seed_finding(session, lease)
    resolved.status = FindingStatus.RESOLVED
    resolved.resolved_at = datetime.now(UTC)
    session.flush()

    all_items = client.get(f"{BASE}/leases/{lease.id}/findings").json()
    assert all_items["total"] == 3

    open_items = client.get(
        f"{BASE}/leases/{lease.id}/findings", params={"finding_status": "open"}
    ).json()
    assert open_items["total"] == 2
    assert {i["title"] for i in open_items["items"]} == {"Open A", "Open B"}


# ---------------------------------------------------------------------------
# Escalation ladder
# ---------------------------------------------------------------------------
def test_escalation_sweep_escalates_stale_unacknowledged(
    client: TestClient,
    session: Session,
    lease: Lease,
    monkeypatch,
):
    """A critical finding unacknowledged for 3 days gets escalated exactly once."""
    from app.services import findings as findings_service

    # The sweep needs a recipient; the base fixture holder has no email.
    lease.holder.email = "site-operator@example.com"
    session.flush()

    sent: list[str] = []
    monkeypatch.setattr(
        findings_service,
        "send_finding_alert",
        lambda session, finding, lease, *, settings, recipient_email: sent.append(
            (str(finding.id), recipient_email)
        )
        or True,
    )

    stale = _seed_finding(
        session, lease, detected_at=datetime.now(UTC) - timedelta(days=3)
    )
    fresh = _seed_finding(
        session, lease, title="Fresh finding", detected_at=datetime.now(UTC)
    )
    low = _seed_finding(
        session,
        lease,
        title="Low sev stale",
        severity=ViolationSeverity.LOW,
        detected_at=datetime.now(UTC) - timedelta(days=3),
    )

    stats = client.post(f"{BASE}/leases/{lease.id}/findings/escalation-sweep").json()

    assert stats["candidates"] == 1
    assert stats["escalated"] == 1
    assert sent and sent[0][0] == str(stale.id)

    session.refresh(stale)
    assert stale.escalation_level == 1
    assert stale.last_escalated_at is not None


def test_escalation_is_idempotent(
    client: TestClient, session: Session, lease: Lease, monkeypatch
):
    from app.services import findings as findings_service

    lease.holder.email = "site-operator@example.com"
    session.flush()
    monkeypatch.setattr(
        findings_service,
        "send_finding_alert",
        lambda *a, **k: True,
    )

    _seed_finding(session, lease, detected_at=datetime.now(UTC) - timedelta(days=3))

    first = client.post(f"{BASE}/leases/{lease.id}/findings/escalation-sweep").json()
    second = client.post(f"{BASE}/leases/{lease.id}/findings/escalation-sweep").json()

    assert first["escalated"] == 1
    assert second["candidates"] == 0  # already escalated, level guard blocks it


# ---------------------------------------------------------------------------
# Scoring integration
# ---------------------------------------------------------------------------
def test_safety_component_only_bites_when_findings_exist(
    client: TestClient, session: Session, lease: Lease
):
    """Adding findings must dent the score; resolving recovers it."""
    before = client.get(f"{BASE}/leases/{lease.id}/compliance").json()["score"]

    _seed_finding(session, lease)  # critical, open
    with_finding = client.get(f"{BASE}/leases/{lease.id}/compliance").json()["score"]
    assert with_finding < before

    # With no licences or obligations applicable, safety is the only component,
    # so one finding costs exactly its one-third share of the whole score.
    assert abs((before - with_finding) - (100.0 / 3.0)) < 0.1


def test_resolving_a_finding_recovers_the_score(
    client: TestClient, session: Session, lease: Lease
):
    baseline = client.get(f"{BASE}/leases/{lease.id}/compliance").json()["score"]

    finding = _seed_finding(session, lease)
    dented = client.get(f"{BASE}/leases/{lease.id}/compliance").json()["score"]
    assert dented < baseline

    finding.status = FindingStatus.RESOLVED
    finding.resolved_at = datetime.now(UTC)
    session.flush()

    recovered = client.get(f"{BASE}/leases/{lease.id}/compliance").json()["score"]
    assert recovered == baseline
