from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field, StringConstraints

from app.schemas.base import validate_password_bytes

PasswordStr = Annotated[
    str,
    Field(min_length=8, max_length=128),
    AfterValidator(validate_password_bytes),
]
LoginPasswordStr = Annotated[
    str,
    Field(min_length=1, max_length=128),
    AfterValidator(validate_password_bytes),
]
TrimmedFullName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)
]


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: TrimmedFullName
    password: PasswordStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: LoginPasswordStr


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
