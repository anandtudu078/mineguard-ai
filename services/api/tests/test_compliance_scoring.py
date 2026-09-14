"""Unit tests for the compliance scoring engine.

``_build_assessment`` is a pure function over pre-aggregated counts, so the
scoring rules are testable without a database. That separation is deliberate:
the tricky part is the weighting policy, not the SQL.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import RiskLevel
from app.services.compliance import (
    LICENCE_WEIGHT,
    OBLIGATION_WEIGHT,
    SAFETY_WEIGHT,
    TIMELINESS_WEIGHT,
    _build_assessment,
    _round_score,
    risk_level_for,
)

WARNING_DAYS = 90
LEASE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def assess(licences: dict | None = None, obligations: dict | None = None):
    return _build_assessment(LEASE_ID, licences or {}, obligations or {}, WARNING_DAYS)


def component(assessment, name: str):
    return next(c for c in assessment.components if c.name == name)


def test_weights_total_one_hundred():
    assert (
        LICENCE_WEIGHT + OBLIGATION_WEIGHT + TIMELINESS_WEIGHT + SAFETY_WEIGHT == 100.0
    )


def test_lease_with_no_records_scores_perfect_and_flags_the_gap():
    assessment = assess()

    assert assessment.score == 100.0
    assert assessment.risk_level is RiskLevel.LOW
    # Every component is excluded, and the operator is told why.
    assert all(not c.applicable for c in assessment.components)
    assert any("No clearances recorded" in note for note in assessment.notes)


def test_fully_compliant_lease_scores_one_hundred():
    assessment = assess(
        licences={"total": 4, "valid": 4, "expiring": 0, "invalid": 0},
        obligations={
            "come_due": 10,
            "compliant": 10,
            "submitted": 10,
            "on_time": 10,
            "overdue": 0,
            "open": 0,
        },
    )

    assert assessment.score == 100.0
    assert assessment.risk_level is RiskLevel.LOW
    assert assessment.overdue_obligations == 0


def test_weight_is_redistributed_when_a_component_is_not_applicable():
    """A brand-new lease with nothing due should not be penalised."""
    assessment = assess(licences={"total": 2, "valid": 2, "expiring": 0, "invalid": 0})

    licence_component = component(assessment, "clearance_validity")
    filing_component = component(assessment, "filing_adherence")

    assert licence_component.applicable
    assert not filing_component.applicable
    # Only the licence component can contribute, so a perfect licence record is 100.
    assert licence_component.earned == LICENCE_WEIGHT
    assert assessment.score == 100.0


def test_lapsed_clearances_reduce_the_score_proportionally():
    assessment = assess(licences={"total": 4, "valid": 2, "expiring": 0, "invalid": 2})

    licence_component = component(assessment, "clearance_validity")
    assert licence_component.ratio == 0.5
    assert licence_component.earned == LICENCE_WEIGHT * 0.5
    # Licences are the only applicable component, so the score is that ratio.
    assert assessment.score == 50.0
    assert assessment.risk_level is RiskLevel.HIGH
    assert any("2 clearance(s) lapsed or revoked" in note for note in assessment.notes)


def test_overdue_filings_dominate_the_score():
    assessment = assess(
        licences={"total": 4, "valid": 4, "expiring": 0, "invalid": 0},
        obligations={
            "come_due": 8,
            "compliant": 2,
            "submitted": 2,
            "on_time": 2,
            "overdue": 6,
            "open": 6,
        },
    )

    # licences 40 + filings (45 * 2/8 = 11.25) + timeliness 15 = 66.25 -> 66.3 half-up.
    # Banker's rounding would give 66.2 here but 66.4 for 66.35, which reads as a bug.
    assert assessment.score == 66.3
    assert assessment.risk_level is RiskLevel.HIGH
    assert any("6 obligation(s) overdue" in note for note in assessment.notes)


def test_late_filings_lose_timeliness_points_only():
    assessment = assess(
        licences={"total": 1, "valid": 1, "expiring": 0, "invalid": 0},
        obligations={
            "come_due": 4,
            "compliant": 4,
            "submitted": 4,
            "on_time": 0,
            "overdue": 0,
            "open": 0,
        },
    )

    assert component(assessment, "filing_adherence").ratio == 1.0
    assert component(assessment, "timeliness").ratio == 0.0
    # Everything filed, but none on time: 40 + 45 + 0 = 85.
    assert assessment.score == 85.0
    assert assessment.risk_level is RiskLevel.LOW


def test_upcoming_obligations_are_reported_but_not_penalised():
    assessment = assess(
        obligations={
            "come_due": 0,
            "compliant": 0,
            "submitted": 0,
            "on_time": 0,
            "overdue": 0,
            "open": 5,
        }
    )

    assert assessment.score == 100.0
    assert assessment.open_obligations == 5
    assert any("none yet due" in note for note in assessment.notes)


def test_expiring_clearances_are_flagged_without_deducting_points():
    """Expiry warnings are advisory; only lapsed clearances cost points."""
    assessment = assess(licences={"total": 3, "valid": 3, "expiring": 2, "invalid": 0})

    assert assessment.score == 100.0
    assert assessment.expiring_licences == 2
    assert any("expire within 90 days" in note for note in assessment.notes)


def test_components_are_reported_for_explainability():
    assessment = assess(
        licences={"total": 2, "valid": 1, "expiring": 0, "invalid": 1},
        obligations={
            "come_due": 2,
            "compliant": 1,
            "submitted": 1,
            "on_time": 1,
            "overdue": 1,
            "open": 1,
        },
    )

    names = {c.name for c in assessment.components}
    assert names == {"clearance_validity", "filing_adherence", "timeliness", "site_safety"}
    for item in assessment.components:
        assert item.detail  # every component explains itself


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(66.25, 66.3), (66.35, 66.4), (85.0, 85.0), (84.949, 84.9)],
)
def test_score_rounding_is_half_up_not_bankers(raw, expected):
    assert _round_score(raw) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, RiskLevel.LOW),
        (85.0, RiskLevel.LOW),
        (84.9, RiskLevel.MEDIUM),
        (70.0, RiskLevel.MEDIUM),
        (69.9, RiskLevel.HIGH),
        (50.0, RiskLevel.HIGH),
        (49.9, RiskLevel.CRITICAL),
        (0.0, RiskLevel.CRITICAL),
    ],
)
def test_risk_bands_are_inclusive_at_the_lower_bound(score, expected):
    assert risk_level_for(score) is expected
