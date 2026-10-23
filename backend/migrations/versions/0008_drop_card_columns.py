"""drop plaintext card columns (S3.5, ruling D8)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-24

Card metadata with no payment provider behind it is pure liability. The columns are deleted, not
encrypted; Stripe customer/payment-method ids replace them in S6.1. Downgrade restores empty
columns only: the values are intentionally unrecoverable.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ("saved_card_last4", "saved_card_expiry", "saved_card_holder")


def upgrade() -> None:
    for column in COLUMNS:
        op.drop_column("users", column)


def downgrade() -> None:
    for column in COLUMNS:
        op.add_column("users", sa.Column(column, sa.String(), nullable=True))
