from datetime import UTC, datetime

from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate


class InMemoryTaskService:
    """Temporary in-memory task service used for the Day 1 skeleton app."""

    def __init__(self) -> None:
        self._tasks: dict[int, TaskResponse] = {}
        self._next_id: int = 1

    def list_tasks(self) -> list[TaskResponse]:
        return list(self._tasks.values())

    def get_task(self, task_id: int) -> TaskResponse | None:
        return self._tasks.get(task_id)

    def create_task(self, payload: TaskCreate) -> TaskResponse:
        task = TaskResponse(
            id=self._next_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            created_at=datetime.now(UTC),
        )
        self._tasks[self._next_id] = task
        self._next_id += 1
        return task

    def update_task(self, task_id: int, payload: TaskUpdate) -> TaskResponse | None:
        existing = self._tasks.get(task_id)
        if existing is None:
            return None
        updated = existing.model_copy(update=payload.model_dump(exclude_unset=True))
        self._tasks[task_id] = updated
        return updated

    def delete_task(self, task_id: int) -> bool:
        return self._tasks.pop(task_id, None) is not None


_task_service = InMemoryTaskService()


def get_task_service() -> InMemoryTaskService:
    """Dependency returning the in-memory task service."""
    return _task_service
