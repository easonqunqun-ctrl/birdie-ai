"""P2-M7-11 W25+W20-A · 推杆问题诊断（rule-based）。

与 full_swing ``diagnose`` 同款 code-based rule（复用 ``DiagnosedIssue`` 数据结构），
但只吃推杆 4 特征 + ``PuttingPhaseResult`` + 可选时序信号（``signals.py``）。

已落地 10 条：
| type                       | 触发（主）                              | 依据 |
|----------------------------|----------------------------------------|------|
| putting_unstable_pendulum  | pendulum_stability > 2×ideal_max       | 4 特征 |
| putting_head_moved         | head_stability > 2×ideal_max           | 4 特征 |
| putting_face_open          | face_alignment > 8°                     | 4 特征 |
| putting_rushed_tempo       | tempo_ratio < 1.5                       | 4 特征 |
| putting_slow_tempo         | tempo_ratio > 3.5                       | 4 特征 |
| putting_wrist_hinge        | wrist_hinge_delta > 8°                  | 时序信号 |
| putting_short_backstroke   | backstroke_amp_ratio < 0.5              | 时序信号 |
| putting_decel_stroke       | decel_speed_ratio < 0.8                 | 时序信号 |
| putting_aim_off            | setup_aim_offset > 5°                   | 时序信号 |
| putting_lift_putter        | putter_lift_norm > 阈值                 | 时序信号（腕代理杆头） |

缺信号（``nan``）时对应 rule 跳过；M7-09 杆追踪到位后可替换 lift 信号。
"""

from __future__ import annotations

import logging
import math

from app.pipeline.diagnose import DiagnosedIssue
from app.pipeline.putting.constants import putting_feature_meta
from app.pipeline.putting.phases import PuttingPhaseResult
from app.pipeline.putting.signals import (
    DECEL_SPEED_RATIO,
    PUTTER_LIFT_NORM,
    SETUP_AIM_OFFSET_DEG,
    SHORT_BACKSTROKE_RATIO,
    WRIST_HINGE_TRIGGER_DEG,
    extract_putting_diagnostic_signals,
)

log = logging.getLogger("ai_engine.putting.diagnose")

MIN_DISPLAY_CONFIDENCE = 0.6
MAX_ISSUES = 8

# 推杆 issue 中文名
PUTTING_ISSUE_NAMES: dict[str, str] = {
    "putting_unstable_pendulum": "钟摆不稳",
    "putting_head_moved": "头部移动",
    "putting_face_open": "杆面不正",
    "putting_rushed_tempo": "推击过急",
    "putting_slow_tempo": "节奏拖沓",
    "putting_wrist_hinge": "手腕翻折",
    "putting_short_backstroke": "回摆过短",
    "putting_decel_stroke": "减速击球",
    "putting_aim_off": "瞄准偏移",
    "putting_lift_putter": "杆头抬起",
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
    feat: dict[str, float], phases: PuttingPhaseResult, _signals: dict[str, float]
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
    feat: dict[str, float], phases: PuttingPhaseResult, _signals: dict[str, float]
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
    feat: dict[str, float], phases: PuttingPhaseResult, _signals: dict[str, float]
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
    feat: dict[str, float], phases: PuttingPhaseResult, _signals: dict[str, float]
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
    feat: dict[str, float], phases: PuttingPhaseResult, _signals: dict[str, float]
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


def _sig_val(signals: dict[str, float], key: str) -> float | None:
    val = signals.get(key, float("nan"))
    if val is None or not math.isfinite(val):
        return None
    return val


def _rule_wrist_hinge(
    _feat: dict[str, float], phases: PuttingPhaseResult, signals: dict[str, float]
) -> DiagnosedIssue | None:
    val = _sig_val(signals, "wrist_hinge_delta_deg")
    if val is None or val <= WRIST_HINGE_TRIGGER_DEG:
        return None
    dev = (val - WRIST_HINGE_TRIGGER_DEG) / WRIST_HINGE_TRIGGER_DEG
    return DiagnosedIssue(
        type="putting_wrist_hinge",
        name=PUTTING_ISSUE_NAMES["putting_wrist_hinge"],
        severity=_severity(dev),
        description=(
            f"推杆过程中手腕角度变化约 {val:.0f}°，手腕过度翻折会破坏杆面稳定，"
            "建议锁腕、用肩部和手臂做钟摆。"
        ),
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"wrist_hinge_delta_deg": val},
    )


