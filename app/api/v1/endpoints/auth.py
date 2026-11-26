from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account."""
    service = AuthService(session)
    user = await service.register(payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenPairResponse, summary="Authenticate user")
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPairResponse:
    """Authenticate with email and password and receive JWT tokens."""
    service = AuthService(session)
    return await service.login(payload)


@router.post("/refresh", response_model=TokenPairResponse, summary="Refresh access token")
async def refresh_token(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPairResponse:
    """Exchange a valid refresh token for a fresh access + refresh token pair."""
    service = AuthService(session)
    return await service.refresh(payload)


@router.post("/logout", response_model=MessageResponse, summary="Revoke refresh token")
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke the provided refresh token."""
    service = AuthService(session)
    await service.logout(payload)
    return MessageResponse(message="Successfully logged out")
