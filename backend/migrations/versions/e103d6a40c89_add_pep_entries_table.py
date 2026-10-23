"""add_pep_entries_table

Revision ID: e103d6a40c89
Revises: 0002
Create Date: 2026-10-23 23:11:26.595392
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e103d6a40c89'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pep_entries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('position', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pep_entries_name'), 'pep_entries', ['name'], unique=False)
    op.create_index(op.f('ix_pep_entries_country'), 'pep_entries', ['country'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pep_entries_country'), table_name='pep_entries')
    op.drop_index(op.f('ix_pep_entries_name'), table_name='pep_entries')
    op.drop_table('pep_entries')
