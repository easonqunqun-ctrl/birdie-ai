"""P2-M7-04 · 机位检测 + enum 规范化 + 双套标尺单测。

覆盖 kickoff §3.2.1（enum 映射） / §3.3（>15° hook）/ §4.1（双套权重）/ §4.3（fallback）。
"""

from __future__ import annotations

import pytest

from app.pipeline.camera_angle import (
    DETECTION_CONFIDENCE_FALLBACK,
    OFFSET_HARD_THRESHOLD,
    CameraAngleResult,
    angle_engine_warnings,
    attach_declared,
    detect_camera_angle,
    normalize_camera_angle,
    resolve_effective_angle,
    summarize_pose_for_angle,
)
from app.pipeline.angle_profiles import (
    IDEAL_OVERRIDES_BY_ANGLE,
    PHASE_WEIGHT_MIN_DIFF,
    PHASE_WEIGHTS_BY_ANGLE,
    PHASE_WEIGHTS_DOWN_THE_LINE,
    PHASE_WEIGHTS_FACE_ON,
    ideal_for_angle,
    phase_weights_diff,
    phase_weights_for,
)


# ============================================================
# 1. normalize_camera_angle（§3.2.1）
# ============================================================


def test_normalize_face_on_aliases():
    assert normalize_camera_angle("face_on") == "face_on"
    assert normalize_camera_angle("Face_On") == "face_on"
    assert normalize_camera_angle("face-on") == "face_on"


def test_normalize_dtl_aliases():
    assert normalize_camera_angle("dtl") == "down_the_line"
    assert normalize_camera_angle("DTL") == "down_the_line"
    assert normalize_camera_angle("down_the_line") == "down_the_line"
    assert normalize_camera_angle("down-the-line") == "down_the_line"


def test_normalize_none_inputs():
    assert normalize_camera_angle(None) is None
    assert normalize_camera_angle("") is None
    assert normalize_camera_angle("  ") is None


def test_normalize_oblique_returns_none_not_raise():
    """oblique 仅作中间态，normalize 后视为缺失（§3.2.1 末尾批注）。"""
    assert normalize_camera_angle("oblique") is None


def test_normalize_unknown_raises():
    with pytest.raises(ValueError):
        normalize_camera_angle("front_view")
    with pytest.raises(ValueError):
        normalize_camera_angle("side")


# ============================================================
# 2. resolve_effective_angle（§4.3 fallback 规则）
# ============================================================


def test_resolve_uses_detected_when_confidence_high():
    out = resolve_effective_angle(detected="face_on", declared="down_the_line", confidence=0.95)
    assert out == "face_on"


def test_resolve_fallback_to_declared_when_confidence_low():
    out = resolve_effective_angle(
        detected="face_on", declared="down_the_line", confidence=0.6
    )
    assert out == "down_the_line"


def test_resolve_oblique_falls_back_to_declared():
    out = resolve_effective_angle(detected="oblique", declared="face_on", confidence=0.99)
    assert out == "face_on"


def test_resolve_no_declared_oblique_defaults_face_on():
    """detected=oblique 且 declared=None → 保守 face_on。"""
    out = resolve_effective_angle(detected="oblique", declared=None, confidence=0.9)
    assert out == "face_on"


def test_resolve_no_declared_low_confidence_defaults_face_on():
    out = resolve_effective_angle(detected="down_the_line", declared=None, confidence=0.3)
    assert out == "face_on"


# ============================================================
# 3. detect_camera_angle 启发式 PoC
# ============================================================


def test_detect_face_on_wide_shoulders():
    """肩宽 ≥ 0.18 → face_on。"""
    summary = summarize_pose_for_angle(
        left_shoulder_x=0.30,
        right_shoulder_x=0.50,  # 肩宽 0.20
        left_hip_x=0.32,
        right_hip_x=0.48,
        head_x=0.40,
        head_y=0.10,
        valid_frame_ratio=0.95,
    )
    result = detect_camera_angle(summary)
    assert result.detected_angle == "face_on"
    assert result.confidence > 0.5
    assert 0.0 <= result.offset_deg <= 90.0


