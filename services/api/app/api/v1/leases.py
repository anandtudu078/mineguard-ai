"""Lease endpoints: the register, compliance assessment and renewal queue."""

import re
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    AppSettings,
    AsOfDate,
    AuditCtx,
    CurrentPrincipal,
    DbSession,
    PaginationDep,
    conflict,
    is_unique_violation,
)
from app.core.storage import UploadStorage
from app.models.document import DocumentStatus, DocumentType, LeaseDocument
from app.models.enums import LeaseStatus, LeaseType, ObligationStatus, RiskLevel
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.mineral import Mineral
from app.models.obligation import LeaseObligation
from app.schemas.common import Page
from app.schemas.compliance import ComplianceComponent, ComplianceScore
from app.schemas.document import DocumentUpdate
from app.schemas.lease import LeaseCreate, LeaseListItem, LeaseRead, LeaseUpdate
from app.services import geo
from app.services import leases as lease_service
from app.services.authorization import assert_lease_access
from app.services.compliance import score_lease
from app.services.document_extraction import extract_document_metadata
from app.services.reference import apply_partial_update

router = APIRouter(prefix="/leases", tags=["leases"])


def _extract_date_from_text(text: str) -> date | None:
    """Extract the first ISO-style date seen in uploaded text."""
    matches = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if not matches:
        return None
    return date.fromisoformat(matches[0])


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """Parse a ``minLon,minLat,maxLon,maxLat`` bounding box."""
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "bbox must be four comma-separated numbers: minLon,minLat,maxLon,maxLat",
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in parts)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "bbox values must be numeric"
        ) from error
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "bbox must satisfy minLon < maxLon and minLat < maxLat",
        )
    return min_lon, min_lat, max_lon, max_lat


