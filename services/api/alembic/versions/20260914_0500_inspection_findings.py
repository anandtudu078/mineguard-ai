"""add inspection findings for the visual compliance loop

Revision ID: inspection_findings_20260914
Revises: document_extraction_20260914
Create Date: 2026-09-14 05:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "inspection_findings_20260914"
down_revision: Union[str, None] = "document_extraction_20260914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inspection_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "lease_id",
            sa.Uuid(),
            sa.ForeignKey("leases.id", ondelete="CASCADE", name="fk_inspection_findings_lease_id_leases"),
            nullable=False,
            index=True,
        ),
        sa.Column("source", sa.String(length=48), nullable=False, server_default="manual", index=True),
        sa.Column("image_path", sa.String(length=400)),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("severity", sa.String(length=48), nullable=False, server_default="medium", index=True),
        sa.Column("status", sa.String(length=48), nullable=False, server_default="open", index=True),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("ai_model", sa.String(length=80)),
        sa.Column("ai_raw", JSONB()),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("first_alerted_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_escalated_at", sa.DateTime(timezone=True)),
        sa.Column("corrective_action", sa.Text()),
        sa.Column("action_owner", sa.String(length=200)),
        sa.Column("action_due_date", sa.Date()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(length=320)),
        sa.Column("resolution_note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "source IN ('ai_vision', 'operator', 'inspector', 'manual')",
            name="ck_inspection_findings_source",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name="ck_inspection_findings_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'false_positive')",
            name="ck_inspection_findings_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("inspection_findings")
