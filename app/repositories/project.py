from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Data access repository for Project entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)

    async def list_by_workspace(
        self,
        workspace_id: int,
        *,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        """List all projects in a workspace, optionally filtered by status."""
        stmt = select(Project).where(Project.workspace_id == workspace_id)
        if status is not None:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
