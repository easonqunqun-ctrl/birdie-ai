"""V1 路由聚合."""

from fastapi import APIRouter

from app.api.v1 import (
    analyses,
    assets,
    auth,
    chat,
    common,
    events,
    feedback,
    invitations,
    payments,
    pros,
    security,
    shares,
    training,
    users,
    wechat_push,
)

api_router = APIRouter()

api_router.include_router(common.router, tags=["通用"])
# W8 真机回归修复：图片资源同源代理（解决微信小程序真机 <Image> 对 MinIO 9000 端口拒绝）
api_router.include_router(assets.router, tags=["资源代理"])
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(analyses.router, prefix="/analyses", tags=["分析"])
api_router.include_router(chat.router, prefix="/chat", tags=["AI 对话"])
api_router.include_router(payments.router, prefix="/payments", tags=["支付"])
api_router.include_router(wechat_push.router, prefix="/wechat", tags=["微信推送"])
# /me/orders、/me/membership、/me/training-plan、/me/practice-logs 挂 /users/me 下（集中聚合）
api_router.include_router(payments.me_router, prefix="/users/me", tags=["支付"])
# M12-02 球手对比库（公开读端点）；写入仍在 service 层 / 后续 admin 工具
api_router.include_router(pros.router, prefix="/pros", tags=["球手对比库"])
api_router.include_router(training.router, prefix="/training-plan", tags=["训练"])
api_router.include_router(training.me_router, prefix="/users/me", tags=["训练"])
api_router.include_router(training.drills_router, prefix="/drills", tags=["训练"])
api_router.include_router(invitations.me_router, prefix="/users/me", tags=["邀请"])
api_router.include_router(shares.shares_router, prefix="/shares", tags=["分享"])
api_router.include_router(
    shares.analyses_public_router, prefix="/analyses", tags=["分享"]
)
# W8-T5：内容安全（视频首帧合规）+ 通用埋点 / 错误上报
api_router.include_router(security.router, prefix="/security", tags=["内容安全"])
api_router.include_router(events.router, prefix="/events", tags=["埋点"])
# 意见反馈（docs/02 §2.6）
api_router.include_router(feedback.router, prefix="/feedback", tags=["意见反馈"])
