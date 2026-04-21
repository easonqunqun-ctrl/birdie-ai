"""用户相关 Pydantic schema."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GolfLevel = Literal["beginner", "elementary", "intermediate", "advanced"]
WeeklyFreq = Literal["occasional", "once", "frequent", "daily"]
PrimaryGoal = Literal["distance", "accuracy", "short_game", "putting", "consistency"]
MembershipType = Literal["free", "monthly", "yearly", "family"]


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
    stats: UserStats | None = None
    quota: UserQuota | None = None
    created_at: datetime


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
