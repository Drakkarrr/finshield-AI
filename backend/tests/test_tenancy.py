"""Tests for multi-tenancy (S3.4)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.database import Base
from app.db_models import Tenant, User
from app.main import app
from app.domain.tenancy import TenantService


@pytest.fixture
def db():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def tenant_a(db: Session):
    """Create tenant A."""
    return TenantService.create_tenant(
        db,
        name="Tenant Alpha",
        slug="tenant-alpha",
        plan="starter",
        max_users=10,
    )


@pytest.fixture
def tenant_b(db: Session):
    """Create tenant B."""
    return TenantService.create_tenant(
        db,
        name="Tenant Beta",
        slug="tenant-beta",
        plan="starter",
        max_users=10,
    )


@pytest.fixture
def user_a(db: Session, tenant_a: Tenant):
    """Create user in tenant A."""
    user = User(
        email="user-a@example.com",
        first_name="User",
        last_name="A",
        tenant_id=tenant_a.id,
        role="user",
    )
    user.hashed_password = hash_password("password123")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_b(db: Session, tenant_b: Tenant):
    """Create user in tenant B."""
    user = User(
        email="user-b@example.com",
        first_name="User",
        last_name="B",
        tenant_id=tenant_b.id,
        role="user",
    )
    user.hashed_password = hash_password("password123")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_tenant_creation(db: Session):
    """Test creating a tenant."""
    tenant = TenantService.create_tenant(
        db,
        name="Test Tenant",
        slug="test-tenant",
        plan="professional",
        max_users=50,
    )
    
    assert tenant.id is not None
    assert tenant.name == "Test Tenant"
    assert tenant.slug == "test-tenant"
    assert tenant.plan == "professional"
    assert tenant.max_users == 50
    assert tenant.is_active is True


def test_tenant_slug_uniqueness(db: Session, tenant_a: Tenant):
    """Test that tenant slugs must be unique."""
    with pytest.raises(Exception):  # IntegrityError or ValueError
        TenantService.create_tenant(
            db,
            name="Duplicate Slug",
            slug="tenant-alpha",  # Same as tenant_a
            plan="starter",
            max_users=10,
        )


def test_assign_user_to_tenant(db: Session, tenant_a: Tenant):
    """Test assigning a user to a tenant."""
    user = User(
        email="new-user@example.com",
        first_name="New",
        last_name="User",
        role="user",
    )
    user.hashed_password = hash_password("password123")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    TenantService.assign_user_to_tenant(db, user.id, tenant_a.id)
    
    db.refresh(user)
    assert user.tenant_id == tenant_a.id


def test_max_users_limit(db: Session):
    """Test that tenant max_users limit is enforced."""
    tenant = TenantService.create_tenant(
        db,
        name="Small Tenant",
        slug="small-tenant",
        plan="starter",
        max_users=2,  # Only 2 users allowed
    )
    
    # Add 2 users (should succeed)
    for i in range(2):
        user = User(
            email=f"user{i}@example.com",
            first_name="User",
            last_name=str(i),
            role="user",
        )
        user.hashed_password = hash_password("password123")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        TenantService.assign_user_to_tenant(db, user.id, tenant.id)
    
    # Try to add 3rd user (should fail)
    user3 = User(
        email="user3@example.com",
        first_name="User",
        last_name="3",
        role="user",
    )
    user3.hashed_password = hash_password("password123")
    db.add(user3)
    db.commit()
    db.refresh(user3)
    
    with pytest.raises(ValueError, match="max users"):
        TenantService.assign_user_to_tenant(db, user3.id, tenant.id)


def test_tenant_isolation_get_tenant(db: Session, tenant_a: Tenant, tenant_b: Tenant):
    """Test that get_tenant only returns the requested tenant."""
    retrieved_a = TenantService.get_tenant(db, tenant_a.id)
    retrieved_b = TenantService.get_tenant(db, tenant_b.id)
    
    assert retrieved_a is not None
    assert retrieved_b is not None
    assert retrieved_a.id != retrieved_b.id
    assert retrieved_a.slug == "tenant-alpha"
    assert retrieved_b.slug == "tenant-beta"


def test_require_tenant_context_blocks_cross_tenant(
    db: Session, tenant_a: Tenant, tenant_b: Tenant, user_a: User, user_b: User
):
    """Test that require_tenant_context blocks cross-tenant access."""
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        TenantService.require_tenant_context(db, user_a, tenant_b.id)
    
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_require_tenant_context_allows_same_tenant(
    db: Session, tenant_a: Tenant, user_a: User
):
    """Test that require_tenant_context allows same-tenant access."""
    # Should not raise
    TenantService.require_tenant_context(db, user_a, tenant_a.id)


def test_get_tenant_by_slug(db: Session, tenant_a: Tenant):
    """Test retrieving tenant by slug."""
    retrieved = TenantService.get_tenant_by_slug(db, "tenant-alpha")
    assert retrieved is not None
    assert retrieved.id == tenant_a.id
    assert retrieved.slug == "tenant-alpha"


def test_inactive_tenant_cannot_add_users(db: Session):
    """Test that inactive tenants cannot have users added."""
    tenant = TenantService.create_tenant(
        db,
        name="Inactive Tenant",
        slug="inactive-tenant",
        plan="starter",
        max_users=10,
    )
    
    # Deactivate tenant
    tenant.is_active = False
    db.commit()
    
    user = User(
        email="orphan@example.com",
        first_name="Orphan",
        last_name="User",
        role="user",
    )
    user.hashed_password = hash_password("password123")
    db.add(user)
    db.commit()
    db.refresh(user)
    
    with pytest.raises(ValueError, match="inactive"):
        TenantService.assign_user_to_tenant(db, user.id, tenant.id)
