"""add_dsar_requests_table

Revision ID: fafd9c7b4985
Revises: e36babffa1a1
Create Date: 2026-10-23 23:41:49.380404
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'fafd9c7b4985'
down_revision: Union[str, None] = 'e36babffa1a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dsar_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('request_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by', sa.String(), nullable=True),
        sa.Column('data_export_path', sa.String(), nullable=True),
        sa.Column('records_affected', sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column('retention_preserved', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_dsar_requests_user_id'), 'dsar_requests', ['user_id'], unique=False)
    op.create_index(op.f('ix_dsar_requests_status'), 'dsar_requests', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dsar_requests_status'), table_name='dsar_requests')
    op.drop_index(op.f('ix_dsar_requests_user_id'), table_name='dsar_requests')
    op.drop_table('dsar_requests')
