"""FinShield AI — Tenant user management (S3.1). Admin only (app.permissions.MATRIX)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.core import client_ip_pseudonymised
from app.database import get_db, rls_bypass
from app.db_models import AuditLog, User

router = APIRouter()

Role = Literal["analyst", "investigator", "supervisor", "admin"]


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=12)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    role: Role = "analyst"


class UserUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


def _out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "first_name": u.first_name, "last_name": u.last_name, "role": u.role,
            "is_active": u.is_active, "created_at": u.created_at.isoformat() if u.created_at else None}


@router.get("/api/v1/admin/users", tags=["Admin"])
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Users of the caller's organisation."""
    rows = db.query(User).filter(User.tenant_id == current_user.tenant_id).order_by(User.created_at).all()
    return [_out(u) for u in rows]


@router.post("/api/v1/admin/users", status_code=201, tags=["Admin"])
def create_user(request: Request, req: UserCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a user to the caller's organisation with the given role."""
    with rls_bypass(db):  # email uniqueness is global
        if db.query(User).filter(User.email == req.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, hashed_password=hash_password(req.password), first_name=req.first_name,
                last_name=req.last_name, company=current_user.company, role=req.role, plan=current_user.plan,
                is_trial=current_user.is_trial, trial_expires_at=current_user.trial_expires_at)
    db.add(user)
    db.flush()
    ip_pseudo = client_ip_pseudonymised(request)
    db.add(AuditLog(user_id=current_user.id, action="user_created", resource_type="user", resource_id=user.id,
                    details={"role": req.role}, ip_address=ip_pseudo))
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/api/v1/admin/users/{user_id}", tags=["Admin"])
def update_user(request: Request, user_id: str, req: UserUpdate, current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Change a user's role or (de)activate them. The organisation always keeps an active admin."""
    user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    before = {"role": user.role, "is_active": user.is_active}
    losing_admin = user.role == "admin" and user.is_active and (
        (req.role is not None and req.role != "admin") or req.is_active is False)
    if losing_admin:
        admins = db.query(User).filter(User.tenant_id == current_user.tenant_id, User.role == "admin",
                                       User.is_active == True).count()  # noqa: E712
        if admins <= 1:
            raise HTTPException(status_code=409, detail="The organisation must keep at least one active admin")
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    ip_pseudo = client_ip_pseudonymised(request)
    db.add(AuditLog(user_id=current_user.id, action="user_updated", resource_type="user", resource_id=user.id,
                    details={"before": before, "after": {"role": user.role, "is_active": user.is_active}},
                    ip_address=ip_pseudo))
    db.commit()
    return _out(user)
