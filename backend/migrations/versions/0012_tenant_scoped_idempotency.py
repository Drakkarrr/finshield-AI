"""tenant-scoped idempotency (S7.0)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-26

Drop the global unique constraint on transactions.idempotency_key and replace it with a
tenant-scoped constraint so two tenants can independently use the same key.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_transactions_idempotency_key', table_name='transactions')
    op.create_index('ix_transactions_idempotency_key', 'transactions', ['idempotency_key'])
    op.create_unique_constraint(
        'uq_transactions_tenant_idempotency',
        'transactions',
        ['tenant_id', 'idempotency_key']
    )


def downgrade() -> None:
    op.drop_constraint('uq_transactions_tenant_idempotency', 'transactions', type_='unique')
    op.drop_index('ix_transactions_idempotency_key', table_name='transactions')
    op.create_index('ix_transactions_idempotency_key', 'transactions', ['idempotency_key'], unique=True)