@router.get("", response_model=Page[LeaseListItem], summary="List leases")
def list_leases(
    session: DbSession,
    settings: AppSettings,
    page: PaginationDep,
    as_of: AsOfDate,
    q: Annotated[str | None, Query(description="Match lease number, name or village")] = None,
    state: Annotated[str | None, Query()] = None,
    district: Annotated[str | None, Query()] = None,
    lease_status: Annotated[
        list[LeaseStatus] | None, Query(alias="status", description="Repeatable")
    ] = None,
    lease_type: Annotated[list[LeaseType] | None, Query(description="Repeatable")] = None,
    holder_id: Annotated[uuid.UUID | None, Query()] = None,
    mineral_id: Annotated[uuid.UUID | None, Query()] = None,
    expiring_within_days: Annotated[
        int | None, Query(ge=0, le=3650, description="Leases whose term lapses within N days")
    ] = None,
    risk_level: Annotated[
        list[RiskLevel] | None, Query(description="Repeatable compliance risk band")
    ] = None,
    bbox: Annotated[
        str | None, Query(description="Spatial filter: minLon,minLat,maxLon,maxLat")
    ] = None,
    sort: Annotated[
        str,
        Query(
            description=(
                "lease_number | name | district | state | effective_to | "
                "area_hectares | created_at | compliance_score"
            )
        ),
    ] = "lease_number",
    descending: Annotated[bool, Query()] = False,
) -> Page[LeaseListItem]:
    items, total = lease_service.list_leases(
        session,
        limit=page.limit,
        offset=page.offset,
        as_of=as_of,
        warning_days=settings.licence_expiry_warning_days,
        q=q,
        state=state,
        district=district,
        status=lease_status,
        lease_type=lease_type,
        holder_id=holder_id,
        mineral_id=mineral_id,
        expiring_within_days=expiring_within_days,
        bbox=_parse_bbox(bbox),
        risk_level=risk_level,
        sort=sort,
        descending=descending,
    )
    return Page[LeaseListItem](
        items=[LeaseListItem.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=LeaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a lease",
)
def create_lease(payload: LeaseCreate, session: DbSession) -> LeaseRead:
    if session.get(LeaseHolder, payload.holder_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown holder_id")
    if session.get(Mineral, payload.mineral_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown mineral_id")

    data = payload.model_dump(exclude={"boundary", "centroid"})
    lease = Lease(**data)

    # Geometry is assigned as a PostGIS expression so conversion happens in the
    # database and no WKB ever passes through Python.
    if payload.boundary is not None:
        lease.boundary = geo.geojson_to_multipolygon(payload.boundary)
    if payload.centroid is not None:
        lease.centroid = geo.geojson_to_point(payload.centroid)

    session.add(lease)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if is_unique_violation(error):
            raise conflict(f"Lease '{payload.lease_number}' already exists") from error
        raise

    created = lease_service.get_lease(session, lease.id)
    if created is None:  # pragma: no cover - defensive
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Lease vanished after commit")
    return LeaseRead.model_validate(created)


@router.get("/expiring", response_model=list[LeaseRead], summary="Leases expiring soon")
def expiring_leases(
    session: DbSession,
    as_of: AsOfDate,
    within_days: Annotated[int, Query(ge=1, le=3650)] = 90,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[LeaseRead]:
    rows = lease_service.expiring_leases(session, as_of, within_days, limit)
    return [LeaseRead.model_validate(row) for row in rows]


@router.get(
    "/geojson",
    response_model=dict,
    summary="Leases as a GeoJSON FeatureCollection",
)
def lease_geojson(
    session: DbSession,
    settings: AppSettings,
    as_of: AsOfDate,
    q: Annotated[str | None, Query(description="Match lease number, name or village")] = None,
    state: Annotated[str | None, Query()] = None,
    district: Annotated[str | None, Query()] = None,
    lease_status: Annotated[list[LeaseStatus] | None, Query(alias="status")] = None,
    lease_type: Annotated[list[LeaseType] | None, Query()] = None,
    risk_level: Annotated[list[RiskLevel] | None, Query()] = None,
    expiring_within_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
    bbox: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict:
    """All matching leases as a single GeoJSON FeatureCollection.

    Exists so the map can render the whole register in one request. Properties
    carry the compliance posture alongside the geometry, which lets the map
    colour features without a follow-up query.
    """
    return lease_service.lease_feature_collection(
        session,
        as_of=as_of,
        warning_days=settings.licence_expiry_warning_days,
        q=q,
        state=state,
        district=district,
        status=lease_status,
        lease_type=lease_type,
        risk_level=risk_level,
        expiring_within_days=expiring_within_days,
        bbox=_parse_bbox(bbox),
        limit=limit,
    )


@router.get("/{lease_id}", response_model=LeaseRead, summary="Get a lease")
def get_lease(lease_id: uuid.UUID, session: DbSession) -> LeaseRead:
    lease = lease_service.get_lease(session, lease_id)
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")
    return LeaseRead.model_validate(lease)


@router.patch("/{lease_id}", response_model=LeaseRead, summary="Update a lease")
def update_lease(lease_id: uuid.UUID, payload: LeaseUpdate, session: DbSession) -> LeaseRead:
    lease = session.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    if payload.holder_id is not None and session.get(LeaseHolder, payload.holder_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown holder_id")
    if payload.mineral_id is not None and session.get(Mineral, payload.mineral_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown mineral_id")

    apply_partial_update(lease, payload, exclude={"boundary", "centroid"})

    if payload.boundary is not None:
        lease.boundary = geo.geojson_to_multipolygon(payload.boundary)
    if payload.centroid is not None:
        lease.centroid = geo.geojson_to_point(payload.centroid)

    session.commit()

    updated = lease_service.get_lease(session, lease_id)
    if updated is None:  # pragma: no cover - defensive
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")
    return LeaseRead.model_validate(updated)


@router.delete("/{lease_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a lease")
def delete_lease(lease_id: uuid.UUID, session: DbSession) -> None:
    lease = session.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")
    # Clearances and calendar entries cascade with the lease.
    session.delete(lease)
    session.commit()


@router.get(
    "/{lease_id}/compliance",
    response_model=ComplianceScore,
    summary="Compliance score for a lease",
)
def lease_compliance(
    lease_id: uuid.UUID, session: DbSession, settings: AppSettings, as_of: AsOfDate
) -> ComplianceScore:
    lease = session.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    assessment = score_lease(session, lease_id, as_of, settings.licence_expiry_warning_days)
    return ComplianceScore(
        lease_id=assessment.lease_id,
        lease_number=lease.lease_number,
        score=assessment.score,
        risk_level=assessment.risk_level,
        components=[
            ComplianceComponent(
                name=component.name,
                weight=component.weight,
                applicable=component.applicable,
                earned=round(component.earned, 2),
                ratio=round(component.ratio, 4) if component.ratio is not None else None,
                detail=component.detail,
            )
            for component in assessment.components
        ],
        total_licences=assessment.total_licences,
        valid_licences=assessment.valid_licences,
        expiring_licences=assessment.expiring_licences,
        expired_licences=assessment.expired_licences,
        open_obligations=assessment.open_obligations,
        overdue_obligations=assessment.overdue_obligations,
        submitted_obligations=assessment.submitted_obligations,
        notes=assessment.notes,
    )


@router.get(
    "/{lease_id}/timeline",
    response_model=list[dict],
    summary="Recent and upcoming calendar entries for a lease",
)
def lease_timeline(
    lease_id: uuid.UUID,
    session: DbSession,
    as_of: AsOfDate,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    """A merged view of what is overdue, due next, and recently filed."""
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    rows = session.scalars(
        select(LeaseObligation)
        .where(
            LeaseObligation.lease_id == lease_id,
            LeaseObligation.status != ObligationStatus.NOT_APPLICABLE,
        )
        .order_by(LeaseObligation.due_date.asc())
        .limit(limit)
    ).all()

    return [
        {
            "id": row.id,
            "due_date": row.due_date,
            "status": row.status,
            "days_until_due": row.days_to_due(as_of),
            "code": row.obligation.code if row.obligation else None,
            "title": row.obligation.title if row.obligation else None,
            "category": row.obligation.category if row.obligation else None,
            "requires_payment": row.obligation.requires_payment if row.obligation else None,
            "period_start": row.period_start,
            "period_end": row.period_end,
        }
        for row in rows
    ]


@router.get(
    "/{lease_id}/licences",
    response_model=list[dict],
    summary="Clearances recorded against a lease",
)
def lease_licences(lease_id: uuid.UUID, session: DbSession, as_of: AsOfDate) -> list[dict]:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    rows = session.scalars(
        select(Licence)
        .where(Licence.lease_id == lease_id)
        .order_by(Licence.valid_to.asc().nulls_last())
    ).all()

    return [
        {
            "id": row.id,
            "licence_type": row.licence_type,
            "status": row.status,
            "authority": row.authority,
            "reference_number": row.reference_number,
            "issued_date": row.issued_date,
            "valid_from": row.valid_from,
            "valid_to": row.valid_to,
            "is_mandatory": row.is_mandatory,
            "is_expired": row.is_expired_on(as_of),
            "days_until_expiry": row.days_to_expiry(as_of),
            "document_path": row.document_path,
            "notes": row.notes,
        }
        for row in rows
    ]


@router.post(
    "/{lease_id}/documents",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a compliance document",
)
async def upload_lease_document(
    lease_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(default=DocumentType.GENERAL),
    title: str = Form(...),
    notes: str | None = Form(default=None),
    source: str = Form(default="manual"),
) -> dict:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Uploaded file is empty")

    file_name = file.filename or f"document-{uuid.uuid4()}"
    reference = UploadStorage(settings).save_upload(raw_bytes, file_name, file.content_type)

    text_payload = raw_bytes.decode("utf-8", errors="ignore")
    expiry_date = _extract_date_from_text(text_payload)
    extracted_summary = f"Uploaded {file_name}"
    extracted_reference_number = None
    extracted_authority = None
    if file.content_type:
        try:
            metadata = extract_document_metadata(raw_bytes, file.content_type, settings)
        except Exception:
            metadata = None
        if metadata:
            expiry_date = metadata["expiry_date"] or expiry_date
            extracted_summary = metadata["summary"] or extracted_summary
            extracted_reference_number = metadata["reference_number"]
            extracted_authority = metadata["authority"]

    document = LeaseDocument(
        lease_id=lease_id,
        title=title,
        file_name=file_name,
        content_type=file.content_type or "application/octet-stream",
        file_path=reference,
        document_type=document_type,
        source=source,
        status=DocumentStatus.PENDING_REVIEW,
        notes=notes,
        extracted_summary=extracted_summary,
        extracted_reference_number=extracted_reference_number,
        extracted_authority=extracted_authority,
        extracted_expiry_date=(
            date.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
        ),
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    return {
        "id": str(document.id),
        "lease_id": str(document.lease_id),
        "title": document.title,
        "file_name": document.file_name,
        "content_type": document.content_type,
        "file_path": document.file_path,
        "document_type": document.document_type,
        "source": document.source,
        "status": document.status,
        "notes": document.notes,
        "extracted_summary": document.extracted_summary,
        "extracted_reference_number": document.extracted_reference_number,
        "extracted_authority": document.extracted_authority,
        "extracted_expiry_date": document.extracted_expiry_date.isoformat()
        if document.extracted_expiry_date is not None
        else None,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


@router.get(
    "/{lease_id}/documents/{document_id}/download",
    response_class=Response,
    summary="Download an uploaded document or site photo",
)
def download_lease_document(
    lease_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
    audit: AuditCtx,
) -> Response:
    """Stream the stored file, wherever it lives.

    With Supabase Storage enabled the browser cannot fetch the object directly
    (the bucket is private by design), so the API proxies it after checking the
    caller may reach the lease.
    """
    assert_lease_access(session, principal, audit, lease_id, action="download document")

    document = session.get(LeaseDocument, document_id)
    if document is None or document.lease_id != lease_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    try:
        payload, media_type = UploadStorage(settings).open_download(document.file_path)
    except (OSError, FileNotFoundError) as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stored file is missing") from error
    except Exception as error:  # Storage network errors surface as 502.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Storage backend error: {error}"
        ) from error

    return Response(
        content=payload,
        media_type=media_type or document.content_type,
        headers={"Content-Disposition": f'inline; filename="{document.file_name}"'},
    )


@router.get(
    "/{lease_id}/documents",
    response_model=Page[dict],
    summary="List documents attached to a lease",
)
def list_lease_documents(
    lease_id: uuid.UUID,
    session: DbSession,
    page: PaginationDep,
) -> Page[dict]:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    stmt = select(LeaseDocument).where(LeaseDocument.lease_id == lease_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(LeaseDocument.created_at.desc()).limit(page.limit).offset(page.offset)
    ).all()

    return Page[dict](
        items=[
            {
                "id": str(row.id),
                "lease_id": str(row.lease_id),
                "title": row.title,
                "file_name": row.file_name,
                "content_type": row.content_type,
                "file_path": row.file_path,
                "document_type": row.document_type,
                "source": row.source,
                "status": row.status,
                "notes": row.notes,
                "extracted_summary": row.extracted_summary,
                "extracted_reference_number": row.extracted_reference_number,
                "extracted_authority": row.extracted_authority,
                "extracted_expiry_date": row.extracted_expiry_date.isoformat()
                if row.extracted_expiry_date is not None
                else None,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.patch(
    "/{lease_id}/documents/{document_id}",
    response_model=dict,
    summary="Review a lease document",
)
def update_lease_document(
    lease_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    session: DbSession,
) -> dict:
    document = session.scalar(
        select(LeaseDocument).where(
            LeaseDocument.id == document_id,
            LeaseDocument.lease_id == lease_id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    if payload.status is not None:
        document.status = payload.status
    if payload.notes is not None:
        document.notes = payload.notes
    session.commit()
    session.refresh(document)

    return {
        "id": str(document.id),
        "lease_id": str(document.lease_id),
        "title": document.title,
        "file_name": document.file_name,
        "content_type": document.content_type,
        "file_path": document.file_path,
        "document_type": document.document_type,
        "source": document.source,
        "status": document.status,
        "notes": document.notes,
        "extracted_summary": document.extracted_summary,
        "extracted_reference_number": document.extracted_reference_number,
        "extracted_authority": document.extracted_authority,
        "extracted_expiry_date": document.extracted_expiry_date.isoformat()
        if document.extracted_expiry_date is not None
        else None,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


@router.get("/{lease_id}/summary", response_model=dict, summary="Counts for a lease")
def lease_summary(lease_id: uuid.UUID, session: DbSession) -> dict:
    if session.get(Lease, lease_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found")

    licence_count = session.scalar(
        select(func.count()).select_from(Licence).where(Licence.lease_id == lease_id)
    )
    obligation_count = session.scalar(
        select(func.count())
        .select_from(LeaseObligation)
        .where(LeaseObligation.lease_id == lease_id)
    )
    return {
        "lease_id": lease_id,
        "licence_count": licence_count or 0,
        "obligation_count": obligation_count or 0,
    }
