"""add_user_role_column

Revision ID: 8fa4ddee248c
Revises: 40c3dd896fc7
Create Date: 2026-10-23 23:22:54.156810
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '8fa4ddee248c'
down_revision: Union[str, None] = '40c3dd896fc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(), nullable=True, server_default='user'))
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_column('users', 'role')
