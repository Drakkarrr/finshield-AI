"""filing versioning for submitted filings (S7.3)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-26 05:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "finshield_app"
POLICY = ("current_setting('app.rls_bypass', true) = 'on' "
          "OR tenant_id = current_setting('app.tenant_id', true)")


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"

    op.create_table(
        'filing_versions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('filing_id', sa.String(), sa.ForeignKey('filings.id'), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('narrative', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.UniqueConstraint('filing_id', 'version_number', name='uq_filing_versions_filing_version'),
    )

    if pg:
        op.execute("ALTER TABLE filing_versions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE filing_versions FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON filing_versions USING ({POLICY}) WITH CHECK ({POLICY})")

        # Backfill version 1 for existing submitted/confirmed filings (pre-existing data protection)
        # gen_random_uuid() is Postgres-only; SQLite tests use empty databases or Python-generated IDs
        op.execute("""
            INSERT INTO filing_versions (id, filing_id, tenant_id, version_number, narrative, changed_by, changed_at, change_reason)
            SELECT
                gen_random_uuid()::text,
                f.id,
                f.tenant_id,
                1,
                f.narrative,
                COALESCE(f.submitted_by, f.user_id),
                COALESCE(f.submitted_at, f.updated_at, f.created_at, now()),
                'Backfilled version 1 for pre-existing filing'
            FROM filings f
            WHERE f.status IN ('submitted', 'confirmed')
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON filing_versions")
        op.execute("ALTER TABLE filing_versions NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE filing_versions DISABLE ROW LEVEL SECURITY")
    op.drop_table('filing_versions')
