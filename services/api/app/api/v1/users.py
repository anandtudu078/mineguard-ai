"""User administration.

Role assignment is the only thing here that grants access, so every endpoint is
admin-only and every change is audited. Accounts themselves are created in
Supabase; these endpoints pre-provision the application profile for a Supabase
user id, so an administrator can set somebody up before their first sign-in.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuditCtx, CurrentPrincipal, DbSession
from app.core.permissions import Permission
from app.models.enums import AppRole, AuditAction, AuditEntity
from app.models.holder import LeaseHolder
from app.models.user import AppUser
from app.schemas.identity import AppUserCreate, AppUserRead, AppUserUpdate
from app.services import audit, users as user_service
from app.services.authorization import require_permission

router = APIRouter(prefix="/users", tags=["users"])


def _require_admin(session: Session, principal, context) -> None:
    require_permission(
        session,
        principal,
        context,
        Permission.USER_MANAGE,
        entity_type=AuditEntity.USER,
        entity_id=principal.user_id,
        entity_label=principal.display,
    )


def _check_holder(session: Session, holder_id: uuid.UUID | None) -> None:
    if holder_id is not None and session.get(LeaseHolder, holder_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown holder_id")


@router.get("", response_model=list[AppUserRead], summary="List users")
def list_users(
    session: DbSession,
    principal: CurrentPrincipal,
    context: AuditCtx,
    role: Annotated[AppRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[AppUserRead]:
    _require_admin(session, principal, context)
    rows = user_service.list_users(session, role=role, is_active=is_active)
    return [AppUserRead.model_validate(row) for row in rows]


@router.post(
    "",
    response_model=AppUserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Pre-provision a user",
)
def create_user(
    payload: AppUserCreate,
    session: DbSession,
    principal: CurrentPrincipal,
    context: AuditCtx,
) -> AppUserRead:
    """Create the profile for a Supabase user id ahead of their first sign-in."""
    _require_admin(session, principal, context)
    _check_holder(session, payload.holder_id)

    try:
        user_service.validate_operator_scope(payload.role, payload.holder_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    if session.get(AppUser, payload.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That user id already has a profile")

    user = AppUser(
        id=payload.id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        holder_id=payload.holder_id,
        notes=payload.notes,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That user id already has a profile"
        ) from error

    audit.record(
        session,
        principal,
        context,
        action=AuditAction.CREATE,
        entity_type=AuditEntity.USER,
        entity_id=user.id,
        entity_label=user.email or str(user.id),
        summary=(
            f"Provisioned {user.email or user.id} as {user.role}."
            + (f" Scoped to holder {user.holder_id}." if user.holder_id else "")
        ),
        changed_fields=("role", "holder_id", "email", "full_name"),
    )
    session.commit()
    session.refresh(user)
    return AppUserRead.model_validate(user)


@router.patch("/{user_id}", response_model=AppUserRead, summary="Change a user's role or scope")
def update_user(
    user_id: uuid.UUID,
    payload: AppUserUpdate,
    session: DbSession,
    principal: CurrentPrincipal,
    context: AuditCtx,
) -> AppUserRead:
    _require_admin(session, principal, context)

    user = session.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    new_role = payload.role if payload.role is not None else user.role
    new_holder = payload.holder_id if "holder_id" in payload.model_fields_set else user.holder_id
    new_active = payload.is_active if payload.is_active is not None else user.is_active

    _check_holder(session, new_holder)
    try:
        user_service.validate_operator_scope(new_role, new_holder)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    try:
        user_service.assert_admin_survives(session, user, new_role, new_active)
    except user_service.LastAdminError as error:
        # A refusal on the user list rather than a permission: worth recording,
        # since it is a deliberate attempt to change who can administer the system.
        audit.record_denied(
            session,
            principal,
            context,
            action=AuditAction.ACCESS_DENIED,
            entity_type=AuditEntity.USER,
            entity_id=user.id,
            entity_label=user.email or str(user.id),
            summary=f"Refused edit of {user.email or user.id}: {error}",
        )
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    changed: list[str] = []
    if payload.full_name is not None and payload.full_name != user.full_name:
        user.full_name = payload.full_name
        changed.append("full_name")
    if new_role != user.role:
        user.role = new_role
        changed.append("role")
    if new_holder != user.holder_id:
        user.holder_id = new_holder
        changed.append("holder_id")
    if new_active != user.is_active:
        user.is_active = new_active
        changed.append("is_active")
    if payload.notes is not None and payload.notes != user.notes:
        user.notes = payload.notes
        changed.append("notes")

    if changed:
        audit.record(
            session,
            principal,
            context,
            action=AuditAction.UPDATE,
            entity_type=AuditEntity.USER,
            entity_id=user.id,
            entity_label=user.email or str(user.id),
            summary=f"Updated user {user.email or user.id}: {', '.join(changed)}.",
            changed_fields=changed,
        )
    session.commit()
    session.refresh(user)
    return AppUserRead.model_validate(user)
