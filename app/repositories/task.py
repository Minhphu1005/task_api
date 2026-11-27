from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_LIMIT
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Comment, Label, Task, TaskLabel
from app.repositories.base import BaseRepository, PaginatedResult


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Task)

    async def get_with_details(self, task_id: int) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.id == task_id)
            .options(
                selectinload(Task.project),
                selectinload(Task.labels),
                selectinload(Task.assignee),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: int,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: int | None = None,
        search: str | None = None,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> PaginatedResult[Task]:
        stmt = select(Task).where(Task.project_id == project_id).options(selectinload(Task.labels))
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        if search:
            stmt = stmt.where(Task.title.icontains(search, autoescape=True))
        stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())
        return await self.paginate(stmt, page=page, limit=limit)

    async def get_task_label(self, task_id: int, label_id: int) -> TaskLabel | None:
        stmt = select(TaskLabel).where(
            TaskLabel.task_id == task_id,
            TaskLabel.label_id == label_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def attach_label(self, task_id: int, label_id: int) -> TaskLabel:
        assoc = TaskLabel(task_id=task_id, label_id=label_id)
        self.session.add(assoc)
        await self.session.flush()
        return assoc

    async def detach_label(self, assoc: TaskLabel) -> None:
        await self.session.delete(assoc)
        await self.session.flush()


class LabelRepository(BaseRepository[Label]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Label)

    async def list_by_project(self, project_id: int) -> list[Label]:
        stmt = select(Label).where(Label.project_id == project_id).order_by(Label.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_project_and_name(self, project_id: int, name: str) -> Label | None:
        stmt = select(Label).where(Label.project_id == project_id, Label.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class CommentRepository(BaseRepository[Comment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Comment)

    async def list_by_task(self, task_id: int) -> list[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.task_id == task_id)
            .options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_task(self, comment_id: int) -> Comment | None:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.task).selectinload(Task.project))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
