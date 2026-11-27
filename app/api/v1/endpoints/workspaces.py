from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationDep, get_current_user
from app.db.session import get_db
from app.models.enums import ProjectStatus
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceMemberInvite,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.project import ProjectService
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    service = WorkspaceService(session)
    workspace = await service.create_workspace(current_user, payload)
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=list[WorkspaceResponse], summary="List workspaces")
async def list_workspaces(
    pagination: PaginationDep,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    service = WorkspaceService(session)
    workspaces = await service.list_workspaces(
        current_user,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return [WorkspaceResponse.model_validate(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse, summary="Get workspace")
async def get_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceDetailResponse:
    service = WorkspaceService(session)
    return await service.get_workspace(workspace_id, current_user)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse, summary="Update workspace")
async def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    service = WorkspaceService(session)
    workspace = await service.update_workspace(workspace_id, current_user, payload)
    return WorkspaceResponse.model_validate(workspace)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
)
async def delete_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    service = WorkspaceService(session)
    await service.delete_workspace(workspace_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member to workspace",
)
async def invite_member(
    workspace_id: int,
    payload: WorkspaceMemberInvite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    service = WorkspaceService(session)
    return await service.invite_member(workspace_id, current_user, payload)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member role",
)
async def update_member_role(
    workspace_id: int,
    user_id: int,
    payload: WorkspaceMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    service = WorkspaceService(session)
    return await service.update_member_role(workspace_id, user_id, current_user, payload)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from workspace",
)
async def remove_member(
    workspace_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    service = WorkspaceService(session)
    await service.remove_member(workspace_id, user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project in workspace",
    tags=["Projects"],
)
async def create_project(
    workspace_id: int,
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(session)
    project = await service.create_project(workspace_id, current_user, payload)
    return ProjectResponse.model_validate(project)


@router.get(
    "/{workspace_id}/projects",
    response_model=list[ProjectResponse],
    summary="List projects in workspace",
    tags=["Projects"],
)
async def list_projects(
    workspace_id: int,
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    service = ProjectService(session)
    projects = await service.list_projects(workspace_id, current_user, status=project_status)
    return [ProjectResponse.model_validate(p) for p in projects]
