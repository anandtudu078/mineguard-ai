"""Tests for provider-neutral reminder preparation."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.core.config import Settings
from app.models.lease import Lease
from app.schemas.reminder import ReminderPreview
from app.services.reminders import send_reminders

BASE = "/api/v1"


def test_reminder_preview_builds_plain_language_message(client, lease: Lease, monthly_rule):
    generated = client.post(
        f"{BASE}/leases/{lease.id}/obligations/generate",
        json={"window_start": "2026-08-01", "window_end": "2026-08-31"},
    )
    assert generated.status_code == 201, generated.text

    response = client.get(
        f"{BASE}/calendar/reminders/preview",
        params={"as_of": date(2026, 9, 14).isoformat(), "days": 30},
    )

    assert response.status_code == 200, response.text
    reminders = response.json()
    assert len(reminders) == 1
    assert reminders[0]["kind"] == "upcoming"
    assert reminders[0]["site_name"] == lease.name
    assert "is due on 15 Sep 2026" in reminders[0]["message"]

    send_response = client.post(
        f"{BASE}/calendar/reminders/send",
        params={"as_of": "2026-09-14"},
        json={"dry_run": True, "days": 30},
    )
    assert send_response.status_code == 200, send_response.text
    assert send_response.json()["prepared"] == 1
    assert send_response.json()["skipped"] == 1

    history_response = client.get(f"{BASE}/calendar/reminders/history")
    assert history_response.status_code == 200, history_response.text
    assert history_response.json()[0]["status"] == "skipped"


def test_send_reminders_uses_resend(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "email-123"})

    monkeypatch.setattr("app.services.reminders.httpx.post", fake_post)
    reminder = ReminderPreview(
        obligation_id="00000000-0000-0000-0000-000000000001",
        lease_id="00000000-0000-0000-0000-000000000002",
        site_name="Test site",
        site_number="ML/TEST/1",
        title="Monthly return",
        due_date=date(2026, 9, 15),
        days_until_due=1,
        kind="upcoming",
        message="Please file the monthly return.",
        recipient_email="operator@example.com",
    )

    result = send_reminders(
        [reminder],
        settings=Settings(
            resend_api_key="test-key",
            resend_from_email="compliance@example.com",
        ),
        dry_run=False,
    )

    assert result[:3] == (1, 0, 0)
    assert calls[0][0] == "https://api.resend.com/emails"
    assert calls[0][1]["json"]["to"] == ["operator@example.com"]
