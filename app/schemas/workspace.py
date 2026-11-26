from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)


class WorkspaceMemberInvite(BaseModel):
    email: EmailStr | None = None
    user_id: int | None = None
    role: WorkspaceRole = WorkspaceRole.VIEWER


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: int
    user_id: int
    role: WorkspaceRole
    email: EmailStr | None = None
    full_name: str | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime


class WorkspaceDetailResponse(WorkspaceResponse):
    members: list[WorkspaceMemberResponse] = Field(default_factory=list)
