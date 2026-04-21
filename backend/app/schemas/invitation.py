"""邀请相关 Pydantic schema (W7-T4)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

InvitationStatus = Literal["registered", "valid"]


class InvitationItem(BaseModel):
    """邀请记录条目（邀请记录页用）。invitee 昵称经脱敏处理."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    invitee_id: str
    invitee_nickname_masked: str  # `*** + 最后一字`
    status: InvitationStatus
    bonus_granted: bool
    bonus_granted_at: datetime | None
    created_at: datetime


class InviteInfo(BaseModel):
    """我的邀请概览（我的邀请页顶部卡片用）."""

    invite_code: str
    total_invited: int  # 所有被邀请者数量
    valid_count: int  # status=valid 数量
    next_reward_at: int  # 下一次奖励门槛，如 5
    days_to_next_reward: int  # 还差几个 valid 到下一档（可能 >0）
    total_bonus_days: int  # 已发放的总奖励天数
