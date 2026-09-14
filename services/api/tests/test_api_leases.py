"""Integration tests for the lease register and compliance endpoints.

These exercise PostGIS geometry round-trips, partial updates and the derived
compliance score against a real database.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import LeaseStatus, LeaseType
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence

BASE = "/api/v1"

SQUARE_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [76.38, 15.26],
            [76.40, 15.26],
            [76.40, 15.28],
            [76.38, 15.28],
            [76.38, 15.26],
        ]
    ],
}


def test_health_endpoints_respond(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Minerals
# ---------------------------------------------------------------------------
def test_create_and_fetch_mineral(client: TestClient):
    created = client.post(
        f"{BASE}/minerals",
        json={
            "code": "TEST_GOLD",
            "name": "Gold",
            "category": "major",
            "royalty_basis": "ad_valorem",
            "royalty_rate": "3.0",
            "royalty_unit": "percent_of_sale_value",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "TEST_GOLD"

    fetched = client.get(f"{BASE}/minerals/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Gold"


def test_duplicate_mineral_code_is_rejected(client: TestClient):
    payload = {"code": "TEST_DUP", "name": "First"}
    assert client.post(f"{BASE}/minerals", json=payload).status_code == 201

    duplicate = client.post(f"{BASE}/minerals", json={"code": "TEST_DUP", "name": "Second"})
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_patch_leaves_omitted_fields_untouched(client: TestClient):
    created = client.post(
        f"{BASE}/minerals",
        json={"code": "TEST_PATCH", "name": "Original", "description": "keep me"},
    ).json()

    patched = client.patch(f"{BASE}/minerals/{created['id']}", json={"name": "Renamed"})
    assert patched.status_code == 200

    body = patched.json()
    assert body["name"] == "Renamed"
    # Omitted fields must survive a partial update.
    assert body["description"] == "keep me"
    assert body["code"] == "TEST_PATCH"


# ---------------------------------------------------------------------------
# Leases
# ---------------------------------------------------------------------------
def test_create_lease_with_boundary_returns_geojson_and_area(
    client: TestClient, holder: LeaseHolder, mineral
):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": "ML/TEST/2024/9001",
            "name": "Boundary Test Lease",
            "district": "Vijayanagara",
            "state": "Karnataka",
            "effective_from": "2024-01-01",
            "effective_to": "2044-01-01",
            "holder_id": str(holder.id),
            "mineral_id": str(mineral.id),
            "boundary": SQUARE_POLYGON,
            "centroid": {"type": "Point", "coordinates": [76.39, 15.27]},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # A Polygon is coerced to MultiPolygon so it matches the column type.
    assert body["boundary"]["type"] == "MultiPolygon"
    assert len(body["boundary"]["coordinates"]) == 1
    assert body["centroid"] == {"lat": 15.27, "lon": 76.39}

    # PostGIS computes the area on the spheroid; ~0.02 x 0.02 degrees near 15N.
    assert body["surveyed_area_hectares"] is not None
    assert 350 < body["surveyed_area_hectares"] < 550

    # Nested context is expanded for the UI.
    assert body["holder"]["name"] == holder.name
    assert body["mineral"]["code"] == mineral.code


def test_centroid_rejects_a_non_point(client: TestClient, holder, mineral):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": "ML/TEST/2024/9002",
            "name": "Bad Centroid",
            "district": "D",
            "state": "S",
            "effective_from": "2024-01-01",
            "holder_id": str(holder.id),
            "mineral_id": str(mineral.id),
            "centroid": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        },
    )
    assert response.status_code == 422


def test_boundary_must_be_areal(client: TestClient, holder, mineral):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": "ML/TEST/2024/9003",
            "name": "Bad Boundary",
            "district": "D",
            "state": "S",
            "effective_from": "2024-01-01",
            "holder_id": str(holder.id),
            "mineral_id": str(mineral.id),
            "boundary": {"type": "Point", "coordinates": [76.0, 15.0]},
        },
    )
    assert response.status_code == 422


def test_term_must_be_ordered(client: TestClient, holder, mineral):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": "ML/TEST/2024/9004",
            "name": "Backwards Term",
            "district": "D",
            "state": "S",
            "effective_from": "2030-01-01",
            "effective_to": "2025-01-01",
            "holder_id": str(holder.id),
            "mineral_id": str(mineral.id),
        },
    )
    assert response.status_code == 422


def test_create_lease_rejects_unknown_holder(client: TestClient, mineral):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": "ML/TEST/2024/9005",
            "name": "Orphan",
            "district": "D",
            "state": "S",
            "effective_from": "2024-01-01",
            "holder_id": "00000000-0000-0000-0000-0000000000ff",
            "mineral_id": str(mineral.id),
        },
    )
    assert response.status_code == 422
    assert "holder_id" in response.json()["detail"]


def test_duplicate_lease_number_conflicts(client: TestClient, lease: Lease):
    response = client.post(
        f"{BASE}/leases",
        json={
            "lease_number": lease.lease_number,
            "name": "Duplicate",
            "district": "D",
            "state": "S",
            "effective_from": "2024-01-01",
            "holder_id": str(lease.holder_id),
            "mineral_id": str(lease.mineral_id),
        },
    )
    assert response.status_code == 409


def test_lease_list_reports_compliance_posture(
    client: TestClient, lease: Lease, valid_licence: Licence
):
    response = client.get(f"{BASE}/leases")
    assert response.status_code == 200

    page = response.json()
    assert page["total"] >= 1
    item = next(row for row in page["items"] if row["id"] == str(lease.id))

    assert item["lease_number"] == lease.lease_number
    assert item["compliance_score"] is not None
    assert item["risk_level"] in {"low", "medium", "high", "critical"}
    assert item["centroid"] == {"lat": 15.27, "lon": 76.39}


def test_lease_list_filters_by_state(client: TestClient, lease: Lease):
    matching = client.get(f"{BASE}/leases", params={"state": "Karnataka"}).json()
    assert any(row["id"] == str(lease.id) for row in matching["items"])

    missing = client.get(f"{BASE}/leases", params={"state": "Nowhere"}).json()
    assert missing["total"] == 0
    assert missing["items"] == []


def test_lease_list_filters_by_bounding_box(client: TestClient, lease: Lease):
    # A box around the seeded centroid must include the lease.
    inside = client.get(f"{BASE}/leases", params={"bbox": "76.0,15.0,77.0,16.0"}).json()
    assert any(row["id"] == str(lease.id) for row in inside["items"])

    outside = client.get(f"{BASE}/leases", params={"bbox": "10.0,10.0,11.0,11.0"}).json()
    assert all(row["id"] != str(lease.id) for row in outside["items"])


def test_malformed_bbox_is_rejected(client: TestClient):
    assert client.get(f"{BASE}/leases", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get(f"{BASE}/leases", params={"bbox": "a,b,c,d"}).status_code == 422
    # Inverted bounds would silently match nothing.
    assert client.get(f"{BASE}/leases", params={"bbox": "5,5,1,1"}).status_code == 422


def test_lease_search_matches_number_and_name(client: TestClient, lease: Lease):
    by_number = client.get(f"{BASE}/leases", params={"q": "ML/TEST"}).json()
    assert any(row["id"] == str(lease.id) for row in by_number["items"])

    by_name = client.get(f"{BASE}/leases", params={"q": "Iron Ore Block"}).json()
    assert any(row["id"] == str(lease.id) for row in by_name["items"])


def test_expiring_within_days_finds_leases_nearing_expiry(
    client: TestClient, session: Session, holder: LeaseHolder, mineral
):
    today = date.today()
    expiring = Lease(
        lease_number="ML/TEST/2024/9010",
        name="Nearly Expired",
        lease_type=LeaseType.MINING_LEASE,
        status=LeaseStatus.ACTIVE,
        holder_id=holder.id,
        mineral_id=mineral.id,
        district="D",
        state="S",
        effective_from=today - timedelta(days=3000),
        effective_to=today + timedelta(days=40),
    )
    session.add(expiring)
    session.flush()

    response = client.get(f"{BASE}/leases", params={"expiring_within_days": 90})
    assert response.status_code == 200
    numbers = [row["lease_number"] for row in response.json()["items"]]
    assert "ML/TEST/2024/9010" in numbers


def test_patch_lease_updates_only_sent_fields(client: TestClient, lease: Lease):
    original_district = lease.district

    response = client.patch(f"{BASE}/leases/{lease.id}", json={"name": "Renamed Lease"})
    assert response.status_code == 200

    body = response.json()
    assert body["name"] == "Renamed Lease"
    assert body["district"] == original_district
    assert body["lease_number"] == lease.lease_number


def test_delete_lease_cascades_to_licences(
    client: TestClient, session: Session, lease: Lease, valid_licence: Licence
):
    licence_id = valid_licence.id

    assert client.delete(f"{BASE}/leases/{lease.id}").status_code == 204
    assert client.get(f"{BASE}/leases/{lease.id}").status_code == 404
    # The clearance is owned by the lease and must go with it.
    assert session.get(Licence, licence_id) is None


# ---------------------------------------------------------------------------
# Clearances
# ---------------------------------------------------------------------------
def test_create_licence_and_report_days_to_expiry(client: TestClient, lease: Lease, today: date):
    expiry = today + timedelta(days=45)
    response = client.post(
        f"{BASE}/leases/{lease.id}/licences",
        json={
            "licence_type": "consent_to_operate",
            "authority": "State Pollution Control Board",
            "reference_number": "CTO/TEST/1",
            "valid_from": str(today - timedelta(days=320)),
            "valid_to": str(expiry),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["days_until_expiry"] == 45


def test_licence_update_changes_status_and_expiry(
    client: TestClient, lease: Lease, valid_licence: Licence
):
    response = client.patch(
        f"{BASE}/licences/{valid_licence.id}",
        json={"status": "revoked", "notes": "Withdrawn by regulator"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_expiring_clearances_endpoint(client: TestClient, lease: Lease, today: date):
    client.post(
        f"{BASE}/leases/{lease.id}/licences",
        json={
            "licence_type": "ground_water_ntoc",
            "authority": "CGWA",
            "reference_number": "GW/TEST/1",
            "valid_to": str(today + timedelta(days=20)),
        },
    )

    response = client.get(f"{BASE}/clearances/expiring", params={"within_days": 30})
    assert response.status_code == 200
    assert any(row["reference_number"] == "GW/TEST/1" for row in response.json())


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
def test_compliance_endpoint_explains_the_score(
    client: TestClient, lease: Lease, valid_licence: Licence
):
    response = client.get(f"{BASE}/leases/{lease.id}/compliance")
    assert response.status_code == 200

    body = response.json()
    assert body["lease_number"] == lease.lease_number
    assert 0 <= body["score"] <= 100

    # The breakdown must be present so the number is defensible.
    names = {c["name"] for c in body["components"]}
    assert names == {"clearance_validity", "filing_adherence", "timeliness"}
    for component in body["components"]:
        assert component["detail"]

    assert body["total_licences"] == 1
    assert body["valid_licences"] == 1


def test_compliance_drops_when_a_clearance_lapses(client: TestClient, lease: Lease, today: date):
    client.post(
        f"{BASE}/leases/{lease.id}/licences",
        json={
            "licence_type": "environmental_clearance",
            "authority": "MoEFCC",
            "reference_number": "EC/LAPSED",
            "valid_from": str(today - timedelta(days=800)),
            "valid_to": str(today - timedelta(days=10)),
        },
    )

    body = client.get(f"{BASE}/leases/{lease.id}/compliance").json()
    assert body["expired_licences"] == 1
    assert body["score"] < 100
    assert any("lapsed or revoked" in note for note in body["notes"])


def test_compliance_404s_for_unknown_lease(client: TestClient):
    response = client.get(f"{BASE}/leases/{uuid_of_zeros()}/compliance")
    assert response.status_code == 404


def test_as_of_date_can_be_pinned(client: TestClient, lease: Lease, today: date):
    """An auditor must be able to ask what the position was on a given date."""
    past = today - timedelta(days=400)
    response = client.get(f"{BASE}/leases/{lease.id}/compliance", params={"as_of": str(past)})
    assert response.status_code == 200
    assert response.json()["score"] == 100.0


def uuid_of_zeros() -> str:
    return "00000000-0000-0000-0000-0000000000ff"


# ---------------------------------------------------------------------------
# Holders
# ---------------------------------------------------------------------------
def test_delete_holder_in_use_is_refused(client: TestClient, lease: Lease):
    response = client.delete(f"{BASE}/holders/{lease.holder_id}")
    assert response.status_code == 409
    assert "lease(s)" in response.json()["detail"]


def test_delete_unused_holder_succeeds(client: TestClient):
    created = client.post(f"{BASE}/holders", json={"name": "Unused Holder"}).json()

    assert client.delete(f"{BASE}/holders/{created['id']}").status_code == 204
    assert client.get(f"{BASE}/holders/{created['id']}").status_code == 404
