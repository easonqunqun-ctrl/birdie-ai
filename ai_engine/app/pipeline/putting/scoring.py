"""P2-M7-11 W24 · 推杆评分（kickoff §3.4）。

复用 full_swing ``scoring.score_feature`` 作底层双边带状评分；推杆 3 个稳定度特征是
**单边（越小越好）**，单独处理：value≤ideal_min → 100，ideal_max → 85，超出按
tolerance 线性到 0。tempo_ratio 是双边区间，直接走 ``score_feature``。

输出（kickoff §4）：``{"overall": int, "features": {name:int}, "phases": {phase:int}}``。
overall = 各特征分按 ``PUTTING_FEATURE_WEIGHTS`` 加权（4 特征直接定调，比阶段加权更稳）；
phases 仅供报告分阶段展示（按 ``PUTTING_PHASE_FEATURE_MAP`` 组内归一化加权）。
"""

from __future__ import annotations

from app.pipeline.scoring import score_feature
from app.pipeline.putting.constants import (
    PUTTING_FEATURE_WEIGHTS,
    PUTTING_FEATURES,
    PUTTING_PHASE_FEATURE_MAP,
    PUTTING_PHASE_ORDER,
    PuttingFeatureMeta,
    putting_feature_meta,
)


def score_putting_feature(value: float, meta: PuttingFeatureMeta) -> int:
    """单个推杆特征评分 0-100。单边特征越小越好，双边走 ``score_feature``。"""
    ideal_min, ideal_max = meta["ideal_min"], meta["ideal_max"]
    tol = meta["tolerance"]

    if not meta["lower_is_better"]:
        return score_feature(value, ideal_min, ideal_max, tol)

    # 单边（越小越好）
    if ideal_max <= ideal_min:
        return 85
    if value <= ideal_min:
        return 100
    if value <= ideal_max:
        frac = (value - ideal_min) / (ideal_max - ideal_min)  # [0,1]
        return int(round(100 - 15 * frac))
    width = ideal_max - ideal_min
    deviation = (value - ideal_max) / width
    if deviation > tol:
        return 0
    return int(round(84 * (1 - deviation / tol)))


def score_putting_features(features: dict[str, float]) -> dict[str, int]:
    """逐特征评分；缺失特征记 0 分。"""
    out: dict[str, int] = {}
    for meta in PUTTING_FEATURES:
        name = meta["name"]
        out[name] = score_putting_feature(features[name], meta) if name in features else 0
    return out


def score_putting_overall(feature_scores: dict[str, int]) -> int:
    """综合分 = 各特征分按 PUTTING_FEATURE_WEIGHTS 加权。"""
    total = sum(feature_scores.get(n, 0) * w for n, w in PUTTING_FEATURE_WEIGHTS.items())
    return int(round(total))


def score_putting_phases(feature_scores: dict[str, int]) -> dict[str, int]:
    """阶段分（展示用）= 该阶段贡献特征分在组内按特征权重归一化加权。"""
    out: dict[str, int] = {}
    for phase in PUTTING_PHASE_ORDER:
        feats = PUTTING_PHASE_FEATURE_MAP[phase]
        wsum = sum(PUTTING_FEATURE_WEIGHTS[f] for f in feats)
        if wsum <= 0:
            out[phase] = 0
            continue
        s = sum(feature_scores.get(f, 0) * PUTTING_FEATURE_WEIGHTS[f] for f in feats)
        out[phase] = int(round(s / wsum))
    return out


def score_putting(features: dict[str, float]) -> dict:
    """推杆总评分入口：返回 overall + per-feature + per-phase。"""
    feature_scores = score_putting_features(features)
    return {
        "overall": score_putting_overall(feature_scores),
        "features": feature_scores,
        "phases": score_putting_phases(feature_scores),
    }


# 防御：phase map 引用的特征必须都在 PUTTING_FEATURES 内（typo 早炸）
_known = {f["name"] for f in PUTTING_FEATURES}
for _phase, _feats in PUTTING_PHASE_FEATURE_MAP.items():
    for _f in _feats:
        putting_feature_meta(_f)  # KeyError if unknown
        assert _f in _known
