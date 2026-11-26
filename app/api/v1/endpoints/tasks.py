from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import CommentCreate, CommentResponse, TaskResponse, TaskUpdate
from app.services.task import CommentService, TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=TaskResponse, summary="Get a task by ID")
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Return a single task by ID."""
    service = TaskService(session)
    return await service.get_task(task_id, current_user)


@router.patch("/{task_id}", response_model=TaskResponse, summary="Update a task")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Partially update a task (owner or editor)."""
    service = TaskService(session)
    return await service.update_task(
        task_id,
        current_user,
        payload,
        background_tasks=background_tasks,
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a task (owner or editor)."""
    service = TaskService(session)
    await service.delete_task(task_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    summary="Attach a label to a task",
    tags=["Labels"],
)
async def attach_label(
    task_id: int,
    label_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Attach a project label to a task (owner or editor)."""
    service = TaskService(session)
    return await service.attach_label(task_id, label_id, current_user)


@router.delete(
    "/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    summary="Detach a label from a task",
    tags=["Labels"],
)
async def detach_label(
    task_id: int,
    label_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Detach a label from a task (owner or editor)."""
    service = TaskService(session)
    return await service.detach_label(task_id, label_id, current_user)


@router.post(
    "/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a task",
    tags=["Comments"],
)
async def add_comment(
    task_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Post a new comment on a task (any workspace member)."""
    service = CommentService(session)
    comment = await service.add_comment(task_id, current_user, payload)
    return CommentResponse.model_validate(comment)


@router.get(
    "/{task_id}/comments",
    response_model=list[CommentResponse],
    summary="List comments on a task",
    tags=["Comments"],
)
async def list_comments(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CommentResponse]:
    """List all comments on a task."""
    service = CommentService(session)
    comments = await service.list_comments(task_id, current_user)
    return [CommentResponse.model_validate(c) for c in comments]
