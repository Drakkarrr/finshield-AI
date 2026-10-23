"""payments: provider-confirmed credit purchases (S6.1)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-24 01:20:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('payments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('tenant_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('provider_ref', sa.String(), nullable=False),
    sa.Column('credits', sa.Integer(), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_payments_tenant_id'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_payments_user_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_ref', name='uq_payments_provider_ref'),
    )
    op.create_index(op.f('ix_payments_tenant_id'), 'payments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        policy = ("current_setting('app.rls_bypass', true) = 'on' "
                  "OR tenant_id = current_setting('app.tenant_id', true)")
        op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE payments FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON payments USING ({policy}) WITH CHECK ({policy})")


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_tenant_id'), table_name='payments')
    op.drop_table('payments')
