"""
FinShield AI — FastAPI Application (Production)
Full API with authentication, database persistence, rate limiting, and compliance engine.
"""
import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import get_db, init_db
from app.db_models import User, ApiKey, Transaction, Case, AuditLog, Notification, NotificationPreference, RuleConfig, CaseComment
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, generate_api_key,
)
from app.compliance_engine import ComplianceEngine
from app.models import (
    CaseCreateRequest, CaseResponse, CaseStatus, CreditsResponse,
    HealthResponse, TransactionRequest, TransactionResponse,
    ScreeningResult, ScreeningStatus, CreditTier, RuleResult,
)
from datetime import timedelta

# --- Logging ---
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finshield")

# --- App Setup ---
app = FastAPI(
    title="FinShield AI",
    description="Transaction Compliance Engine — Production API with auth, DB, and rate limiting",
    version="2.4.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# --- CORS ---
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate Limiting ---
_is_test = os.getenv("APP_ENV") == "test"
limiter = Limiter(
    key_func=get_remote_address,
    enabled=not _is_test,
)
app.state.limiter = limiter


# --- Exception Handlers ---
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded: {request.method} {request.url.path} from {request.client.host}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.info(f"HTTP {exc.status_code}: {request.method} {request.url.path} — {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {request.method} {request.url.path} — {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request data", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {request.method} {request.url.path} — {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# --- Middleware ---
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)")
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response

# --- State ---
engine = ComplianceEngine()
start_time = time.monotonic()

# --- Startup ---
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Database initialized")
    logger.info(f"FinShield AI v2.4.0 started on port {os.getenv('APP_PORT', '8091')}")


# ============================================================
# AUTH ROUTES
# ============================================================

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
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


@app.post("/api/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new account with 14-day free trial (Starter plan, 1,000 credits)."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.utcnow()
    trial_expiry = now + timedelta(days=14)

    # Create user on Starter trial
    user = User(
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
    audit = AuditLog(user_id=user.id, action="user_registered", details={"email": req.email, "trial": True})
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
    logger.info(f"New trial user registered: {req.email}")

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "company": user.company,
            "plan": user.plan,
            "credits_remaining": user.total_credits,
            "is_trial": True,
            "trial_expires_at": trial_expiry.isoformat(),
        },
    )


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT token."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Create audit log
    audit = AuditLog(user_id=user.id, action="user_login")
    db.add(audit)
    db.commit()

    token = create_access_token(data={"sub": user.id})
    logger.info(f"User logged in: {req.email}")

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "company": user.company,
            "plan": user.plan,
            "credits_remaining": user.total_credits - round(user.used_credits),
        },
    )


