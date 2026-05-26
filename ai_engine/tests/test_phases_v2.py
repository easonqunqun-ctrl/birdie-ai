"""P2-M7-07 · phases_v2 fallback 链路 + 硬约束 + segmentation_method 单测。

W22 起跑前置：本 PR 验证骨架行为，NN 推理具体实现在 W23-W26 PR 独立测试。
"""

from __future__ import annotations

import pytest

from app.pipeline.phases_v2 import (
    HARD_MIN_FRAMES_SETUP_TO_IMPACT,
    M7_V2_SEGMENT_MIN_DURATION_SEC,
    M7_V2_SEGMENT_NN_ENABLED_DEFAULT,
    NN_CONFIDENCE_THRESHOLD,
    SegmenterNNNotReadyError,
    V2PhaseFrames,
    _infer_nn,
    get_segmentation_method,
    segment_phases_v2,
    validate_hard_constraints,
    with_segmentation_method,
)


# ============================================================
# 1. 配置常量与 kickoff §4.2 对齐
# ============================================================


def test_min_duration_sec_aligned_with_kickoff():
    """kickoff R-03：从 V1 的 2.0 → V2 1.5（兼容慢挥）。"""
    assert M7_V2_SEGMENT_MIN_DURATION_SEC == 1.5


def test_nn_default_disabled():
    """安全默认：未灰度时不走 NN。"""
    assert M7_V2_SEGMENT_NN_ENABLED_DEFAULT is False


def test_nn_confidence_threshold():
    assert NN_CONFIDENCE_THRESHOLD == 0.6


def test_hard_min_frames_setup_to_impact():
    """≥1s @30fps = 30 帧（kickoff §3.5）。"""
    assert HARD_MIN_FRAMES_SETUP_TO_IMPACT == 30


# ============================================================
# 2. validate_hard_constraints（§3.5）
# ============================================================


def _make_v2_result(
    *,
    setup_start=0,
    setup_end=10,
    top_frame=50,
    impact_frame=80,
    follow_end=120,
    confidence=0.8,
):
    return V2PhaseFrames(
        setup_start=setup_start,
        setup_end=setup_end,
        top_frame=top_frame,
        impact_frame=impact_frame,
        follow_end=follow_end,
        confidence=confidence,
    )


def test_hard_constraints_pass_for_valid_swing():
    result = _make_v2_result()
    ok, reason = validate_hard_constraints(result)
    assert ok is True
    assert reason is None


def test_hard_constraints_fail_when_setup_end_after_top():
    result = _make_v2_result(setup_end=60, top_frame=50)
    ok, reason = validate_hard_constraints(result)
    assert ok is False
    assert "setup_end" in reason


def test_hard_constraints_fail_when_top_after_impact():
    result = _make_v2_result(top_frame=85, impact_frame=80)
    ok, reason = validate_hard_constraints(result)
    assert ok is False
    assert "top_frame" in reason


def test_hard_constraints_fail_when_impact_after_follow():
    result = _make_v2_result(impact_frame=130, follow_end=120)
    ok, reason = validate_hard_constraints(result)
    assert ok is False
    assert "impact_frame" in reason


def test_hard_constraints_fail_too_short_setup_to_impact():
    """setup→impact <30 帧应 fail（kickoff §3.5 ≥1s @30fps）。"""
    result = _make_v2_result(setup_end=70, top_frame=80, impact_frame=90)
    ok, reason = validate_hard_constraints(result)
    assert ok is False
    assert "frames" in reason


# ============================================================
# 3. fallback 链路（§3.4 五分支全覆盖）
# ============================================================


def _v1_stub(_pose):
    """V1 启发式 stub：返回固定标识。"""
    return {"_v1_marker": True, "phases": {"setup": {}}}


def test_fallback_nn_disabled_goes_v1():
    """Branch 1：nn_enabled=False → 直走 V1。"""
    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=False,
    )
    assert result == {"_v1_marker": True, "phases": {"setup": {}}}
    assert method == "v1_heuristic"
    assert warnings == []


def test_fallback_nn_not_ready_goes_v1_with_warning():
    """Branch 2：NN 模型未就绪（NotImplementedError）→ fallback v1。"""
    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=True,
    )
    assert result == {"_v1_marker": True, "phases": {"setup": {}}}
    assert method == "v1_heuristic"
    assert any(w.code == "phase_seg_nn_not_ready" for w in warnings)


