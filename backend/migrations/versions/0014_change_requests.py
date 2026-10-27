"""four-eyes approval workflow for detection changes (S7.4)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-26 06:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "finshield_app"
POLICY = ("current_setting('app.rls_bypass', true) = 'on' "
          "OR tenant_id = current_setting('app.tenant_id', true)")


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"

    op.create_table(
        'change_requests',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('change_type', sa.String(), nullable=False),  # model_promote, rule_disable, rule_override
        sa.Column('resource_id', sa.String(), nullable=False),  # model version id or rule_id
        sa.Column('proposed_by', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('proposed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('approved_by', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),  # pending, approved, rejected
        sa.Column('payload', sa.JSON(), nullable=False),  # The proposed change details
        sa.Column('reason', sa.Text(), nullable=True),
    )

    # Partial unique index: one pending change per resource per tenant
    op.create_index(
        'uq_change_requests_one_pending_per_resource',
        'change_requests',
        ['tenant_id', 'resource_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'") if pg else None,
        sqlite_where=sa.text("status = 'pending'") if not pg else None,
    )

    if pg:
        op.execute("ALTER TABLE change_requests ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE change_requests FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON change_requests USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON change_requests")
        op.execute("ALTER TABLE change_requests NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE change_requests DISABLE ROW LEVEL SECURITY")
    op.drop_table('change_requests')
