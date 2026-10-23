"""Multi-tenancy service with tenant isolation (S3.4)."""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db_models import Tenant, User


class TenantService:
    """Service for multi-tenancy operations."""

    @staticmethod
    def get_tenant(db: Session, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    @staticmethod
    def get_tenant_by_slug(db: Session, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        return db.query(Tenant).filter(Tenant.slug == slug).first()

    @staticmethod
    def create_tenant(
        db: Session,
        name: str,
        slug: str,
        domain: Optional[str] = None,
        plan: str = "starter",
        max_users: int = 10,
    ) -> Tenant:
        """Create a new tenant."""
        # Check if slug already exists
        existing = db.query(Tenant).filter(Tenant.slug == slug).first()
        if existing:
            raise ValueError(f"Tenant slug '{slug}' already exists")

        tenant = Tenant(
            name=name,
            slug=slug,
            domain=domain,
            plan=plan,
            max_users=max_users,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def assign_user_to_tenant(db: Session, user_id: str, tenant_id: str) -> User:
        """Assign a user to a tenant."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        if not tenant.is_active:
            raise ValueError(f"Tenant {tenant.slug} is inactive")

        # Check tenant user limit
        user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
        if user_count >= tenant.max_users:
            raise ValueError(f"Tenant {tenant.slug} has reached max users ({tenant.max_users})")

        user.tenant_id = tenant_id
        db.commit()
        return user

    @staticmethod
    def require_tenant_context(db: Session, user: User, resource_tenant_id: Optional[str]):
        """Ensure user can only access resources in their tenant."""
        if user.tenant_id is None:
            # User is not in a tenant, allow access (single-tenant mode)
            return

        if resource_tenant_id is None:
            # Resource has no tenant, deny access
            raise HTTPException(403, "Tenant context required")

        if user.tenant_id != resource_tenant_id:
            # Cross-tenant access denied
            raise HTTPException(404, "Resource not found")

    @staticmethod
    def setup_rls_policies(db: Session):
        """Set up Postgres Row Level Security policies for tenant isolation."""
        # Enable RLS on tables
        tables = ["users", "transactions", "cases", "notifications", "api_keys"]
        
        for table in tables:
            # Enable RLS
            db.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            
            # Create policy for tenant isolation
            # Users can only see rows where tenant_id matches their tenant
            policy_name = f"{table}_tenant_isolation"
            db.execute(text(f"""
                CREATE POLICY {policy_name} ON {table}
                FOR ALL
                USING (
                    tenant_id IS NULL OR 
                    tenant_id = current_setting('app.current_tenant_id', true)::text
                )
            """))
        
        db.commit()

    @staticmethod
    def set_current_tenant(db: Session, tenant_id: str):
        """Set the current tenant context for RLS."""
        db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    @staticmethod
    def clear_current_tenant(db: Session):
        """Clear the current tenant context."""
        db.execute(text("RESET app.current_tenant_id"))
