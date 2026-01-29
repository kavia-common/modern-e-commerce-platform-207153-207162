import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_jwt_secret() -> str:
    """
    Resolve JWT secret from environment.

    Required env var:
      - JWT_SECRET

    For local/dev in this template, we fall back to a deterministic value.
    In production you MUST set JWT_SECRET.
    """
    return _env("JWT_SECRET", "dev-insecure-secret-change-me")  # pragma: allowlist secret


def _get_jwt_exp_minutes() -> int:
    try:
        return int(_env("JWT_EXPIRES_MINUTES", "1440") or "1440")
    except ValueError:
        return 1440


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return pwd_context.verify(password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(*, user_id: int, role: str) -> str:
    """Create a signed JWT access token for a user."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=_get_jwt_exp_minutes())
    payload = {"sub": str(user_id), "role": role, "iat": int(now.timestamp()), "exp": exp}
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


# PUBLIC_INTERFACE
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve and return the currently authenticated user from Authorization: Bearer <token>.
    """
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()

    token = creds.credentials
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise _unauthorized("Invalid token")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


# PUBLIC_INTERFACE
def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the current user has admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
