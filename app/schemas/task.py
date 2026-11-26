from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskPriority, TaskStatus


class LabelCreate(BaseModel):
    """Payload to create a project label."""

    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field(default="#6366F1", pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelUpdate(BaseModel):
    """Payload to update a project label."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelResponse(BaseModel):
    """Representation of a project label."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    color: str


class TaskCreate(BaseModel):
    """Payload to create a task inside a project."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    """Payload to partially update a task."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    due_date: datetime | None = None


class TaskResponse(BaseModel):
    """Representation of a task."""

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
    """Paginated list of tasks."""

    items: list[TaskResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CommentCreate(BaseModel):
    """Payload to post a comment on a task."""

    content: str = Field(..., min_length=1, max_length=4000)


class CommentResponse(BaseModel):
    """Representation of a task comment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime
