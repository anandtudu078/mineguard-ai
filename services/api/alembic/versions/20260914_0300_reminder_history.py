"""add reminder delivery history

Revision ID: reminder_history_20260914
Revises: lease_documents_20260914
Create Date: 2026-09-14 03:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "reminder_history_20260914"
down_revision: Union[str, None] = "lease_documents_20260914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminder_deliveries",
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("provider", sa.String(length=32), server_default="resend", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["obligation_id"], ["lease_obligations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_deliveries")),
    )
    op.create_index(op.f("ix_reminder_deliveries_obligation_id"), "reminder_deliveries", ["obligation_id"])
    op.create_index(op.f("ix_reminder_deliveries_recipient_email"), "reminder_deliveries", ["recipient_email"])
    op.create_index(op.f("ix_reminder_deliveries_status"), "reminder_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_reminder_deliveries_status"), table_name="reminder_deliveries")
    op.drop_index(op.f("ix_reminder_deliveries_recipient_email"), table_name="reminder_deliveries")
    op.drop_index(op.f("ix_reminder_deliveries_obligation_id"), table_name="reminder_deliveries")
    op.drop_table("reminder_deliveries")