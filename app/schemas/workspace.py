from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.enums import WorkspaceRole
from app.schemas.base import TrimmedBaseModel, reject_explicit_nulls


class WorkspaceCreate(TrimmedBaseModel):
    name: str = Field(..., min_length=2, max_length=150)


class WorkspaceUpdate(TrimmedBaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)

    @model_validator(mode="before")
    @classmethod
    def check_no_nulls(cls, data: Any) -> Any:
        return reject_explicit_nulls(data, ("name",))


class WorkspaceMemberInvite(TrimmedBaseModel):
    email: EmailStr | None = None
    user_id: int | None = None
    role: WorkspaceRole = WorkspaceRole.VIEWER

    @model_validator(mode="after")
    def validate_exactly_one_identifier(self) -> "WorkspaceMemberInvite":
        if (self.email is None) == (self.user_id is None):
            raise ValueError("Provide exactly one of 'email' or 'user_id'")
        return self


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
