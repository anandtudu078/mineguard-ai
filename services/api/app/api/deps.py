"""Shared FastAPI dependencies."""

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.security import DEV_PRINCIPAL, Principal, TokenError, verify_token
from app.services import users as user_service
from app.services.audit import AuditContext

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

#: Header a client must present. Kept plain ``Bearer`` so the frontend and any
#: HTTP tool can both use it without special handling.
BEARER_PREFIX = "bearer "


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith(BEARER_PREFIX):
        return None
    token = header[len(BEARER_PREFIX) :].strip()
    return token or None


def get_principal(request: Request, session: DbSession, settings: AppSettings) -> Principal:
    """Resolve the caller, or refuse the request.

    The result is also stashed on ``request.state`` so error handlers can name
    who was denied, without every handler re-doing the verification.
    """
    if not settings.auth_enabled:
        request.state.principal = DEV_PRINCIPAL
        return DEV_PRINCIPAL

    token = _bearer_token(request)
    if token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to use this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_token(token)
    except TokenError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            error.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    # Raises IdentityError, which ``main`` turns into a 403 naming the problem.
    principal = user_service.resolve_principal(session, claims)
    request.state.principal = principal

    # A verified user with no profile holds no permissions. Refusing here rather
    # than letting every endpoint deny separately keeps the message the same.
    if not principal.has_profile:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your account has no role assigned yet. Ask an administrator.",
        )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def get_audit_context(request: Request) -> AuditContext:
    """Capture the request details every audit entry records."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip()
    elif request.client is not None:
        ip_address = request.client.host
    else:
        ip_address = None

    return AuditContext(
        method=request.method,
        path=request.url.path,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )


AuditCtx = Annotated[AuditContext, Depends(get_audit_context)]


class Pagination:
    """Validated offset pagination parameters."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200, description="Page size")] = 50,
        offset: Annotated[int, Query(ge=0, description="Rows to skip")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends()]


def as_of_date(
    as_of: Annotated[
        date | None,
        Query(description="Evaluate compliance as at this date. Defaults to today."),
    ] = None,
) -> date:
    """Resolve the evaluation date, defaulting to today.

    Exposing this matters: an auditor needs to ask "what did this look like on
    31 March" and get the same answer the system gave then.
    """
    return as_of or date.today()


AsOfDate = Annotated[date, Depends(as_of_date)]


def conflict(detail: str) -> HTTPException:
    """Build a 409 for uniqueness violations."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def is_unique_violation(error: IntegrityError) -> bool:
    """Whether an IntegrityError is a unique-constraint failure."""
    return getattr(getattr(error, "orig", None), "sqlstate", None) == "23505"
