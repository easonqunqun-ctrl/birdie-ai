"""用户相关 Pydantic schema."""

import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coach_profile import CoachProfileBrief

GolfLevel = Literal["beginner", "elementary", "intermediate", "advanced"]
WeeklyFreq = Literal["occasional", "once", "frequent", "daily"]
PrimaryGoal = Literal["distance", "accuracy", "short_game", "putting", "consistency"]
MembershipType = Literal["free", "monthly", "yearly", "family"]

_LOG = logging.getLogger(__name__)
_VALID_GOLF_LEVELS = frozenset({"beginner", "elementary", "intermediate", "advanced"})
_VALID_WEEKLY_FREQ = frozenset({"occasional", "once", "frequent", "daily"})
_VALID_MEMBERSHIP = frozenset({"free", "monthly", "yearly", "family"})


def sanitize_primary_goals_for_response(raw: object) -> list[str]:
    """JSONB `primary_goals` 若为 dict / 非标量元素，整块丢弃或过滤，避免 DTO ValidationError."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, (int, float, bool)):
            out.append(str(x))
    return out[:5]


def sanitize_optional_golf_level(raw: str | None) -> GolfLevel | None:
    if raw is None or raw not in _VALID_GOLF_LEVELS:
        if raw is not None and raw not in _VALID_GOLF_LEVELS:
            _LOG.warning("invalid_user_golf_level_cleared", extra={"raw": raw})
        return None
    return raw  # type: ignore[return-value]


def sanitize_optional_weekly_freq(raw: str | None) -> WeeklyFreq | None:
    if raw is None or raw not in _VALID_WEEKLY_FREQ:
        if raw is not None and raw not in _VALID_WEEKLY_FREQ:
            _LOG.warning("invalid_user_weekly_frequency_cleared", extra={"raw": raw})
        return None
    return raw  # type: ignore[return-value]


def sanitize_membership_type_for_response(raw: str | None) -> MembershipType:
    v = raw or "free"
    if v in _VALID_MEMBERSHIP:
        return v  # type: ignore[return-value]
    _LOG.warning("invalid_user_membership_type_coerced", extra={"raw": raw})
    return "free"


class UserStats(BaseModel):
    total_analyses: int = 0
    total_practices: int = 0
    streak_days: int = 0
    best_score: int = 0
    score_improvement: int = 0


class UserQuota(BaseModel):
    analysis_remaining: int
    analysis_total: int
    analysis_reset_at: datetime | None = None
    chat_remaining_today: int
    chat_total_today: int


class PromoFreeStatus(BaseModel):
    """公测免费促销（``PROMO_FREE_UNTIL``）；见 ``promo_service``."""

    active: bool = False
    until: str | None = None
    message: str | None = None


class UserBrief(BaseModel):
    """简化版用户信息（首页等场景用）."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    nickname: str | None
    avatar_url: str | None
    membership_type: MembershipType


class UserResponse(BaseModel):
    """完整用户信息."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    nickname: str | None
    avatar_url: str | None
    golf_level: GolfLevel | None
    primary_goals: list[str] = Field(default_factory=list)
    weekly_practice_frequency: WeeklyFreq | None
    membership_type: MembershipType
    membership_expires_at: datetime | None
    # W7-T1：前端多处需要"是否会员 / 还剩几天"，派生自 membership_type +
    # membership_expires_at；放到顶层避免客户端重复计算时区
    is_member: bool = False
    membership_days_remaining: int = 0
    onboarding_completed: bool
    # O-03：曾完成至少一次非示例分析；为 true 时客户端隐藏示例报告入口
    has_completed_real_analysis: bool = False
    stats: UserStats | None = None
    quota: UserQuota | None = None
    promo_free: PromoFreeStatus | None = None
    created_at: datetime
    # MVP §3.4 注销冷静期：非空表示将于该 UTC 时间后硬删
    account_deletion_scheduled_at: datetime | None = None
    # M12-09：教练批注入口（COACH_COURSE_USER_IDS 白名单 + 灰度开启）
    can_coach_annotate: bool = False
    # M8-01：教练档案摘要（PHASE2_COACH_ENABLED 时由 /users/me 填充）
    coach_profile: CoachProfileBrief | None = None
    is_active_coach: bool = False


class AccountDeletionRequest(BaseModel):
    """须输入大写 `DELETE` 以二次确认。"""

    confirm_text: str = Field(..., min_length=3, max_length=32)


class WechatLoginRequest(BaseModel):
    code: str = Field(..., description="wx.login 获取的临时 code")
    invite_code: str | None = Field(default=None, description="邀请码（可选）")


class WechatLoginResponse(BaseModel):
    token: str
    expires_in: int
    is_new_user: bool
    user: UserResponse


class TokenRefreshResponse(BaseModel):
    token: str
    expires_in: int


class OnboardingRequest(BaseModel):
    golf_level: GolfLevel
    primary_goals: list[PrimaryGoal] = Field(..., min_length=1, max_length=5)
    weekly_practice_frequency: WeeklyFreq


class UserUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=12)
    avatar_url: str | None = None
    golf_level: GolfLevel | None = None
    primary_goals: list[PrimaryGoal] | None = None
    weekly_practice_frequency: WeeklyFreq | None = None
    # 引导流程"跳过"入口会走 PATCH /me 仅置该字段为 true；
    # 不允许通过此接口置 false（语义上"取消完成"应走专门逻辑，当前不开放）。
    onboarding_completed: bool | None = Field(default=None)
