"""W6-T2：问题诊断（docs/05 §2.7 · 规则引擎，MVP 覆盖 15 种）。

每个 rule 吃 `{feature_name: value}` + `PhaseSegmentResult`，判断是否触发，
触发则返回 `DiagnosedIssue`。全部 rule 由 `diagnose` 统一跑，按严重度排序返回。

Rules 清单（docs/14 附录 A）
--------------------------
| # | type                | 触发条件（主）                                        |
|---|---------------------|---------------------------------------------------|
| 1 | casting             | wrist_release_timing < 0.40                       |
| 2 | over_the_top        | (需 down_the_line，这里用 x_factor 负值 + 肩过度转做粗略代理) |
| 3 | early_extension     | spine_angle_impact_delta > 8                      |
| 4 | sway_slide          | head_lateral_shift > 0.12                         |
| 5 | loss_of_posture     | spine_angle_impact_delta ∈ (5, 8] 或头抖动中等         |
| 6 | reverse_spine       | top_wrist_position < 0，即手腕不在头上                   |
| 7 | chicken_wing        | finish_height > 0（手腕低于肩）+ 左臂伸直度异常              |
| 8 | sway_lead           | downswing_sequence < -2（肩先动）                     |
| 9 | hanging_back        | finish_balance > 0.04 + spine_angle 暴增           |
|10 | over_rotation       | shoulder_rotation_top > 105                      |
|11 | under_rotation      | shoulder_rotation_top < 75                       |
|12 | flat_shoulder       | shoulder_rotation_top > hip_rotation_top + 60     |
|13 | steep_shoulder      | shoulder_rotation_top - hip_rotation_top < 20 + x_factor 小  |
|14 | open_stance         | setup 肩线相对水平过大偏斜（粗估）                        |
|15 | grip_weak           | 低置信度兜底，仅在无其他 issue 时出                       |

说明
----
- docs/05 §2.7 要求 confidence < 0.6 的诊断不展示；我们 rule 里算出 confidence，
  在 `diagnose` 主入口统一过滤
- 严重度按偏离程度动态计算，而不是用 constants 里的 default_severity（那只作兜底）
- 规则是**互斥的**：某些 issue 会互相抑制（比如 over_rotation + under_rotation 不可能共存，
  代码里的阈值设计保证不会同时触发）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.pipeline.constants import issue_meta
from app.pipeline.phases import PhaseSegmentResult

log = logging.getLogger("ai_engine.diagnose")

# docs/05：confidence < 0.6 的 issue 不展示
MIN_DISPLAY_CONFIDENCE = 0.6

# 单次分析最多返回几条 issue（防刷屏）
MAX_ISSUES = 5


# ==================== 数据结构 ====================


@dataclass
class DiagnosedIssue:
    """单个诊断结果。

    Attributes:
        type: issue type（与 constants.ISSUE_TYPES 一致）
        name: 中文名
        severity: "high" / "medium" / "low"（由偏离度动态计算）
        description: 给用户看的说明文案
        confidence: 0-1；低于 MIN_DISPLAY_CONFIDENCE 不展示
        key_frame_timestamp: 出错的关键帧时间戳（秒，用于前端跳转）
        metrics: 诊断依据的特征值，调试/解释用
    """

    type: str
    name: str
    severity: str
    description: str
    confidence: float
    key_frame_timestamp: float | None = None
    metrics: dict[str, float] = field(default_factory=dict)


# ==================== 工具 ====================


def _severity(deviation: float, low: float, high: float) -> str:
    """按偏离量分三档。deviation < low → low；≥ high → high；中间 medium。"""
    if deviation >= high:
        return "high"
    if deviation >= low:
        return "medium"
    return "low"


def _frame_to_time(frame: int, fps: float) -> float:
    return round(frame / fps, 2) if fps > 0 else None


# ==================== Rule 集 ====================


def _rule_casting(feat: dict[str, float], phases: PhaseSegmentResult) -> DiagnosedIssue | None:
    timing = feat["wrist_release_timing"]
    if timing >= 0.40:
        return None
    dev = (0.40 - timing) / 0.20  # 0-2
    conf = min(1.0, dev)
    sev = _severity(dev, 0.4, 0.8)
    name = issue_meta("casting")["name"]
    return DiagnosedIssue(
        type="casting",
        name=name,
        severity=sev,
        description=(
            f"手腕在下杆 {timing * 100:.0f}% 就开始释放（理想 50%-70%），"
            "过早释放容易导致杆面打开、产生右曲球。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"wrist_release_timing": timing, "ideal_min": 0.50, "ideal_max": 0.70},
    )


def _rule_over_the_top(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    # MVP 代理：X-Factor 过大（肩远转而髋没转）+ 下杆顺序错乱
    xf = feat["x_factor"]
    seq = feat["downswing_sequence"]
    if xf < 55 or seq >= 0:
        return None
    dev = (xf - 55) / 20
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="over_the_top",
        name=issue_meta("over_the_top")["name"],
        severity=sev,
        description=(
            f"X-Factor {xf:.0f}° 偏大、且下杆顺序不正（肩先于髋 {-seq:.0f} 帧），"
            "杆头容易从身体外侧切入击球区。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"x_factor": xf, "downswing_sequence": seq},
    )


def _rule_early_extension(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    delta = feat["spine_angle_impact_delta"]
    if delta <= 8.0:
        return None
    dev = (delta - 8.0) / 10.0
    conf = min(1.0, 0.6 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="early_extension",
        name=issue_meta("early_extension")["name"],
        severity=sev,
        description=(
            f"击球时脊柱角比准备位变化了 {delta:.1f}°（理想 ≤5°），"
            "髋部过早前伸，击球距离和稳定性受损。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"spine_angle_impact_delta": delta},
    )


def _rule_sway_slide(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    shift = feat["head_lateral_shift"]
    if shift <= 0.12:
        return None
    dev = (shift - 0.12) / 0.08
    conf = min(1.0, 0.6 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="sway_slide",
        name=issue_meta("sway_slide")["name"],
        severity=sev,
        description=(
            f"头部水平位移 {shift * 100:.1f}%（约超过 10cm），"
            "重心在侧向大幅移动，下杆回正困难。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"head_lateral_shift": shift},
    )


def _rule_loss_of_posture(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    delta = feat["spine_angle_impact_delta"]
    shift = feat["head_lateral_shift"]
    # early_extension 阈值 8° 以下；这里抓中等偏离
    if delta <= 5.0 or delta > 8.0:
        if shift <= 0.08 or shift > 0.12:
            return None
    dev = max((delta - 5.0) / 3.0, (shift - 0.08) / 0.04)
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="loss_of_posture",
        name=issue_meta("loss_of_posture")["name"],
        severity=sev,
        description=(
            f"挥杆过程中脊柱 / 头部稳定性不足（脊柱变化 {delta:.1f}°，"
            f"头部位移 {shift * 100:.1f}%），影响击球点一致性。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.impact_frame, phases.fps),
        metrics={"spine_angle_impact_delta": delta, "head_lateral_shift": shift},
    )


def _rule_reverse_spine(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    wp = feat["top_wrist_position"]
    if wp >= 0.0:
        return None
    dev = -wp / 0.2
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="reverse_spine",
        name=issue_meta("reverse_spine")["name"],
        severity=sev,
        description=(
            f"顶点手腕位置过低（低于头顶 {abs(wp) * 100:.1f}%），"
            "脊柱可能向目标侧反向倾斜，存在受伤风险。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"top_wrist_position": wp},
    )


def _rule_chicken_wing(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    arm = feat["left_arm_straightness"]
    finish_h = feat["finish_height"]
    # 左臂明显弯折 + 收杆位偏低
    if arm >= 150.0 and finish_h <= -0.05:
        return None
    dev = max((150.0 - arm) / 30.0, (finish_h + 0.10) / 0.10)
    if dev <= 0:
        return None
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="chicken_wing",
        name=issue_meta("chicken_wing")["name"],
        severity=sev,
        description=(
            f"跟进时左臂夹角 {arm:.0f}°，伸直度不足；收杆手腕相对肩 {finish_h:.2f}，"
            "跟进动作受限。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.phases["follow_through"].key_frame, phases.fps),
        metrics={"left_arm_straightness": arm, "finish_height": finish_h},
    )


def _rule_sway_lead(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    seq = feat["downswing_sequence"]
    if seq >= -2.0:
        return None
    dev = (-seq - 2.0) / 3.0
    conf = min(1.0, 0.6 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="sway_lead",
        name=issue_meta("sway_lead")["name"],
        severity=sev,
        description=(
            f"下杆时肩比髋先动约 {abs(seq):.0f} 帧（理想髋先于肩 2-7 帧），"
            "发力顺序不对，容易拉击或右曲。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"downswing_sequence": seq},
    )


def _rule_hanging_back(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    balance = feat["finish_balance"]
    if balance <= 0.04:
        return None
    dev = (balance - 0.04) / 0.04
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="hanging_back",
        name=issue_meta("hanging_back")["name"],
        severity=sev,
        description=(
            f"收杆不稳定（双脚踝抖动 {balance:.3f}，理想 <0.02），"
            "可能是击球后重心未完成转移。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.phases["follow_through"].end_frame, phases.fps),
        metrics={"finish_balance": balance},
    )


def _rule_over_rotation(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    shoulder = feat["shoulder_rotation_top"]
    if shoulder <= 105:
        return None
    dev = (shoulder - 105) / 15
    conf = min(1.0, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="over_rotation",
        name=issue_meta("over_rotation")["name"],
        severity=sev,
        description=(
            f"顶点肩旋转 {shoulder:.0f}°（理想 80°-100°），过度转肩可能影响节奏。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"shoulder_rotation_top": shoulder},
    )


def _rule_under_rotation(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    shoulder = feat["shoulder_rotation_top"]
    if shoulder >= 75:
        return None
    dev = (75 - shoulder) / 20
    conf = min(1.0, 0.6 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="under_rotation",
        name=issue_meta("under_rotation")["name"],
        severity=sev,
        description=(
            f"顶点肩旋转仅 {shoulder:.0f}°（理想 80°-100°），上杆力量传递受限。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"shoulder_rotation_top": shoulder},
    )


def _rule_flat_shoulder(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    xf = feat["x_factor"]
    if xf <= 60:
        return None
    dev = (xf - 60) / 20
    conf = min(0.9, 0.55 + dev * 0.3)  # 粗估，不给 1.0
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="flat_shoulder",
        name=issue_meta("flat_shoulder")["name"],
        severity=sev,
        description=(
            f"肩/髋角度差 {xf:.0f}°，肩旋转平面偏水平，上杆路径可能过内。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"x_factor": xf},
    )


def _rule_steep_shoulder(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    xf = feat["x_factor"]
    if xf >= 25:
        return None
    dev = (25 - xf) / 15
    conf = min(0.85, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="steep_shoulder",
        name=issue_meta("steep_shoulder")["name"],
        severity=sev,
        description=(
            f"肩/髋角度差仅 {xf:.0f}°，肩旋转平面偏陡，上杆可能过外。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.top_frame, phases.fps),
        metrics={"x_factor": xf},
    )


def _rule_open_stance(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    # Setup 阶段肩线相对水平偏斜：用 knee_flexion_setup 过直（>165）做代理（粗估）。
    kf = feat["knee_flexion_setup"]
    if kf <= 170:
        return None
    dev = (kf - 170) / 10
    conf = min(0.8, 0.55 + dev * 0.3)
    sev = _severity(dev, 0.3, 0.8)
    return DiagnosedIssue(
        type="open_stance",
        name=issue_meta("open_stance")["name"],
        severity=sev,
        description=(
            f"准备位膝弯角 {kf:.0f}°（理想 150°-165°），双腿过直，站位可能偏开。"
        ),
        confidence=conf,
        key_frame_timestamp=_frame_to_time(phases.phases["setup"].key_frame, phases.fps),
        metrics={"knee_flexion_setup": kf},
    )


def _rule_grip_weak(
    feat: dict[str, float], phases: PhaseSegmentResult
) -> DiagnosedIssue | None:
    # 仅作置信度兜底：所有关键特征都在边缘值附近时，给 low-severity 的"弱握可能"。
    # MVP 期很可能永远不触发；保留为占位。
    return None


# ==================== 主入口 ====================

_RULES = [
    _rule_casting,
    _rule_over_the_top,
    _rule_early_extension,
    _rule_sway_slide,
    _rule_loss_of_posture,
    _rule_reverse_spine,
    _rule_chicken_wing,
    _rule_sway_lead,
    _rule_hanging_back,
    _rule_over_rotation,
    _rule_under_rotation,
    _rule_flat_shoulder,
    _rule_steep_shoulder,
    _rule_open_stance,
    _rule_grip_weak,
]


def diagnose(
    features: dict[str, float],
    phases: PhaseSegmentResult,
    *,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
) -> list[DiagnosedIssue]:
    """跑所有 rule，过滤置信度，按严重度排序返回 TopN。

    排序规则：
    1. severity 降序（high > medium > low）
    2. confidence 降序（同严重度里置信度高的优先）
    """
    issues: list[DiagnosedIssue] = []
    for rule in _RULES:
        try:
            result = rule(features, phases)
        except Exception as exc:  # pragma: no cover
            log.warning("rule_error", extra={"rule": rule.__name__, "error": str(exc)})
            continue
        if result is None:
            continue
        if result.confidence < min_confidence:
            log.debug(
                "issue_filtered_low_conf",
                extra={"type": result.type, "confidence": result.confidence},
            )
            continue
        issues.append(result)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (severity_order[x.severity], -x.confidence))

    return issues[:max_issues]
