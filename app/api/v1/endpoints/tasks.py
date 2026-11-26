from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.task import InMemoryTaskService, get_task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=list[TaskResponse], summary="List all tasks")
async def list_tasks(
    service: InMemoryTaskService = Depends(get_task_service),
) -> list[TaskResponse]:
    """Return all tasks."""
    return service.list_tasks()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(
    payload: TaskCreate,
    service: InMemoryTaskService = Depends(get_task_service),
) -> TaskResponse:
    """Create a new task."""
    return service.create_task(payload)


@router.get("/{task_id}", response_model=TaskResponse, summary="Get a task by ID")
async def get_task(
    task_id: int,
    service: InMemoryTaskService = Depends(get_task_service),
) -> TaskResponse:
    """Return a single task by ID."""
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse, summary="Update a task")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: InMemoryTaskService = Depends(get_task_service),
) -> TaskResponse:
    """Partially update an existing task."""
    task = service.update_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: int,
    service: InMemoryTaskService = Depends(get_task_service),
) -> Response:
    """Delete a task by ID."""
    if not service.delete_task(task_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
