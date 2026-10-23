"""add_tenants_table

Revision ID: 4c5d420e6115
Revises: fafd9c7b4985
Create Date: 2026-10-23 23:46:59.486648
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '4c5d420e6115'
down_revision: Union[str, None] = 'fafd9c7b4985'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("domain", sa.String(), nullable=True, unique=True),
        sa.Column("plan", sa.String(), nullable=False, server_default="starter"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Add tenant_id to users
    op.add_column("users", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)
    
    # Add tenant_id to transactions
    op.add_column("transactions", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_transactions_tenant_id"), "transactions", ["tenant_id"], unique=False)
    
    # Add tenant_id to cases
    op.add_column("cases", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_cases_tenant_id"), "cases", ["tenant_id"], unique=False)
    
    # Add tenant_id to notifications
    op.add_column("notifications", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_notifications_tenant_id"), "notifications", ["tenant_id"], unique=False)
    
    # Add tenant_id to api_keys
    op.add_column("api_keys", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_api_keys_tenant_id"), "api_keys", ["tenant_id"], unique=False)


def downgrade() -> None:
    # Remove tenant_id columns
    op.drop_index(op.f("ix_api_keys_tenant_id"), table_name="api_keys")
    op.drop_column("api_keys", "tenant_id")
    
    op.drop_index(op.f("ix_notifications_tenant_id"), table_name="notifications")
    op.drop_column("notifications", "tenant_id")
    
    op.drop_index(op.f("ix_cases_tenant_id"), table_name="cases")
    op.drop_column("cases", "tenant_id")
    
    op.drop_index(op.f("ix_transactions_tenant_id"), table_name="transactions")
    op.drop_column("transactions", "tenant_id")
    
    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_column("users", "tenant_id")
    
    # Drop tenants table
    op.drop_table("tenants")