@app.get("/api/auth/me", tags=["Auth"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "company": current_user.company,
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
        "saved_card_last4": current_user.saved_card_last4,
        "saved_card_expiry": current_user.saved_card_expiry,
        "saved_card_holder": current_user.saved_card_holder,
    }


class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    timezone: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@app.patch("/api/auth/me", tags=["Auth"])
async def update_profile(
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


@app.post("/api/auth/change-password", tags=["Auth"])
async def change_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    audit = AuditLog(user_id=current_user.id, action="password_changed")
    db.add(audit)
    db.commit()
    return {"detail": "Password updated successfully"}


# ============================================================
# API KEY MANAGEMENT
# ============================================================

class ApiKeyCreateRequest(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


@app.post("/api/v1/keys", response_model=dict, status_code=201, tags=["API Keys"])
async def create_api_key(
    req: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new API key for programmatic access."""
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        user_id=current_user.id,
        name=req.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(api_key)
    db.commit()

    logger.info(f"API key created for user {current_user.email}: {req.name}")

    # Return full key ONLY on creation
    return {
        "id": api_key.id,
        "name": req.name,
        "key": raw_key,
        "key_prefix": key_prefix,
        "created_at": api_key.created_at.isoformat(),
    }


@app.get("/api/v1/keys", response_model=list[ApiKeyResponse], tags=["API Keys"])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()
    return [
        ApiKeyResponse(
            id=k.id, name=k.name, key_prefix=k.key_prefix,
            is_active=k.is_active, created_at=k.created_at, last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@app.delete("/api/v1/keys/{key_id}", tags=["API Keys"])
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.user_id == current_user.id
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    db.commit()
    logger.info(f"API key revoked: {key_id}")
    return {"detail": "API key revoked"}


# ============================================================
# COMPLIANCE ROUTES (authenticated + persisted)
# ============================================================

@app.post("/api/v1/transactions", response_model=TransactionResponse, tags=["Compliance"])
@limiter.limit("60/minute")
async def screen_transaction(
    request: Request,
    tx: TransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen a transaction through the full compliance pipeline."""
    # Check trial expiry
    if current_user.is_trial and current_user.trial_expires_at:
        if datetime.utcnow() > current_user.trial_expires_at:
            raise HTTPException(status_code=403, detail="Trial expired. Upgrade to continue screening transactions.")

    # Check credits
    remaining = current_user.total_credits - current_user.used_credits
    if remaining < 1.0:
        raise HTTPException(status_code=402, detail="Insufficient credits. Purchase more or upgrade your plan.")

    # Idempotency: if this key was already screened, return the stored result (no crash, no double-charge)
    existing_tx = db.query(Transaction).filter(
        Transaction.idempotency_key == tx.idempotency_key, Transaction.user_id == current_user.id
    ).first()
    if existing_tx:
        return TransactionResponse(success=True, data=ScreeningResult(
            transaction_id=existing_tx.id,
            idempotency_key=existing_tx.idempotency_key,
            status=ScreeningStatus(existing_tx.status),
            risk_score=existing_tx.risk_score,
            credit_tier=CreditTier(existing_tx.credit_tier),
            credits_consumed=existing_tx.credits_consumed,
            rule_results=[RuleResult(**r) for r in (existing_tx.rule_results or [])],
            behavioral_score=existing_tx.behavioral_score,
            ml_classification=existing_tx.ml_classification,
            ml_confidence=existing_tx.ml_confidence,
            total_latency_ms=existing_tx.total_latency_ms or 0.0,
            pipeline_stages=existing_tx.pipeline_stages or [],
            timestamp=existing_tx.created_at,
        ))

    # Load the user's rule config overrides and pass them to the engine
    user_rule_configs = {
        rc.rule_id: {"enabled": rc.enabled, "custom_parameters": rc.custom_parameters}
        for rc in db.query(RuleConfig).filter(RuleConfig.user_id == current_user.id).all()
    }

    # Run compliance engine (respects user rule configs)
    result = engine.screen(tx, rule_configs=user_rule_configs)

    # Update user credits
    current_user.used_credits += result.credits_consumed

    # Persist transaction
    db_tx = Transaction(
        user_id=current_user.id,
        idempotency_key=tx.idempotency_key,
        amount=tx.amount,
        currency=tx.currency,
        transaction_type=tx.transaction_type.value,
        sender_name=tx.sender_name,
        receiver_name=tx.receiver_name,
        destination_country=tx.destination_country,
        status=result.status.value,
        risk_score=result.risk_score,
        credit_tier=result.credit_tier.value,
        credits_consumed=result.credits_consumed,
        rule_results=[r.model_dump() for r in result.rule_results],
        behavioral_score=result.behavioral_score,
        ml_classification=result.ml_classification,
        ml_confidence=result.ml_confidence,
        total_latency_ms=result.total_latency_ms,
        pipeline_stages=result.pipeline_stages,
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)

    # Return the persisted DB id (single source of truth for downstream case creation)
    result.transaction_id = db_tx.id

    # Generate notifications for important events
    if result.status.value == "blocked":
        notif = Notification(
            user_id=current_user.id,
            type="blocked_tx",
            title="Transaction blocked",
            message=f"${tx.amount:,.2f} {tx.currency} from {tx.sender_name} blocked (risk: {result.risk_score:.0%}).",
            link="/transactions",
        )
        db.add(notif)

    # Credit usage alert (below 20%)
    remaining_after = current_user.total_credits - current_user.used_credits
    pct_remaining = remaining_after / max(current_user.total_credits, 1)
    if pct_remaining < 0.2 and remaining_after > 0:
        notif = Notification(
            user_id=current_user.id,
            type="credit_alert",
            title="Low credit balance",
            message=f"You have {remaining_after:.0f} credits remaining ({pct_remaining:.0%}). Consider purchasing more.",
            link="/settings?tab=billing",
        )
        db.add(notif)

    db.commit()

    logger.info(
        f"Transaction screened: {result.status.value} | risk={result.risk_score:.2f} | "
        f"tier={result.credit_tier.value} | user={current_user.email}"
    )

    return TransactionResponse(success=True, data=result)


@app.get("/api/v1/transactions", tags=["Compliance"])
async def list_transactions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent transactions for the current user."""
    txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "currency": t.currency,
            "type": t.transaction_type,
            "sender": t.sender_name,
            "receiver": t.receiver_name,
            "status": t.status,
            "risk_score": t.risk_score,
            "credit_tier": t.credit_tier,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs
    ]


@app.get("/api/v1/transactions/{tx_id}", tags=["Compliance"])
async def get_transaction(
    tx_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full transaction detail including rule results (for explainability)."""
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "id": tx.id,
        "amount": tx.amount,
        "currency": tx.currency,
        "transaction_type": tx.transaction_type,
        "sender_name": tx.sender_name,
        "receiver_name": tx.receiver_name,
        "destination_country": tx.destination_country,
        "status": tx.status,
        "risk_score": tx.risk_score,
        "credit_tier": tx.credit_tier,
        "credits_consumed": tx.credits_consumed,
        "idempotency_key": tx.idempotency_key,
        "rule_results": tx.rule_results or [],
        "created_at": tx.created_at.isoformat(),
    }


@app.delete("/api/v1/transactions/{tx_id}", tags=["Compliance"])
async def delete_transaction(
    tx_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a transaction and its associated cases."""
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Delete associated cases first (FK constraint)
    db.query(Case).filter(Case.transaction_id == tx_id).delete()
    db.query(CaseComment).filter(
        CaseComment.case_id.in_(
            db.query(Case.id).filter(Case.transaction_id == tx_id)
        )
    ).delete()
    db.delete(tx)
    db.commit()
    return {"deleted": tx_id}


@app.get("/api/v1/transactions/export", tags=["Compliance"])
async def export_transactions(
    fmt: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export transactions as CSV with optional date range filter."""
    from io import StringIO
    import csv
    from fastapi.responses import StreamingResponse

    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    # Apply date range filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Transaction.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Transaction.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")

    txs = query.order_by(Transaction.created_at.desc()).all()
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Amount", "Currency", "Type", "Sender", "Receiver",
        "Country", "Status", "Risk Score", "Credit Tier", "Credits Used", "Created At",
    ])
    for t in txs:
        writer.writerow([
            t.id, t.amount, t.currency, t.transaction_type,
            t.sender_name, t.receiver_name, t.destination_country or "",
            t.status, t.risk_score, t.credit_tier, t.credits_consumed,
            t.created_at.isoformat(),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=finshield_transactions.csv"},
    )


# ============================================================
# CASES ROUTES
# ============================================================

@app.post("/api/v1/cases", response_model=CaseResponse, status_code=201, tags=["Cases"])
async def create_case(
    req: CaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new compliance case."""
    # Referential integrity: the transaction must exist and belong to this user
    tx_exists = db.query(Transaction).filter(
        Transaction.id == req.transaction_id, Transaction.user_id == current_user.id
    ).first()
    if not tx_exists:
        raise HTTPException(status_code=404, detail="Transaction not found for this account")

    case_id = f"CASE-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.utcnow()
    case = Case(
        id=case_id,
        user_id=current_user.id,
        transaction_id=req.transaction_id,
        status=CaseStatus.CREATED,
        priority=req.priority.value,
        reason=req.reason,
        assigned_to=req.assigned_to,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Notify on new case creation
    notif = Notification(
        user_id=current_user.id,
        type="new_case",
        title="Case created",
        message=f"Case {case_id} opened for transaction {req.transaction_id[:8]}… ({req.priority.value} priority).",
        link="/cases",
    )
    db.add(notif)
    db.commit()

    logger.info(f"Case created: {case_id} by {current_user.email}")

    return CaseResponse(
        case_id=case.id,
        transaction_id=case.transaction_id,
        status=case.status,
        priority=case.priority,
        reason=case.reason,
        assigned_to=case.assigned_to,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@app.get("/api/v1/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
async def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific case."""
    case = db.query(Case).filter(
        Case.id == case_id, Case.user_id == current_user.id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        case_id=case.id, transaction_id=case.transaction_id,
        status=case.status, priority=case.priority, reason=case.reason,
        assigned_to=case.assigned_to, created_at=case.created_at, updated_at=case.updated_at,
    )


@app.get("/api/v1/cases", response_model=list[CaseResponse], tags=["Cases"])
async def list_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all cases for the current user."""
    cases = db.query(Case).filter(Case.user_id == current_user.id).order_by(Case.created_at.desc()).all()
    return [
        CaseResponse(
            case_id=c.id, transaction_id=c.transaction_id,
            status=c.status, priority=c.priority, reason=c.reason,
            assigned_to=c.assigned_to, created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in cases
    ]


# ============================================================
# ACCOUNT ROUTES
# ============================================================

@app.get("/api/v1/credits", response_model=CreditsResponse, tags=["Account"])
async def get_credits(current_user: User = Depends(get_current_user)):
    """Get current credit balance."""
    return CreditsResponse(
        total_credits=current_user.total_credits,
        used_credits=round(current_user.used_credits),
        remaining_credits=current_user.total_credits - round(current_user.used_credits),
        plan=current_user.plan,
    )


# ============================================================
# ANALYTICS / STATS
# ============================================================

@app.get("/api/v1/stats", tags=["Analytics"])
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate dashboard metrics computed from the user's real data."""
    base = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    total = base.count()
    blocked = base.filter(Transaction.status == "blocked").count()
    flagged = base.filter(Transaction.status == "flagged").count()
    in_review = base.filter(Transaction.status == "in_review").count()
    approved = base.filter(Transaction.status == "approved").count()

    open_cases = (
        db.query(Case)
        .filter(Case.user_id == current_user.id, Case.status.notin_(["resolved", "closed"]))
        .count()
    )

    # Average risk score across all screened transactions
    avg_risk = db.query(func.avg(Transaction.risk_score)).filter(
        Transaction.user_id == current_user.id
    ).scalar() or 0.0

    return {
        "total_transactions": total,
        "approved": approved,
        "flagged": flagged,
        "blocked": blocked,
        "in_review": in_review,
        "open_cases": open_cases,
        "avg_risk_score": round(float(avg_risk), 4),
        "credits_used": round(current_user.used_credits),
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
    }


# ============================================================
# BILLING & SUBSCRIPTION
# ============================================================

PLANS = [
    {
        "id": "starter",
        "name": "Starter",
        "price_monthly": 29,
        "included_credits": 15000,
        "features": ["Up to 15,000 credits/mo", "Rule + behavioral screening", "Email support", "1 API key"],
    },
    {
        "id": "growth",
        "name": "Growth",
        "price_monthly": 99,
        "included_credits": 60000,
        "features": ["Up to 60,000 credits/mo", "Full ML pipeline", "Case management", "Priority support"],
    },
    {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 299,
        "included_credits": 250000,
        "features": ["Up to 250,000 credits/mo", "Everything in Growth", "SAR/STR filing", "Dedicated CSM"],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly": None,
        "included_credits": None,
        "features": ["Unlimited credits", "On-premise / VPC", "SSO + audit export", "99.9% uptime SLA"],
    },
]

CREDIT_PACKS = {
    10000: 9,
    50000: 39,
    200000: 129,
}


class SubscribeRequest(BaseModel):
    plan_id: str


class PurchaseRequest(BaseModel):
    credits: int


class CheckoutRequest(BaseModel):
    credits: int
    card_last4: Optional[str] = None
    card_expiry: Optional[str] = None
    card_holder: Optional[str] = None
    use_saved_card: bool = False


class SavedCardRequest(BaseModel):
    """Save or update the user's payment method on file."""
    card_last4: str
    card_expiry: str
    card_holder: str


class RemoveSavedCardRequest(BaseModel):
    """Remove the saved payment method."""
    pass


@app.get("/api/v1/billing/plans", tags=["Billing"])
async def list_plans(current_user: User = Depends(get_current_user)):
    """List available subscription plans."""
    # Calculate days remaining: billing cycle if paid, else trial expiry
    days_remaining = None
    cycle_end = current_user.billing_cycle_end
    if cycle_end:
        days_remaining = max(0, (cycle_end - datetime.utcnow()).days)
    elif current_user.is_trial and current_user.trial_expires_at:
        days_remaining = max(0, (current_user.trial_expires_at - datetime.utcnow()).days)
    return {
        "plans": PLANS,
        "current_plan": current_user.plan,
        "billing_cycle_start": current_user.billing_cycle_start.isoformat() if current_user.billing_cycle_start else None,
        "billing_cycle_end": cycle_end.isoformat() if cycle_end else None,
        "days_remaining": days_remaining,
        "pending_plan_change": current_user.pending_plan_change,
        "is_trial": current_user.is_trial,
        "trial_expires_at": current_user.trial_expires_at.isoformat() if current_user.trial_expires_at else None,
    }


@app.post("/api/v1/billing/subscribe", tags=["Billing"])
async def subscribe(
    req: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the account's subscription plan with real-world constraints."""
    plan = next((p for p in PLANS if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    if plan["included_credits"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans require contacting sales")
    if plan["id"] == current_user.plan:
        raise HTTPException(status_code=400, detail="Already on this plan")

    current_plan = next((p for p in PLANS if p["id"] == current_user.plan), None)
    current_price = current_plan["price_monthly"] if current_plan else 0
    new_price = plan["price_monthly"]
    is_upgrade = new_price > (current_price or 0)

    # Initialize billing cycle if not set
    now = datetime.utcnow()
    if not current_user.billing_cycle_start:
        current_user.billing_cycle_start = now
        current_user.billing_cycle_end = now + timedelta(days=30)

    proration = 0
    if is_upgrade:
        # Upgrades take effect immediately with proration
        cycle_total_days = (current_user.billing_cycle_end - current_user.billing_cycle_start).days or 30
        days_left = max(1, (current_user.billing_cycle_end - now).days)
        proration = round((new_price - (current_price or 0)) * (days_left / cycle_total_days), 2)

        current_user.plan = plan["id"]
        current_user.is_trial = False
        current_user.trial_expires_at = None
        # Top up credits to new plan allowance
        if plan["included_credits"] > current_user.total_credits:
            current_user.total_credits = plan["included_credits"]

        # Create notification
        notif = Notification(
            user_id=current_user.id,
            type="plan_change",
            title="Plan upgraded",
            message=f"Upgraded to {plan['name']}. Prorated charge: ${proration}. Credits adjusted.",
            link="/settings?tab=billing",
        )
        db.add(notif)
    else:
        # Downgrades take effect at end of billing cycle
        current_user.pending_plan_change = plan["id"]

        notif = Notification(
            user_id=current_user.id,
            type="plan_change",
            title="Downgrade scheduled",
            message=f"Your plan will change to {plan['name']} at the end of your current billing cycle ({current_user.billing_cycle_end.strftime('%b %d, %Y')}).",
            link="/settings?tab=billing",
        )
        db.add(notif)

    audit = AuditLog(user_id=current_user.id, action="plan_subscribed",
                     resource_type="billing",
                     details={"plan": plan["id"], "is_upgrade": is_upgrade, "proration": proration if is_upgrade else None})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} {'upgraded' if is_upgrade else 'scheduled downgrade'} to plan: {plan['id']}")

    return {
        "plan": plan["id"],
        "is_upgrade": is_upgrade,
        "effective": "immediately" if is_upgrade else f"at end of cycle ({current_user.billing_cycle_end.strftime('%b %d, %Y') if current_user.billing_cycle_end else 'N/A'})",
        "proration_usd": proration if is_upgrade else 0,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "pending_plan_change": current_user.pending_plan_change,
        "message": f"{'Upgraded' if is_upgrade else 'Downgrade scheduled'} to {plan['name']}" + (f" (prorated ${proration})" if is_upgrade else ""),
    }


@app.post("/api/v1/credits/checkout", tags=["Billing"])
async def checkout_credits(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulated payment checkout for credit purchase. Supports saved card (Qoder-like flow)."""
    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit pack")

    # Determine card details: use saved card or validate new card
    if req.use_saved_card:
        if not current_user.saved_card_last4:
            raise HTTPException(status_code=400, detail="No saved payment method. Please add a card first.")
        card_last4 = current_user.saved_card_last4
        card_expiry = current_user.saved_card_expiry
        card_holder = current_user.saved_card_holder
    else:
        # Validate new card details
        if not req.card_last4 or len(req.card_last4) != 4 or not req.card_last4.isdigit():
            raise HTTPException(status_code=400, detail="Invalid card last 4 digits")
        if not req.card_expiry or "/" not in req.card_expiry:
            raise HTTPException(status_code=400, detail="Invalid card expiry format (MM/YY)")
        if not req.card_holder or len(req.card_holder.strip()) < 2:
            raise HTTPException(status_code=400, detail="Invalid card holder name")
        card_last4 = req.card_last4
        card_expiry = req.card_expiry
        card_holder = req.card_holder

    price = CREDIT_PACKS[req.credits]

    # Simulate payment processing (in production, this would call Stripe/PayPal)
    # Simulate decline for card ending in 0000
    if card_last4 == "0000":
        raise HTTPException(status_code=402, detail="Payment declined. Please try a different card.")

    # Payment "approved" — add credits
    current_user.total_credits += req.credits

    # Save card for future use (Qoder-like flow: first payment saves billing info)
    current_user.saved_card_last4 = card_last4
    current_user.saved_card_expiry = card_expiry
    current_user.saved_card_holder = card_holder

    # Create notification
    notif = Notification(
        user_id=current_user.id,
        type="credit_alert",
        title="Credits purchased",
        message=f"{req.credits:,} credits added for ${price}. Card ending in {card_last4}.",
        link="/settings?tab=billing",
    )
    db.add(notif)

    audit = AuditLog(user_id=current_user.id, action="credits_purchased",
                     resource_type="billing",
                     details={"credits": req.credits, "price_usd": price, "card_last4": card_last4, "used_saved": req.use_saved_card})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} purchased {req.credits} credits for ${price} (card ****{card_last4}, saved={req.use_saved_card})")

    return {
        "credits_added": req.credits,
        "price_usd": price,
        "card_last4": card_last4,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "status": "completed",
    }


@app.patch("/api/v1/billing/saved-card", tags=["Billing"])
async def update_saved_card(
    req: SavedCardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update the user's payment method on file."""
    if not req.card_last4 or len(req.card_last4) != 4 or not req.card_last4.isdigit():
        raise HTTPException(status_code=400, detail="Invalid card last 4 digits")
    if not req.card_expiry or "/" not in req.card_expiry:
        raise HTTPException(status_code=400, detail="Invalid card expiry format (MM/YY)")
    if not req.card_holder or len(req.card_holder.strip()) < 2:
        raise HTTPException(status_code=400, detail="Invalid card holder name")

    current_user.saved_card_last4 = req.card_last4
    current_user.saved_card_expiry = req.card_expiry
    current_user.saved_card_holder = req.card_holder.strip()
    db.commit()
    db.refresh(current_user)
    return {"detail": "Payment method saved", "card_last4": current_user.saved_card_last4, "card_expiry": current_user.saved_card_expiry, "card_holder": current_user.saved_card_holder}


@app.delete("/api/v1/billing/saved-card", tags=["Billing"])
async def remove_saved_card(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the saved payment method."""
    current_user.saved_card_last4 = None
    current_user.saved_card_expiry = None
    current_user.saved_card_holder = None
    db.commit()
    return {"detail": "Payment method removed"}


@app.post("/api/v1/credits/purchase", tags=["Billing"])
async def purchase_credits(
    req: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase an additional credit pack (legacy — use /checkout for payment verification)."""
    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit pack")
    price = CREDIT_PACKS[req.credits]

    current_user.total_credits += req.credits
    audit = AuditLog(user_id=current_user.id, action="credits_purchased",
                     resource_type="billing",
                     details={"credits": req.credits, "price_usd": price})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} purchased {req.credits} credits")

    return {
        "credits_added": req.credits,
        "price_usd": price,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
    }


# ============================================================
# SEARCH
# ============================================================

@app.get("/api/v1/search", tags=["Search"])
async def global_search(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Global search across transactions, cases, and API keys."""
    if not q or len(q.strip()) < 2:
        return {"query": q, "transactions": [], "cases": [], "api_keys": []}

    pattern = f"%{q.strip()}%"

    # Search transactions (parties, id, country, type, status)
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            (Transaction.sender_name.ilike(pattern))
            | (Transaction.receiver_name.ilike(pattern))
            | (Transaction.id.ilike(pattern))
            | (Transaction.destination_country.ilike(pattern))
            | (Transaction.transaction_type.ilike(pattern))
            | (Transaction.status.ilike(pattern))
            | (Transaction.currency.ilike(pattern))
        )
        .order_by(Transaction.created_at.desc())
        .limit(10)
        .all()
    )

    # Search cases
    cases = (
        db.query(Case)
        .filter(
            Case.user_id == current_user.id,
            (Case.id.ilike(pattern))
            | (Case.reason.ilike(pattern))
            | (Case.transaction_id.ilike(pattern))
            | (Case.assigned_to.ilike(pattern))
        )
        .order_by(Case.created_at.desc())
        .limit(10)
        .all()
    )

    # Search API keys
    keys = (
        db.query(ApiKey)
        .filter(
            ApiKey.user_id == current_user.id,
            ApiKey.name.ilike(pattern),
            ApiKey.is_active == True,
        )
        .limit(5)
        .all()
    )

    return {
        "query": q,
        "transactions": [
            {"id": t.id, "amount": t.amount, "currency": t.currency, "sender": t.sender_name, "receiver": t.receiver_name, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in txs
        ],
        "cases": [
            {"case_id": c.id, "reason": c.reason, "status": c.status, "priority": c.priority, "created_at": c.created_at.isoformat()}
            for c in cases
        ],
        "api_keys": [
            {"id": k.id, "name": k.name, "key_prefix": k.key_prefix, "is_active": k.is_active}
            for k in keys
        ],
    }


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.get("/api/v1/notifications", tags=["Notifications"])
async def list_notifications(
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current user."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    notifs = query.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).count()
    return {
        "notifications": [
            {"id": n.id, "type": n.type, "title": n.title, "message": n.message, "is_read": n.is_read, "link": n.link, "created_at": n.created_at.isoformat()}
            for n in notifs
        ],
        "unread_count": unread_count,
    }


@app.patch("/api/v1/notifications/{notif_id}/read", tags=["Notifications"])
async def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notif_id, Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"detail": "Marked as read"}


@app.post("/api/v1/notifications/read-all", tags=["Notifications"])
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"detail": "All notifications marked as read"}


# ============================================================
# NOTIFICATION PREFERENCES
# ============================================================

@app.get("/api/v1/notifications/preferences", tags=["Notifications"])
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get notification preferences."""
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not prefs:
        # Create defaults
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return {
        "email_blocked_tx": prefs.email_blocked_tx,
        "email_new_cases": prefs.email_new_cases,
        "email_daily_summary": prefs.email_daily_summary,
        "email_weekly_report": prefs.email_weekly_report,
        "email_system_downtime": prefs.email_system_downtime,
        "email_credit_alerts": prefs.email_credit_alerts,
    }


class NotificationPreferencesUpdate(BaseModel):
    email_blocked_tx: Optional[bool] = None
    email_new_cases: Optional[bool] = None
    email_daily_summary: Optional[bool] = None
    email_weekly_report: Optional[bool] = None
    email_system_downtime: Optional[bool] = None
    email_credit_alerts: Optional[bool] = None


@app.put("/api/v1/notifications/preferences", tags=["Notifications"])
async def update_notification_preferences(
    req: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update notification preferences."""
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)
    db.commit()
    return {"detail": "Preferences updated"}


# ============================================================
# RULE MANAGEMENT
# ============================================================

class RuleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    custom_parameters: Optional[dict] = None


@app.patch("/api/v1/rules/{rule_id}", tags=["Rules"])
async def update_rule(
    rule_id: str,
    req: RuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle or customize a compliance rule for the current user."""
    # Verify rule exists
    definitions = engine.rule_definitions()
    rule_def = next((r for r in definitions if r["rule_id"] == rule_id), None)
    if not rule_def:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Get or create user-specific config
    config = db.query(RuleConfig).filter(
        RuleConfig.user_id == current_user.id, RuleConfig.rule_id == rule_id
    ).first()
    if not config:
        config = RuleConfig(user_id=current_user.id, rule_id=rule_id)
        db.add(config)

    if req.enabled is not None:
        config.enabled = req.enabled
    if req.custom_parameters is not None:
        config.custom_parameters = req.custom_parameters

    db.commit()
    db.refresh(config)

    audit = AuditLog(user_id=current_user.id, action="rule_updated",
                     resource_type="rule", resource_id=rule_id,
                     details={"enabled": config.enabled, "custom_parameters": config.custom_parameters})
    db.add(audit)
    db.commit()

    return {
        "rule_id": rule_id,
        "enabled": config.enabled,
        "custom_parameters": config.custom_parameters,
        "detail": f"Rule {rule_id} updated",
    }


@app.get("/api/v1/rules", tags=["Rules"])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List rules with user-specific overrides applied."""
    definitions = engine.rule_definitions()
    # Apply user-specific overrides
    user_configs = db.query(RuleConfig).filter(RuleConfig.user_id == current_user.id).all()
    config_map = {c.rule_id: c for c in user_configs}

    for rule in definitions:
        config = config_map.get(rule["rule_id"])
        if config:
            rule["enabled"] = config.enabled
            # is_customized only when parameters were actually changed (not just an on/off toggle)
            if config.custom_parameters:
                rule["parameters"] = {**rule["parameters"], **config.custom_parameters}
                rule["is_customized"] = True
            else:
                rule["is_customized"] = False
        else:
            rule["is_customized"] = False

    return definitions


# ============================================================
# CASE MANAGEMENT
# ============================================================

class CaseUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None


class CaseCommentRequest(BaseModel):
    body: str


@app.patch("/api/v1/cases/{case_id}", tags=["Cases"])
async def update_case(
    case_id: str,
    req: CaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update case status, assignment, or priority."""
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == current_user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    valid_statuses = ["created", "open", "under_review", "in_progress", "escalated", "resolved", "closed"]
    if req.status is not None:
        if req.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        case.status = req.status
    if req.assigned_to is not None:
        case.assigned_to = req.assigned_to
    if req.priority is not None:
        case.priority = req.priority

    db.commit()
    db.refresh(case)

    audit = AuditLog(user_id=current_user.id, action="case_updated",
                     resource_type="case", resource_id=case_id,
                     details={"status": case.status, "assigned_to": case.assigned_to})
    db.add(audit)
    db.commit()

    return CaseResponse(
        case_id=case.id, transaction_id=case.transaction_id,
        status=case.status, priority=case.priority, reason=case.reason,
        assigned_to=case.assigned_to, created_at=case.created_at, updated_at=case.updated_at,
    )


@app.get("/api/v1/cases/{case_id}/comments", tags=["Cases"])
async def list_case_comments(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments on a case."""
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == current_user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    comments = db.query(CaseComment).filter(CaseComment.case_id == case_id).order_by(CaseComment.created_at.asc()).all()
    return [
        {"id": c.id, "body": c.body, "user_id": c.user_id, "created_at": c.created_at.isoformat()}
        for c in comments
    ]


@app.post("/api/v1/cases/{case_id}/comments", tags=["Cases"])
async def add_case_comment(
    case_id: str,
    req: CaseCommentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a case."""
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == current_user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")

    comment = CaseComment(case_id=case_id, user_id=current_user.id, body=req.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "body": comment.body, "user_id": comment.user_id, "created_at": comment.created_at.isoformat()}


@app.delete("/api/v1/cases/{case_id}", tags=["Cases"])
async def delete_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a case and its comments."""
    case = db.query(Case).filter(
        Case.id == case_id, Case.user_id == current_user.id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.query(CaseComment).filter(CaseComment.case_id == case_id).delete()
    db.delete(case)
    db.commit()
    return {"deleted": case_id}


# ============================================================
# SYSTEM ROUTES
# ============================================================

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="2.4.0",
        services={
            "rule_engine": "healthy",
            "behavioral_ml": "healthy",
            "rag_classifier": "healthy",
            "case_manager": "healthy",
            "api_gateway": "healthy",
            "database": "healthy",
        },
        uptime_seconds=round(time.monotonic() - start_time, 2),
    )


@app.get("/", tags=["System"])
async def root():
    return {
        "service": "FinShield AI",
        "version": "2.4.0",
        "docs": "/api/docs",
        "health": "/api/health",
    }