def test_fallback_nn_runtime_error_goes_v1():
    """Branch 2.5：NN 推理抛非预期异常 → fallback v1 + warn。"""

    def _broken_infer(_pose):
        raise RuntimeError("CUDA OOM")

    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=True,
        nn_inference=_broken_infer,
    )
    assert result == {"_v1_marker": True, "phases": {"setup": {}}}
    assert method == "v2_nn_fallback_v1"
    assert any(w.code == "phase_seg_v2_nn_failure" for w in warnings)


def test_fallback_low_confidence_goes_v1():
    """Branch 3：NN 推理成功但 confidence < 0.6 → fallback v1。"""
    low_conf_result = _make_v2_result(confidence=0.4)
    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=True,
        nn_inference=lambda _: low_conf_result,
    )
    assert method == "v2_nn_fallback_v1"
    assert any(w.code == "phase_seg_v2_low_confidence" for w in warnings)
    assert result == {"_v1_marker": True, "phases": {"setup": {}}}


def test_fallback_hard_constraint_violation_goes_v1():
    """Branch 4：confidence 够但硬约束 fail → fallback v1。"""
    bad_result = _make_v2_result(
        setup_end=70, top_frame=80, impact_frame=90, confidence=0.9
    )
    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=True,
        nn_inference=lambda _: bad_result,
    )
    assert method == "v2_nn_fallback_v1"
    assert any(w.code == "phase_seg_v2_hard_constraint_fail" for w in warnings)


def test_fallback_nn_success_returns_v2_result():
    """Branch 5：NN 通过 → 返回 V2 结果。"""
    good_result = _make_v2_result()
    result, method, warnings = segment_phases_v2(
        pose_summary={"frames": []},
        v1_fallback=_v1_stub,
        nn_enabled=True,
        nn_inference=lambda _: good_result,
    )
    assert result is good_result
    assert method == "v2_nn"
    assert warnings == []  # 干净路径无 warning


# ============================================================
# 4. _infer_nn raises（W23-W26 实现前的兜底）
# ============================================================


def test_infer_nn_raises_not_ready():
    with pytest.raises(SegmenterNNNotReadyError):
        _infer_nn({"frames": []})


# ============================================================
# 5. segmentation_method 字段（§4.1 JSONB 追加）
# ============================================================


def test_with_segmentation_method_adds_field():
    phase_scores = {"setup": {"score": 80}}
    out = with_segmentation_method(phase_scores, "v2_nn")
    assert out["segmentation_method"] == "v2_nn"
    # 不破坏原 dict
    assert "segmentation_method" not in phase_scores


def test_with_segmentation_method_preserves_existing_keys():
    phase_scores = {"setup": {"score": 80}, "impact": {"score": 75}}
    out = with_segmentation_method(phase_scores, "v1_heuristic")
    assert out["setup"] == {"score": 80}
    assert out["impact"] == {"score": 75}


def test_with_segmentation_method_invalid_value_raises():
    with pytest.raises(ValueError):
        with_segmentation_method({}, "v3_transformer")  # type: ignore[arg-type]


def test_get_segmentation_method_missing_defaults_v1():
    """老报告（无字段）兜底 v1。"""
    assert get_segmentation_method(None) == "v1_heuristic"
    assert get_segmentation_method({}) == "v1_heuristic"
    assert get_segmentation_method({"setup": {}}) == "v1_heuristic"


def test_get_segmentation_method_returns_set_value():
    assert get_segmentation_method({"segmentation_method": "v2_nn"}) == "v2_nn"
    assert (
        get_segmentation_method({"segmentation_method": "v2_nn_fallback_v1"})
        == "v2_nn_fallback_v1"
    )


def test_get_segmentation_method_invalid_value_defaults_v1():
    """脏数据（字段值非枚举内）→ v1 兜底，不抛错。"""
    assert get_segmentation_method({"segmentation_method": "garbage"}) == "v1_heuristic"


# ============================================================
# 6. V2PhaseFrames dataclass 默认行为
# ============================================================


def test_v2_phase_frames_default_method_is_v2_nn():
    r = _make_v2_result()
    assert r.method == "v2_nn"
    assert r.per_phase_confidence == {}
    assert r.engine_warnings == []


def test_v2_phase_frames_supports_per_phase_confidence():
    r = V2PhaseFrames(
        setup_start=0,
        setup_end=10,
        top_frame=50,
        impact_frame=80,
        follow_end=120,
        confidence=0.85,
        per_phase_confidence={"setup": 0.9, "impact": 0.8},
    )
    assert r.per_phase_confidence["setup"] == 0.9
