"""Statutory calendar arithmetic and obligation materialisation.

Scheduling is derived, never hardcoded. An obligation rule says "due N days
after the reporting period ends", and the fiscal year end month is data, so the
same engine serves a March-ending Indian fiscal year and a December-ending one
without code changes.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ObligationStatus, Recurrence
from app.models.lease import Lease
from app.models.obligation import LeaseObligation, Obligation

#: Guards against pathological recurrence configuration causing an endless loop.
_MAX_PERIODS = 400

#: How far past the current fiscal year the default calendar window reaches.
_DEFAULT_LOOKAHEAD_MONTHS = 18


@dataclass(frozen=True, slots=True)
class Period:
    """An inclusive reporting period covered by a filing."""

    start: date
    end: date


@dataclass(frozen=True, slots=True)
class PlannedInstance:
    """A dated obligation instance that should exist, before persistence."""

    obligation_id: object
    period_start: date | None
    period_end: date | None
    due_date: date


def add_months(anchor: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the target month length.

    Clamping is what makes 31 January minus one month land on 28/29 February
    rather than raising, which matters because period ends are often month ends.
    """
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor.day, _calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_end(year: int, month: int) -> date:
    return date(year, month, _calendar.monthrange(year, month)[1])


def fiscal_position(month: int, fiscal_year_end_month: int) -> int:
    """Zero-based position of a calendar month within the fiscal year.

    With a March year end, April is position 0 and March is position 11.
    """
    return (month - fiscal_year_end_month - 1) % 12


def fiscal_year_start(anchor: date, fiscal_year_end_month: int) -> date:
    """First day of the fiscal year containing ``anchor``.

    With a March year end, any date from 1 April 2025 to 31 March 2026 returns
    1 April 2025.
    """
    start_year = anchor.year if anchor.month > fiscal_year_end_month else anchor.year - 1
    return add_months(date(start_year, fiscal_year_end_month, 1), 1)


def fiscal_year_end(anchor: date, fiscal_year_end_month: int) -> date:
    """Last day of the fiscal year containing ``anchor``."""
    return add_months(fiscal_year_start(anchor, fiscal_year_end_month), 12) - timedelta(days=1)


def period_containing(
    anchor: date, recurrence: Recurrence, fiscal_year_end_month: int
) -> Period | None:
    """The reporting period of the given cadence that contains ``anchor``."""
    match recurrence:
        case Recurrence.MONTHLY:
            return Period(
                start=date(anchor.year, anchor.month, 1),
                end=month_end(anchor.year, anchor.month),
            )
        case Recurrence.QUARTERLY:
            return _block_period(anchor, fiscal_year_end_month, months_per_block=3)
        case Recurrence.HALF_YEARLY:
            return _block_period(anchor, fiscal_year_end_month, months_per_block=6)
        case Recurrence.ANNUAL:
            return Period(
                start=fiscal_year_start(anchor, fiscal_year_end_month),
                end=fiscal_year_end(anchor, fiscal_year_end_month),
            )
        case _:
            # One-time obligations cover no period; their due date is explicit.
            return None


def _block_period(anchor: date, fiscal_year_end_month: int, months_per_block: int) -> Period:
    """The fiscal sub-period (quarter or half year) containing ``anchor``."""
    position = fiscal_position(anchor.month, fiscal_year_end_month)
    block = position // months_per_block
    year_start = fiscal_year_start(anchor, fiscal_year_end_month)
    start = add_months(year_start, block * months_per_block)
    end = add_months(start, months_per_block) - timedelta(days=1)
    return Period(start=start, end=end)


def periods_in_window(
    window_start: date,
    window_end: date,
    recurrence: Recurrence,
    fiscal_year_end_month: int,
) -> list[Period]:
    """Every period of the given cadence overlapping ``[window_start, window_end]``."""
    if recurrence is Recurrence.ONE_TIME:
        return []

    first = period_containing(window_start, recurrence, fiscal_year_end_month)
    if first is None:
        return []

    periods: list[Period] = []
    cursor = first
    for _ in range(_MAX_PERIODS):
        if cursor.start > window_end:
            break
        if cursor.end >= window_start:
            periods.append(cursor)
        cursor = period_containing(
            cursor.end + timedelta(days=1), recurrence, fiscal_year_end_month
        )
        if cursor is None:  # pragma: no cover - defensive
            break
    return periods


