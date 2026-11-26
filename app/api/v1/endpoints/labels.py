from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import LabelResponse, LabelUpdate
from app.services.task import LabelService

router = APIRouter(prefix="/labels", tags=["Labels"])


@router.patch("/{label_id}", response_model=LabelResponse, summary="Update a label")
async def update_label(
    label_id: int,
    payload: LabelUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Update a label's name or color (owner or editor)."""
    service = LabelService(session)
    label = await service.update_label(label_id, current_user, payload)
    return LabelResponse.model_validate(label)


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label",
)
async def delete_label(
    label_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a label (owner or editor)."""
    service = LabelService(session)
    await service.delete_label(label_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
