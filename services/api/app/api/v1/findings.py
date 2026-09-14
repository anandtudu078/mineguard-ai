"""Inspection findings: the photo-to-resolution compliance loop.

Endpoints cover the whole arc: upload a site photo and let the vision model
detect violations, acknowledge/assign/resolve findings, and trigger the 48-hour
escalation sweep manually (the same code path a scheduled job would call).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import AppSettings, AuditCtx, CurrentPrincipal, DbSession, PaginationDep
from app.core.permissions import Permission, role_has
from app.models.document import DocumentStatus, DocumentType, LeaseDocument
from app.models.enums import (
    AuditAction,
    AuditEntity,
    FindingSource,
    FindingStatus,
    ViolationSeverity,
)
from app.models.finding import InspectionFinding
from app.schemas.common import Page
from app.services import vision
from app.services.audit import record
from app.services.authorization import assert_lease_access, require_permission
from app.services.findings import run_escalation_sweep, send_finding_alert

router = APIRouter(prefix="/leases/{lease_id}/findings", tags=["findings"])

#: Severities that page someone immediately on detection.
_IMMEDIATE_ALERT_SEVERITIES = {ViolationSeverity.CRITICAL, ViolationSeverity.HIGH}


def _serialize(finding: InspectionFinding) -> dict:
    """One finding as the API returns it."""
    return {
        "id": str(finding.id),
        "lease_id": str(finding.lease_id),
        "source": finding.source,
        "image_path": finding.image_path,
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity,
        "status": finding.status,
        "confidence": float(finding.confidence) if finding.confidence is not None else None,
        "ai_model": finding.ai_model,
        "detected_at": finding.detected_at.isoformat(),
        "first_alerted_at": finding.first_alerted_at.isoformat() if finding.first_alerted_at else None,
        "acknowledged_at": finding.acknowledged_at.isoformat() if finding.acknowledged_at else None,
        "escalation_level": finding.escalation_level,
        "last_escalated_at": finding.last_escalated_at.isoformat() if finding.last_escalated_at else None,
        "corrective_action": finding.corrective_action,
        "action_owner": finding.action_owner,
        "action_due_date": finding.action_due_date.isoformat() if finding.action_due_date else None,
        "resolved_at": finding.resolved_at.isoformat() if finding.resolved_at else None,
        "resolved_by": finding.resolved_by,
        "resolution_note": finding.resolution_note,
        "created_at": finding.created_at.isoformat(),
        "updated_at": finding.updated_at.isoformat(),
    }


def _alert_recipients(lease) -> list[str]:
    """Who gets alerts for this lease: the holder's registered contact."""
    if lease.holder and lease.holder.email:
        return [lease.holder.email]
    return []


