"""P2-M9-02 装备清单 CRUD Pydantic schemas（对齐 docs/02 §11.3 草案 + M9-01 UserClub 模型）.

依赖 M9-01 PR #90 合入：复用 `app.models.user_profile_v2.UserClub` + `MAX_CLUBS_PER_USER=14`。
本 PR 仅扩 schemas + service + API + UI，不动 ORM 模型。

字段约束（与 M9-01 CheckConstraint 对齐）
----------------------------------------
- club_type：与 client/src/types/api.ts `ClubType` 一致（详 P2-M7-05 PR #99）
- nickname：≤40 字（与 ORM column）
- self_yardage_m：0-400（chk_user_clubs_self_yardage_m）
- sort_order：≥0
- is_active：默认 True

错误码（kickoff §4.1）
----------------------
- 40002：参数校验失败（如 self_yardage_m > 400 / nickname > 40）
- 40020：装备清单 14 支上限（自定义业务错误码）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 与 backend/app/schemas/analysis.py ClubType + types/api.ts 对齐
ClubType = Literal[
    "driver",
    "fairway_wood",
    "iron_3",
    "iron_4",
    "iron_5",
    "iron_6",
    "iron_7",
    "iron_8",
    "iron_9",
    "wedge",
    "putter",
    "unknown",
]


class UserClubCreate(BaseModel):
    """POST /v1/users/me/clubs 请求体."""

    club_type: ClubType = Field(..., description="球杆类型（22 种枚举之一）")
    nickname: str | None = Field(default=None, max_length=40, description="自定义昵称")
    self_yardage_m: int | None = Field(
        default=None, ge=0, le=400, description="自评码数（米）"
    )
    is_active: bool = Field(default=True, description="是否启用（默认 True）")
    sort_order: int = Field(default=0, ge=0, description="排序，0 表示首选")


class UserClubUpdate(BaseModel):
    """PUT /v1/users/me/clubs/{id} 请求体（部分字段可选）."""

    club_type: ClubType | None = None
    nickname: str | None = Field(default=None, max_length=40)
    self_yardage_m: int | None = Field(default=None, ge=0, le=400)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class UserClubResponse(BaseModel):
    """GET / POST / PUT 响应体."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_type: ClubType
    nickname: str | None = None
    self_yardage_m: int | None = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class UserClubListResponse(BaseModel):
    """GET /v1/users/me/clubs 响应体（包含 14 支上限信息）."""

    items: list[UserClubResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="当前已有球杆数")
    max_clubs: int = Field(..., ge=0, description="单用户上限（M9-01 MAX_CLUBS_PER_USER）")
    remaining: int = Field(..., ge=0, description="还可添加数 = max_clubs - total")


__all__ = [
    "ClubType",
    "UserClubCreate",
    "UserClubListResponse",
    "UserClubResponse",
    "UserClubUpdate",
]
