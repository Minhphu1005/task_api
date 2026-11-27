from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from app.models.enums import UserRole
from app.schemas.auth import LoginPasswordStr, PasswordStr, TrimmedFullName
from app.schemas.base import TrimmedBaseModel, reject_explicit_nulls


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdateRequest(TrimmedBaseModel):
    full_name: TrimmedFullName | None = None

    @model_validator(mode="before")
    @classmethod
    def check_no_nulls(cls, data: Any) -> Any:
        return reject_explicit_nulls(data, ("full_name",))


class ChangePasswordRequest(BaseModel):
    current_password: LoginPasswordStr
    new_password: PasswordStr
