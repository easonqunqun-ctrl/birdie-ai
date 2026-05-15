"""分享服务（W7-T5）.

两个核心职责：

1. **埋点**（`log_share`）：把用户的分享动作落到 `share_actions`。
   - 不做配额/奖励扣减（W7 不上分享奖励，字段留着 W8 运营配置）
   - 不强校验 target_id 的存在性：埋点不应让 UI 卡在网络错；拿不到 analysis 也先记下来

2. **公开报告**（`get_public_report`）：
   - 不校验调用者身份（接口本身可以是 `@router.get` 不带 auth）
   - 但对 `is_sample=True` / 分析未完成 / 不存在 → 404
   - 脱敏规则见 `schemas/share.py::PublicReport` 的 docstring
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.share import ShareAction
from app.models.user import User
from app.schemas.analysis import score_level
from app.schemas.share import PublicReport, PublicReportIssue, ShareLogRequest
from app.services.analysis_service import to_proxy_image_url
from app.services.invitation_service import mask_nickname


# ============================================================
# 埋点
# ============================================================
async def log_share(
    db: AsyncSession, *, user: User, payload: ShareLogRequest
) -> ShareAction:
    """插入一条 share_actions 记录。目前不做去重（一次触发分享就记一次，用于漏斗统计）。"""
    action = ShareAction(
        id=new_id("sha"),
        user_id=user.id,
        share_type=payload.share_type,
        target_id=payload.target_id,
        bonus_granted=False,
    )
    db.add(action)
    await db.flush()
    return action


# ============================================================
# 公开报告
# ============================================================
async def get_public_report(
    db: AsyncSession, *, analysis_id: str
) -> PublicReport:
    """被分享者点开分享链接 → 拿到的脱敏报告。

    校验链条：
    1. 分析存在（否则 404）
    2. 状态 completed（进行中 / 失败的分享没意义 → 404）
    3. 不是 sample（sample 有自己的 /sample 端点，不走分享）
    """
    stmt = (
        select(SwingAnalysis)
        .options(selectinload(SwingAnalysis.issues))
        .where(
            SwingAnalysis.id == analysis_id,
            SwingAnalysis.deleted_at.is_(None),
        )
    )
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if analysis is None:
        raise NotFoundError(code=40402, message="分享的报告不存在或已删除")
    if analysis.status != "completed":
        raise NotFoundError(code=40402, message="分析还未完成，暂时无法分享")
    if analysis.is_sample:
        raise NotFoundError(code=40402, message="示例报告不支持公开分享")

    # 拿分享者昵称 → 脱敏
    owner = await db.get(User, analysis.user_id)
    owner_nickname_masked = mask_nickname(owner.nickname if owner else None)

    # 只返回 severity=high/medium 的前 3 个问题（kakadbrush 公开版）
    issue_rows = sorted(analysis.issues, key=lambda x: x.sort_order)
    public_issues = [
        PublicReportIssue(name=it.name, severity=it.severity)  # type: ignore[arg-type]
        for it in issue_rows
        if it.severity in ("high", "medium")
    ][:3]

    return PublicReport(
        id=analysis.id,
        overall_score=analysis.overall_score,
        score_level=score_level(analysis.overall_score),
        thumbnail_url=to_proxy_image_url(analysis.thumbnail_url),
        camera_angle=analysis.camera_angle,
        club_type=analysis.club_type,
        issues=public_issues,
        issues_total=len(issue_rows),
        analyzed_at=analysis.analyzed_at,
        owner_nickname_masked=owner_nickname_masked,
    )
