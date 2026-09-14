"""Tests for authentication token verification and identity management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    DEV_PRINCIPAL,
    TokenClaims,
    TokenError,
    verify_token,
)
from app.models.enums import AppRole
from app.models.user import AppUser
from app.services import users as user_service


def _mint_test_token(
    payload: dict[str, Any],
    secret: str = "test-secret-at-least-32-bytes-long-for-hs256",
    algorithm: str = "HS256",
) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def test_jwt_secret(monkeypatch) -> str:
    secret = "test-secret-at-least-32-bytes-long-for-hs256"
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    monkeypatch.setattr(settings, "supabase_url", "https://testproj.supabase.co")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", None)
    return secret


def test_verify_token_symmetric_with_supabase_issuer(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "tester@example.com",
        "aud": "authenticated",
        "iss": "supabase",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {"full_name": "Test User"},
    }
    token = _mint_test_token(payload, test_jwt_secret)
    claims = verify_token(token)

    assert claims.subject == user_id
    assert claims.email == "tester@example.com"
    assert claims.display_name == "Test User"
    assert claims.supabase_role == "authenticated"


def test_verify_token_symmetric_with_project_url_issuer(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "operator@example.com",
        "aud": "authenticated",
        "iss": "https://testproj.supabase.co/auth/v1",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "app_metadata": {"name": "Operator Person"},
    }
    token = _mint_test_token(payload, test_jwt_secret)
    claims = verify_token(token)

    assert claims.subject == user_id
    assert claims.email == "operator@example.com"
    assert claims.display_name == "Operator Person"


def test_verify_token_rejects_unexpected_issuer(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "attacker@example.com",
        "aud": "authenticated",
        "iss": "https://evil.example.com/auth/v1",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = _mint_test_token(payload, test_jwt_secret)

    with pytest.raises(TokenError) as exc_info:
        verify_token(token)
    assert "unexpected issuer" in exc_info.value.message.lower()


def test_verify_token_rejects_expired_token(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "expired@example.com",
        "aud": "authenticated",
        "iss": "supabase",
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    token = _mint_test_token(payload, test_jwt_secret)

    with pytest.raises(TokenError) as exc_info:
        verify_token(token)
    assert exc_info.value.expired
    assert "expired" in exc_info.value.message.lower()


def test_verify_token_rejects_invalid_signature(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "wrongsig@example.com",
        "aud": "authenticated",
        "iss": "supabase",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = _mint_test_token(payload, secret="completely-different-signing-key-32b")

    with pytest.raises(TokenError) as exc_info:
        verify_token(token)
    assert "signature is not valid" in exc_info.value.message.lower()


def test_verify_token_rejects_wrong_audience(test_jwt_secret: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": "wrongaud@example.com",
        "aud": "anon",
        "iss": "supabase",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = _mint_test_token(payload, test_jwt_secret)

    with pytest.raises(TokenError) as exc_info:
        verify_token(token)
    assert "audience" in exc_info.value.message.lower()


def test_resolve_principal_bootstraps_first_user(session: Session):
    user_id = uuid.uuid4()
    claims = TokenClaims(
        subject=str(user_id),
        email="firstadmin@example.com",
        metadata={"full_name": "First Admin"},
    )
    principal = user_service.resolve_principal(session, claims)

    assert principal.user_id == str(user_id)
    assert principal.email == "firstadmin@example.com"
    assert principal.role == AppRole.ADMIN
    assert principal.is_admin
    assert principal.has_profile


def test_resolve_principal_refuses_unprovisioned_subsequent_user(session: Session):
    first_id = uuid.uuid4()
    first_claims = TokenClaims(
        subject=str(first_id),
        email="first@example.com",
    )
    user_service.resolve_principal(session, first_claims)

    second_id = uuid.uuid4()
    second_claims = TokenClaims(
        subject=str(second_id),
        email="stranger@example.com",
    )
    with pytest.raises(user_service.UnprovisionedIdentityError):
        user_service.resolve_principal(session, second_claims)


def test_resolve_principal_self_registers_when_enabled(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "self_registration_enabled", True)
    monkeypatch.setattr(settings, "self_registration_role", "inspector")

    first_id = uuid.uuid4()
    user_service.resolve_principal(
        session,
        TokenClaims(subject=str(first_id), email="first@example.com"),
    )

    second_id = uuid.uuid4()
    principal = user_service.resolve_principal(
        session,
        TokenClaims(
            subject=str(second_id),
            email="walkin@example.com",
            metadata={"full_name": "Walk-in User"},
        ),
    )

    assert principal.role is AppRole.INSPECTOR
    assert principal.has_profile
    stored = session.get(AppUser, second_id)
    assert stored is not None
    assert stored.role is AppRole.INSPECTOR
    assert "Self-registered" in (stored.notes or "")


def test_resolve_principal_self_registration_honours_custom_role(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "self_registration_enabled", True)
    monkeypatch.setattr(settings, "self_registration_role", "operator")

    user_id = uuid.uuid4()
    principal = user_service.resolve_principal(
        session,
        TokenClaims(subject=str(user_id), email="first@example.com"),
    )

    # Empty register: bootstrap wins, and BOOTSTRAP_ROLE still applies.
    assert principal.role is AppRole.ADMIN


def test_resolve_principal_refuses_when_self_registration_disabled(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "self_registration_enabled", False)

    first_id = uuid.uuid4()
    user_service.resolve_principal(
        session,
        TokenClaims(subject=str(first_id), email="first@example.com"),
    )

    second_id = uuid.uuid4()
    with pytest.raises(user_service.UnprovisionedIdentityError):
        user_service.resolve_principal(
            session,
            TokenClaims(subject=str(second_id), email="stranger@example.com"),
        )


def test_resolve_principal_self_registration_falls_back_on_bad_role(
    session: Session, monkeypatch
):
    monkeypatch.setattr(settings, "self_registration_enabled", True)
    monkeypatch.setattr(settings, "self_registration_role", "wizard")

    first_id = uuid.uuid4()
    user_service.resolve_principal(
        session,
        TokenClaims(subject=str(first_id), email="first@example.com"),
    )

    second_id = uuid.uuid4()
    principal = user_service.resolve_principal(
        session,
        TokenClaims(subject=str(second_id), email="walkin@example.com"),
    )

    assert principal.role is AppRole.INSPECTOR


def test_resolve_principal_refuses_inactive_user(session: Session):
    user_id = uuid.uuid4()
    user = AppUser(
        id=user_id,
        email="disabled@example.com",
        role=AppRole.INSPECTOR,
        is_active=False,
    )
    session.add(user)
    session.commit()

    claims = TokenClaims(
        subject=str(user_id),
        email="disabled@example.com",
    )
    with pytest.raises(user_service.InactiveIdentityError):
        user_service.resolve_principal(session, claims)


def test_auth_me_when_auth_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "disabled")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == DEV_PRINCIPAL.user_id
    assert data["auth_enabled"] is False
    assert data["role"] == "admin"


def test_auth_endpoints_with_valid_bearer_token(
    client: TestClient, session: Session, test_jwt_secret: str
):
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": "bootstrapped@example.com",
        "aud": "authenticated",
        "iss": "supabase",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "user_metadata": {"name": "Admin Tester"},
    }
    token = _mint_test_token(payload, test_jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me boots first admin and returns profile
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user_id"] == str(user_id)
    assert me_data["email"] == "bootstrapped@example.com"
    assert me_data["auth_enabled"] is True
    assert me_data["role"] == "admin"

    # /auth/session records audit login
    session_res = client.post("/api/v1/auth/session", headers=headers)
    assert session_res.status_code == 200
    assert session_res.json()["user_id"] == str(user_id)
