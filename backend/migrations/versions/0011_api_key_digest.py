"""api key digest for O(1), bcrypt-free per-request lookup (S6.5)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-24 03:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing keys keep NULL and get their digest on first successful use (bcrypt verified once).
    op.add_column('api_keys', sa.Column('key_digest', sa.String(), nullable=True))
    op.create_unique_constraint('uq_api_keys_key_digest', 'api_keys', ['key_digest'])


def downgrade() -> None:
    op.drop_constraint('uq_api_keys_key_digest', 'api_keys', type_='unique')
    op.drop_column('api_keys', 'key_digest')
