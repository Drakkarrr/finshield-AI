"""add_webhook_subscriptions

Revision ID: 52ea8383fc71
Revises: ab01b7d53a98
Create Date: 2026-10-23 23:55:01.698110
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '52ea8383fc71'
down_revision: Union[str, None] = 'ab01b7d53a98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("delivery_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_webhook_subscriptions_user_id"), "webhook_subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_webhook_subscriptions_is_active"), "webhook_subscriptions", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_subscriptions_is_active"), table_name="webhook_subscriptions")
    op.drop_index(op.f("ix_webhook_subscriptions_user_id"), table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
