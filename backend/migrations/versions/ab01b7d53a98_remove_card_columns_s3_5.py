"""remove_card_columns_s3_5

Revision ID: ab01b7d53a98
Revises: 4c5d420e6115
Create Date: 2026-10-23 23:52:20.435845
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'ab01b7d53a98'
down_revision: Union[str, None] = '4c5d420e6115'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove card columns (S3.5 - no storing payment card data)
    op.drop_column("users", "saved_card_last4")
    op.drop_column("users", "saved_card_expiry")
    op.drop_column("users", "saved_card_holder")


def downgrade() -> None:
    # Restore card columns
    op.add_column("users", sa.Column("saved_card_holder", sa.String(), nullable=True))
    op.add_column("users", sa.Column("saved_card_expiry", sa.String(), nullable=True))
    op.add_column("users", sa.Column("saved_card_last4", sa.String(), nullable=True))
