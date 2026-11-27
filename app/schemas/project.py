from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus
from app.schemas.base import TrimmedBaseModel, reject_explicit_nulls


class ProjectCreate(TrimmedBaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdate(TrimmedBaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def check_no_nulls(cls, data: Any) -> Any:
        return reject_explicit_nulls(data, ("name",))


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
