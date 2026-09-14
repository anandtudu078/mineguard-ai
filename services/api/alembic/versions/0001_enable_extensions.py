"""Enable required PostgreSQL extensions.

These must exist before any table is created, so this revision is the base of
the migration chain and is intentionally separate from the schema revision that
follows it.

Revision ID: 0001
Revises:
Create Date: 2026-09-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: ``postgis``  -> boundary polygons, centroids and spatial predicates
#: ``vector``   -> pgvector, semantic search over regulations and documents
#: ``pg_trgm``  -> fuzzy matching on lease numbers and holder names
#: ``btree_gist`` -> exclusion constraints over validity windows
EXTENSIONS = (
    ("postgis", "PostGIS"),
    ("vector", "pgvector"),
    ("pg_trgm", "pg_trgm"),
    ("btree_gist", "btree_gist"),
)


def upgrade() -> None:
    for extension, label in EXTENSIONS:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")
        print(f"  ensured extension: {label}")


def downgrade() -> None:
    # Extensions are left in place: dropping them would cascade into columns
    # owned by other consumers of the database.
    pass
