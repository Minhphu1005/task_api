from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages as msg
from app.core.constants import DEFAULT_PAGE_LIMIT
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.permissions import ALL_WORKSPACE_ROLES, OWNER_ONLY, ensure_workspace_role
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceMemberInvite,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
    WorkspaceUpdate,
)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspaces = WorkspaceRepository(session)
        self.users = UserRepository(session)

    async def create_workspace(self, current_user: User, payload: WorkspaceCreate) -> Workspace:
        workspace = await self.workspaces.create(
            name=payload.name,
            owner_id=current_user.id,
        )
        await self.workspaces.add_member(workspace.id, current_user.id, WorkspaceRole.OWNER)
        await self.session.commit()
        return workspace

    async def list_workspaces(
        self,
        current_user: User,
        *,
        offset: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> list[Workspace]:
        if current_user.role == UserRole.ADMIN:
            return await self.workspaces.list_all(offset=offset, limit=limit)
        return await self.workspaces.list_for_user(current_user.id, offset=offset, limit=limit)

    async def get_workspace(
        self,
        workspace_id: int,
        current_user: User,
    ) -> WorkspaceDetailResponse:
        await ensure_workspace_role(self.session, workspace_id, current_user, ALL_WORKSPACE_ROLES)
        workspace = await self.workspaces.get_with_members(workspace_id)
        if workspace is None:
            raise NotFoundError(msg.WORKSPACE_NOT_FOUND)
        members = [
            WorkspaceMemberResponse(
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                role=m.role,
                email=m.user.email if m.user else None,
                full_name=m.user.full_name if m.user else None,
            )
            for m in workspace.members
        ]
        return WorkspaceDetailResponse(
            id=workspace.id,
            name=workspace.name,
            owner_id=workspace.owner_id,
            created_at=workspace.created_at,
            members=members,
        )

    async def update_workspace(
        self,
        workspace_id: int,
        current_user: User,
        payload: WorkspaceUpdate,
    ) -> Workspace:
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return workspace
        updated = await self.workspaces.update(workspace, **updates)
        await self.session.commit()
        return updated

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        await self.workspaces.delete(workspace)
        await self.session.commit()

    async def invite_member(
        self,
        workspace_id: int,
        current_user: User,
        payload: WorkspaceMemberInvite,
    ) -> WorkspaceMemberResponse:
        await ensure_workspace_role(self.session, workspace_id, current_user, OWNER_ONLY)

        target_user: User | None = None
        if payload.user_id is not None:
            target_user = await self.users.get_by_id(payload.user_id)
        elif payload.email is not None:
            target_user = await self.users.get_by_email(payload.email)

        if target_user is None:
            raise NotFoundError(msg.TARGET_USER_NOT_FOUND)

        existing = await self.workspaces.get_member(workspace_id, target_user.id)
        if existing is not None:
            raise ConflictError(msg.MEMBER_ALREADY_EXISTS)

        try:
            member = await self.workspaces.add_member(workspace_id, target_user.id, payload.role)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(msg.MEMBER_ALREADY_EXISTS) from exc

        return WorkspaceMemberResponse(
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role=member.role,
            email=target_user.email,
            full_name=target_user.full_name,
        )

    async def update_member_role(
        self,
        workspace_id: int,
        target_user_id: int,
        current_user: User,
        payload: WorkspaceMemberRoleUpdate,
    ) -> WorkspaceMemberResponse:
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        if target_user_id == workspace.owner_id and payload.role != WorkspaceRole.OWNER:
            raise BadRequestError(msg.CANNOT_DOWNGRADE_OWNER)

        member: WorkspaceMember | None = await self.workspaces.get_member(
            workspace_id, target_user_id
        )
        if member is None:
            raise NotFoundError(msg.MEMBER_NOT_FOUND)

        member.role = payload.role
        await self.session.commit()
        user = await self.users.get_by_id(target_user_id)
        return WorkspaceMemberResponse(
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role=member.role,
            email=user.email if user else None,
            full_name=user.full_name if user else None,
        )

    async def remove_member(
        self,
        workspace_id: int,
        target_user_id: int,
        current_user: User,
    ) -> None:
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        if target_user_id == workspace.owner_id:
            raise BadRequestError(msg.CANNOT_REMOVE_OWNER)

        member = await self.workspaces.get_member(workspace_id, target_user_id)
        if member is None:
            raise NotFoundError(msg.MEMBER_NOT_FOUND)

        await self.workspaces.remove_member(member)
        await self.session.commit()
