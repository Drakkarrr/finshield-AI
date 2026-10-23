"""FinShield AI — Admin user management API (S3.1 RBAC)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role, PERMISSION_MATRIX
from app.database import get_db
from app.db_models import User

router = APIRouter()


@router.get("/api/v1/admin/users", tags=["Admin"])
@require_role("admin", "super_admin")
def list_users(
    limit: int = 100,
    offset: int = 0,
    role: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users (admin only)."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    
    users = query.offset(offset).limit(limit).all()
    
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "is_active": u.is_active,
                "is_verified": u.is_verified,
                "plan": u.plan,
                "total_credits": u.total_credits,
                "used_credits": u.used_credits,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "count": len(users),
    }


@router.get("/api/v1/admin/users/{user_id}", tags=["Admin"])
@require_role("admin", "super_admin")
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "company": user.company,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "plan": user.plan,
        "total_credits": user.total_credits,
        "used_credits": user.used_credits,
        "timezone": user.timezone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.put("/api/v1/admin/users/{user_id}/role", tags=["Admin"])
@require_role("super_admin")
def update_user_role(
    user_id: str,
    role: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user role (super_admin only)."""
    if role not in PERMISSION_MATRIX:
        raise HTTPException(400, f"Invalid role: {role}. Must be one of: {', '.join(PERMISSION_MATRIX.keys())}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    old_role = user.role
    user.role = role
    db.commit()
    
    return {
        "success": True,
        "user_id": user_id,
        "old_role": old_role,
        "new_role": role,
        "message": f"User role updated from {old_role} to {role}",
    }


@router.post("/api/v1/admin/users/{user_id}/activate", tags=["Admin"])
@require_role("admin", "super_admin")
def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    user.is_active = True
    db.commit()
    
    return {
        "success": True,
        "user_id": user_id,
        "is_active": True,
        "message": "User activated",
    }


@router.post("/api/v1/admin/users/{user_id}/deactivate", tags=["Admin"])
@require_role("admin", "super_admin")
def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    # Prevent deactivating yourself
    if user.id == current_user.id:
        raise HTTPException(400, "Cannot deactivate your own account")
    
    user.is_active = False
    db.commit()
    
    return {
        "success": True,
        "user_id": user_id,
        "is_active": False,
        "message": "User deactivated",
    }


@router.get("/api/v1/admin/permissions", tags=["Admin"])
@require_role("admin", "super_admin")
def get_permission_matrix(
    current_user: User = Depends(get_current_user),
):
    """Get the permission matrix (admin only)."""
    return {
        "roles": list(PERMISSION_MATRIX.keys()),
        "permissions": {
            role: sorted(perms) for role, perms in PERMISSION_MATRIX.items()
        },
    }
