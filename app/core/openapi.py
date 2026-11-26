from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.exceptions import ErrorResponse

API_DESCRIPTION = """
TaskHub API for managing workspaces, projects, tasks, labels, and comments.

Authentication:
- Call `POST /api/v1/auth/login` to get `access_token` and `refresh_token`.
- Click **Authorize** and enter the access token.

Roles:
- `ADMIN` (global): full access
- `OWNER` (workspace): manage workspace, members, projects, tasks, labels, comments
- `EDITOR` (workspace): create/update projects, tasks, labels, comments
- `VIEWER` (workspace): read-only access + create/delete own comments
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {"name": "Health", "description": "Health check endpoint"},
    {"name": "Authentication", "description": "Register, login, refresh token, logout"},
    {"name": "Users", "description": "Current user profile and password"},
    {"name": "Workspaces", "description": "Workspace CRUD and member management"},
    {"name": "Projects", "description": "Project CRUD and archive"},
    {"name": "Tasks", "description": "Task CRUD, filters, pagination, and Redis cache"},
    {"name": "Labels", "description": "Project labels and task label mapping"},
    {"name": "Comments", "description": "Task comments"},
]

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Bad Request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Not Found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    422: {"model": ErrorResponse, "description": "Validation Error"},
}


def configure_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=API_DESCRIPTION,
            routes=app.routes,
            tags=TAGS_METADATA,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token from POST /api/v1/auth/login",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
