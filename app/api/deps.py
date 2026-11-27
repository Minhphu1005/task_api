from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages as msg
from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="JWT access token from POST /api/v1/auth/login",
)


@dataclass(slots=True)
class PaginationParams:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def get_pagination(
    page: Annotated[int, Query(ge=1)] = DEFAULT_PAGE,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError(msg.NOT_AUTHENTICATED, headers={"WWW-Authenticate": "Bearer"})

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (TokenError, ValueError) as exc:
        raise UnauthorizedError(
            msg.INVALID_ACCESS_TOKEN, headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError(msg.USER_NOT_FOUND, headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise ForbiddenError(msg.USER_INACTIVE)
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError(msg.ADMIN_REQUIRED)
    return current_user
