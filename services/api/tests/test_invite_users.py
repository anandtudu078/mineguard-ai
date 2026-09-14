"""Tests for the admin invite flow.

``invite_user`` (the Supabase admin call) is monkeypatched, so these tests
exercise the endpoint's policy — admin-only, profile keyed to the Supabase id,
email failure leaves no residue — without touching the network.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.supabase_admin import SupabaseAdminError
from app.models.enums import AppRole
from app.models.user import AppUser

BASE = "/api/v1"

SECRET = "test-secret-at-least-32-bytes-long-for-hs256"


def _mint(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def admin_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://testproj.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", None)
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    token = _mint(
        {
            "sub": str(user_id),
            "email": "inviter@example.com",
            "aud": "authenticated",
            "iss": "supabase",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_invite(monkeypatch) -> dict[str, str]:
    """Replace the Supabase call with a stub that records and succeeds."""
    issued_id = str(uuid.uuid4())
    calls: dict[str, str] = {"issued_id": issued_id}

    def _fake(email: str, redirect_to: str) -> str:
        calls["email"] = email
        calls["redirect_to"] = redirect_to
        return issued_id

    monkeypatch.setattr("app.api.v1.users.invite_user", _fake)
    return calls


def test_invite_provisions_profile_with_supabase_id(
    client: TestClient,
    admin_headers: dict[str, str],
    fake_invite: dict[str, str],
    holder,
):
    response = client.post(
        f"{BASE}/users/invite",
        headers=admin_headers,
        json={
            "email": "New.Operator@Example.com",
            "full_name": "New Operator",
            "role": "operator",
            "holder_id": str(holder.id),
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    # The profile id is the id Supabase issued, and the email is normalised.
    assert body["id"] == fake_invite["issued_id"]
    assert body["email"] == "new.operator@example.com"
    assert fake_invite["email"] == "new.operator@example.com"
    assert fake_invite["redirect_to"] == settings.invite_redirect_url


def test_invite_operator_without_holder_is_rejected(
    client: TestClient, admin_headers: dict[str, str], fake_invite: dict[str, str]
):
    response = client.post(
        f"{BASE}/users/invite",
        headers=admin_headers,
        json={"email": "scopeless@example.com", "role": "operator"},
    )
    assert response.status_code == 422
    assert "lease holder" in response.json()["detail"]


def test_invite_requires_admin(
    client: TestClient, session: Session, monkeypatch
):
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://testproj.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", None)

    inspector_id = uuid.uuid4()
    session.add(
        AppUser(id=inspector_id, email="inspector@example.com", role=AppRole.INSPECTOR)
    )
    session.commit()

    now = datetime.now(UTC)
    token = _mint(
        {
            "sub": str(inspector_id),
            "email": "inspector@example.com",
            "aud": "authenticated",
            "iss": "supabase",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
    )

    response = client.post(
        f"{BASE}/users/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "someone@example.com"},
    )
    assert response.status_code == 403


def test_invite_failure_leaves_no_profile(
    client: TestClient, session: Session, admin_headers: dict[str, str], monkeypatch
):
    def _boom(email: str, redirect_to: str) -> str:
        raise SupabaseAdminError("Supabase rejected the invite (422): bad email")

    monkeypatch.setattr("app.api.v1.users.invite_user", _boom)

    response = client.post(
        f"{BASE}/users/invite",
        headers=admin_headers,
        json={"email": "doomed@example.com", "role": "inspector"},
    )
    assert response.status_code == 502
    assert "rejected the invite" in response.json()["detail"]

    remaining = session.scalars(
        select(AppUser).where(AppUser.email == "doomed@example.com")
    ).all()
    assert remaining == []
