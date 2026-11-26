from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.task import CommentService

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    service = CommentService(session)
    await service.delete_comment(comment_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
