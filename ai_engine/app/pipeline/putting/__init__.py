"""P2-M7-11 · 推杆 mode 独立 pipeline 子包。

W22 落地：常量（``constants``）+ 阶段数据结构骨架（``phases``）+ 4 个专属特征
（``features``）。phases 分割本体 / scoring / diagnose / main 路由 / 错误码 50123
按 kickoff §6 周计划排 W23-W25。

真源：``docs/release-notes/p2-m7-11-putting-pipeline-kickoff.md``（上游 docs/23 §3.11）。
"""

from __future__ import annotations

from app.pipeline.putting.constants import (
    PUTTING_FEATURE_WEIGHTS,
    PUTTING_FEATURES,
    PUTTING_PHASE_ORDER,
    PUTTING_PHASE_WEIGHTS,
    putting_feature_meta,
)
from app.pipeline.putting.features import extract_putting_features
from app.pipeline.putting.phases import PuttingPhaseInfo, PuttingPhaseResult

__all__ = [
    "PUTTING_FEATURES",
    "PUTTING_FEATURE_WEIGHTS",
    "PUTTING_PHASE_ORDER",
    "PUTTING_PHASE_WEIGHTS",
    "PuttingPhaseInfo",
    "PuttingPhaseResult",
    "extract_putting_features",
    "putting_feature_meta",
]
