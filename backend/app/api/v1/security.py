"""内容安全相关 API（W8-T5）。

端点
----
- `POST /v1/security/media-check` 视频首帧图片合规预检

设计取舍
--------
1. 需要登录：匿名用户没有业务入口能触发到这里（拍摄前必须过 Onboarding）
2. 只接受一张图片（multipart `media` 字段），≤ 1MB
3. 响应体固定：`{ passed: bool, reason?: str }`，前端按 `passed` 决定 abort 或继续
4. 不强制同步阻塞——任何后端 / 微信侧异常，`passed` 保持 `True`（fail open），
   并在 `reason` 里写"审核服务暂不可用"让前端可选是否降级 toast
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.integrations.wechat_security import check_image
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.security import MediaCheckResponse

logger = get_logger("api.security")

router = APIRouter()

MAX_IMAGE_BYTES = 1 * 1024 * 1024  # 微信 img_sec_check 1MB 上限


@router.post(
    "/media-check",
    summary="视频首帧图片合规预检（微信 img_sec_check）",
    response_model=APIResponse[MediaCheckResponse],
)
async def media_check(
    media: UploadFile = File(..., description="视频首帧图，≤ 1MB"),
    scene: str = Form("analysis", description="业务场景标签，便于后台统计"),
    user: User = Depends(get_current_user),
) -> APIResponse[MediaCheckResponse]:
    """上传首帧图片 → 调微信 img_sec_check → 返回是否通过。

    失败语义：
      - `passed=False`：微信明确判定违规（errcode=87014）→ 前端 toast 拒绝
      - `passed=True` + `reason`：审核服务异常，已放过；前端可选择继续/提示
    """
    raw = await media.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"图片超出 {MAX_IMAGE_BYTES // 1024}KB 上限",
        )

    result = await check_image(raw, file_name=media.filename or "thumb.jpg")
    logger.info(
        "media_check_done",
        user_id=user.id,
        scene=scene,
        passed=result.passed,
        errcode=result.errcode,
        size=len(raw),
    )
    return ok(MediaCheckResponse(passed=result.passed, reason=result.reason))
