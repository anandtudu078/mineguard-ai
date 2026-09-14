"""Unit tests for the statutory calendar engine.

These are pure functions, so they run without a database. The fiscal arithmetic
is the part most likely to be silently wrong - an off-by-one here means every
filing deadline in the product is wrong - so it is tested exhaustively.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.enums import (
    LeaseType,
    MineralCategory,
    ObligationCategory,
    Recurrence,
)
from app.models.lease import Lease
from app.models.mineral import Mineral
from app.models.obligation import Obligation
from app.services.calendar import (
    add_months,
    default_window,
    fiscal_position,
    fiscal_year_end,
    fiscal_year_start,
    period_containing,
    periods_in_window,
    plan_instances,
)

MARCH = 3
DECEMBER = 12


# ---------------------------------------------------------------------------
# Month arithmetic
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 15), 1, date(2026, 2, 15)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),  # leap year
        (date(2026, 3, 31), -1, date(2026, 2, 28)),
        (date(2026, 12, 15), 1, date(2027, 1, 15)),
        (date(2026, 1, 15), -1, date(2025, 12, 15)),
        (date(2026, 1, 1), 12, date(2027, 1, 1)),
        (date(2026, 5, 31), 9, date(2027, 2, 28)),
    ],
)
def test_add_months_clamps_day_to_target_month(start, months, expected):
    assert add_months(start, months) == expected


# ---------------------------------------------------------------------------
# Fiscal year boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("anchor", "expected_start", "expected_end"),
    [
        # Indian fiscal year: 1 April to 31 March.
        (date(2026, 2, 15), date(2025, 4, 1), date(2026, 3, 31)),
        (date(2026, 3, 31), date(2025, 4, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 1), date(2027, 3, 31)),
        (date(2026, 5, 10), date(2026, 4, 1), date(2027, 3, 31)),
        (date(2026, 12, 31), date(2026, 4, 1), date(2027, 3, 31)),
        # Calendar year variant.
        (date(2026, 6, 15), date(2026, 1, 1), date(2026, 12, 31)),
        (date(2026, 12, 31), date(2026, 1, 1), date(2026, 12, 31)),
    ],
)
def test_fiscal_year_bounds_pass_into(anchor, expected_start, expected_end):
    year_end_month = DECEMBER if expected_start.month == 1 else MARCH
    assert fiscal_year_start(anchor, year_end_month) == expected_start
    assert fiscal_year_end(anchor, year_end_month) == expected_end


def test_fiscal_position_counts_from_year_start():
    # With a March year end, April is position 0 and March is position 11.
    assert fiscal_position(4, MARCH) == 0
    assert fiscal_position(6, MARCH) == 2
    assert fiscal_position(12, MARCH) == 8
    assert fiscal_position(1, MARCH) == 9
    assert fiscal_position(3, MARCH) == 11


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("anchor", "recurrence", "fy_end", "expected"),
    [
        (date(2026, 2, 15), Recurrence.MONTHLY, MARCH, (date(2026, 2, 1), date(2026, 2, 28))),
        (date(2024, 2, 15), Recurrence.MONTHLY, MARCH, (date(2024, 2, 1), date(2024, 2, 29))),
        # Quarters are aligned to the fiscal year, not the calendar year.
        (date(2026, 5, 10), Recurrence.QUARTERLY, MARCH, (date(2026, 4, 1), date(2026, 6, 30))),
        (date(2026, 2, 10), Recurrence.QUARTERLY, MARCH, (date(2026, 1, 1), date(2026, 3, 31))),
        (date(2026, 8, 1), Recurrence.QUARTERLY, MARCH, (date(2026, 7, 1), date(2026, 9, 30))),
        (date(2026, 5, 10), Recurrence.HALF_YEARLY, MARCH, (date(2026, 4, 1), date(2026, 9, 30))),
        (date(2026, 11, 10), Recurrence.HALF_YEARLY, MARCH, (date(2026, 10, 1), date(2027, 3, 31))),
        (date(2026, 5, 10), Recurrence.ANNUAL, MARCH, (date(2026, 4, 1), date(2027, 3, 31))),
        (date(2026, 1, 5), Recurrence.ANNUAL, MARCH, (date(2025, 4, 1), date(2026, 3, 31))),
        (date(2026, 5, 10), Recurrence.QUARTERLY, DECEMBER, (date(2026, 4, 1), date(2026, 6, 30))),
    ],
)
def test_period_containing_returns_inclusive_bounds(anchor, recurrence, fy_end, expected):
    period = period_containing(anchor, recurrence, fy_end)
    assert period is not None
    assert (period.start, period.end) == expected


def test_period_containing_is_none_for_one_time():
    assert period_containing(date(2026, 5, 10), Recurrence.ONE_TIME, MARCH) is None


@pytest.mark.parametrize(
    ("recurrence", "window_start", "window_end", "expected_count"),
    [
        (Recurrence.MONTHLY, date(2026, 1, 1), date(2026, 3, 31), 3),
        (Recurrence.MONTHLY, date(2026, 1, 1), date(2027, 1, 31), 13),
        (Recurrence.QUARTERLY, date(2026, 1, 1), date(2026, 12, 31), 4),
        # A window that straddles a boundary pulls in both periods, because the
        # filing for a period is still owed while that period is open.
        (Recurrence.HALF_YEARLY, date(2026, 1, 1), date(2026, 12, 31), 3),
        (Recurrence.ANNUAL, date(2026, 1, 1), date(2026, 12, 31), 2),
        # Aligned to a single fiscal year, exactly one annual filing falls due.
        (Recurrence.ANNUAL, date(2026, 4, 1), date(2027, 3, 31), 1),
        # 18-month window spans two fiscal years, so two annual filings.
        (Recurrence.ANNUAL, date(2026, 4, 1), date(2027, 9, 30), 2),
        (Recurrence.ONE_TIME, date(2026, 1, 1), date(2026, 12, 31), 0),
    ],
)
def test_periods_in_window_is_contiguous(recurrence, window_start, window_end, expected_count):
    periods = periods_in_window(window_start, window_end, recurrence, MARCH)

    assert len(periods) == expected_count
    # Periods must tile without gap or overlap, which is what guarantees no
    # filing deadline is ever skipped or double-counted.
    for earlier, later in zip(periods, periods[1:], strict=False):
        assert (later.start - earlier.end).days == 1
        assert earlier.start <= earlier.end < later.start


def test_default_window_starts_at_fiscal_year_start():
    start, end = default_window(date(2026, 5, 20), MARCH)
    assert start == date(2026, 4, 1)
    assert end == date(2027, 9, 30)
    assert start < end


# ---------------------------------------------------------------------------
# Instance planning
# ---------------------------------------------------------------------------
def _mineral(category: MineralCategory = MineralCategory.MAJOR) -> Mineral:
    return Mineral(
        id=uuid.uuid4(),
        code="TEST",
        name="Test Mineral",
        category=category,
        royalty_basis="ad_valorem",
        royalty_rate=0,
    )


def _lease(
    *,
    lease_type: LeaseType = LeaseType.MINING_LEASE,
    effective_from: date = date(2000, 1, 1),
    effective_to: date | None = None,
    category: MineralCategory = MineralCategory.MAJOR,
) -> Lease:
    lease = Lease(
        id=uuid.uuid4(),
        lease_number="ML/TEST/0001",
        name="Test Lease",
        lease_type=lease_type,
        district="Test District",
        state="Test State",
        effective_from=effective_from,
        effective_to=effective_to,
    )
    lease.mineral = _mineral(category)
    return lease


def _rule(
    *,
    code: str = "TEST_RULE",
    recurrence: Recurrence = Recurrence.MONTHLY,
    due_days: int = 15,
    applies_to_lease_types: list[str] | None = None,
    applies_to_mineral_categories: list[str] | None = None,
    is_active: bool = True,
) -> Obligation:
    return Obligation(
        id=uuid.uuid4(),
        code=code,
        title="Test Rule",
        category=ObligationCategory.RETURN_FILING,
        recurrence=recurrence,
        due_days_after_period_end=due_days,
        fiscal_year_end_month=MARCH,
        applies_to_lease_types=applies_to_lease_types or [],
        applies_to_mineral_categories=applies_to_mineral_categories or [],
        is_active=is_active,
    )


def test_plan_instances_offsets_due_date_from_period_end():
    lease = _lease()
    rule = _rule()

    planned = plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31))

    assert [(p.period_start, p.due_date) for p in planned] == [
        (date(2026, 1, 1), date(2026, 2, 15)),
        (date(2026, 2, 1), date(2026, 3, 15)),
        (date(2026, 3, 1), date(2026, 4, 15)),
    ]
    assert all(p.period_end is not None for p in planned)


def test_plan_instances_filters_by_lease_type():
    lease = _lease(lease_type=LeaseType.QUARRY_LEASE)
    rule = _rule(applies_to_lease_types=[LeaseType.MINING_LEASE.value])

    assert plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31)) == []


def test_plan_instances_filters_by_mineral_category():
    lease = _lease(category=MineralCategory.MINOR)
    rule = _rule(applies_to_mineral_categories=[MineralCategory.MAJOR.value])

    assert plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31)) == []


def test_plan_instances_ignores_inactive_rules():
    lease = _lease()
    rule = _rule(is_active=False)

    assert plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31)) == []


def test_plan_instances_excludes_periods_before_the_lease_started():
    lease = _lease(effective_from=date(2026, 2, 10))
    rule = _rule()

    planned = plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31))

    # January's period ends before the lease exists, so only February onward counts.
    assert [p.period_start for p in planned] == [date(2026, 2, 1), date(2026, 3, 1)]


def test_plan_instances_excludes_periods_after_the_lease_ended():
    lease = _lease(effective_to=date(2026, 2, 15))
    rule = _rule()

    planned = plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 3, 31))

    # February's period starts before expiry and is therefore still owed.
    assert [p.period_start for p in planned] == [date(2026, 1, 1), date(2026, 2, 1)]


def test_plan_instances_skips_one_time_without_an_explicit_due_date():
    lease = _lease()
    rule = _rule(recurrence=Recurrence.ONE_TIME)

    assert plan_instances(lease, [rule], date(2026, 1, 1), date(2026, 12, 31)) == []


def test_plan_instances_honours_one_time_due_date():
    lease = _lease()
    rule = _rule(recurrence=Recurrence.ONE_TIME)

    planned = plan_instances(
        lease,
        [rule],
        date(2026, 1, 1),
        date(2026, 12, 31),
        one_time_due_date=date(2026, 6, 30),
    )

    assert len(planned) == 1
    assert planned[0].due_date == date(2026, 6, 30)
    assert planned[0].period_start is None


def test_plan_instances_rejects_one_time_date_outside_the_window():
    lease = _lease()
    rule = _rule(recurrence=Recurrence.ONE_TIME)

    planned = plan_instances(
        lease,
        [rule],
        date(2026, 1, 1),
        date(2026, 12, 31),
        one_time_due_date=date(2027, 6, 30),
    )

    assert planned == []


def test_annual_rule_due_date_matches_indian_annual_return_deadline():
    """For the year ending 31 March 2026, the annual return is due 1 July 2026."""
    lease = _lease()
    rule = _rule(recurrence=Recurrence.ANNUAL, due_days=92)

    # FY 2025-26: 1 April 2025 to 31 March 2026.
    planned = plan_instances(lease, [rule], date(2025, 4, 1), date(2026, 3, 31))

    assert len(planned) == 1
    assert planned[0].period_end == date(2026, 3, 31)
    assert planned[0].due_date == date(2026, 7, 1)
