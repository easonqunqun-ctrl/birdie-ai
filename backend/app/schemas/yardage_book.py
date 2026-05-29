"""M10-03 · yardage book Pydantic schema."""

from typing import Literal

from pydantic import BaseModel, Field


class YardageBookClubItem(BaseModel):
    club_id: str
    club_type: str
    nickname: str | None = None
    my_yards: int | None = Field(default=None, description="自填或反推均值（码）")
    std_yards: float | None = Field(default=None, description="反推标准差；自填时为 null")
    sample_count: int = 0
    source: Literal["self", "inferred", "none"] = "none"


class YardageBookResponse(BaseModel):
    clubs: list[YardageBookClubItem]


class YardageBookUpdateItem(BaseModel):
    club_id: str
    self_yardage_m: int | None = Field(default=None, ge=0, le=400)


class YardageBookUpdateRequest(BaseModel):
    clubs: list[YardageBookUpdateItem] = Field(default_factory=list)
