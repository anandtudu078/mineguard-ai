"""Dashboard endpoints: the portfolio rollup that opens the product."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AppSettings, AsOfDate, DbSession
from app.schemas.compliance import DashboardSummary
from app.services.dashboard import summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Portfolio compliance summary",
)
def dashboard_summary(
    session: DbSession,
    settings: AppSettings,
    as_of: AsOfDate,
    warning_days: Annotated[
        int | None,
        Query(ge=1, le=365, description="Clearance expiry horizon; defaults to configuration"),
    ] = None,
) -> DashboardSummary:
    payload = summary(
        session,
        as_of,
        warning_days=warning_days or settings.licence_expiry_warning_days,
    )
    return DashboardSummary.model_validate(payload)
