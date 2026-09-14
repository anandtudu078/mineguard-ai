"""add structured document extraction fields

Revision ID: document_extraction_20260914
Revises: reminder_history_20260914
Create Date: 2026-09-14 04:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "document_extraction_20260914"
down_revision: Union[str, None] = "reminder_history_20260914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lease_documents", sa.Column("extracted_reference_number", sa.String(length=160)))
    op.add_column("lease_documents", sa.Column("extracted_authority", sa.String(length=200)))


def downgrade() -> None:
    op.drop_column("lease_documents", "extracted_authority")
    op.drop_column("lease_documents", "extracted_reference_number")