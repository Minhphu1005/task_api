from collections.abc import Iterable

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    cache_service,
    invalidate_project_tasks_cache,
    project_tasks_cache_key,
)
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import (
    ALL_WORKSPACE_ROLES,
    EDITOR_OR_OWNER,
    ensure_project_role,
    ensure_workspace_role,
)
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.task import Comment, Label, Task
from app.models.user import User
from app.repositories.task import CommentRepository, LabelRepository, TaskRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.task import (
    CommentCreate,
    LabelCreate,
    LabelResponse,
    LabelUpdate,
    PaginatedTaskResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.notification import send_task_assigned_email


def serialize_task(task: Task, *, include_labels: bool = True) -> TaskResponse:
    labels = [LabelResponse.model_validate(lbl) for lbl in task.labels] if include_labels else []
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        assignee_id=task.assignee_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        created_by=task.created_by,
        created_at=task.created_at,
        labels=labels,
    )


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.labels = LabelRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.users = UserRepository(session)

    async def _get_authorized_task(
        self,
        task_id: int,
        current_user: User,
        allowed_roles: Iterable[WorkspaceRole],
    ) -> Task:
        task = await self.tasks.get_with_details(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        await ensure_workspace_role(
            self.session, task.project.workspace_id, current_user, allowed_roles
        )
        return task

    async def _validate_assignee(self, workspace_id: int, assignee_id: int | None) -> User | None:
        if assignee_id is None:
            return None
        member = await self.workspaces.get_member(workspace_id, assignee_id)
        if member is None:
            raise BadRequestError("Assignee must be a member of the workspace")
        return await self.users.get_by_id(assignee_id)

    @staticmethod
    def _queue_assignment_notification(
        background_tasks: BackgroundTasks | None,
        *,
        assignee: User | None,
        task_title: str,
        project_id: int,
        assigned_by: str,
    ) -> None:
        if assignee is not None and background_tasks is not None:
            background_tasks.add_task(
                send_task_assigned_email,
                recipient_email=assignee.email,
                recipient_name=assignee.full_name,
                task_title=task_title,
                project_id=project_id,
                assigned_by=assigned_by,
            )

    async def create_task(
        self,
        project_id: int,
        current_user: User,
        payload: TaskCreate,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        project = await ensure_project_role(self.session, project_id, current_user, EDITOR_OR_OWNER)
        if project.status == ProjectStatus.ARCHIVED:
            raise BadRequestError("Cannot create tasks in an archived project")

        assignee = await self._validate_assignee(project.workspace_id, payload.assignee_id)

        task = await self.tasks.create(
            project_id=project_id,
            assignee_id=payload.assignee_id,
            title=payload.title.strip(),
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            due_date=payload.due_date,
            created_by=current_user.id,
        )
        await self.session.commit()
        await invalidate_project_tasks_cache(project_id)
        self._queue_assignment_notification(
            background_tasks,
            assignee=assignee,
            task_title=task.title,
            project_id=project_id,
            assigned_by=current_user.full_name,
        )
        return serialize_task(task, include_labels=False)

    async def list_project_tasks(
        self,
        project_id: int,
        current_user: User,
        *,
        task_status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: int | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedTaskResponse:
        await ensure_project_role(self.session, project_id, current_user, ALL_WORKSPACE_ROLES)

        cache_key = project_tasks_cache_key(
            project_id,
            status=task_status.value if task_status else None,
            priority=priority.value if priority else None,
            assignee_id=assignee_id,
            search=search,
            page=page,
            limit=limit,
        )
        cached = await cache_service.get_json(cache_key)
        if cached is not None:
            return PaginatedTaskResponse.model_validate(cached)

        result = await self.tasks.list_by_project(
            project_id,
            status=task_status,
            priority=priority,
            assignee_id=assignee_id,
            search=search,
            page=page,
            limit=limit,
        )
        response = PaginatedTaskResponse(
            items=[serialize_task(item) for item in result.items],
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=result.total_pages,
        )
        await cache_service.set_json(cache_key, response.model_dump(mode="json"))
        return response

    async def get_task(self, task_id: int, current_user: User) -> TaskResponse:
        task = await self._get_authorized_task(task_id, current_user, ALL_WORKSPACE_ROLES)
        return serialize_task(task)

    async def update_task(
        self,
        task_id: int,
        current_user: User,
        payload: TaskUpdate,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        task = await self._get_authorized_task(task_id, current_user, EDITOR_OR_OWNER)
        previous_assignee_id = task.assignee_id
        updates = payload.model_dump(exclude_unset=True)

        new_assignee: User | None = None
        if "assignee_id" in updates:
            new_assignee = await self._validate_assignee(
                task.project.workspace_id, updates["assignee_id"]
            )
        if "title" in updates and updates["title"] is not None:
            updates["title"] = updates["title"].strip()

        if updates:
            await self.tasks.update(task, **updates)
            await self.session.commit()
            await invalidate_project_tasks_cache(task.project_id)
            if new_assignee is not None and new_assignee.id != previous_assignee_id:
                self._queue_assignment_notification(
                    background_tasks,
                    assignee=new_assignee,
                    task_title=task.title,
                    project_id=task.project_id,
                    assigned_by=current_user.full_name,
                )

        refreshed = await self.tasks.get_with_details(task_id)
        assert refreshed is not None
        return serialize_task(refreshed)

    async def delete_task(self, task_id: int, current_user: User) -> int:
        task = await self._get_authorized_task(task_id, current_user, EDITOR_OR_OWNER)
        project_id = task.project_id
        await self.tasks.delete(task)
        await self.session.commit()
        await invalidate_project_tasks_cache(project_id)
        return project_id

    async def attach_label(
        self,
        task_id: int,
        label_id: int,
        current_user: User,
    ) -> TaskResponse:
        task = await self._get_authorized_task(task_id, current_user, EDITOR_OR_OWNER)
        label = await self.labels.get_by_id(label_id)
        if label is None or label.project_id != task.project_id:
            raise NotFoundError("Label not found in this project")

        existing = await self.tasks.get_task_label(task_id, label_id)
        if existing is None:
            await self.tasks.attach_label(task_id, label_id)
            await self.session.commit()
            await invalidate_project_tasks_cache(task.project_id)

        self.session.expire(task, ["labels"])
        refreshed = await self.tasks.get_with_details(task_id)
        assert refreshed is not None
        return serialize_task(refreshed)

    async def detach_label(
        self,
        task_id: int,
        label_id: int,
        current_user: User,
    ) -> TaskResponse:
        task = await self._get_authorized_task(task_id, current_user, EDITOR_OR_OWNER)
        existing = await self.tasks.get_task_label(task_id, label_id)
        if existing is None:
            raise NotFoundError("Label is not attached to this task")

        await self.tasks.detach_label(existing)
        await self.session.commit()
        await invalidate_project_tasks_cache(task.project_id)
        self.session.expire(task, ["labels"])
        refreshed = await self.tasks.get_with_details(task_id)
        assert refreshed is not None
        return serialize_task(refreshed)


class LabelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.labels = LabelRepository(session)

    async def create_label(
        self,
        project_id: int,
        current_user: User,
        payload: LabelCreate,
    ) -> Label:
        await ensure_project_role(self.session, project_id, current_user, EDITOR_OR_OWNER)
        name = payload.name.strip()
        existing = await self.labels.get_by_project_and_name(project_id, name)
        if existing is not None:
            raise ConflictError("Label with this name already exists in the project")
        label = await self.labels.create(
            project_id=project_id,
            name=name,
            color=payload.color,
        )
        await self.session.commit()
        return label

    async def list_labels(self, project_id: int, current_user: User) -> list[Label]:
        await ensure_project_role(self.session, project_id, current_user, ALL_WORKSPACE_ROLES)
        return await self.labels.list_by_project(project_id)

    async def update_label(
        self,
        label_id: int,
        current_user: User,
        payload: LabelUpdate,
    ) -> Label:
        label = await self.labels.get_by_id(label_id)
        if label is None:
            raise NotFoundError("Label not found")
        await ensure_project_role(self.session, label.project_id, current_user, EDITOR_OR_OWNER)

        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] is not None:
            updates["name"] = updates["name"].strip()
            existing = await self.labels.get_by_project_and_name(label.project_id, updates["name"])
            if existing is not None and existing.id != label.id:
                raise ConflictError("Label with this name already exists in the project")
        if not updates:
            return label
        updated = await self.labels.update(label, **updates)
        await self.session.commit()
        await invalidate_project_tasks_cache(label.project_id)
        return updated

    async def delete_label(self, label_id: int, current_user: User) -> int:
        label = await self.labels.get_by_id(label_id)
        if label is None:
            raise NotFoundError("Label not found")
        await ensure_project_role(self.session, label.project_id, current_user, EDITOR_OR_OWNER)
        project_id = label.project_id
        await self.labels.delete(label)
        await self.session.commit()
        await invalidate_project_tasks_cache(project_id)
        return project_id


class CommentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.comments = CommentRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def _ensure_task_member(self, task_id: int, current_user: User) -> Task:
        task = await self.tasks.get_with_details(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        await ensure_workspace_role(
            self.session, task.project.workspace_id, current_user, ALL_WORKSPACE_ROLES
        )
        return task

    async def add_comment(
        self,
        task_id: int,
        current_user: User,
        payload: CommentCreate,
    ) -> Comment:
        await self._ensure_task_member(task_id, current_user)
        comment = await self.comments.create(
            task_id=task_id,
            author_id=current_user.id,
            content=payload.content.strip(),
        )
        await self.session.commit()
        return comment

    async def list_comments(self, task_id: int, current_user: User) -> list[Comment]:
        await self._ensure_task_member(task_id, current_user)
        return await self.comments.list_by_task(task_id)

    async def delete_comment(self, comment_id: int, current_user: User) -> None:
        comment = await self.comments.get_with_task(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")

        workspace_id = comment.task.project.workspace_id
        if current_user.role != UserRole.ADMIN and comment.author_id != current_user.id:
            member = await self.workspaces.get_member(workspace_id, current_user.id)
            if member is None or member.role != WorkspaceRole.OWNER:
                raise ForbiddenError(
                    "Only the comment author, workspace owner, or admin can delete it"
                )

        await self.comments.delete(comment)
        await self.session.commit()
