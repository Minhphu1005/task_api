from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Business logic for workspaces and workspace membership management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspaces = WorkspaceRepository(session)
        self.users = UserRepository(session)

    async def create_workspace(self, current_user: User, payload: WorkspaceCreate) -> Workspace:
        """Create a workspace and assign the creator as OWNER."""
        workspace = await self.workspaces.create(
            name=payload.name.strip(),
            owner_id=current_user.id,
        )
        await self.workspaces.add_member(workspace.id, current_user.id, WorkspaceRole.OWNER)
        await self.session.commit()
        return workspace

    async def list_workspaces(self, current_user: User) -> list[Workspace]:
        """List workspaces visible to the current user."""
        if current_user.role == UserRole.ADMIN:
            return await self.workspaces.list_all(limit=200)
        return await self.workspaces.list_for_user(current_user.id)

    async def get_workspace(
        self,
        workspace_id: int,
        current_user: User,
    ) -> WorkspaceDetailResponse:
        """Return workspace details and members if authorized."""
        await ensure_workspace_role(self.session, workspace_id, current_user, ALL_WORKSPACE_ROLES)
        workspace = await self.workspaces.get_with_members(workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
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
        """Update workspace fields (OWNER or ADMIN only)."""
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
        if not updates:
            return workspace
        updated = await self.workspaces.update(workspace, **updates)
        await self.session.commit()
        return updated

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        """Delete a workspace (OWNER or ADMIN only)."""
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
        """Invite an existing user to a workspace (OWNER or ADMIN only)."""
        await ensure_workspace_role(self.session, workspace_id, current_user, OWNER_ONLY)

        target_user: User | None = None
        if payload.user_id is not None:
            target_user = await self.users.get_by_id(payload.user_id)
        elif payload.email is not None:
            target_user = await self.users.get_by_email(payload.email)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or email must be provided",
            )

        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found",
            )

        existing = await self.workspaces.get_member(workspace_id, target_user.id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this workspace",
            )

        member = await self.workspaces.add_member(workspace_id, target_user.id, payload.role)
        await self.session.commit()
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
        """Update a workspace member's role (OWNER or ADMIN only)."""
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        if target_user_id == workspace.owner_id and payload.role != WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot downgrade the workspace owner",
            )

        member: WorkspaceMember | None = await self.workspaces.get_member(
            workspace_id, target_user_id
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        member.role = payload.role
        await self.session.flush()
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
        """Remove a member from a workspace (OWNER or ADMIN only)."""
        workspace = await ensure_workspace_role(
            self.session, workspace_id, current_user, OWNER_ONLY
        )
        if target_user_id == workspace.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the workspace owner",
            )

        member = await self.workspaces.get_member(workspace_id, target_user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        await self.workspaces.remove_member(member)
        await self.session.commit()
