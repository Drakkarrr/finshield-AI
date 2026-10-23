"""
FinShield AI — Authentication
JWT-based authentication with password hashing.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import ApiKey, User

# --- Configuration ---
APP_ENV = os.getenv("APP_ENV", "production")
_jwt_secret = os.getenv("JWT_SECRET_KEY")
if not _jwt_secret and APP_ENV != "test":
    raise RuntimeError("JWT_SECRET_KEY must be set in non-test environments")
SECRET_KEY = _jwt_secret or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# --- Bearer Token ---
security = HTTPBearer(auto_error=False)


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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency to get the current authenticated user.

    Accepts either a JWT bearer token or a live API key (fsk_... prefix).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Path 1: API key (starts with the fsk_ prefix)
    if token.startswith("fsk_"):
        prefix = token[:12] + "..."
        candidates = db.query(ApiKey).filter(ApiKey.key_prefix == prefix, ApiKey.is_active == True).all()
        matched = next((k for k in candidates if verify_password(token, k.key_hash)), None)
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
        db.commit()
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


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, key_hash, key_prefix)."""
    raw_key = f"fsk_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_password(raw_key)
    key_prefix = raw_key[:12] + "..."
    return raw_key, key_hash, key_prefix


# --- RBAC (S3.1) ---

# Permission matrix: role -> set of permissions
PERMISSION_MATRIX = {
    "user": {
        "transactions:create",
        "transactions:read_own",
        "cases:read_own",
        "cases:create",
    },
    "analyst": {
        "transactions:create",
        "transactions:read_own",
        "transactions:read_all",
        "cases:read_own",
        "cases:read_all",
        "cases:create",
        "cases:update",
        "filings:create",
        "filings:update",
        "lists:read",
    },
    "admin": {
        "transactions:create",
        "transactions:read_own",
        "transactions:read_all",
        "cases:read_own",
        "cases:read_all",
        "cases:create",
        "cases:update",
        "cases:assign",
        "filings:create",
        "filings:update",
        "filings:submit",
        "lists:read",
        "lists:write",
        "users:read",
        "users:update",
        "settings:read",
        "settings:update",
        "models:read",
        "models:update",
    },
    "super_admin": {
        "transactions:create",
        "transactions:read_own",
        "transactions:read_all",
        "cases:read_own",
        "cases:read_all",
        "cases:create",
        "cases:update",
        "cases:assign",
        "cases:delete",
        "filings:create",
        "filings:update",
        "filings:submit",
        "filings:delete",
        "lists:read",
        "lists:write",
        "users:read",
        "users:create",
        "users:update",
        "users:delete",
        "settings:read",
        "settings:update",
        "models:read",
        "models:create",
        "models:update",
        "models:delete",
        "system:admin",
    },
}


def has_permission(user: User, permission: str) -> bool:
    """Check if user has a specific permission."""
    user_role = user.role or "user"
    role_permissions = PERMISSION_MATRIX.get(user_role, set())
    return permission in role_permissions


def require_role(*roles: str):
    """Decorator to require specific roles for an endpoint.

    Usage:
        @router.get("/admin/only")
        @require_role("admin", "super_admin")
        def admin_only_endpoint(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, current_user: User, **kwargs):
            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires one of roles: {', '.join(roles)}",
                )
            return func(*args, current_user=current_user, **kwargs)

        return wrapper
    return decorator


def require_permission(permission: str):
    """Decorator to require a specific permission for an endpoint.

    Usage:
        @router.post("/transactions")
        @require_permission("transactions:create")
        def create_transaction(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, current_user: User, **kwargs):
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires permission: {permission}",
                )
            return func(*args, current_user=current_user, **kwargs)

        return wrapper
    return decorator
