"""add_audit_hash_chain

Revision ID: e36babffa1a1
Revises: 8fa4ddee248c
Create Date: 2026-10-23 23:33:51.393067
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e36babffa1a1'
down_revision: Union[str, None] = '8fa4ddee248c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('entry_hash', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('chain_sequence', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_audit_logs_entry_hash'), 'audit_logs', ['entry_hash'], unique=False)
    op.create_index(op.f('ix_audit_logs_chain_sequence'), 'audit_logs', ['chain_sequence'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_chain_sequence'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_entry_hash'), table_name='audit_logs')
    op.drop_column('audit_logs', 'chain_sequence')
    op.drop_column('audit_logs', 'entry_hash')
    op.drop_column('audit_logs', 'prev_hash')
