from typing import Any

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


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Validation Error",
        503: "Service Unavailable",
    }
    return {
        code: {"model": ErrorResponse, "description": descriptions.get(code, "Error")}
        for code in codes
    }
