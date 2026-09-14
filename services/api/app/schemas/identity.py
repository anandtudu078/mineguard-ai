"""Schemas for identity, user administration and the audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AppRole, AuditAction, AuditEntity, AuditOutcome
from app.schemas.common import ORMModel


class PrincipalRead(BaseModel):
    """Who the caller is, and what they may do.

    The UI uses this to hide controls that would only produce a 403, and
    ``auth_enabled`` to decide whether to show the "authentication is disabled"
    warning.
    """

    user_id: str
    email: str | None = None
    label: str
    role: AppRole | None = None
    holder_id: uuid.UUID | None = None
    holder_name: str | None = None
    is_authenticated: bool
    auth_method: str
    #: False when the server is running with AUTH_MODE=disabled.
    auth_enabled: bool
    permissions: list[str] = Field(default_factory=list)
    #: True for an operator whose account has no organisation linked, which is
    #: why their register would be empty.
    operator_without_scope: bool = False


class AppUserRead(ORMModel):
    id: uuid.UUID
    email: str | None
    full_name: str | None
    role: AppRole
    holder_id: uuid.UUID | None
    is_active: bool
    last_seen_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AppUserCreate(BaseModel):
    """Pre-provision a user before they first sign in.

    ``id`` is the Supabase user id - Supabase is the identity provider, so the
    caller has to supply the id it issued rather than this API inventing one.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(description="The Supabase user id (the token's 'sub' claim)")
    #: Plain string rather than EmailStr: Supabase is the authority on whether an
    #: address is valid, and adding a validator dependency for one admin field
    #: would not buy anything the identity provider has not already enforced.
    email: str | None = Field(default=None, max_length=320)
    full_name: str | None = Field(default=None, max_length=200)
    role: AppRole = AppRole.OPERATOR
    holder_id: uuid.UUID | None = None
    notes: str | None = None


class AppUserInvite(BaseModel):
    """Invite a colleague: sends the Supabase invite and provisions the profile.

    One call instead of two so an admin can never end up with a Supabase
    account that has no role, or a role that has no way to sign in.
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    full_name: str | None = Field(default=None, max_length=200)
    role: AppRole = AppRole.OPERATOR
    holder_id: uuid.UUID | None = None
    notes: str | None = None


class AppUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    role: AppRole | None = None
    holder_id: uuid.UUID | None = None
    is_active: bool | None = None
    notes: str | None = None


class AuditLogRead(ORMModel):
    id: uuid.UUID
    occurred_at: datetime

    actor_id: str
    actor_email: str | None
    actor_label: str | None
    actor_role: str | None
    auth_method: str

    action: AuditAction
    outcome: AuditOutcome
    summary: str

    entity_type: AuditEntity
    entity_id: str | None
    entity_label: str | None

    changed_fields: list[str]
    context: dict[str, Any] | None

    http_method: str | None
    http_path: str | None
    http_status: int | None
    ip_address: str | None
    user_agent: str | None


class AuditSummary(BaseModel):
    """Outcome counts for the audit page header."""

    succeeded: int
    denied: int
    failed: int
    total: int
