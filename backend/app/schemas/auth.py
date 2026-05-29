"""M8-02 · 教练身份切换 schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

AppRoleLiteral = Literal["user", "coach"]


class RoleSwitchRequest(BaseModel):
    role: AppRoleLiteral

    model_config = ConfigDict(extra="forbid")


class RoleSwitchResponse(BaseModel):
    token: str
    expires_in: int
    role: AppRoleLiteral


__all__ = ["AppRoleLiteral", "RoleSwitchRequest", "RoleSwitchResponse"]
