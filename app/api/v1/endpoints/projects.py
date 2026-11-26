from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.services.project import ProjectService

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
