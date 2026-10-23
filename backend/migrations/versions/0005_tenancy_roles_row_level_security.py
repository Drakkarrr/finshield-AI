"""tenancy, roles, row-level security (S3.1, S3.4; ruling D3)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23

- tenants table; tenant_id (NOT NULL, FK, indexed) on every tenant-owned table.
- Backfill: before tenancy each user's data was isolated per user, so every existing user becomes
  its own tenant (id 'tenant-<user id>'); child rows inherit their owner's tenant; audit rows with
  no user go to a 'system' tenant. Existing users become admin of their tenant (single-user
  reality; revisit before inviting users).
- users.role with a check constraint (analyst | investigator | supervisor | admin).
- Postgres only: a NOLOGIN application role (finshield_app) that the API switches to on connect,
  because superusers and table owners bypass RLS; grants; RLS policies keyed on app.tenant_id with
  an explicit app.rls_bypass for auth bootstrap and system jobs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "finshield_app"
CHILD_TABLES = ("api_keys", "transactions", "cases", "notifications", "notification_preferences", "rule_configs",
                "case_comments", "case_notes", "filings", "webhook_events", "account_baselines")
RLS_TABLES = ("users", "audit_logs") + CHILD_TABLES
POLICY = ("current_setting('app.rls_bypass', true) = 'on' "
          "OR tenant_id = current_setting('app.tenant_id', true)")


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("users", sa.Column("role", sa.String(), server_default="analyst", nullable=False))
    for table in RLS_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))

    # --- backfill -------------------------------------------------------------------------------
    op.execute("INSERT INTO tenants (id, name, created_at) SELECT 'tenant-' || id, COALESCE(company, email), "
               "COALESCE(created_at, CURRENT_TIMESTAMP) FROM users")
    op.execute("UPDATE users SET tenant_id = 'tenant-' || id, role = 'admin'")
    for table in CHILD_TABLES:
        op.execute(f"UPDATE {table} SET tenant_id = (SELECT u.tenant_id FROM users u WHERE u.id = {table}.user_id)")
    op.execute("UPDATE audit_logs SET tenant_id = (SELECT u.tenant_id FROM users u WHERE u.id = audit_logs.user_id)")
    op.execute("INSERT INTO tenants (id, name, created_at) "
               "SELECT 'system', 'system', CURRENT_TIMESTAMP WHERE EXISTS "
               "(SELECT 1 FROM audit_logs WHERE tenant_id IS NULL)")
    op.execute("UPDATE audit_logs SET tenant_id = 'system' WHERE tenant_id IS NULL")

    # --- constraints ----------------------------------------------------------------------------
    for table in RLS_TABLES:
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False)
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(f"fk_{table}_tenant_id", table, "tenants", ["tenant_id"], ["id"])
    op.create_check_constraint("ck_users_role", "users", "role IN ('analyst', 'investigator', 'supervisor', 'admin')")
    op.drop_constraint("uq_account_baselines_user_account", "account_baselines", type_="unique")
    op.create_unique_constraint("uq_account_baselines_tenant_account", "account_baselines", ["tenant_id", "account_id"])

    if not pg:
        return
    # --- application role + row-level security (Postgres) ---------------------------------------
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END $$""")
    op.execute(f"GRANT {APP_ROLE} TO CURRENT_USER")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {APP_ROLE}")
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in RLS_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {APP_ROLE}")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {APP_ROLE}")
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
        op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.drop_constraint("uq_account_baselines_tenant_account", "account_baselines", type_="unique")
    op.create_unique_constraint("uq_account_baselines_user_account", "account_baselines", ["user_id", "account_id"])
    op.drop_constraint("ck_users_role", "users", type_="check")
    for table in RLS_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_column("users", "role")
    op.drop_table("tenants")
