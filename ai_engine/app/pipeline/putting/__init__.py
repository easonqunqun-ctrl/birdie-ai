"""P2-M7-11 · 推杆 mode 独立 pipeline 子包。

W22：常量 + 阶段数据结构骨架 + 4 个专属特征。
W23：``phases.segment_putting_phases`` 4 阶段分割本体。
W24：``scoring.score_putting`` 推杆评分（overall + per-feature + per-phase）。
W25：``diagnose.diagnose_putting`` 5 条 rule + main `mode=putting` 路由 + 50123。
     编排入口 ``pipeline.run_putting_analysis`` 走函数级 import（依赖重，避免拖累子包导入）。

真源：``docs/release-notes/p2-m7-11-putting-pipeline-kickoff.md``（上游 docs/23 §3.11）。
"""

from __future__ import annotations

from app.pipeline.putting.constants import (
    PUTTING_FEATURE_WEIGHTS,
    PUTTING_FEATURES,
    PUTTING_PHASE_FEATURE_MAP,
    PUTTING_PHASE_LABELS,
    PUTTING_PHASE_ORDER,
    PUTTING_PHASE_WEIGHTS,
    putting_feature_meta,
)
from app.pipeline.putting.diagnose import (
    PUTTING_ISSUE_NAMES,
    diagnose_putting,
)
from app.pipeline.putting.features import extract_putting_features
from app.pipeline.putting.phases import (
    PuttingPhaseInfo,
    PuttingPhaseResult,
    segment_putting_phases,
)
from app.pipeline.putting.scoring import (
    score_putting,
    score_putting_feature,
    score_putting_features,
    score_putting_overall,
    score_putting_phases,
)

__all__ = [
    "PUTTING_FEATURES",
    "PUTTING_FEATURE_WEIGHTS",
    "PUTTING_ISSUE_NAMES",
    "PUTTING_PHASE_FEATURE_MAP",
    "PUTTING_PHASE_LABELS",
    "PUTTING_PHASE_ORDER",
    "PUTTING_PHASE_WEIGHTS",
    "PuttingPhaseInfo",
    "PuttingPhaseResult",
    "diagnose_putting",
    "extract_putting_features",
    "putting_feature_meta",
    "score_putting",
    "score_putting_feature",
    "score_putting_features",
    "score_putting_overall",
    "score_putting_phases",
    "segment_putting_phases",
]
