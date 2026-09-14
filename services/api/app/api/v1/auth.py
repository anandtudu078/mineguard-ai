"""Identity endpoints.

The API deliberately does not implement sign-in. Supabase Auth owns credentials
-you sign in against Supabase, receive its token, and present it here. This
router answers the two questions the client then has: *who am I now*, and *has
this sign-in been recorded*.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.deps import AuditCtx, CurrentPrincipal, DbSession
from app.core.config import settings
from app.models.enums import AuditAction, AuditEntity
from app.models.holder import LeaseHolder
from app.schemas.identity import PrincipalRead
from app.services import audit
from app.services.authorization import permission_summary

router = APIRouter(prefix="/auth", tags=["auth"])


def _principal_payload(session: Session, principal) -> PrincipalRead:
    holder_name = None
    if principal.holder_id is not None:
        holder = session.get(LeaseHolder, principal.holder_id)
        holder_name = holder.name if holder else None

    return PrincipalRead(
        user_id=principal.user_id,
        email=principal.email,
        label=principal.display,
        role=principal.role,
        holder_id=principal.holder_id,
        holder_name=holder_name,
        is_authenticated=principal.is_authenticated,
        auth_method=principal.auth_method,
        auth_enabled=settings.auth_enabled,
        permissions=permission_summary(principal),
        operator_without_scope=principal.is_scoped_to_holder and principal.holder_id is None,
    )


@router.get("/me", response_model=PrincipalRead, summary="Who am I")
def read_principal(session: DbSession, principal: CurrentPrincipal) -> PrincipalRead:
    """Resolve the caller's identity, role and capabilities."""
    return _principal_payload(session, principal)


@router.post("/session", response_model=PrincipalRead, summary="Record a sign-in")
def record_session(
    session: DbSession, principal: CurrentPrincipal, context: AuditCtx
) -> PrincipalRead:
    """Write a sign-in to the audit trail.

    Called by the client straight after Supabase accepts the credentials. Kept
    separate from token verification on purpose: a token is presented on every
    request, and recording a "login" for each one would drown the trail in noise.
    """
    audit.record(
        session,
        principal,
        context,
        action=AuditAction.LOGIN,
        entity_type=AuditEntity.SESSION,
        entity_id=principal.user_id,
        entity_label=principal.display,
        summary=f"{principal.display} signed in.",
        context_extra={"auth_method": principal.auth_method},
    )
    session.commit()
    return _principal_payload(session, principal)
