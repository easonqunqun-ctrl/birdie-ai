"""V1 路由聚合."""

from fastapi import APIRouter

from app.api.v1 import (
    admin_coach,
    analyses,
    assets,
    auth,
    chat,
    coach_annotations,
    coach_courses,
    coach_profile,
    coach_recap,
    coach_spectator,
    coach_students,
    coach_tasks,
    common,
    course_certificates,
    courses,
    events,
    feedback,
    invitations,
    lessons,
    meetup_events,
    meetup_feedbacks,
    meetup_responses,
    meetup_safety,
    meetups,
    payments,
    pro_favorites,
    pros,
    security,
    shares,
    training,
    users,
    venues,
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
# M11-02 课程体系（学习路径读端点）；写入仍在 service 层 / 后续 admin 工具
api_router.include_router(courses.router, prefix="/courses", tags=["课程"])
api_router.include_router(
    course_certificates.router, prefix="/users/me", tags=["课程"]
)
api_router.include_router(
    coach_courses.router, prefix="/users/me/coach/courses", tags=["课程"]
)
api_router.include_router(coach_annotations.router, prefix="/coach", tags=["教练"])
api_router.include_router(coach_profile.router, prefix="/coach", tags=["教练"])
api_router.include_router(coach_spectator.router, prefix="/coach", tags=["教练"])
api_router.include_router(coach_students.router, prefix="/coach", tags=["教练"])
api_router.include_router(coach_tasks.router, prefix="/coach", tags=["教练"])
api_router.include_router(coach_recap.router, prefix="/coach", tags=["教练"])
api_router.include_router(admin_coach.router, prefix="/admin", tags=["管理"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["课程"])
# M12-02 球手对比库（公开读端点）；写入仍在 service 层 / 后续 admin 工具
api_router.include_router(pros.router, prefix="/pros", tags=["球手对比库"])
api_router.include_router(pro_favorites.router, prefix="/users/me", tags=["球手对比库"])
# M13-02 球场 nearby 搜索
api_router.include_router(venues.router, prefix="/venues", tags=["约球"])
# M13-03 约球邀请创建 / 撤回 / 列表
api_router.include_router(meetups.router, prefix="/meetups", tags=["约球"])
api_router.include_router(meetup_feedbacks.router, prefix="/meetups", tags=["约球"])
api_router.include_router(meetup_events.router, prefix="/meetups", tags=["约球"])
api_router.include_router(meetup_safety.router, prefix="/meetups", tags=["约球"])
api_router.include_router(meetup_feedbacks.me_router, prefix="/users/me", tags=["约球"])
api_router.include_router(meetups.me_router, prefix="/users/me", tags=["约球"])
# M13-04 约球邀请 accept / decline
api_router.include_router(meetup_responses.router, prefix="/meetups", tags=["约球"])
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
