"""用户相关接口."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.user import User
from app.models.user_profile_v2 import MAX_CLUBS_PER_USER
from app.schemas.analysis import AnalysisProgressResponse
from app.schemas.base import APIResponse, ok
from app.schemas.user import (
    AccountDeletionRequest,
    OnboardingRequest,
    UserQuota,
    UserResponse,
    UserUpdateRequest,
)
from app.schemas.user_club import (
    UserClubCreate,
    UserClubListResponse,
    UserClubResponse,
    UserClubUpdate,
)
from app.schemas.user_profile_v2 import (
    CoachConsentRead,
    CoachConsentUpdate,
    UserProfileV2Read,
    UserProfileV2Update,
)
from app.services import (
    account_deletion_service,
    analysis_service,
    quota_service,
    user_clubs_service,
    user_profile_v2_service,
)
from app.services.profile_v2_consent import merged_update_payload
from app.services.user_presenter import build_user_response

router = APIRouter()


def _ensure_profile_v2_enabled() -> None:
    """守门：未启用 PHASE2_PROFILE_V2_ENABLED 直接 404，不暴露端点（kickoff §4.2 + 与 M9-02 / M9-03 共用）."""
    if not settings.PHASE2_PROFILE_V2_ENABLED:
        raise NotFoundError(code=40404, message="二期画像功能未开放")


@router.get(
    "/me",
    summary="获取当前用户信息",
    response_model=APIResponse[UserResponse],
)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a_quota = await quota_service.get_or_create_analysis_quota(db, user)
    c_quota = await quota_service.get_or_create_chat_quota(db, user)
    await db.commit()

    resp = build_user_response(user)
    # W8-T3：会员 / QUOTA_MODE=unlimited 都走 -1 表示无限。
    #   前端约定：值 < 0 显示"无限"，>= 0 显示具体数字。
    resp.quota = UserQuota(
        analysis_remaining=quota_service.analysis_remaining(a_quota),
        analysis_total=(
            a_quota.total + a_quota.bonus
            if a_quota.total >= 0
            else quota_service.UNLIMITED_REMAINING
        ),
        analysis_reset_at=quota_service.next_month_reset_iso(),
        chat_remaining_today=quota_service.chat_remaining(c_quota),
        chat_total_today=(
            c_quota.total
            if c_quota.total >= 0
            else quota_service.UNLIMITED_REMAINING
        ),
    )
    return ok(resp)


@router.post(
    "/me/onboarding",
    summary="完成新用户引导",
    response_model=APIResponse[UserResponse],
)
async def complete_onboarding(
    payload: OnboardingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.golf_level = payload.golf_level
    user.primary_goals = list(payload.primary_goals)
    user.weekly_practice_frequency = payload.weekly_practice_frequency
    user.onboarding_completed = True
    await db.commit()
    await db.refresh(user)
    return ok(build_user_response(user, include_stats=False))


@router.patch(
    "/me",
    summary="更新当前用户信息",
    response_model=APIResponse[UserResponse],
)
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_dict = payload.model_dump(exclude_unset=True)
    # 语义守门：PATCH /me 仅允许把 onboarding_completed 从 false 置为 true（"跳过"入口），
    # 不允许通过该接口反向置 false（那应由专门的重置/注销逻辑承担）。
    if update_dict.get("onboarding_completed") is False:
        raise BadRequestError(code=40010, message="不允许将 onboarding_completed 置为 false")
    for k, v in update_dict.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return ok(build_user_response(user))


@router.get(
    "/me/analysis-progress",
    summary="挥杆分析得分时间序列（进步曲线数据源）",
    response_model=APIResponse[AnalysisProgressResponse],
)
async def get_analysis_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    window_days: int | None = Query(
        default=None,
        ge=0,
        le=3660,
        description="仅取最近 N 天的得分点；不传或 0 表示不按天截断（仍受服务端 max_points 限制）",
    ),
):
    wd = window_days if window_days and window_days > 0 else None
    data = await analysis_service.get_user_analysis_progress(db, user, window_days=wd)
    return ok(data)


@router.post(
    "/me/account-deletion",
    summary="申请注销账号（7 天冷静期，MVP §3.4）",
    response_model=APIResponse[UserResponse],
)
async def request_account_deletion(
    payload: AccountDeletionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await account_deletion_service.request_account_deletion(
        db, user, confirm_text=payload.confirm_text
    )
    await db.commit()
    await db.refresh(user)
    return ok(build_user_response(user))


@router.post(
    "/me/account-deletion/cancel",
    summary="取消注销申请",
    response_model=APIResponse[UserResponse],
)
async def cancel_account_deletion(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await account_deletion_service.cancel_account_deletion(db, user)
    await db.commit()
    await db.refresh(user)
    return ok(build_user_response(user))


# ==================== P2-M9-02 装备清单（依赖 M9-01 user_clubs 表） ====================


@router.get(
    "/me/clubs",
    summary="获取我的装备清单（P2-M9-02）",
    response_model=APIResponse[UserClubListResponse],
)
async def list_my_clubs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    items = await user_clubs_service.list_clubs(db, user)
    total = len(items)
    return ok(
        UserClubListResponse(
            items=[UserClubResponse.model_validate(c) for c in items],
            total=total,
            max_clubs=MAX_CLUBS_PER_USER,
            remaining=max(0, MAX_CLUBS_PER_USER - total),
        )
    )


@router.post(
    "/me/clubs",
    summary="新增球杆（14 支上限）",
    response_model=APIResponse[UserClubResponse],
)
async def create_my_club(
    payload: UserClubCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    club = await user_clubs_service.add_club(db, user, payload)
    await db.commit()
    await db.refresh(club)
    return ok(UserClubResponse.model_validate(club))


@router.put(
    "/me/clubs/{club_id}",
    summary="更新球杆信息",
    response_model=APIResponse[UserClubResponse],
)
async def update_my_club(
    club_id: str,
    payload: UserClubUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    club = await user_clubs_service.update_club(db, user, club_id, payload)
    await db.commit()
    await db.refresh(club)
    return ok(UserClubResponse.model_validate(club))


@router.delete(
    "/me/clubs/{club_id}",
    summary="删除球杆（不影响 swing_analyses 历史报告）",
    response_model=APIResponse[dict],
)
async def delete_my_club(
    club_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    await user_clubs_service.delete_club(db, user, club_id)
    await db.commit()
    return ok({"id": club_id, "deleted": True})


# ==================== P2-M9-03 onboarding 2.0（profile-v2 PATCH 语义） ====================


@router.get(
    "/me/profile-v2",
    summary="获取画像 2.0（P2-M9-03）",
    response_model=APIResponse[UserProfileV2Read],
)
async def get_my_profile_v2(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    profile = await user_profile_v2_service.get_profile(db, user.id)
    if profile is None:
        # 老用户没填过 → 返回空 schema（前端可直接渲染表单初值）
        return ok(UserProfileV2Read(user_id=user.id))
    payload = user_profile_v2_service.project_for_self(profile)
    return ok(UserProfileV2Read.model_validate(payload))


@router.put(
    "/me/profile-v2",
    summary="更新画像 2.0（PATCH 语义，consent 自动推断）",
    response_model=APIResponse[UserProfileV2Read],
)
async def update_my_profile_v2(
    payload: UserProfileV2Update,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_profile_v2_enabled()
    existing = await user_profile_v2_service.get_profile(db, user.id)
    existing_payload = existing.privacy_payload if existing else None
    # M9-03 helper：客户端只传字段值，consent 自动推断
    merged = merged_update_payload(payload, existing_payload)
    profile = await user_profile_v2_service.upsert_profile(
        db, user_id=user.id, payload=merged
    )
    await db.commit()
    await db.refresh(profile)
    response_payload = user_profile_v2_service.project_for_self(profile)
    return ok(UserProfileV2Read.model_validate(response_payload))


# ==================== P2-M9-06 教练可见性 consent（独立原子端点） ====================


@router.get(
    "/me/profile-v2/coach-consent",
    summary="读取教练可见性 consent + 当前白名单（M9-06）",
    response_model=APIResponse[CoachConsentRead],
)
async def get_my_coach_consent(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """读取当前用户的「教练可见性总开关 + 字段列表 + 可选白名单」.

    返回 ``allowed_fields`` 让 UI 渲染勾选项，避免硬编码白名单。
    """

    _ensure_profile_v2_enabled()
    profile = await user_profile_v2_service.get_profile(db, user.id)
    view = user_profile_v2_service.coach_consent_view(profile)
    return ok(CoachConsentRead.model_validate(view))


@router.put(
    "/me/profile-v2/coach-consent",
    summary="原子更新教练可见性 consent + 可见字段（M9-06）",
    response_model=APIResponse[CoachConsentRead],
)
async def update_my_coach_consent(
    payload: CoachConsentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """原子更新教练可见性，避免「开关与字段不一致」的中间态.

    服务层保证：
    - ``visible=False`` ⇒ 服务器把字段列表强制清空（PIPL 删除权）
    - ``visible=True``  ⇒ ``fields`` 必须非空，否则 40022
    """

    _ensure_profile_v2_enabled()
    profile = await user_profile_v2_service.update_coach_consent(
        db, user_id=user.id, visible=payload.visible, fields=payload.fields
    )
    await db.commit()
    await db.refresh(profile)
    view = user_profile_v2_service.coach_consent_view(profile)
    return ok(CoachConsentRead.model_validate(view))
