from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole, WorkspaceRole
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.project import ProjectRepository
from app.repositories.workspace import WorkspaceRepository

ALL_WORKSPACE_ROLES: frozenset[WorkspaceRole] = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER}
)
EDITOR_OR_OWNER: frozenset[WorkspaceRole] = frozenset({WorkspaceRole.OWNER, WorkspaceRole.EDITOR})
OWNER_ONLY: frozenset[WorkspaceRole] = frozenset({WorkspaceRole.OWNER})


async def ensure_workspace_role(
    session: AsyncSession,
    workspace_id: int,
    user: User,
    allowed_roles: Iterable[WorkspaceRole],
) -> Workspace:
    repo = WorkspaceRepository(session)
    workspace = await repo.get_by_id(workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace not found")

    if user.role == UserRole.ADMIN:
        return workspace

    membership = await repo.get_member(workspace_id, user.id)
    if membership is None or membership.role not in set(allowed_roles):
        raise ForbiddenError("Insufficient permissions for this workspace")
    return workspace


async def ensure_project_role(
    session: AsyncSession,
    project_id: int,
    user: User,
    allowed_roles: Iterable[WorkspaceRole],
) -> Project:
    project_repo = ProjectRepository(session)
    project = await project_repo.get_by_id(project_id)
    if project is None:
        raise NotFoundError("Project not found")
    await ensure_workspace_role(session, project.workspace_id, user, allowed_roles)
    return project