def test_detect_down_the_line_narrow_shoulders():
    """肩宽 ≤ 0.09 → down_the_line（侧身遮挡）。"""
    summary = summarize_pose_for_angle(
        left_shoulder_x=0.40,
        right_shoulder_x=0.46,  # 肩宽 0.06
        left_hip_x=0.41,
        right_hip_x=0.45,
        head_x=0.43,
        head_y=0.10,
        valid_frame_ratio=0.90,
    )
    result = detect_camera_angle(summary)
    assert result.detected_angle == "down_the_line"


def test_detect_oblique_intermediate():
    """肩宽介于阈值之间 → oblique 中间态。"""
    summary = summarize_pose_for_angle(
        left_shoulder_x=0.38,
        right_shoulder_x=0.50,  # 肩宽 0.12
        left_hip_x=0.40,
        right_hip_x=0.48,
        head_x=0.44,
        head_y=0.10,
        valid_frame_ratio=0.95,
    )
    result = detect_camera_angle(summary)
    assert result.detected_angle == "oblique"


def test_detect_confidence_drops_with_low_valid_frame_ratio():
    summary = summarize_pose_for_angle(
        left_shoulder_x=0.30,
        right_shoulder_x=0.50,
        left_hip_x=0.32,
        right_hip_x=0.48,
        head_x=0.40,
        head_y=0.10,
        valid_frame_ratio=0.30,
    )
    result = detect_camera_angle(summary)
    assert result.confidence < 0.5


# ============================================================
# 4. CameraAngleResult + attach_declared
# ============================================================


def test_attach_declared_no_mismatch_when_aligned():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=5.0,
        confidence=0.9,
        declared_angle=None,
        mismatch=False,
    )
    out = attach_declared(base, "face_on")
    assert out.declared_angle == "face_on"
    assert out.mismatch is False


def test_attach_declared_mismatch_when_detected_differs():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=5.0,
        confidence=0.9,
        declared_angle=None,
        mismatch=False,
    )
    out = attach_declared(base, "dtl")
    assert out.declared_angle == "down_the_line"
    assert out.mismatch is True


def test_attach_declared_no_mismatch_when_confidence_low():
    """confidence 不达 0.7 → 不算 mismatch（容忍检测器不确定）。"""
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=5.0,
        confidence=0.5,
        declared_angle=None,
        mismatch=False,
    )
    out = attach_declared(base, "down_the_line")
    assert out.mismatch is False


def test_attach_declared_oblique_no_mismatch():
    """oblique 中间态不参与 mismatch 判定。"""
    base = CameraAngleResult(
        detected_angle="oblique",
        offset_deg=20.0,
        confidence=0.9,
        declared_angle=None,
        mismatch=False,
    )
    out = attach_declared(base, "face_on")
    assert out.mismatch is False


def test_effective_angle_falls_back_to_declared_for_oblique():
    base = CameraAngleResult(
        detected_angle="oblique",
        offset_deg=12.0,
        confidence=0.9,
        declared_angle="down_the_line",
        mismatch=False,
    )
    assert base.effective_angle == "down_the_line"


def test_should_recommend_retake_above_threshold():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=16.0,
        confidence=0.95,
        declared_angle="face_on",
        mismatch=False,
    )
    assert base.should_recommend_retake is True

    safe = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=15.0,
        confidence=0.95,
        declared_angle="face_on",
        mismatch=False,
    )
    assert safe.should_recommend_retake is False


# ============================================================
# 5. engine_warnings 集成（M7-02 联动）
# ============================================================


def test_engine_warnings_emit_large_offset():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=22.0,
        confidence=0.9,
        declared_angle="face_on",
        mismatch=False,
    )
    warnings = angle_engine_warnings(base)
    assert any(w.code == "camera_angle_large_offset" for w in warnings)
    large_warn = next(w for w in warnings if w.code == "camera_angle_large_offset")
    assert large_warn.level == "warn"


