from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.core.cache import cache_service
from app.core.config import get_settings


class TokenError(Exception):
    """Raised when a JWT token is invalid, expired, or revoked."""


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, role: str) -> str:
    """Create a signed JWT refresh token."""
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token")
    if "sub" not in payload or "jti" not in payload:
        raise TokenError("Malformed token payload")
    return payload


class TokenBlacklist:
    """Stores revoked refresh token JTIs in Redis (with in-memory fallback)."""

    PREFIX = "revoked_token:"

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Mark a token JTI as revoked for its remaining lifetime."""
        await cache_service.set_flag(f"{self.PREFIX}{jti}", ttl_seconds=max(ttl_seconds, 1))

    async def is_revoked(self, jti: str) -> bool:
        """Return True if the token JTI has been revoked."""
        return await cache_service.exists(f"{self.PREFIX}{jti}")


token_blacklist = TokenBlacklist()