@router.post(
    "/analyze",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a site photo, run AI violation detection, record findings",
)
async def analyze_lease_photo(
    lease_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
    audit: AuditCtx,
    file: UploadFile = File(...),
    auto_alert: bool = Form(default=True),
) -> dict:
    """Photo in, structured findings out.

    The vision call is fail-closed: if the model is unreachable or returns
    garbage, nothing is recorded as AI-produced and the error names the cause.
    """
    lease = assert_lease_access(session, principal, audit, lease_id, action="analyse site photo")
    require_permission(
        session,
        principal,
        audit,
        Permission.LEASE_WRITE,
        entity_type=AuditEntity.FINDING,
        entity_id=lease_id,
        entity_label=lease.lease_number,
    )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Uploaded file is empty")

    # Persist the photo first: evidence survives even if analysis fails.
    storage_dir = Path(settings.document_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_name = file.filename or f"site-photo-{uuid.uuid4()}.jpg"
    stored_name = f"{uuid.uuid4()}_{file_name}"
    stored_path = storage_dir / stored_name
    stored_path.write_bytes(raw_bytes)

    document = LeaseDocument(
        lease_id=lease_id,
        title=f"Site photo: {file_name}",
        file_name=file_name,
        content_type=file.content_type or "image/jpeg",
        file_path=str(stored_path),
        document_type=DocumentType.EVIDENCE,
        source="ai_vision",
        status=DocumentStatus.PENDING_REVIEW,
        notes="Uploaded for AI violation detection",
        extracted_summary="Uploaded for AI violation detection",
    )
    session.add(document)
    session.flush()

    try:
        result = vision.analyze_site_photo(
            raw_bytes, file.content_type or "image/jpeg", settings
        )
    except Exception as error:
        session.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Vision analysis failed: {error}",
        ) from error

    created: list[InspectionFinding] = []
    for item in result.findings:
        finding = InspectionFinding(
            lease_id=lease_id,
            source=FindingSource.AI_VISION,
            image_path=str(stored_path),
            title=item.title,
            description=item.description,
            severity=item.severity,
            status=FindingStatus.OPEN,
            confidence=item.confidence,
            ai_model=result.model_name,
            ai_raw=result.raw,
        )
        session.add(finding)
        created.append(finding)

    if created:
        recipients = _alert_recipients(lease)
        if auto_alert and recipients:
            for finding in created:
                if finding.severity in _IMMEDIATE_ALERT_SEVERITIES:
                    if send_finding_alert(
                        session, finding, lease, settings=settings, recipient_email=recipients[0]
                    ):
                        finding.first_alerted_at = finding.first_alerted_at or datetime.now(UTC)

        record(
            session,
            principal,
            audit,
            action=AuditAction.CREATE,
            entity_type=AuditEntity.FINDING,
            summary=f"AI vision detected {len(created)} finding(s) from {file_name}",
            entity_id=created[0].id,
            entity_label=f"{lease.lease_number} / {created[0].title}",
            context_extra={
                "lease_id": str(lease_id),
                "finding_count": len(created),
                "model": result.model_name,
                "severities": [f.severity.value for f in created],
            },
        )

    session.commit()
    for finding in created:
        session.refresh(finding)

    return {
        "lease_id": str(lease_id),
        "document_id": str(document.id),
        "summary": result.summary,
        "model": result.model_name,
        "findings": [_serialize(f) for f in created],
    }


@router.get(
    "",
    response_model=Page[dict],
    summary="List findings for a lease",
)
def list_findings(
    lease_id: uuid.UUID,
    session: DbSession,
    principal: CurrentPrincipal,
    audit: AuditCtx,
    page: PaginationDep,
    finding_status: FindingStatus | None = None,
    severity: ViolationSeverity | None = None,
) -> Page[dict]:
    assert_lease_access(session, principal, audit, lease_id, action="list findings")

    conditions = [InspectionFinding.lease_id == lease_id]
    if finding_status is not None:
        conditions.append(InspectionFinding.status == finding_status)
    if severity is not None:
        conditions.append(InspectionFinding.severity == severity)

    total = (
        session.scalar(
            select(func.count()).select_from(InspectionFinding).where(*conditions)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(InspectionFinding)
            .where(*conditions)
            .order_by(InspectionFinding.detected_at.desc())
            .limit(page.limit)
            .offset(page.offset)
        ).all()
    )
    return Page(items=[_serialize(f) for f in rows], total=total, limit=page.limit, offset=page.offset)


@router.post(
    "/escalation-sweep",
    response_model=dict,
    summary="Escalate unacknowledged critical/high findings older than 48h",
)
def escalation_sweep(
    lease_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
    audit: AuditCtx,
) -> dict:
    """Manual trigger for the demo; a scheduled job would call the same service."""
    lease = assert_lease_access(session, principal, audit, lease_id, action="run escalation sweep")
    require_permission(
        session,
        principal,
        audit,
        Permission.LEASE_WRITE,
        entity_type=AuditEntity.FINDING,
        entity_id=lease_id,
        entity_label=lease.lease_number,
    )

    recipients = _alert_recipients(lease)
    stats = run_escalation_sweep(
        session,
        settings=settings,
        inspector_email=recipients[0] if recipients else None,
    )
    record(
        session,
        principal,
        audit,
        action=AuditAction.UPDATE,
        entity_type=AuditEntity.FINDING,
        summary=(
            f"Escalation sweep on {lease.lease_number}: "
            f"{stats['escalated']} escalated, {stats['failed']} failed"
        ),
        entity_id=lease_id,
        entity_label=lease.lease_number,
        context_extra=stats,
    )
    session.commit()
    return stats


