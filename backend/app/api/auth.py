"""FinShield AI — Registration, login and profile."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crypto
from app.auth import (
    clear_session_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from app.core import client_ip_pseudonymised, limiter, logger
from app.database import bind_tenant, get_db, rls_bypass
from app.db_models import (
    AuditChainHead,
    AuditLog,
    Notification,
    Tenant,
    User,
)
from app.domain import audit as audit_trail

router = APIRouter()


# ============================================================
# AUTH ROUTES
# ============================================================

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=12, description="Password must be at least 12 characters")
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    company: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/api/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
@limiter.limit("5/minute")
def register(request: Request, response: Response, req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new account with 14-day free trial (Starter plan, 1,000 credits)."""
    ip_pseudo = client_ip_pseudonymised(request)
    with rls_bypass(db):  # email uniqueness is global, across tenants
        if db.query(User).filter(User.email == req.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.utcnow()
    trial_expiry = now + timedelta(days=14)

    # A self-serve signup creates its organisation; the first user administers it.
    tenant = Tenant(name=req.company or req.email)
    with rls_bypass(db):
        db.add(tenant)
    bind_tenant(db, tenant.id)
    db.add(AuditChainHead(tenant_id=tenant.id, seq=0, last_hash=audit_trail.GENESIS))  # sealers never race to create it

    # Create user on Starter trial
    user = User(
        role="admin",
        email=req.email,
        hashed_password=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        company=req.company,
        plan="starter",
        total_credits=1000,
        is_trial=True,
        trial_expires_at=trial_expiry,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    audit = AuditLog(user_id=user.id, action="user_registered", details={"trial": True}, ip_address=ip_pseudo)
    db.add(audit)

    # Welcome notification
    welcome = Notification(
        user_id=user.id,
        type="system",
        title="14-day free trial started",
        message="You have 1,000 Starter credits. Upgrade anytime for full ML pipeline, case management, and higher volume.",
        link="/settings?tab=billing",
    )
    db.add(welcome)
    db.commit()

    token = create_access_token(data={"sub": user.id})
    set_session_cookie(response, token)
    logger.info(f"New trial user registered: {req.email}")

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "company": user.company,
            "role": user.role,
            "plan": user.plan,
            "credits_remaining": user.total_credits,
            "is_trial": True,
            "trial_expires_at": trial_expiry.isoformat(),
        },
    )


@router.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
@limiter.limit("10/minute")
def login(request: Request, response: Response, req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT token."""
    ip_pseudo = client_ip_pseudonymised(request)
    email_pseudo = crypto.pseudonym(req.email)
    with rls_bypass(db):  # the tenant is unknown until the user is found
        user = db.query(User).filter(User.email == req.email).first()
        if not user or not verify_password(req.password, user.hashed_password):
            # Audit failed login with pseudonymised email
            # For unknown emails, use system tenant; for known users, use their tenant
            tenant_id = user.tenant_id if user else None
            if tenant_id:
                bind_tenant(db, tenant_id)
            else:
                # Unknown email: audit under system tenant
                system_tenant = db.query(Tenant).filter(Tenant.id == "system").first()
                if not system_tenant:
                    system_tenant = Tenant(id="system", name="system")
                    db.add(system_tenant)
                    db.flush()
                bind_tenant(db, "system")
            db.add(AuditLog(
                user_id=user.id if user else None,
                action="login_failed",
                details={"reason": "invalid_credentials", "email_pseudo": email_pseudo},
                ip_address=ip_pseudo
            ))
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_active:
            # Audit disabled account login attempt
            bind_tenant(db, user.tenant_id)
            db.add(AuditLog(
                user_id=user.id,
                action="login_failed",
                details={"reason": "account_disabled", "email_pseudo": email_pseudo},
                ip_address=ip_pseudo
            ))
            db.commit()
            raise HTTPException(status_code=403, detail="Account is disabled")
        tenant_id = user.tenant_id
    bind_tenant(db, tenant_id)

    # Create audit log
    audit = AuditLog(user_id=user.id, action="user_login", ip_address=ip_pseudo)
    db.add(audit)
    db.commit()

    token = create_access_token(data={"sub": user.id})
    set_session_cookie(response, token)
    logger.info(f"User logged in: {req.email}")

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "company": user.company,
            "role": user.role,
            "plan": user.plan,
            "credits_remaining": user.total_credits - round(user.used_credits),
        },
    )


@router.post("/api/auth/logout", status_code=204, tags=["Auth"])
def logout(response: Response):
    """End the browser session (clears the session cookie). Bearer tokens expire on their own."""
    clear_session_cookie(response)
    response.status_code = 204


@router.get("/api/auth/me", tags=["Auth"])
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "company": current_user.company,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "plan": current_user.plan,
        "total_credits": current_user.total_credits,
        "used_credits": round(current_user.used_credits),
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "created_at": current_user.created_at.isoformat(),
        "billing_cycle_start": current_user.billing_cycle_start.isoformat() if current_user.billing_cycle_start else None,
        "billing_cycle_end": current_user.billing_cycle_end.isoformat() if current_user.billing_cycle_end else None,
        "pending_plan_change": current_user.pending_plan_change,
        "is_trial": current_user.is_trial,
        "trial_expires_at": current_user.trial_expires_at.isoformat() if current_user.trial_expires_at else None,
        "timezone": current_user.timezone,
    }


class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    timezone: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/api/auth/me", tags=["Auth"])
def update_profile(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's profile information."""
    if req.first_name is not None:
        if not req.first_name.strip():
            raise HTTPException(status_code=400, detail="First name cannot be empty")
        current_user.first_name = req.first_name.strip()
    if req.last_name is not None:
        if not req.last_name.strip():
            raise HTTPException(status_code=400, detail="Last name cannot be empty")
        current_user.last_name = req.last_name.strip()
    if req.company is not None:
        current_user.company = req.company.strip() or None
    if req.timezone is not None:
        current_user.timezone = req.timezone.strip() or None
    db.commit()
    db.refresh(current_user)
    return {"detail": "Profile updated", "first_name": current_user.first_name, "last_name": current_user.last_name, "company": current_user.company, "timezone": current_user.timezone}


@router.post("/api/auth/change-password", tags=["Auth"])
def change_password(
    request: Request,
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    ip_pseudo = client_ip_pseudonymised(request)
    audit = AuditLog(user_id=current_user.id, action="password_changed", ip_address=ip_pseudo)
    db.add(audit)
    db.commit()
    return {"detail": "Password updated successfully"}
