"""Application users: the authorisation profile behind a Supabase identity.

Supabase authenticates a person and tells us *who* they are. It deliberately
says nothing about what they may do here, so this table holds that: the role, and
the organisational scope an operator is confined to.

Rows are keyed by the Supabase ``sub`` claim, so the same id appears in the token
and in this table and no mapping step is needed. The trade-off is that Supabase
owns the lifecycle - deleting a user there orphans the row here - which is why
``is_active`` exists: disabling is the in-application lever, and it survives.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, enum_column
from app.models.enums import AppRole

if TYPE_CHECKING:
    from app.models.holder import LeaseHolder


class AppUser(TimestampMixin, Base):
    """A signed-in person and what they are permitted to do."""

    __tablename__ = "app_users"

    #: The Supabase ``sub`` claim. Not generated here - Supabase is the identity
    #: provider, and a locally invented id could never match a real token.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    email: Mapped[str | None] = mapped_column(String(320), index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))

    role: Mapped[AppRole] = mapped_column(
        enum_column(AppRole), default=AppRole.OPERATOR, server_default=text("'operator'"), index=True
    )

    #: The organisation this user acts for. Required in practice for an operator
    #: (it is what their access is scoped to) and ignored for the other roles.
    holder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lease_holders.id", ondelete="SET NULL"), index=True
    )

    #: Soft disable. Preferred over deletion so a departed colleague's audit
    #: entries keep resolving to a real identity.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    holder: Mapped[LeaseHolder | None] = relationship()

    @property
    def is_operator_without_scope(self) -> bool:
        """An operator with no holder cannot legitimately reach any lease.

        Surfaced so the UI can explain the situation rather than showing an
        empty register that looks like a bug.
        """
        return self.role is AppRole.OPERATOR and self.holder_id is None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AppUser {self.email or self.id} role={self.role}>"
