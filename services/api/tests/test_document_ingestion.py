"""Integration tests for compliance document ingestion."""

from __future__ import annotations

from app.models.lease import Lease

BASE = "/api/v1"


def test_upload_and_list_documents_for_a_lease(client, lease: Lease):
    response = client.post(
        f"{BASE}/leases/{lease.id}/documents",
        files={
            "file": (
                "clearance.pdf",
                b"This is an environmental clearance valid until 2027-12-31.",
                "application/pdf",
            )
        },
        data={
            "document_type": "licence",
            "title": "Environmental clearance",
            "notes": "Uploaded by the operator",
            "source": "portal",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["file_name"] == "clearance.pdf"
    assert payload["document_type"] == "licence"
    assert payload["status"] == "pending_review"
    assert payload["extracted_expiry_date"] == "2027-12-31"
    assert payload["lease_id"] == str(lease.id)

    list_response = client.get(f"{BASE}/leases/{lease.id}/documents")
    assert list_response.status_code == 200, list_response.text
    listing = list_response.json()
    assert listing["total"] == 1
    assert listing["items"][0]["file_name"] == "clearance.pdf"

    review_response = client.patch(
        f"{BASE}/leases/{lease.id}/documents/{payload['id']}",
        json={"status": "accepted"},
    )
    assert review_response.status_code == 200, review_response.text
    assert review_response.json()["status"] == "accepted"
