from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import DEFAULT_PAGE_LIMIT
from app.models.enums import WorkspaceRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def get_with_members(self, workspace_id: int) -> Workspace | None:
        stmt = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(
        self,
        workspace_id: int,
        user_id: int,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()