def default_window(today: date, fiscal_year_end_month: int = 3) -> tuple[date, date]:
    """Calendar window used when a caller does not specify one.

    Starts at the beginning of the current fiscal year so that already-lapsed
    filings are still visible, and reaches into the next fiscal year so the
    renewal and filing pipeline can be planned ahead.
    """
    start = fiscal_year_start(today, fiscal_year_end_month)
    return start, add_months(start, _DEFAULT_LOOKAHEAD_MONTHS) - timedelta(days=1)


def rule_applies_to_lease(template: Obligation, lease: Lease) -> bool:
    """Whether an obligation rule is in scope for a lease.

    An empty applicability list means "no restriction", which is how rules that
    apply to every concession are expressed.
    """
    types_ok = (
        not template.applies_to_lease_types
        or lease.lease_type.value in template.applies_to_lease_types
    )
    mineral_category = lease.mineral.category.value if lease.mineral else None
    categories_ok = (
        not template.applies_to_mineral_categories
        or mineral_category in template.applies_to_mineral_categories
    )
    return types_ok and categories_ok


def _period_touches_lease(period: Period, lease: Lease) -> bool:
    """Whether a reporting period falls inside the lease term."""
    if period.end < lease.effective_from:
        return False
    return lease.effective_to is None or period.start <= lease.effective_to


def plan_instances(
    lease: Lease,
    templates: list[Obligation],
    window_start: date,
    window_end: date,
    one_time_due_date: date | None = None,
) -> list[PlannedInstance]:
    """Work out which obligation instances a lease should have in a window."""
    planned: list[PlannedInstance] = []

    for template in templates:
        if not template.is_active or not rule_applies_to_lease(template, lease):
            continue

        if template.recurrence is Recurrence.ONE_TIME:
            # One-time duties have no period, so they need an explicit due date.
            if one_time_due_date is None:
                continue
            if not (window_start <= one_time_due_date <= window_end):
                continue
            if lease.effective_to is not None and one_time_due_date > lease.effective_to:
                continue
            planned.append(
                PlannedInstance(
                    obligation_id=template.id,
                    period_start=None,
                    period_end=None,
                    due_date=one_time_due_date,
                )
            )
            continue

        for period in periods_in_window(
            window_start, window_end, template.recurrence, template.fiscal_year_end_month
        ):
            if not _period_touches_lease(period, lease):
                continue
            planned.append(
                PlannedInstance(
                    obligation_id=template.id,
                    period_start=period.start,
                    period_end=period.end,
                    due_date=period.end + timedelta(days=template.due_days_after_period_end),
                )
            )

    return planned


def generate_instances(
    session: Session,
    lease: Lease,
    templates: list[Obligation],
    window_start: date,
    window_end: date,
    one_time_due_date: date | None = None,
) -> int:
    """Materialise missing obligation instances for one lease.

    Idempotent: instances are matched on (lease, rule, period) so re-running
    generation only ever adds what is genuinely new and never duplicates or
    overwrites operator-entered status.
    """
    planned = plan_instances(lease, templates, window_start, window_end, one_time_due_date)
    if not planned:
        return 0

    existing = set(
        session.execute(
            select(
                LeaseObligation.obligation_id,
                LeaseObligation.period_start,
            ).where(LeaseObligation.lease_id == lease.id)
        ).all()
    )

    created = 0
    for item in planned:
        if (item.obligation_id, item.period_start) in existing:
            continue
        session.add(
            LeaseObligation(
                lease_id=lease.id,
                obligation_id=item.obligation_id,
                period_start=item.period_start,
                period_end=item.period_end,
                due_date=item.due_date,
                status=ObligationStatus.PENDING,
            )
        )
        existing.add((item.obligation_id, item.period_start))
        created += 1

    session.flush()
    return created


def refresh_overdue(session: Session, as_of: date) -> int:
    """Flip lapsed open obligations to OVERDUE. Returns the number changed.

    Status is recomputed from ``due_date`` rather than trusted from a nightly
    job, so a stale row can never masquerade as compliant.
    """
    stale = session.scalars(
        select(LeaseObligation).where(
            LeaseObligation.due_date < as_of,
            LeaseObligation.status.in_([ObligationStatus.PENDING, ObligationStatus.IN_PROGRESS]),
        )
    ).all()

    for instance in stale:
        instance.status = ObligationStatus.OVERDUE

    if stale:
        session.flush()
    return len(stale)
