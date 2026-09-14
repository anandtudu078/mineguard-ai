"""Minimal Supabase Auth admin client.

Only what the invite flow needs. Uses the service-role key, which bypasses
Row Level Security and must therefore never leave the server: tests
monkeypatch :func:`invite_user` directly, so nothing here touches HTTP in
the suite.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INVITE_TIMEOUT_SECONDS = 15.0


class SupabaseAdminError(RuntimeError):
    """The Supabase admin API rejected or could not be reached for a call."""


def _admin_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise SupabaseAdminError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured; user invites cannot be sent"
        )
    if not settings.supabase_url:
        raise SupabaseAdminError("SUPABASE_URL is not configured; user invites cannot be sent")
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def invite_user(email: str, redirect_to: str) -> str:
    """Create the Supabase user and send the invite email; return their id.

    Supabase's ``POST /auth/v1/admin/invite`` creates the ``auth.users`` row
    immediately and emails a link the recipient follows to set a password.
    ``redirect_to`` is where that link lands in this app.

    Returns the Supabase user id so the caller can provision the matching
    ``app_users`` profile. Raises :class:`SupabaseAdminError` on any failure,
    including a response without the id the caller needs.
    """
    base = settings.supabase_url or ""
    url = f"{base.rstrip('/')}/auth/v1/admin/invite"
    try:
        response = httpx.post(
            url,
            headers=_admin_headers(),
            json={"email": email, "redirect_to": redirect_to},
            timeout=INVITE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as error:
        raise SupabaseAdminError(f"Could not reach Supabase Auth: {error}") from error

    if response.status_code >= 400:
        detail = response.text[:200]
        logger.warning("Supabase invite for %s failed: %s %s", email, response.status_code, detail)
        raise SupabaseAdminError(
            f"Supabase rejected the invite ({response.status_code}): {detail}"
        )

    payload: Any = response.json() if response.content else {}
    user_id = payload.get("id") if isinstance(payload, dict) else None
    if not user_id:
        raise SupabaseAdminError("Supabase accepted the invite but returned no user id")
    return str(user_id)
