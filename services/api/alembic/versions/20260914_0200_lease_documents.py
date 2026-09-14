"""add lease document ingestion table

Revision ID: lease_documents_20260914
Revises: 349db90d53f4
Create Date: 2026-09-14 02:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "lease_documents_20260914"
down_revision: Union[str, None] = "349db90d53f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lease_documents",
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("file_path", sa.String(length=400), nullable=False),
        sa.Column("document_type", sa.String(length=48), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extracted_summary", sa.Text(), nullable=True),
        sa.Column("extracted_expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], name=op.f("fk_lease_documents_lease_id_leases"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lease_documents")),
        sa.UniqueConstraint("file_path", name=op.f("uq_lease_documents_file_path")),
    )
    op.create_index(op.f("ix_lease_documents_lease_id"), "lease_documents", ["lease_id"], unique=False)
    op.create_index(op.f("ix_lease_documents_title"), "lease_documents", ["title"], unique=False)
    op.create_index(op.f("ix_lease_documents_file_name"), "lease_documents", ["file_name"], unique=False)
    op.create_index(op.f("ix_lease_documents_content_type"), "lease_documents", ["content_type"], unique=False)
    op.create_index(op.f("ix_lease_documents_document_type"), "lease_documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_lease_documents_source"), "lease_documents", ["source"], unique=False)
    op.create_index(op.f("ix_lease_documents_status"), "lease_documents", ["status"], unique=False)
    op.create_index(op.f("ix_lease_documents_extracted_expiry_date"), "lease_documents", ["extracted_expiry_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_lease_documents_extracted_expiry_date"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_status"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_source"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_document_type"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_content_type"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_file_name"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_title"), table_name="lease_documents")
    op.drop_index(op.f("ix_lease_documents_lease_id"), table_name="lease_documents")
    op.drop_table("lease_documents")
