"""data-subject requests (S3.3)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POLICY = ("current_setting('app.rls_bypass', true) = 'on' "
          "OR tenant_id = current_setting('app.tenant_id', true)")


def upgrade() -> None:
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_ref_enc", sa.Text(), nullable=False),
        sa.Column("subject_ref_hash", sa.String(), nullable=False),
        sa.Column("request_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("handled_by", sa.String(), nullable=True),
        sa.Column("outcome_enc", sa.Text(), nullable=True),
        sa.Column("legal_basis_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["handled_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_privacy_requests_tenant_id", "privacy_requests", ["tenant_id"])
    op.create_index("ix_privacy_requests_subject_ref_hash", "privacy_requests", ["subject_ref_hash"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE privacy_requests ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE privacy_requests FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON privacy_requests USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    op.drop_table("privacy_requests")
