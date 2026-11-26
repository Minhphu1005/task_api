from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.exceptions import ErrorResponse

API_DESCRIPTION = """
**TaskHub** is a collaborative Task Management REST API built with FastAPI, SQLAlchemy 2.x (async),
Alembic, Pydantic v2, and Redis.

### Authentication
Use `POST /api/v1/auth/login` to obtain a JWT `access_token` and `refresh_token`, then click
**Authorize** and paste `Bearer <access_token>` (or just `<access_token>` in Swagger UI).

### Role-Based Access Control (RBAC)
- **ADMIN** (global): Full access across all workspaces and resources.
- **OWNER** (workspace): Manage workspace, members, projects, tasks, labels, and comments.
- **EDITOR** (workspace): Create and update projects, tasks, labels, and comments.
- **VIEWER** (workspace): Read-only access plus posting and deleting own comments.
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {"name": "Health", "description": "Service liveness and environment metadata."},
    {"name": "Authentication", "description": "Register, login, refresh, and logout with JWT."},
    {"name": "Users", "description": "Authenticated user profile and password management."},
    {"name": "Workspaces", "description": "Workspace CRUD and member role management."},
    {"name": "Projects", "description": "Project CRUD and archiving within workspaces."},
    {"name": "Tasks", "description": "Task CRUD, filtering, pagination, and Redis caching."},
    {"name": "Labels", "description": "Project-scoped labels and task-label associations."},
    {"name": "Comments", "description": "Task discussion comments."},
]

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Bad Request"},
    401: {"model": ErrorResponse, "description": "Unauthorized — Missing or invalid Bearer token"},
    403: {"model": ErrorResponse, "description": "Forbidden — Insufficient RBAC permissions"},
    404: {"model": ErrorResponse, "description": "Not Found — Resource does not exist"},
    409: {"model": ErrorResponse, "description": "Conflict — Duplicate or conflicting resource"},
    422: {"model": ErrorResponse, "description": "Validation Error — Invalid request payload"},
}


def configure_openapi(app: FastAPI) -> None:
    """Attach custom OpenAPI schema with explicit HTTP Bearer JWT security scheme."""

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
            "description": "Enter your JWT access token from POST /api/v1/auth/login",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
