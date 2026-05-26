"""P2-M7-06 · 置信度上链路化：三层公式 + 档位分级。

详 docs/release-notes/p2-m7-06-confidence-pipeline-kickoff.md。

层次
----
1. `feature_confidence(...)` 0-1：每特征基于 pose.visibility 子矩阵 + 有效帧占比
2. `issue_confidence(...)`  0-1：每诊断 = 相关 feature_confidence 加权平均 × 阈值距离
3. `compute_analysis_confidence(...)` 0-1：整体可信度 = visibility × quality_warnings 惩罚 ×
   camera_angle_offset_deg 惩罚 × feature_avg

档位（kickoff §3.2.2 + §3.3）
---------------------------
- analysis: ≥0.75 高 / 0.5-0.75 中 / <0.5 低（低 → 报告页"建议重拍" CTA）
- issue:    >0.85 confirmed / 0.6-0.85 leaning / <0.6 hidden（折叠"AI 不太确定"区）

兼容性
------
- V1 引擎遗留报告（无 confidence）：scoring 层兜底 `analysis_confidence = 1.0`，
  客户端 `?? 1.0` 后不展示色块也不展示 CTA（视为"高可信"老路径）
- 灰度回滚：v1 容器输出始终 1.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping

ConfidenceTier = Literal["confirmed", "leaning", "hidden"]
AnalysisTier = Literal["high", "medium", "low"]

# ============================================================
# 档位阈值（kickoff §3.2.2 / §3.3，W17 v0.1）
# ============================================================

ISSUE_CONFIRMED_THRESHOLD = 0.85
ISSUE_LEANING_THRESHOLD = 0.60

ANALYSIS_HIGH_THRESHOLD = 0.75
ANALYSIS_LOW_THRESHOLD = 0.50

# 与 P2-M7-04 §3.3 对齐：>15° 严重惩罚
ANGLE_HARD_OFFSET_DEG = 15.0
ANGLE_PENALTY_BAD = 0.4

# 每条 quality_warning 的惩罚因子（kickoff §3.2.3 典型值案例反推）
PER_WARNING_PENALTY = 0.15

# V1 引擎默认兜底（kickoff §4.3）
V1_DEFAULT_ANALYSIS_CONFIDENCE = 1.0


# ============================================================
# 数据结构
# ============================================================


@dataclass(frozen=True)
class FeatureConfidenceBreakdown:
    """每特征的 confidence 计算明细，供 UI "详情"展开。"""

    feature_name: str
    mean_visibility: float
    valid_frame_ratio: float
    confidence: float


@dataclass(frozen=True)
class IssueConfidenceBreakdown:
    """每诊断的 confidence 明细 + 档位。"""

    issue_type: str
    feature_avg: float
    threshold_distance: float
    confidence: float
    tier: ConfidenceTier


@dataclass(frozen=True)
class AnalysisConfidenceBreakdown:
    """整体 confidence 计算明细（kickoff §3.2.3 典型值表）。"""

    base: float
    quality_warning_penalty: float
    angle_penalty: float
    feature_avg: float
    analysis_confidence: float
    tier: AnalysisTier
    recommend_retake: bool


# ============================================================
# Layer 1：feature_confidence
# ============================================================


def feature_confidence(
    visibility_sub: list[list[float]] | None,
    *,
    min_per_frame_confidence: float = 0.5,
) -> float:
    """每特征 confidence。

    输入：visibility_sub = pose.visibility[phase_frames, relevant_landmarks]，
          shape = (F_phase, K_relevant)
    输出：mean(visibility) × 有效帧占比（mean(per_frame_visibility) ≥ 阈值的占比）

    设计：
    - 不依赖 numpy；纯 Python list 计算便于单测 + RN 客户端可移植
    - 空输入 / 0 帧 → 0.0（保守，不浮报）
    """
    if not visibility_sub:
        return 0.0

    per_frame_means: list[float] = []
    total_sum = 0.0
    total_count = 0
    for row in visibility_sub:
        if not row:
            continue
        row_sum = sum(row)
        row_n = len(row)
        per_frame_means.append(row_sum / row_n)
        total_sum += row_sum
        total_count += row_n

    if total_count == 0 or not per_frame_means:
        return 0.0

    mean_visibility = total_sum / total_count
    valid_frame_ratio = sum(1 for m in per_frame_means if m >= min_per_frame_confidence) / len(
        per_frame_means
    )
    return _clamp01(mean_visibility * valid_frame_ratio)


def build_feature_breakdown(
    feature_name: str,
    visibility_sub: list[list[float]] | None,
    *,
    min_per_frame_confidence: float = 0.5,
) -> FeatureConfidenceBreakdown:
    """同时返回 confidence 与中间项（UI 展开用）。"""
    if not visibility_sub:
        return FeatureConfidenceBreakdown(feature_name, 0.0, 0.0, 0.0)

    per_frame_means: list[float] = []
    total_sum = 0.0
    total_count = 0
    for row in visibility_sub:
        if not row:
            continue
        per_frame_means.append(sum(row) / len(row))
        total_sum += sum(row)
        total_count += len(row)

    if total_count == 0 or not per_frame_means:
        return FeatureConfidenceBreakdown(feature_name, 0.0, 0.0, 0.0)

    mean_vis = total_sum / total_count
    vfr = sum(1 for m in per_frame_means if m >= min_per_frame_confidence) / len(per_frame_means)
    return FeatureConfidenceBreakdown(
        feature_name=feature_name,
        mean_visibility=mean_vis,
        valid_frame_ratio=vfr,
        confidence=_clamp01(mean_vis * vfr),
    )


# ============================================================
# Layer 2：issue_confidence
# ============================================================


def issue_confidence(
    feature_confidences_for_issue: Iterable[float],
    *,
    threshold_distance: float = 0.0,
) -> float:
    """每诊断 confidence = 相关 feature_confidence 加权平均 × σ(threshold_distance)。

    threshold_distance ∈ [0, ∞)：特征值距 ideal 阈值的归一化距离；越远越确信
    无相关特征 → 0.0（防止单凭阈值 σ 浮报）
    """
    feats = list(feature_confidences_for_issue)
    if not feats:
        return 0.0
    feat_avg = sum(feats) / len(feats)
    sigmoid_factor = 0.5 + 0.5 * _sigmoid(threshold_distance)
    return _clamp01(feat_avg * sigmoid_factor)


def issue_tier(confidence: float) -> ConfidenceTier:
    """0.85+ confirmed / 0.6-0.85 leaning / <0.6 hidden。"""
    if confidence > ISSUE_CONFIRMED_THRESHOLD:
        return "confirmed"
    if confidence >= ISSUE_LEANING_THRESHOLD:
        return "leaning"
    return "hidden"


def build_issue_breakdown(
    issue_type: str,
    feature_confidences_for_issue: Iterable[float],
    *,
    threshold_distance: float = 0.0,
) -> IssueConfidenceBreakdown:
    feats = list(feature_confidences_for_issue)
    feat_avg = sum(feats) / len(feats) if feats else 0.0
    conf = issue_confidence(feats, threshold_distance=threshold_distance)
    return IssueConfidenceBreakdown(
        issue_type=issue_type,
        feature_avg=feat_avg,
        threshold_distance=threshold_distance,
        confidence=conf,
        tier=issue_tier(conf),
    )


# ============================================================
# Layer 3：analysis_confidence
# ============================================================


def compute_analysis_confidence(
    *,
    mean_visibility: float,
    quality_warnings: Iterable[str] | None,
    camera_angle_offset_deg: float | None,
    feature_confidences: Mapping[str, float] | None,
) -> float:
    """整体 confidence。

    与 kickoff §3.2.3 公式 1:1：
        base * (1 - 0.15 * len(warnings)) * angle_penalty * feature_avg

    Args:
        mean_visibility: PoseResult.mean_confidence（0-1）
        quality_warnings: 一期 quality_warnings 列表（每个 -0.15）
        camera_angle_offset_deg: M7-04 输出；None 或 0 视为正机位
        feature_confidences: Layer 1 的 dict；缺失则视为 1.0（不惩罚）
    """
    base = _clamp01(mean_visibility)

    warn_count = len(list(quality_warnings)) if quality_warnings else 0
    qw_penalty = max(0.0, 1.0 - PER_WARNING_PENALTY * warn_count)

    offset = abs(camera_angle_offset_deg) if camera_angle_offset_deg is not None else 0.0
    angle_penalty = 1.0 if offset <= ANGLE_HARD_OFFSET_DEG else ANGLE_PENALTY_BAD

    if feature_confidences:
        vals = list(feature_confidences.values())
        feat_avg = sum(vals) / len(vals) if vals else 1.0
    else:
        feat_avg = 1.0

    return _clamp01(base * qw_penalty * angle_penalty * feat_avg)


def analysis_tier(confidence: float) -> AnalysisTier:
    """≥0.75 高 / 0.5-0.75 中 / <0.5 低。"""
    if confidence >= ANALYSIS_HIGH_THRESHOLD:
        return "high"
    if confidence >= ANALYSIS_LOW_THRESHOLD:
        return "medium"
    return "low"


def should_recommend_retake(confidence: float) -> bool:
    """FR-3：overall < 0.5 → 报告页"建议重拍" CTA。"""
    return confidence < ANALYSIS_LOW_THRESHOLD


def build_analysis_breakdown(
    *,
    mean_visibility: float,
    quality_warnings: Iterable[str] | None,
    camera_angle_offset_deg: float | None,
    feature_confidences: Mapping[str, float] | None,
) -> AnalysisConfidenceBreakdown:
    """整体 breakdown（UI"详情"展开 + 单测断言用）。"""
    base = _clamp01(mean_visibility)
    warn_count = len(list(quality_warnings)) if quality_warnings else 0
    qw_penalty = max(0.0, 1.0 - PER_WARNING_PENALTY * warn_count)
    offset = abs(camera_angle_offset_deg) if camera_angle_offset_deg is not None else 0.0
    angle_penalty = 1.0 if offset <= ANGLE_HARD_OFFSET_DEG else ANGLE_PENALTY_BAD
    if feature_confidences:
        vals = list(feature_confidences.values())
        feat_avg = sum(vals) / len(vals) if vals else 1.0
    else:
        feat_avg = 1.0

    overall = _clamp01(base * qw_penalty * angle_penalty * feat_avg)
    return AnalysisConfidenceBreakdown(
        base=base,
        quality_warning_penalty=qw_penalty,
        angle_penalty=angle_penalty,
        feature_avg=feat_avg,
        analysis_confidence=overall,
        tier=analysis_tier(overall),
        recommend_retake=should_recommend_retake(overall),
    )


# ============================================================
# 工具
# ============================================================


def _clamp01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return float(max(0.0, min(1.0, x)))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# ============================================================
# 特征 → 关键点 依赖表（kickoff §3.2.1 表）
# diagnose.py / features.py 改造时按这里 lookup
# ============================================================

FEATURE_LANDMARK_DEPENDENCY: dict[str, list[int]] = {
    # MediaPipe Pose 关键点索引
    # 11=L_shoulder, 12=R_shoulder, 23=L_hip, 24=R_hip, 15=L_wrist, 16=R_wrist
    "spine_angle_setup": [11, 12, 23, 24],
    "x_factor": [11, 12, 23, 24],
    "tempo_ratio": [15, 16],
    # W18 编码时补齐其余 12 特征
}


ISSUE_FEATURE_DEPENDENCY: dict[str, list[str]] = {
    # diagnose.py rule_id → 依赖的 features
    # W18 编码时按 15 条 rule 补齐
    "casting": ["x_factor", "tempo_ratio"],
    "over_the_top": ["x_factor", "spine_angle_setup"],
    "early_extension": ["spine_angle_setup"],
}
