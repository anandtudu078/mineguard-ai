"""Aggregate router for API version 1."""

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    calendar,
    dashboard,
    findings,
    leases,
    licences,
    obligations,
    reference,
    users,
)

api_router = APIRouter()

# Identity first: everything else assumes a signed-in caller.
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
api_router.include_router(reference.router)
api_router.include_router(leases.router)
api_router.include_router(licences.router)
api_router.include_router(obligations.router)
api_router.include_router(calendar.router)
api_router.include_router(findings.router)
