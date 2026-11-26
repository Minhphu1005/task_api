from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import (
    ALL_WORKSPACE_ROLES,
    EDITOR_OR_OWNER,
    OWNER_ONLY,
    ensure_project_role,
    ensure_workspace_role,
)
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """Business logic for projects within workspaces."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectRepository(session)

    async def create_project(
        self,
        workspace_id: int,
        current_user: User,
        payload: ProjectCreate,
    ) -> Project:
        """Create a project inside a workspace (OWNER, EDITOR, or ADMIN)."""
        await ensure_workspace_role(self.session, workspace_id, current_user, EDITOR_OR_OWNER)
        project = await self.projects.create(
            workspace_id=workspace_id,
            name=payload.name.strip(),
            description=payload.description,
            status=ProjectStatus.ACTIVE,
        )
        await self.session.commit()
        return project

    async def list_projects(
        self,
        workspace_id: int,
        current_user: User,
        *,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        """List projects in a workspace for any workspace member."""
        await ensure_workspace_role(self.session, workspace_id, current_user, ALL_WORKSPACE_ROLES)
        return await self.projects.list_by_workspace(workspace_id, status=status)

    async def get_project(self, project_id: int, current_user: User) -> Project:
        """Fetch a project if the user has read access."""
        return await ensure_project_role(
            self.session, project_id, current_user, ALL_WORKSPACE_ROLES
        )

    async def update_project(
        self,
        project_id: int,
        current_user: User,
        payload: ProjectUpdate,
    ) -> Project:
        """Update project metadata (OWNER, EDITOR, or ADMIN)."""
        project = await ensure_project_role(
            self.session, project_id, current_user, EDITOR_OR_OWNER
        )
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        if not updates:
            return project
        updated = await self.projects.update(project, **updates)
        await self.session.commit()
        return updated

    async def archive_project(self, project_id: int, current_user: User) -> Project:
        """Archive a project (OWNER or ADMIN only)."""
        project = await ensure_project_role(self.session, project_id, current_user, OWNER_ONLY)
        updated = await self.projects.update(project, status=ProjectStatus.ARCHIVED)
        await self.session.commit()
        return updated

    async def delete_project(self, project_id: int, current_user: User) -> None:
        """Delete a project (OWNER or ADMIN only)."""
        project = await ensure_project_role(self.session, project_id, current_user, OWNER_ONLY)
        await self.projects.delete(project)
        await self.session.commit()
