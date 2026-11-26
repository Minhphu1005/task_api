from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_blacklist,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)


class AuthService:
    """Handles user registration, login, token refresh, and logout."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
        """Register a new user account."""
        normalized_email = payload.email.lower()
        existing = await self.users.get_by_email(normalized_email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        user = await self.users.create(
            email=normalized_email,
            full_name=payload.full_name.strip(),
            hashed_password=hash_password(payload.password),
        )
        await self.session.commit()
        return user

    async def login(self, payload: LoginRequest) -> TokenPairResponse:
        """Authenticate a user and issue an access + refresh token pair."""
        user = await self.users.get_by_email(payload.email.lower())
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return TokenPairResponse(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id, user.role.value),
        )

    async def refresh(self, payload: RefreshTokenRequest) -> TokenPairResponse:
        """Validate a refresh token, rotate it, and return a new token pair."""
        try:
            claims = decode_token(payload.refresh_token, expected_type="refresh")
            user_id = int(claims["sub"])
            jti = str(claims["jti"])
            exp = int(claims["exp"])
        except (TokenError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            ) from exc

        if await token_blacklist.is_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or inactive",
            )

        ttl = max(int(exp - datetime.now(UTC).timestamp()), 1)
        await token_blacklist.revoke(jti, ttl)

        return TokenPairResponse(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id, user.role.value),
        )

    async def logout(self, payload: LogoutRequest) -> None:
        """Revoke a refresh token so it can no longer be used."""
        try:
            claims = decode_token(payload.refresh_token, expected_type="refresh")
            jti = str(claims["jti"])
            exp = int(claims["exp"])
        except (TokenError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            ) from exc

        ttl = max(int(exp - datetime.now(UTC).timestamp()), 1)
        await token_blacklist.revoke(jti, ttl)
