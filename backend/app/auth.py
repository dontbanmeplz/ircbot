from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer(auto_error=False)


def create_token(is_admin: bool = False) -> str:
    """Create a JWT token after successful password auth."""
    payload = {
        "sub": "admin" if is_admin else "user",
        "admin": is_admin,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token. Returns the payload or None."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def verify_token(token: str) -> bool:
    """Verify a JWT token is valid and not expired."""
    return decode_token(token) is not None


def verify_password(password: str) -> tuple[bool, bool]:
    """Check if the provided password matches.
    
    Returns (is_valid, is_admin).
    """
    if password == settings.admin_password:
        return True, True
    if password == settings.password:
        return True, False
    return False, False


def _extract_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Extract token from Authorization header or query param."""
    if credentials:
        return credentials.credentials
    return request.query_params.get("token")


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """FastAPI dependency that requires valid auth. Returns the decoded payload."""
    token = _extract_token(request, credentials)
    if token:
        payload = decode_token(token)
        if payload:
            return payload

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


async def require_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """FastAPI dependency that requires admin auth."""
    token = _extract_token(request, credentials)
    if token:
        payload = decode_token(token)
        if payload and payload.get("admin"):
            return payload

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
