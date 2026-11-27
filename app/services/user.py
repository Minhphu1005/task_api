from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages as msg
from app.core.exceptions import BadRequestError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import ChangePasswordRequest, UserUpdateRequest


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def update_profile(self, user: User, payload: UserUpdateRequest) -> User:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return user
        updated = await self.users.update(user, **updates)
        await self.session.commit()
        return updated

    async def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise BadRequestError(msg.CURRENT_PASSWORD_INCORRECT)
        if payload.current_password == payload.new_password:
            raise BadRequestError(msg.PASSWORD_MUST_DIFFER)
        await self.users.update(
            user,
            hashed_password=hash_password(payload.new_password),
            password_changed_at=datetime.now(UTC),
        )
        await self.session.commit()
