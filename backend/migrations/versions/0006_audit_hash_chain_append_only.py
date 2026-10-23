"""append-only, hash-chained audit trail (S3.2)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23

Existing rows start unsealed; app.domain.audit.seal() chains them on first verify/export or by
the scheduled sealer, so no hashing logic is duplicated here.
On Postgres a trigger makes audit_logs append-only: DELETE and TRUNCATE always fail; UPDATE only
succeeds for the one-time sealing of an unsealed row with every content column unchanged. The
application role additionally loses DELETE/TRUNCATE on the table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "finshield_app"
GENESIS = "0" * 64

APPEND_ONLY = """
CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.seq IS NULL AND NEW.seq IS NOT NULL
       AND NEW.id = OLD.id
       AND NEW.tenant_id = OLD.tenant_id
       AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id
       AND NEW.action = OLD.action
       AND NEW.resource_type IS NOT DISTINCT FROM OLD.resource_type
       AND NEW.resource_id IS NOT DISTINCT FROM OLD.resource_id
       AND NEW.details::text IS NOT DISTINCT FROM OLD.details::text
       AND NEW.ip_address IS NOT DISTINCT FROM OLD.ip_address
       AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
    THEN
        RETURN NEW;  -- sealing: chain fields written once
    END IF;
    RAISE EXCEPTION 'audit_logs is append-only (% rejected)', TG_OP;
END
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("seq", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("entry_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("sealed_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_audit_logs_tenant_seq", "audit_logs", ["tenant_id", "seq"])
    op.create_table(
        "audit_chain_heads",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("last_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.execute(f"INSERT INTO audit_chain_heads (tenant_id, seq, last_hash, updated_at) "
               f"SELECT id, 0, '{GENESIS}', CURRENT_TIMESTAMP FROM tenants")
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(APPEND_ONLY)
    op.execute("CREATE TRIGGER audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
               "FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()")
    op.execute("CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs "
               "FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_append_only()")
    op.execute(f"REVOKE DELETE, TRUNCATE ON audit_logs FROM {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON audit_chain_heads TO {APP_ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only()")
        op.execute(f"GRANT DELETE, TRUNCATE ON audit_logs TO {APP_ROLE}")
    op.drop_table("audit_chain_heads")
    op.drop_constraint("uq_audit_logs_tenant_seq", "audit_logs", type_="unique")
    for column in ("sealed_at", "entry_hash", "prev_hash", "seq"):
        op.drop_column("audit_logs", column)
