"""The audit trail.

One append-only row per state-changing action, recording **who** did **what** to
**which record**, and whether it was permitted. Deliberately not a field-level
before/after diff: the requirement is to answer "who filed this return, and
when", which a diff makes no easier and considerably bulkier.

Three design choices matter:

* **Append-only in the database.** A trigger rejects UPDATE and DELETE, so the
  guarantee does not depend on application code remembering to behave.
* **No foreign key to the actor.** The trail has to outlive the user it
  describes; deleting a colleague must not cascade their history away. The id,
  email and display name are snapshotted onto each row instead.
* **Refusals are recorded too.** A denied attempt to waive a statutory filing is
  at least as interesting to an auditor as a successful one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, enum_column
from app.models.enums import AuditAction, AuditEntity, AuditOutcome


class AuditLog(UUIDMixin, Base):
    """An immutable record of one attempted or completed action."""

    __tablename__ = "audit_log"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # --- Who ---
    actor_id: Mapped[str] = mapped_column(String(200), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(320))
    actor_label: Mapped[str | None] = mapped_column(String(200))
    actor_role: Mapped[str | None] = mapped_column(String(24))
    #: "supabase" or "disabled" - makes development traffic identifiable in a
    #: production log dump without guessing from the actor id.
    auth_method: Mapped[str] = mapped_column(String(24))

    # --- What ---
    action: Mapped[AuditAction] = mapped_column(enum_column(AuditAction), index=True)
    outcome: Mapped[AuditOutcome] = mapped_column(
        enum_column(AuditOutcome), default=AuditOutcome.SUCCEEDED, index=True
    )
    summary: Mapped[str] = mapped_column(Text)

    # --- Which record ---
    entity_type: Mapped[AuditEntity] = mapped_column(enum_column(AuditEntity), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    #: Human-readable identity captured at write time, so the entry still reads
    #: correctly after the record is renamed or deleted.
    entity_label: Mapped[str | None] = mapped_column(String(240))

    #: Names of the attributes touched. Names only - this is not a value diff.
    changed_fields: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), default=list, server_default=text("'{}'::varchar[]")
    )
    #: Small structured extras that do not fit the columns above, e.g. the reason
    #: recorded for a waiver.
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # --- How ---
    http_method: Mapped[str | None] = mapped_column(String(10))
    http_path: Mapped[str | None] = mapped_column(String(400))
    http_status: Mapped[int | None] = mapped_column(Integer)
    #: Best-effort client address. Behind a proxy this is only as trustworthy as
    #: the proxy's forwarding configuration, so it is evidence, not proof.
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))

    __table_args__ = (
        # The two questions actually asked of a trail: everything that happened
        # to this record, and everything this person did.
        Index("ix_audit_log_entity", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_log_actor_time", "actor_id", "occurred_at"),
        Index("ix_audit_log_outcome_time", "outcome", "occurred_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditLog {self.action} {self.entity_type} by={self.actor_id}>"
