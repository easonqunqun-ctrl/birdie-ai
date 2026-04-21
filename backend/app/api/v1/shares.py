"""分享相关 API（W7-T5）.

端点：
- `POST /v1/shares/log`            埋点（需登录）
- `GET  /v1/analyses/{id}/public`  脱敏报告（公开可访问，用于分享链接着陆）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.share import (
    PublicReport,
    ShareLogRequest,
    ShareLogResponse,
)
from app.services import share_service

shares_router = APIRouter()
analyses_public_router = APIRouter()


@shares_router.post(
    "/log",
    summary="分享埋点（用户触发分享后调用；不做业务校验只落库）",
    response_model=APIResponse[ShareLogResponse],
)
async def log_share(
    payload: ShareLogRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ShareLogResponse]:
    action = await share_service.log_share(db, user=user, payload=payload)
    await db.commit()
    return ok(
        ShareLogResponse(
            id=action.id,
            share_type=action.share_type,  # type: ignore[arg-type]
            created_at=action.created_at,
        )
    )


@analyses_public_router.get(
    "/{analysis_id}/public",
    summary="公开的脱敏报告（供被分享者访问，无需登录）",
    response_model=APIResponse[PublicReport],
)
async def get_public_report(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PublicReport]:
    report = await share_service.get_public_report(db, analysis_id=analysis_id)
    return ok(report)
