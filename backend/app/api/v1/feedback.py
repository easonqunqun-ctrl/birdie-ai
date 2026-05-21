"""意见反馈 API（docs/02 §2.6）.

端点
----
- `POST /v1/feedback` 提交一条用户反馈（需登录）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.feedback import FeedbackCreate, FeedbackCreated
from app.services import feedback_service

router = APIRouter()


@router.post(
    "",
    summary="提交意见反馈",
    response_model=APIResponse[FeedbackCreated],
)
async def submit_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[FeedbackCreated]:
    try:
        fb = await feedback_service.submit_feedback(
            db,
            user_id=user.id,
            content=payload.content,
            contact=payload.contact,
        )
        await db.commit()
    except AppException:
        await db.rollback()
        raise
    return ok(FeedbackCreated(feedback_id=fb.id), message="感谢你的反馈")