@router.post(
    "/{finding_id}/acknowledge",
    response_model=dict,
    summary="Acknowledge a finding (stops the escalation clock)",
)
def acknowledge_finding(
    lease_id: uuid.UUID,
    finding_id: uuid.UUID,
    session: DbSession,
    principal: CurrentPrincipal,
    audit: AuditCtx,
) -> dict:
    finding = _get_finding_or_404(session, lease_id, finding_id)
    _require_write(session, principal, audit, finding)

    if finding.acknowledged_at is None:
        finding.acknowledged_at = datetime.now(UTC)
        record(
            session,
            principal,
            audit,
            action=AuditAction.UPDATE,
            entity_type=AuditEntity.FINDING,
            summary=f"Acknowledged finding: {finding.title}",
            entity_id=finding.id,
            entity_label=finding.title,
        )
        session.commit()
        session.refresh(finding)
    return _serialize(finding)


@router.patch(
    "/{finding_id}",
    response_model=dict,
    summary="Update a finding: assign action, change severity, mark false positive",
)
def update_finding(
    lease_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: dict,
    session: DbSession,
    principal: CurrentPrincipal,
    audit: AuditCtx,
) -> dict:
    finding = _get_finding_or_404(session, lease_id, finding_id)
    _require_write(session, principal, audit, finding)

    changed: list[str] = []
    if "corrective_action" in payload:
        finding.corrective_action = payload["corrective_action"]
        changed.append("corrective_action")
    if "action_owner" in payload:
        finding.action_owner = payload["action_owner"]
        changed.append("action_owner")
    if "action_due_date" in payload:
        raw = payload["action_due_date"]
        finding.action_due_date = date.fromisoformat(raw) if raw else None
        changed.append("action_due_date")
    if payload.get("severity"):
        finding.severity = ViolationSeverity(payload["severity"])
        changed.append("severity")
    if payload.get("status") == "false_positive":
        finding.status = FindingStatus.FALSE_POSITIVE
        changed.append("status")

    if changed:
        record(
            session,
            principal,
            audit,
            action=AuditAction.UPDATE,
            entity_type=AuditEntity.FINDING,
            summary=f"Updated finding {finding.title}: {', '.join(changed)}",
            entity_id=finding.id,
            entity_label=finding.title,
            changed_fields=changed,
        )
        session.commit()
        session.refresh(finding)
    return _serialize(finding)


@router.post(
    "/{finding_id}/resolve",
    response_model=dict,
    summary="Close a finding with a resolution note (recovers the score)",
)
def resolve_finding(
    lease_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: dict,
    session: DbSession,
    principal: CurrentPrincipal,
    audit: AuditCtx,
) -> dict:
    finding = _get_finding_or_404(session, lease_id, finding_id)
    _require_write(session, principal, audit, finding)

    if finding.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE):
        raise HTTPException(status.HTTP_409_CONFLICT, "Finding is already closed")

    finding.status = FindingStatus.RESOLVED
    finding.resolved_at = datetime.now(UTC)
    finding.resolved_by = principal.email or principal.label
    finding.resolution_note = payload.get("resolution_note")
    record(
        session,
        principal,
        audit,
        action=AuditAction.UPDATE,
        entity_type=AuditEntity.FINDING,
        summary=f"Resolved finding: {finding.title}",
        entity_id=finding.id,
        entity_label=finding.title,
    )
    session.commit()
    session.refresh(finding)
    return _serialize(finding)


def _require_write(session, principal, audit, finding) -> None:
    """Permission gate shared by the per-finding mutations."""
    require_permission(
        session,
        principal,
        audit,
        Permission.LEASE_WRITE,
        entity_type=AuditEntity.FINDING,
        entity_id=finding.id,
        entity_label=finding.title,
    )


def _get_finding_or_404(session, lease_id: uuid.UUID, finding_id: uuid.UUID) -> InspectionFinding:
    """Fetch a finding scoped to its lease, or raise 404."""
    finding = session.get(InspectionFinding, finding_id)
    if finding is None or finding.lease_id != lease_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    return finding
