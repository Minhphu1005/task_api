from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages as msg
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
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


def _to_utc_timestamp(dt: datetime) -> float:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).timestamp()
    return dt.timestamp()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
        normalized_email = payload.email.lower()
        existing = await self.users.get_by_email(normalized_email)
        if existing is not None:
            raise ConflictError(msg.EMAIL_ALREADY_REGISTERED)

        try:
            user = await self.users.create(
                email=normalized_email,
                full_name=payload.full_name,
                hashed_password=hash_password(payload.password),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(msg.EMAIL_ALREADY_REGISTERED) from exc
        return user

    async def login(self, payload: LoginRequest) -> TokenPairResponse:
        user = await self.users.get_by_email(payload.email.lower())
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError(msg.INVALID_CREDENTIALS)
        if not user.is_active:
            raise ForbiddenError(msg.USER_INACTIVE)

        return TokenPairResponse(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id, user.role.value),
        )

    async def refresh(self, payload: RefreshTokenRequest) -> TokenPairResponse:
        try:
            claims = decode_token(payload.refresh_token, expected_type="refresh")
            user_id = int(claims["sub"])
            jti = str(claims["jti"])
            iat = float(claims["iat"])
            exp = int(claims["exp"])
        except (TokenError, ValueError, KeyError) as exc:
            raise UnauthorizedError(msg.INVALID_REFRESH_TOKEN) from exc

        # Atomically claim/revoke the refresh token before any DB lookup so concurrent
        # refresh requests with the same token cannot both succeed.
        ttl = max(int(exp - datetime.now(UTC).timestamp()), 1)
        if not await token_blacklist.claim_revoked(jti, ttl):
            raise UnauthorizedError(msg.REFRESH_TOKEN_REVOKED)

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError(msg.USER_NOT_FOUND)

        if user.password_changed_at is not None and iat < _to_utc_timestamp(
            user.password_changed_at
        ):
            raise UnauthorizedError(msg.REFRESH_TOKEN_REVOKED)

        return TokenPairResponse(
            access_token=create_access_token(user.id, user.role.value),
            refresh_token=create_refresh_token(user.id, user.role.value),
        )

    async def logout(self, payload: LogoutRequest) -> None:
        try:
            claims = decode_token(payload.refresh_token, expected_type="refresh")
            jti = str(claims["jti"])
            exp = int(claims["exp"])
        except (TokenError, ValueError, KeyError) as exc:
            raise UnauthorizedError(msg.INVALID_REFRESH_TOKEN) from exc

        ttl = max(int(exp - datetime.now(UTC).timestamp()), 1)
        await token_blacklist.revoke(jti, ttl)
