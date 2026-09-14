"""Integration tests for obligation rule management.

Rules are jurisdiction data. These tests assert that applicability filters
round-trip as string arrays, which is what lets a rule be scoped to a lease type
or mineral category without schema changes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

BASE = "/api/v1"

RULE = {
    "code": "TEST_CUSTOM_RULE",
    "title": "Custom quarterly filing",
    "description": "A rule defined through the API.",
    "category": "environment",
    "legal_reference": "Test Act s.1",
    "jurisdiction": "Karnataka",
    "recurrence": "quarterly",
    "due_days_after_period_end": 21,
    "grace_days": 5,
    "fiscal_year_end_month": 3,
    "applies_to_lease_types": ["mining_lease", "composite_licence"],
    "applies_to_mineral_categories": ["major"],
    "requires_payment": False,
    "penalty_note": "Late filing is reportable.",
}


def test_create_rule_round_trips_applicability_filters(client: TestClient):
    created = client.post(f"{BASE}/obligations", json=RULE)
    assert created.status_code == 201, created.text

    body = created.json()
    assert body["code"] == "TEST_CUSTOM_RULE"
    assert body["applies_to_lease_types"] == ["mining_lease", "composite_licence"]
    assert body["applies_to_mineral_categories"] == ["major"]
    assert body["due_days_after_period_end"] == 21


def test_duplicate_rule_code_conflicts(client: TestClient):
    assert client.post(f"{BASE}/obligations", json=RULE).status_code == 201
    duplicate = client.post(f"{BASE}/obligations", json=RULE)
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_filter_rules_by_category_and_recurrence(client: TestClient):
    client.post(f"{BASE}/obligations", json=RULE)

    by_category = client.get(f"{BASE}/obligations", params={"category": "environment"}).json()
    assert any(row["code"] == "TEST_CUSTOM_RULE" for row in by_category["items"])

    by_recurrence = client.get(f"{BASE}/obligations", params={"recurrence": "quarterly"}).json()
    assert any(row["code"] == "TEST_CUSTOM_RULE" for row in by_recurrence["items"])

    absent = client.get(f"{BASE}/obligations", params={"recurrence": "annual"}).json()
    assert all(row["code"] != "TEST_CUSTOM_RULE" for row in absent["items"])


def test_search_matches_legal_reference(client: TestClient):
    client.post(f"{BASE}/obligations", json=RULE)

    response = client.get(f"{BASE}/obligations", params={"q": "Test Act"}).json()
    assert any(row["code"] == "TEST_CUSTOM_RULE" for row in response["items"])


def test_update_rule_scopes_it_to_a_single_lease_type(client: TestClient):
    created = client.post(f"{BASE}/obligations", json=RULE).json()

    patched = client.patch(
        f"{BASE}/obligations/{created['id']}",
        json={"applies_to_lease_types": ["quarry_lease"], "due_days_after_period_end": 30},
    )
    assert patched.status_code == 200, patched.text

    body = patched.json()
    assert body["applies_to_lease_types"] == ["quarry_lease"]
    assert body["due_days_after_period_end"] == 30
    # Untouched fields survive.
    assert body["jurisdiction"] == "Karnataka"


def test_invalid_recurrence_is_rejected(client: TestClient):
    response = client.post(f"{BASE}/obligations", json={**RULE, "recurrence": "fortnightly"})
    assert response.status_code == 422


def test_unknown_rule_404s(client: TestClient):
    response = client.get(f"{BASE}/obligations/00000000-0000-0000-0000-0000000000ff")
    assert response.status_code == 404
