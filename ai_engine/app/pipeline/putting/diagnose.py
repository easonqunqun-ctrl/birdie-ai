"""P2-M7-11 W25 · 推杆问题诊断（rule-based）。

与 full_swing ``diagnose`` 同款 code-based rule（复用 ``DiagnosedIssue`` 数据结构），
但只吃推杆 4 特征 + ``PuttingPhaseResult``。每条 rule 触发返回一个 ``DiagnosedIssue``，
``diagnose_putting`` 统一过滤低置信度 + 按严重度排序返回 TopN。

已落地 5 条（全部基于现有 4 特征，可测可上线）：
| type                       | 触发（主）                              | 依据特征 |
|----------------------------|----------------------------------------|---------|
| putting_unstable_pendulum  | pendulum_stability > 2×ideal_max       | 钟摆稳定度 |
| putting_head_moved         | head_stability > 2×ideal_max           | 头部稳定度 |
| putting_face_open          | face_alignment > 8°                     | 杆面对准 |
| putting_rushed_tempo       | tempo_ratio < 1.5（前推过急/戳击）       | 节奏比 |
| putting_slow_tempo         | tempo_ratio > 3.5（回摆拖沓/减速）       | 节奏比 |

**待补（kickoff §3.5 草案剩余项）**：杆头抬起 / 手腕翻折 / 回摆过短 / 减速击球 / 瞄准偏移
等需要杆头追踪（M7-09）或额外手腕角序列特征，登记 wait-for-triggers，W-later 落地。
"""

from __future__ import annotations

import logging

from app.pipeline.diagnose import DiagnosedIssue
from app.pipeline.putting.constants import putting_feature_meta
from app.pipeline.putting.phases import PuttingPhaseResult

log = logging.getLogger("ai_engine.putting.diagnose")

MIN_DISPLAY_CONFIDENCE = 0.6
MAX_ISSUES = 5

# 推杆 issue 中文名
PUTTING_ISSUE_NAMES: dict[str, str] = {
    "putting_unstable_pendulum": "钟摆不稳",
    "putting_head_moved": "头部移动",
    "putting_face_open": "杆面不正",
    "putting_rushed_tempo": "推击过急",
    "putting_slow_tempo": "节奏拖沓",
}


def _severity(deviation: float, low: float = 0.3, high: float = 0.8) -> str:
    if deviation >= high:
        return "high"
    if deviation >= low:
        return "medium"
    return "low"


def _frame_to_time(frame: int, fps: float) -> float | None:
    return round(frame / fps, 2) if fps > 0 else None


def _rule_unstable_pendulum(
    feat: dict[str, float], phases: PuttingPhaseResult
) -> DiagnosedIssue | None:
    val = feat["pendulum_stability"]
    ideal_max = putting_feature_meta("pendulum_stability")["ideal_max"]
    trigger = ideal_max * 2
    if val <= trigger:
        return None
    dev = (val - trigger) / max(ideal_max, 1e-9)
    return DiagnosedIssue(
        type="putting_unstable_pendulum",
        name=PUTTING_ISSUE_NAMES["putting_unstable_pendulum"],
        severity=_severity(dev),
        description=(
            "推杆过程中双肩（钟摆轴）晃动偏大，破坏了肩部主导的钟摆节奏，"
            "建议固定下半身、用肩部带动推杆。"
        ),
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"pendulum_stability": val, "ideal_max": ideal_max},
    )


def _rule_head_moved(
    feat: dict[str, float], phases: PuttingPhaseResult
) -> DiagnosedIssue | None:
    val = feat["head_stability"]
    ideal_max = putting_feature_meta("head_stability")["ideal_max"]
    trigger = ideal_max * 2
    if val <= trigger:
        return None
    dev = (val - trigger) / max(ideal_max, 1e-9)
    return DiagnosedIssue(
        type="putting_head_moved",
        name=PUTTING_ISSUE_NAMES["putting_head_moved"],
        severity=_severity(dev),
        description=(
            "击球前后头部移动明显，容易带动肩线和击球方向偏移，"
            "建议击球后保持头部静止、听声音再抬头看球。"
        ),
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"head_stability": val, "ideal_max": ideal_max},
    )


def _rule_face_open(
    feat: dict[str, float], phases: PuttingPhaseResult
) -> DiagnosedIssue | None:
    val = feat["face_alignment"]
    trigger = 8.0  # ideal_max=5°，留 3° 缓冲再判异常
    if val <= trigger:
        return None
    dev = (val - trigger) / 8.0
    return DiagnosedIssue(
        type="putting_face_open",
        name=PUTTING_ISSUE_NAMES["putting_face_open"],
        severity=_severity(dev),
        description=(
            f"击球瞬间杆面（以握把线近似）偏离方正约 {val:.0f}°，杆面不正会直接推偏方向，"
            "建议握把放松、用肩部钟摆保持杆面方正穿过球。"
        ),
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"face_alignment": val},
    )


def _rule_rushed_tempo(
    feat: dict[str, float], phases: PuttingPhaseResult
) -> DiagnosedIssue | None:
    val = feat["tempo_ratio"]
    if val >= 1.5:
        return None
    dev = (1.5 - val) / 0.8
    return DiagnosedIssue(
        type="putting_rushed_tempo",
        name=PUTTING_ISSUE_NAMES["putting_rushed_tempo"],
        severity=_severity(dev),
        description=(
            f"回摆与前推时长比仅 {val:.2f}（理想约 2.0-2.5），前推偏急像「戳击」，"
            "建议放慢前推、让回摆稍长形成稳定钟摆。"
        ),
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"tempo_ratio": val},
    )


def _rule_slow_tempo(
    feat: dict[str, float], phases: PuttingPhaseResult
) -> DiagnosedIssue | None:
    val = feat["tempo_ratio"]
    if val <= 3.5:
        return None
    dev = (val - 3.5) / 1.5
    return DiagnosedIssue(
        type="putting_slow_tempo",
        name=PUTTING_ISSUE_NAMES["putting_slow_tempo"],
        severity=_severity(dev),
        description=(
            f"回摆与前推时长比高达 {val:.2f}（理想约 2.0-2.5），回摆过长、前推拖沓易减速，"
            "建议缩短回摆幅度，保持加速通过球。"
        ),
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"tempo_ratio": val},
    )


_RULES = [
    _rule_unstable_pendulum,
    _rule_head_moved,
    _rule_face_open,
    _rule_rushed_tempo,
    _rule_slow_tempo,
]


def diagnose_putting(
    features: dict[str, float],
    phases: PuttingPhaseResult,
    *,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
) -> list[DiagnosedIssue]:
    """跑所有推杆 rule，过滤低置信度，按严重度→置信度排序返回 TopN。"""
    issues: list[DiagnosedIssue] = []
    for rule in _RULES:
        try:
            res = rule(features, phases)
        except Exception as exc:  # pragma: no cover
            log.warning("putting_rule_error", extra={"rule": rule.__name__, "error": str(exc)})
            continue
        if res is None or res.confidence < min_confidence:
            continue
        issues.append(res)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order[x.severity], -x.confidence))
    return issues[:max_issues]