def _rule_short_backstroke(
    _feat: dict[str, float], phases: PuttingPhaseResult, signals: dict[str, float]
) -> DiagnosedIssue | None:
    val = _sig_val(signals, "backstroke_amp_ratio")
    if val is None or val >= SHORT_BACKSTROKE_RATIO:
        return None
    dev = (SHORT_BACKSTROKE_RATIO - val) / SHORT_BACKSTROKE_RATIO
    return DiagnosedIssue(
        type="putting_short_backstroke",
        name=PUTTING_ISSUE_NAMES["putting_short_backstroke"],
        severity=_severity(dev),
        description=(
            f"回摆幅度仅为前推的 {val * 100:.0f}%（理想至少约 50%），回摆过短难以形成稳定节奏，"
            "建议适当加长回摆、再加速通过球。"
        ),
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.phases["backstroke"].key_frame, phases.fps),
        metrics={"backstroke_amp_ratio": val},
    )


def _rule_decel_stroke(
    _feat: dict[str, float], phases: PuttingPhaseResult, signals: dict[str, float]
) -> DiagnosedIssue | None:
    val = _sig_val(signals, "decel_speed_ratio")
    if val is None or val >= DECEL_SPEED_RATIO:
        return None
    dev = (DECEL_SPEED_RATIO - val) / DECEL_SPEED_RATIO
    return DiagnosedIssue(
        type="putting_decel_stroke",
        name=PUTTING_ISSUE_NAMES["putting_decel_stroke"],
        severity=_severity(dev),
        description=(
            "送杆阶段速度明显低于回摆（疑似减速推击），球容易推短或方向不稳，"
            "建议保持杆头加速通过球、送杆自然延伸。"
        ),
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.phases["follow"].key_frame, phases.fps),
        metrics={"decel_speed_ratio": val},
    )


def _rule_aim_off(
    _feat: dict[str, float], phases: PuttingPhaseResult, signals: dict[str, float]
) -> DiagnosedIssue | None:
    val = _sig_val(signals, "setup_aim_offset_deg")
    if val is None or val <= SETUP_AIM_OFFSET_DEG:
        return None
    dev = (val - SETUP_AIM_OFFSET_DEG) / SETUP_AIM_OFFSET_DEG
    return DiagnosedIssue(
        type="putting_aim_off",
        name=PUTTING_ISSUE_NAMES["putting_aim_off"],
        severity=_severity(dev),
        description=(
            f"瞄准时杆面与最终推击方向偏差约 {val:.0f}°，瞄准线未对齐会推偏，"
            "建议站位时先对齐杆面与目标线再启动钟摆。"
        ),
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_to_time(phases.phases["setup"].key_frame, phases.fps),
        metrics={"setup_aim_offset_deg": val},
    )


def _rule_lift_putter(
    _feat: dict[str, float], phases: PuttingPhaseResult, signals: dict[str, float]
) -> DiagnosedIssue | None:
    val = _sig_val(signals, "putter_lift_norm")
    if val is None or val <= PUTTER_LIFT_NORM:
        return None
    dev = (val - PUTTER_LIFT_NORM) / PUTTER_LIFT_NORM
    return DiagnosedIssue(
        type="putting_lift_putter",
        name=PUTTING_ISSUE_NAMES["putting_lift_putter"],
        severity=_severity(dev),
        description=(
            "送杆过程中杆头（以主腕代理）有明显上抬，容易挑球或节奏中断，"
            "建议保持杆头低平通过球、沿地面延伸送杆。"
        ),
        confidence=min(1.0, 0.55 + dev * 0.25),
        key_frame_timestamp=_frame_to_time(phases.phases["follow"].key_frame, phases.fps),
        metrics={"putter_lift_norm": val},
    )


_RULES = [
    _rule_unstable_pendulum,
    _rule_head_moved,
    _rule_face_open,
    _rule_rushed_tempo,
    _rule_slow_tempo,
    _rule_wrist_hinge,
    _rule_short_backstroke,
    _rule_decel_stroke,
    _rule_aim_off,
    _rule_lift_putter,
]


def diagnose_putting(
    features: dict[str, float],
    phases: PuttingPhaseResult,
    *,
    signals: dict[str, float] | None = None,
    keypoints=None,
    valid_mask=None,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
) -> list[DiagnosedIssue]:
    """跑所有推杆 rule，过滤低置信度，按严重度→置信度排序返回 TopN。"""
    sig = signals
    if sig is None and keypoints is not None:
        sig = extract_putting_diagnostic_signals(keypoints, phases, valid_mask)
    if sig is None:
        sig = {}

    issues: list[DiagnosedIssue] = []
    for rule in _RULES:
        try:
            res = rule(features, phases, sig)
        except Exception as exc:  # pragma: no cover
            log.warning("putting_rule_error", extra={"rule": rule.__name__, "error": str(exc)})
            continue
        if res is None or res.confidence < min_confidence:
            continue
        issues.append(res)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order[x.severity], -x.confidence))
    return issues[:max_issues]
