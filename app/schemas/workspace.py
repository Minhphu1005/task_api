from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import WorkspaceRole


class WorkspaceCreate(BaseModel):
    """Payload to create a new workspace."""

    name: str = Field(..., min_length=2, max_length=150)


class WorkspaceUpdate(BaseModel):
    """Payload to update a workspace."""

    name: str | None = Field(default=None, min_length=2, max_length=150)


class WorkspaceMemberInvite(BaseModel):
    """Payload to invite an existing user into a workspace."""

    email: EmailStr | None = None
    user_id: int | None = None
    role: WorkspaceRole = WorkspaceRole.VIEWER


class WorkspaceMemberRoleUpdate(BaseModel):
    """Payload to change a member's workspace role."""

    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    """Member entry inside a workspace."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: int
    user_id: int
    role: WorkspaceRole
    email: EmailStr | None = None
    full_name: str | None = None


class WorkspaceResponse(BaseModel):
    """Summary representation of a workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime


class WorkspaceDetailResponse(WorkspaceResponse):
    """Workspace representation including its member list."""

    members: list[WorkspaceMemberResponse] = Field(default_factory=list)