def test_engine_warnings_emit_mismatch():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=5.0,
        confidence=0.9,
        declared_angle="down_the_line",
        mismatch=True,
    )
    warnings = angle_engine_warnings(base)
    assert any(w.code == "camera_angle_mismatch" for w in warnings)


def test_engine_warnings_empty_when_clean():
    base = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=3.0,
        confidence=0.9,
        declared_angle="face_on",
        mismatch=False,
    )
    assert angle_engine_warnings(base) == []


# ============================================================
# 6. 双套 PHASE_WEIGHTS（§4.1）
# ============================================================


def test_phase_weights_face_on_sums_to_one():
    assert abs(sum(PHASE_WEIGHTS_FACE_ON.values()) - 1.0) < 1e-9


def test_phase_weights_down_the_line_sums_to_one():
    assert abs(sum(PHASE_WEIGHTS_DOWN_THE_LINE.values()) - 1.0) < 1e-9


def test_phase_weights_for_returns_correct_set():
    assert phase_weights_for("face_on") == PHASE_WEIGHTS_FACE_ON
    assert phase_weights_for("down_the_line") == PHASE_WEIGHTS_DOWN_THE_LINE


def test_phase_weights_for_none_falls_back_to_v1():
    """None / 未知 → V1 单套 PHASE_WEIGHTS（向后兼容）。"""
    from app.pipeline.constants import PHASE_WEIGHTS

    assert phase_weights_for(None) == PHASE_WEIGHTS
    assert phase_weights_for("unknown") == PHASE_WEIGHTS  # type: ignore[arg-type]


def test_phase_weights_differ_between_angles():
    """W19 DoD：双套权重至少在一个 phase 上差异 ≥ 0.03。"""
    diff = phase_weights_diff("face_on", "down_the_line")
    assert max(diff.values()) >= PHASE_WEIGHT_MIN_DIFF


def test_phase_weights_keys_cover_all_phases():
    from app.pipeline.constants import PHASE_ORDER

    for angle in ("face_on", "down_the_line"):
        weights = PHASE_WEIGHTS_BY_ANGLE[angle]
        assert set(weights.keys()) == set(PHASE_ORDER)


# ============================================================
# 7. 双套 ideal（§4.2 至少 3 特征）
# ============================================================


def test_ideal_for_angle_face_on_overrides():
    # face_on 收紧脊柱前倾上下限
    lo, hi = ideal_for_angle("spine_angle_setup", "face_on")
    assert (lo, hi) == (24.0, 36.0)


def test_ideal_for_angle_dtl_overrides():
    lo, hi = ideal_for_angle("top_wrist_position", "down_the_line")
    assert (lo, hi) == (0.15, 0.38)


def test_ideal_for_angle_fallback_to_v1_when_no_override():
    """未在 override 表里的特征 → 沿用 V1 ideal。"""
    lo, hi = ideal_for_angle("knee_flexion_setup", "face_on")
    from app.pipeline.constants import feature_meta

    v1 = feature_meta("knee_flexion_setup")
    assert (lo, hi) == (v1["ideal_min"], v1["ideal_max"])


def test_ideal_for_angle_unknown_feature_raises():
    with pytest.raises(KeyError):
        ideal_for_angle("nonexistent_feature", "face_on")


def test_ideal_overrides_cover_at_least_three_features_per_angle():
    """W19 DoD §4.2：双套 ideal v0.1 至少 3 特征更新。"""
    assert len(IDEAL_OVERRIDES_BY_ANGLE["face_on"]) >= 3
    assert len(IDEAL_OVERRIDES_BY_ANGLE["down_the_line"]) >= 3


# ============================================================
# 8. 阈值常量守门
# ============================================================


def test_offset_hard_threshold_matches_m7_06():
    """与 P2-M7-06 ANGLE_HARD_OFFSET_DEG 必须一致（联动公式）。"""
    assert OFFSET_HARD_THRESHOLD == 15.0


def test_detection_confidence_fallback_threshold():
    assert DETECTION_CONFIDENCE_FALLBACK == 0.7
