"""P2-M7-12 · 切杆评分。"""

from __future__ import annotations

from app.pipeline.scoring import score_feature
from app.pipeline.chipping.constants import (
    CHIPPING_FEATURE_WEIGHTS,
    CHIPPING_FEATURES,
    CHIPPING_PHASE_FEATURE_MAP,
    CHIPPING_PHASE_ORDER,
    ChippingFeatureMeta,
    chipping_feature_meta,
)


def score_chipping_feature(value: float, meta: ChippingFeatureMeta) -> int:
    if meta.get("direct_score"):
        return int(round(max(0.0, min(100.0, value))))
    return score_feature(
        value, meta["ideal_min"], meta["ideal_max"], meta["tolerance"]
    )


def score_chipping_features(features: dict[str, float]) -> dict[str, int]:
    out: dict[str, int] = {}
    for meta in CHIPPING_FEATURES:
        name = meta["name"]
        out[name] = score_chipping_feature(features[name], meta) if name in features else 0
    return out


def score_chipping_overall(feature_scores: dict[str, int]) -> int:
    total = sum(feature_scores.get(n, 0) * w for n, w in CHIPPING_FEATURE_WEIGHTS.items())
    return int(round(total))


def score_chipping_phases(feature_scores: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for phase in CHIPPING_PHASE_ORDER:
        feats = CHIPPING_PHASE_FEATURE_MAP[phase]
        wsum = sum(CHIPPING_FEATURE_WEIGHTS[f] for f in feats)
        if wsum <= 0:
            out[phase] = 0
            continue
        s = sum(feature_scores.get(f, 0) * CHIPPING_FEATURE_WEIGHTS[f] for f in feats)
        out[phase] = int(round(s / wsum))
    return out


def score_chipping(features: dict[str, float]) -> dict:
    feature_scores = score_chipping_features(features)
    return {
        "overall": score_chipping_overall(feature_scores),
        "features": feature_scores,
        "phases": score_chipping_phases(feature_scores),
    }


_known = {f["name"] for f in CHIPPING_FEATURES}
for _feats in CHIPPING_PHASE_FEATURE_MAP.values():
    for _f in _feats:
        chipping_feature_meta(_f)
        assert _f in _known
