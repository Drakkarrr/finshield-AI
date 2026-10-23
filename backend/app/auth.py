"""
FinShield AI — Authentication
JWT-based authentication with password hashing.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
import structlog
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import bind_tenant, get_db, rls_bypass
from app.db_models import ApiKey, User

# --- Configuration ---
APP_ENV = os.getenv("APP_ENV", "production")
_jwt_secret = os.getenv("JWT_SECRET_KEY")
if APP_ENV != "test" and len(_jwt_secret or "") < 32:  # HS256 wants a key of at least 256 bits
    raise RuntimeError("JWT_SECRET_KEY must be set to at least 32 characters in non-test environments")
SECRET_KEY = _jwt_secret or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# --- Bearer Token ---
security = HTTPBearer(auto_error=False)

# --- Browser session (ruling D11) ---
# The web app never sees the token: login sets it as an httpOnly cookie. Programmatic clients keep
# using `Authorization: Bearer` (JWT or API key). Cookie-authenticated unsafe requests must carry
# X-Requested-With: a cross-site form cannot set it, and CORS blocks cross-site scripts from doing so.
SESSION_COOKIE = "finshield_session"
CSRF_HEADER = "X-Requested-With"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() != "false"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
                        httponly=True, secure=COOKIE_SECURE, samesite="lax")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")


# --- Password Hashing ---

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency to get the current authenticated user.

    Accepts a JWT bearer token, a live API key (fsk_... prefix), or the browser session cookie.
    """
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get(SESSION_COOKIE) or ""
        if token.startswith("fsk_"):
            token = ""  # the cookie only ever carries a session JWT
        if token and request.method not in SAFE_METHODS and not request.headers.get(CSRF_HEADER):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"CSRF check failed: cookie-authenticated requests must send {CSRF_HEADER}")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Who the caller is must be resolved before their tenant is known: look up across tenants,
    # then bind the session to the caller's tenant for everything that follows in the request.
    with rls_bypass(db):
        user = _resolve(token, db)
        tenant_id = user.tenant_id
    bind_tenant(db, tenant_id)
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, user_id=user.id)
    return user


def _resolve(token: str, db: Session) -> User:
    # Path 1: API key (starts with the fsk_ prefix)
    if token.startswith("fsk_"):
        digest = api_key_digest(token)
        matched = db.query(ApiKey).filter(ApiKey.key_digest == digest, ApiKey.is_active == True).first()
        if matched is None:  # a key from before migration 0011: verify once with bcrypt, then by digest
            prefix = token[:12] + "..."
            candidates = db.query(ApiKey).filter(ApiKey.key_prefix == prefix, ApiKey.is_active == True,
                                                 ApiKey.key_digest.is_(None)).all()
            matched = next((k for k in candidates if verify_password(token, k.key_hash)), None)
            if matched is not None:
                matched.key_digest = digest
        if matched is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.query(User).filter(User.id == matched.user_id).first()
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
        matched.last_used_at = datetime.utcnow()
        db.info["api_key_id"] = matched.id  # attributed on audit entries
        return user

    # Path 2: JWT bearer token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


def api_key_digest(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, key_hash, key_prefix)."""
    raw_key = f"fsk_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_password(raw_key)
    key_prefix = raw_key[:12] + "..."
    return raw_key, key_hash, key_prefix
