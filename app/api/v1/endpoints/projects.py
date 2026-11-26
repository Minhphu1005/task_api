from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.schemas.task import (
    LabelCreate,
    LabelResponse,
    PaginatedTaskResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.project import ProjectService
from app.services.task import LabelService, TaskService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Return a single project if the user has workspace access."""
    service = ProjectService(session)
    project = await service.get_project(project_id, current_user)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Update project")
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project (owner or editor)."""
    service = ProjectService(session)
    project = await service.update_project(project_id, current_user, payload)
    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project",
)
async def archive_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Mark a project as ARCHIVED (owner only)."""
    service = ProjectService(session)
    project = await service.archive_project(project_id, current_user)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a project (owner only)."""
    service = ProjectService(session)
    await service.delete_project(project_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{project_id}/tasks",
    response_model=PaginatedTaskResponse,
    summary="List tasks in a project",
    tags=["Tasks"],
)
async def list_project_tasks(
    project_id: int,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    assignee_id: int | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PaginatedTaskResponse:
    """List tasks in a project with filtering and pagination."""
    service = TaskService(session)
    return await service.list_project_tasks(
        project_id,
        current_user,
        task_status=task_status,
        priority=priority,
        assignee_id=assignee_id,
        search=search,
        page=page,
        limit=limit,
    )


@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task in a project",
    tags=["Tasks"],
)
async def create_project_task(
    project_id: int,
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a new task inside a project (owner or editor)."""
    service = TaskService(session)
    return await service.create_task(project_id, current_user, payload)


@router.post(
    "/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a label in a project",
    tags=["Labels"],
)
async def create_project_label(
    project_id: int,
    payload: LabelCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Create a project-scoped label (owner or editor)."""
    service = LabelService(session)
    label = await service.create_label(project_id, current_user, payload)
    return LabelResponse.model_validate(label)


@router.get(
    "/{project_id}/labels",
    response_model=list[LabelResponse],
    summary="List labels in a project",
    tags=["Labels"],
)
async def list_project_labels(
    project_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[LabelResponse]:
    """List all labels defined for a project."""
    service = LabelService(session)
    labels = await service.list_labels(project_id, current_user)
    return [LabelResponse.model_validate(lbl) for lbl in labels]
