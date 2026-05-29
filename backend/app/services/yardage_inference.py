"""M10-03 · 从挥杆分析历史反推每杆码数."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import SwingAnalysis

MIN_INFERENCE_SAMPLES = 5
MAX_INFERENCE_SAMPLES = 50


@dataclass(frozen=True)
class YardageInference:
    avg: int
    std: float
    sample_count: int


async def infer_yardage_for_club(
    db: AsyncSession,
    *,
    user_id: str,
    club_type: str,
) -> YardageInference | None:
    """按 club_type 聚合 target_yardage；样本 <5 返回 None。"""
    stmt = (
        select(SwingAnalysis.target_yardage)
        .where(
            SwingAnalysis.user_id == user_id,
            SwingAnalysis.club_type == club_type,
            SwingAnalysis.status == "completed",
            SwingAnalysis.target_yardage.isnot(None),
            SwingAnalysis.deleted_at.is_(None),
        )
        .order_by(SwingAnalysis.created_at.desc())
        .limit(MAX_INFERENCE_SAMPLES)
    )
    rows = [int(r) for r in (await db.execute(stmt)).scalars().all() if r is not None]
    if len(rows) < MIN_INFERENCE_SAMPLES:
        return None
    avg = round(statistics.mean(rows))
    std = float(statistics.pstdev(rows)) if len(rows) > 1 else 0.0
    return YardageInference(avg=avg, std=std, sample_count=len(rows))
