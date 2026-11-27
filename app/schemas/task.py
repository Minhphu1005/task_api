from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.base import TrimmedBaseModel, reject_explicit_nulls


class LabelCreate(TrimmedBaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field(default="#6366F1", pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelUpdate(TrimmedBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="before")
    @classmethod
    def check_no_nulls(cls, data: Any) -> Any:
        return reject_explicit_nulls(data, ("name", "color"))


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    color: str


class TaskCreate(TrimmedBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    due_date: datetime | None = None


class TaskUpdate(TrimmedBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    due_date: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def check_no_nulls(cls, data: Any) -> Any:
        return reject_explicit_nulls(data, ("title", "status", "priority"))


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    assignee_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    created_by: int
    created_at: datetime
    labels: list[LabelResponse] = Field(default_factory=list)


class PaginatedTaskResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CommentCreate(TrimmedBaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime
