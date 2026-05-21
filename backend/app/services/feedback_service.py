"""意见反馈服务（docs/02 §2.6）.

反垃圾策略：
- 60 秒内同一用户重复提交直接 429（`TooManyRequests`），不写表
- 不限制日总量（产品现阶段反馈量小）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, TooManyRequestsError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.feedback import Feedback

logger = get_logger("feedback")

_RATE_LIMIT_WINDOW_SECONDS = 60


async def submit_feedback(
    db: AsyncSession,
    *,
    user_id: str,
    content: str,
    contact: str | None,
) -> Feedback:
    """记录一条反馈；60 秒节流。"""

    normalized = content.strip()
    if not normalized:
        raise BadRequestError(code=40001, message="反馈内容不能为空")

    # 服务层硬截断（DB CheckConstraint 也兜底）
    if len(normalized) > 500:
        normalized = normalized[:500]

    cleaned_contact = (contact or "").strip() or None
    if cleaned_contact and len(cleaned_contact) > 128:
        cleaned_contact = cleaned_contact[:128]

    cutoff = datetime.now(UTC) - timedelta(seconds=_RATE_LIMIT_WINDOW_SECONDS)
    recent_q = await db.execute(
        select(Feedback.id)
        .where(Feedback.user_id == user_id)
        .where(Feedback.created_at >= cutoff)
        .limit(1)
    )
    if recent_q.scalar_one_or_none() is not None:
        raise TooManyRequestsError(message="反馈太频繁，请稍后再试")

    fb = Feedback(
        id=new_id("fb"),
        user_id=user_id,
        content=normalized,
        contact=cleaned_contact,
    )
    db.add(fb)
    await db.flush()
    logger.info(
        "feedback_created",
        feedback_id=fb.id,
        user_id=user_id,
        content_len=len(normalized),
        has_contact=bool(cleaned_contact),
    )
    return fb
