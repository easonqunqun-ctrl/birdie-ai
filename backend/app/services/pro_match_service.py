"""P2-M12-04 · 「和你最像的」职业球手镜头匹配（启发式 v0.1）.

基于 ``club_type`` 硬过滤 + ``overall_score`` / ``phase_scores`` 相似度 +
``camera_angle`` 加分；Top-N 结果可选写入 ``user_pro_match_history``。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError
from app.core.logging import get_logger
from app.models.analysis import SwingAnalysis
from app.models.pro_library import ProPlayer, ProSwingClip, UserProMatchHistory
from app.services import pro_library_service

logger = get_logger("pro_match")

STANDARD_PHASES: tuple[str, ...] = (
    "setup",
    "takeaway",
    "top",
    "downswing",
    "impact",
    "follow_through",
)

CAMERA_ANGLE_BONUS = 15.0
OVERALL_WEIGHT = 0.45
PHASE_PROXY_WEIGHT = 0.35
FEATURE_WEIGHT = 0.20


@dataclass(frozen=True)
class AnalysisMatchInput:
    club_type: str
    camera_angle: str
    overall_score: int | None
    phase_scores: dict | None


@dataclass(frozen=True)
class ProMatchCandidate:
    clip: ProSwingClip
    player: ProPlayer
    match_score: Decimal
    match_details: dict


def _quantize_score(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _phase_score_value(raw: object) -> float | None:
    """V1 报告 phase_scores 为数值；V2 为 ``{label, score, is_weakest}`` 对象。"""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        score = raw.get("score")
        if isinstance(score, (int, float)):
            return float(score)
    return None


def _phase_average(phase_scores: dict | None) -> float | None:
    if not phase_scores:
        return None
    vals = [
        v
        for k in STANDARD_PHASES
        if k in phase_scores and (v := _phase_score_value(phase_scores[k])) is not None
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _overall_similarity(user_score: int | None, clip_score: int | None) -> float | None:
    if user_score is None or clip_score is None:
        return None
    diff = abs(int(user_score) - int(clip_score))
    return max(0.0, 100.0 - diff * 1.5)


def _phase_proxy_similarity(
    user_avg: float | None, clip_score: int | None
) -> float | None:
    if user_avg is None:
        return None
    target = float(clip_score) if clip_score is not None else user_avg
    return max(0.0, 100.0 - abs(user_avg - target) * 1.2)


def _feature_snapshot_similarity(
    user_avg: float | None, features_snapshot: dict | None
) -> float | None:
    if not features_snapshot or user_avg is None:
        return None
    nums = [float(v) for v in features_snapshot.values() if isinstance(v, (int, float))]
    if not nums:
        return None
    clip_avg = sum(nums) / len(nums)
    # features 量纲可能与 0-100 分不同；归一化到 0-100 尺度再比
    if clip_avg <= 10:
        clip_avg *= 10
    elif clip_avg > 100:
        clip_avg = min(100.0, clip_avg / 10)
    return max(0.0, 100.0 - abs(user_avg - clip_avg) * 0.8)


def score_clip_match(
    analysis: AnalysisMatchInput, clip: ProSwingClip
) -> tuple[float, dict]:
    """返回 (0-100 匹配分, 细节 dict) — 纯函数，便于单测."""

    parts: list[tuple[str, float, float]] = []
    details: dict = {}

    overall_sim = _overall_similarity(analysis.overall_score, clip.overall_score)
    if overall_sim is not None:
        parts.append(("overall", overall_sim, OVERALL_WEIGHT))
        details["overall_diff"] = abs(
            int(analysis.overall_score or 0) - int(clip.overall_score or 0)
        )

    user_avg = _phase_average(analysis.phase_scores)
    phase_sim = _phase_proxy_similarity(user_avg, clip.overall_score)
    if phase_sim is not None:
        parts.append(("phase_proxy", phase_sim, PHASE_PROXY_WEIGHT))
        if user_avg is not None:
            details["user_phase_avg"] = round(user_avg, 2)

    feat_sim = _feature_snapshot_similarity(user_avg, clip.features_snapshot)
    if feat_sim is not None:
        parts.append(("features", feat_sim, FEATURE_WEIGHT))

    if parts:
        total_w = sum(weight for _, _, weight in parts)
        base = sum(score * weight for _, score, weight in parts) / total_w
        details["components"] = {
            name: round(score, 2) for name, score, _ in parts
        }
    else:
        base = 50.0
        details["components"] = {"fallback": 50.0}

    camera_match = analysis.camera_angle == clip.camera_angle
    details["camera_angle_match"] = camera_match
    final = min(100.0, base + (CAMERA_ANGLE_BONUS if camera_match else 0.0))
    details["base_score"] = round(base, 2)
    return final, details


def rank_clip_matches(
    analysis: AnalysisMatchInput,
    candidates: list[tuple[ProSwingClip, ProPlayer]],
    *,
    limit: int = 5,
) -> list[ProMatchCandidate]:
    scored: list[ProMatchCandidate] = []
    for clip, player in candidates:
        raw, details = score_clip_match(analysis, clip)
        scored.append(
            ProMatchCandidate(
                clip=clip,
                player=player,
                match_score=_quantize_score(raw),
                match_details=details,
            )
        )
    scored.sort(
        key=lambda item: (item.match_score, item.clip.overall_score or 0),
        reverse=True,
    )
    return scored[:limit]


async def _list_matchable_clips(
    db: AsyncSession, *, club_type: str
) -> list[tuple[ProSwingClip, ProPlayer]]:
    rows = await db.execute(
        select(ProSwingClip, ProPlayer)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(
            ProSwingClip.is_published.is_(True),
            ProSwingClip.club_type == club_type,
            ProPlayer.is_active.is_(True),
        )
        .order_by(ProSwingClip.created_at.desc())
    )
    return list(rows.all())


def _analysis_input(analysis: SwingAnalysis) -> AnalysisMatchInput:
    return AnalysisMatchInput(
        club_type=analysis.club_type,
        camera_angle=analysis.camera_angle,
        overall_score=analysis.overall_score,
        phase_scores=dict(analysis.phase_scores or {}),
    )


async def match_analysis_to_pro_clips(
    db: AsyncSession,
    *,
    user_id: str,
    analysis: SwingAnalysis,
    limit: int = 5,
    record: bool = True,
) -> tuple[list[ProMatchCandidate], UserProMatchHistory | None]:
    if analysis.user_id != user_id:
        raise ForbiddenError(code=40301, message="无权访问该分析")
    if analysis.is_sample:
        raise BadRequestError(code=40093, message="示例分析报告不可用于球手匹配")
    if analysis.status != "completed":
        raise BadRequestError(code=40001, message="仅已完成分析可匹配职业镜头")
    if analysis.overall_score is None:
        raise BadRequestError(code=40001, message="分析报告缺少综合分，无法匹配")

    candidates = await _list_matchable_clips(db, club_type=analysis.club_type)
    ranked = rank_clip_matches(_analysis_input(analysis), candidates, limit=limit)

    history: UserProMatchHistory | None = None
    if record and ranked:
        top = ranked[0]
        history = await pro_library_service.record_match(
            db,
            user_id=user_id,
            analysis_id=analysis.id,
            matched_clip_id=top.clip.id,
            match_score=top.match_score,
            match_details=top.match_details,
        )
        logger.info(
            "pro_match_completed",
            analysis_id=analysis.id,
            clip_id=top.clip.id,
            score=str(top.match_score),
        )
    return ranked, history


__all__ = [
    "AnalysisMatchInput",
    "ProMatchCandidate",
    "match_analysis_to_pro_clips",
    "rank_clip_matches",
    "score_clip_match",
]
