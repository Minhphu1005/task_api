from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request payload for email/password login."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Request payload for refreshing an access token."""

    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """Request payload for revoking a refresh token on logout."""

    refresh_token: str = Field(..., min_length=1)


class TokenPairResponse(BaseModel):
    """Response containing JWT access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
