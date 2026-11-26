import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("taskhub.exceptions")


class ErrorResponse(BaseModel):
    """Standardized API error response schema."""

    error: str
    detail: Any
    request_id: str | None = None


class AppError(Exception):
    """Base domain exception mapped to an HTTP status code."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error: str = "application_error",
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.error = error


class BadRequestError(AppError):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(detail, status_code=status.HTTP_400_BAD_REQUEST, error="bad_request")


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(detail, status_code=status.HTTP_401_UNAUTHORIZED, error="unauthorized")


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(detail, status_code=status.HTTP_403_FORBIDDEN, error="forbidden")


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(detail, status_code=status.HTTP_404_NOT_FOUND, error="not_found")


class ConflictError(AppError):
    def __init__(self, detail: str = "Resource conflict") -> None:
        super().__init__(detail, status_code=status.HTTP_409_CONFLICT, error="conflict")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach centralized exception handlers to the FastAPI app."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(error=exc.error, detail=exc.detail, request_id=_request_id(request))
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        body = ErrorResponse(
            error=f"http_{exc.status_code}",
            detail=exc.detail,
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        body = ErrorResponse(
            error="validation_error",
            detail=exc.errors(),
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", exc)
        body = ErrorResponse(
            error="internal_server_error",
            detail="An unexpected internal error occurred",
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )
