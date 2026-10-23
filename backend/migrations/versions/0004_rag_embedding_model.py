"""record the embedding model on every RAG row (S2.4)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("compliance_documents", "sanctions_entries", "precedent_decisions")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("embedding_model", sa.String(), nullable=True))
        # Rows written before S2.4 were embedded by the hashing embedder (the semantic path could
        # not activate). Labelling them lets retrieval refuse to mix them with MiniLM vectors.
        op.execute(f"UPDATE {table} SET embedding_model = 'hash-v1' WHERE embedding IS NOT NULL")


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "embedding_model")
