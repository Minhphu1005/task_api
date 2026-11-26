from sqlalchemy.ext.asyncio import AsyncSession

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
        if "full_name" in updates and updates["full_name"] is not None:
            updates["full_name"] = updates["full_name"].strip()
        if not updates:
            return user
        updated = await self.users.update(user, **updates)
        await self.session.commit()
        return updated

    async def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise BadRequestError("Current password is incorrect")
        if payload.current_password == payload.new_password:
            raise BadRequestError("New password must be different from current password")
        await self.users.update(user, hashed_password=hash_password(payload.new_password))
        await self.session.commit()
