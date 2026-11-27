import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt
from redis.exceptions import RedisError

from app.core.cache import cache_service
from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.messages import TOKEN_STORE_UNAVAILABLE


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(
    user_id: int,
    role: str,
    *,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now.timestamp(),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id,
        role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id,
        role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
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
    if "sub" not in payload or "jti" not in payload or "iat" not in payload:
        raise TokenError("Malformed token payload")
    return payload


class TokenBlacklist:
    """Revoked refresh-token store.

    Uses Redis with atomic SET NX EX in staging/production (failing closed with 503 if
    Redis is unavailable). Allows in-memory fallback only in development/test.
    """

    PREFIX = "revoked_token:"

    def __init__(self) -> None:
        self._memory: dict[str, float] = {}

    def _allow_memory_fallback(self) -> bool:
        return get_settings().environment in {"development", "test"}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, exp in self._memory.items() if now >= exp]
        for key in expired:
            self._memory.pop(key, None)

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        key = f"{self.PREFIX}{jti}"
        ttl = max(ttl_seconds, 1)
        client = cache_service.redis_client
        if client is not None:
            try:
                await client.set(key, "1", ex=ttl)
                return
            except RedisError as exc:
                if not self._allow_memory_fallback():
                    raise ServiceUnavailableError(TOKEN_STORE_UNAVAILABLE) from exc
        elif not self._allow_memory_fallback():
            raise ServiceUnavailableError(TOKEN_STORE_UNAVAILABLE)

        self._evict_expired()
        self._memory[key] = time.monotonic() + ttl

    async def claim_revoked(self, jti: str, ttl_seconds: int) -> bool:
        """Atomically mark a JTI as revoked.

        Returns True if the token was newly claimed (first use), or False if it was
        already revoked/consumed by a previous or concurrent request.
        """
        key = f"{self.PREFIX}{jti}"
        ttl = max(ttl_seconds, 1)
        client = cache_service.redis_client
        if client is not None:
            try:
                created = await client.set(key, "1", ex=ttl, nx=True)
                return bool(created)
            except RedisError as exc:
                if not self._allow_memory_fallback():
                    raise ServiceUnavailableError(TOKEN_STORE_UNAVAILABLE) from exc
        elif not self._allow_memory_fallback():
            raise ServiceUnavailableError(TOKEN_STORE_UNAVAILABLE)

        self._evict_expired()
        if key in self._memory:
            return False
        self._memory[key] = time.monotonic() + ttl
        return True

    def clear_memory(self) -> None:
        self._memory.clear()


token_blacklist = TokenBlacklist()
