"""Alert and escalation ladder for inspection findings.

Severity decides who hears about a finding and how fast:

* **critical/high** -> email immediately on detection, escalate to the inspector
  role if still unacknowledged after 48 hours.
* **medium/low** -> email only, no automatic escalation.

Deliveries go through Resend (already wired for reminders) and every step is
audit-logged, because "the AI said so" must itself be accountable.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import (
    AuditAction,
    AuditEntity,
    FindingStatus,
    ViolationSeverity,
)
from app.models.finding import InspectionFinding
from app.models.lease import Lease
from app.services.audit import record

logger = logging.getLogger(__name__)

#: An unacknowledged critical/high finding older than this gets escalated.
ESCALATION_AFTER_HOURS = 48

_ESCALATION_LADDER = {ViolationSeverity.CRITICAL, ViolationSeverity.HIGH}

#: Severity -> subject prefix, so a full inbox can be triaged at a glance.
_SUBJECT_TAG = {
    ViolationSeverity.CRITICAL: "CRITICAL",
    ViolationSeverity.HIGH: "HIGH",
    ViolationSeverity.MEDIUM: "MEDIUM",
    ViolationSeverity.LOW: "LOW",
}


def send_finding_alert(
    session: Session,
    finding: InspectionFinding,
    lease: Lease,
    *,
    settings: Settings,
    recipient_email: str,
) -> bool:
    """Email one finding alert. Returns True when Resend accepted it."""
    if not settings.resend_api_key or not settings.resend_from_email:
        logger.warning("Resend not configured; finding alert for %s skipped", finding.id)
        return False

    tag = _SUBJECT_TAG.get(finding.severity, "FINDING")
    subject = f"[{tag}] {finding.title} - {lease.name} ({lease.lease_number})"
    body = "\n".join(
        [
            f"A site finding requires attention at {lease.name} ({lease.lease_number}).",
            "",
            f"Finding:    {finding.title}",
            f"Severity:   {finding.severity.value.upper()}",
            f"Source:     {finding.source.value}",
            f"Detected:   {finding.detected_at:%d %b %Y %H:%M UTC}",
            "",
            finding.description or "",
            "",
            (
                f"Corrective action required: {finding.corrective_action}"
                if finding.corrective_action
                else "Corrective action: to be assigned."
            ),
            "",
            "Open the lease dashboard to acknowledge or resolve this finding.",
        ]
    )

    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [recipient_email],
                "subject": subject,
                "text": body,
            },
            timeout=20,
        )
        response.raise_for_status()
    except Exception as error:
        logger.error("Failed to send finding alert for %s: %s", finding.id, error)
        return False

    if finding.first_alerted_at is None:
        finding.first_alerted_at = datetime.now(UTC)
    return True


def run_escalation_sweep(
    session: Session,
    *,
    settings: Settings,
    as_of: datetime | None = None,
    inspector_email: str | None = None,
) -> dict[str, int]:
    """Escalate unacknowledged critical/high findings older than 48h.

    Designed to be called from a periodic job (Celery beat or cron). Idempotent:
    a finding is escalated at most once per sweep cycle because the level guard
    advances only when an email is actually sent.
    """
    now = as_of or datetime.now(UTC)
    cutoff = now - timedelta(hours=ESCALATION_AFTER_HOURS)

    candidates = list(
        session.scalars(
            select(InspectionFinding)
            .where(
                InspectionFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_PROGRESS]),
                InspectionFinding.severity.in_(_ESCALATION_LADDER),
                InspectionFinding.acknowledged_at.is_(None),
                InspectionFinding.detected_at <= cutoff,
                InspectionFinding.escalation_level == 0,
            )
            .order_by(InspectionFinding.detected_at.asc())
        ).all()
    )

    stats = {"candidates": len(candidates), "escalated": 0, "failed": 0, "skipped": 0}
    if not candidates:
        return stats

    for finding in candidates:
        lease = session.get(Lease, finding.lease_id)
        if lease is None:
            stats["skipped"] += 1
            continue

        target = inspector_email
        if not target:
            # Fall back to the holder's own contact; the ladder needs a person.
            target = lease.holder.email if lease.holder else None
        if not target:
            stats["skipped"] += 1
            continue

        if send_finding_alert(session, finding, lease, settings=settings, recipient_email=target):
            finding.escalation_level = 1
            finding.last_escalated_at = now
            record(
                session,
                _system_principal(settings),
                None,
                action=AuditAction.UPDATE,
                entity_type=AuditEntity.FINDING,
                summary=f"Escalated unacknowledged {finding.severity.value} finding: {finding.title}",
                entity_id=finding.id,
                entity_label=f"{lease.lease_number} / {finding.title}",
            )
            stats["escalated"] += 1
        else:
            stats["failed"] += 1

    session.commit()
    return stats


def _system_principal(settings: Settings):  # noqa: ANN202 - Principal import cycle
    """A synthetic principal for machine-initiated audit entries.

    Imported lazily: ``Principal`` lives in security, which imports config but
    not services, so a top-level import would be fine - this is purely about
    keeping the module import graph shallow for tests.
    """
    from app.core.security import Principal

    return Principal(
        user_id="system:escalation",
        email=None,
        label="Escalation worker",
        role=None,
        holder_id=None,
        auth_method="system",
    )
