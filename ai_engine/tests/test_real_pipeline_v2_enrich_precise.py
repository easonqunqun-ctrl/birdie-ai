"""P2-W9 ENG-D · ``_enrich_v2`` **精算版**专属单测.

W7 的 ``test_real_pipeline_v2_enrich.py`` 在统一 visibility 场景下仍能 pass（公式向下
兼容）；本文件覆盖 W9 **新增的「按 landmark 子矩阵 + 阈值距离实算」分支**：

- 同 mean_visibility 下，不同 feature 的 landmark 子集 visibility 差异 → 出不同 confidence
- ``_compute_threshold_distance`` 各 operator + ideal_max-ideal_min scale 归一
- ``_issue_threshold_distance`` 多 AND 条件取 min（短板原则）
- issue 偏离阈值更远 → confidence 更高
- finish_balance 只看脚踝、head_lateral_shift 只看 NOSE 等 landmark-局部失明场景
"""

from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.confidence import (
    ISSUE_CONFIRMED_THRESHOLD,
    ISSUE_LEANING_THRESHOLD,
)
from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_KNEE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_KNEE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)
from app.pipeline.real_pipeline import PipelineCtx
from app.pipeline.real_pipeline_v2 import (
    _STATIC_FEATURE_LANDMARKS,
    _compute_threshold_distance,
    _enrich_v2,
    _feature_phase_frames,
    _issue_threshold_distance,
    _landmark_indices_for,
    _lead_landmark_indices,
    _visibility_sub_for_feature,
    reset_caches,
)
from app.pipeline.rule_engine import RuleCondition, RuleEngine
from app.schemas import AnalyzeResult, IssueItem


@pytest.fixture(autouse=True)
def _reset():
    reset_caches()


# ---------- 通用 fixture ----------


def _phases_right_handed(num_frames: int = 60) -> PhaseSegmentResult:
    """构造一个 60 帧、右撇子（lead=left）、phase 边界宽裕的 PhaseSegmentResult."""
    return PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(start_frame=0, end_frame=4, key_frame=2),
            "backswing": PhaseInfo(start_frame=5, end_frame=24, key_frame=15),
            "top": PhaseInfo(start_frame=25, end_frame=25, key_frame=25),
            "downswing": PhaseInfo(start_frame=26, end_frame=34, key_frame=30),
            "impact": PhaseInfo(start_frame=35, end_frame=35, key_frame=35),
            "follow_through": PhaseInfo(start_frame=36, end_frame=59, key_frame=45),
        },
        top_frame=25,
        impact_frame=35,
        swing_start=5,
        swing_end=55,
        handedness="right",
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        fps=30.0,
    )


def _phases_left_handed(num_frames: int = 60) -> PhaseSegmentResult:
    p = _phases_right_handed(num_frames)
    p.handedness = "left"
    p.lead_wrist_idx = LANDMARK_RIGHT_WRIST
    p.lead_shoulder_idx = LANDMARK_RIGHT_SHOULDER
    return p


def _make_pose(num_frames: int = 60, vis: float | np.ndarray = 0.9) -> PoseResult:
    if isinstance(vis, (int, float)):
        v = np.full((num_frames, 33), float(vis), dtype=np.float32)
    else:
        v = vis
    return PoseResult(
        keypoints=np.zeros((num_frames, 33, 3), dtype=np.float32),
        visibility=v,
        valid_mask=np.ones(num_frames, dtype=bool),
        num_frames=num_frames,
        fps=30.0,
    )


# ============================================================
# Layer 1：_landmark_indices_for / _lead_landmark_indices
# ============================================================


def test_lead_landmark_indices_returns_none_for_static_features():
    phases = _phases_right_handed()
    for name in (
        "spine_angle_setup",
        "knee_flexion_setup",
        "x_factor",
        "head_lateral_shift",
        "finish_balance",
    ):
        assert _lead_landmark_indices(name, phases) is None


def test_lead_landmark_indices_right_handed_uses_left_wrist_elbow():
    phases = _phases_right_handed()
    assert _lead_landmark_indices("top_wrist_position", phases) == [
        LANDMARK_NOSE, LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER,
    ]
    assert _lead_landmark_indices("wrist_release_angle", phases) == [
        LANDMARK_LEFT_WRIST, LANDMARK_LEFT_ELBOW,
    ]
    assert _lead_landmark_indices("tempo_ratio", phases) == [LANDMARK_LEFT_WRIST]
    assert _lead_landmark_indices("finish_height", phases) == [
        LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER,
    ]


def test_lead_landmark_indices_left_handed_uses_right_wrist_elbow():
    phases = _phases_left_handed()
    assert _lead_landmark_indices("wrist_release_angle", phases) == [
        LANDMARK_RIGHT_WRIST, LANDMARK_RIGHT_ELBOW,
    ]
    assert _lead_landmark_indices("finish_height", phases) == [
        LANDMARK_RIGHT_WRIST, LANDMARK_RIGHT_SHOULDER,
    ]


def test_landmark_indices_for_falls_back_to_static_table():
    phases = _phases_right_handed()
    assert set(_landmark_indices_for("finish_balance", phases)) == {
        LANDMARK_LEFT_ANKLE, LANDMARK_RIGHT_ANKLE,
    }
    assert set(_landmark_indices_for("head_lateral_shift", phases)) == {LANDMARK_NOSE}
    assert set(_landmark_indices_for("knee_flexion_setup", phases)) == {
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
        LANDMARK_LEFT_KNEE, LANDMARK_RIGHT_KNEE,
        LANDMARK_LEFT_ANKLE, LANDMARK_RIGHT_ANKLE,
    }


def test_landmark_indices_for_unknown_feature_returns_empty():
    phases = _phases_right_handed()
    assert _landmark_indices_for("not_a_feature_xyz", phases) == []


def test_static_table_covers_all_phase_features_except_lead_dependent():
    """W9 静态表 + lead 动态表合起来应覆盖 ``constants.FEATURES`` 全部 15 项."""
    from app.pipeline.constants import FEATURES

    lead_features = {
        "top_wrist_position",
        "wrist_release_angle",
        "wrist_release_timing",
        "tempo_ratio",
        "finish_height",
    }
    expected_static = {f["name"] for f in FEATURES} - lead_features
    assert set(_STATIC_FEATURE_LANDMARKS.keys()) == expected_static


# ============================================================
# Layer 1：_feature_phase_frames
# ============================================================


def test_phase_frames_setup_window_around_key_frame():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("spine_angle_setup", phases, num_frames=60)
    assert frames == [0, 1, 2, 3, 4]  # key=2 ± 2 = [0..4]


def test_phase_frames_clamps_to_valid_range():
    phases = _phases_right_handed()
    # num_frames=3 → key_frame=2 ± 2 → 应 clamp 到 [0, 2]
    frames = _feature_phase_frames("spine_angle_setup", phases, num_frames=3)
    assert frames == [0, 1, 2]


def test_phase_frames_top_features_use_top_window():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("left_arm_straightness", phases, num_frames=60)
    assert frames == [23, 24, 25, 26, 27]


def test_phase_frames_crosses_setup_top_for_rotation():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("x_factor", phases, num_frames=60)
    # setup window [0..4] + top window [23..27]
    assert frames == [0, 1, 2, 3, 4, 23, 24, 25, 26, 27]


def test_phase_frames_downswing_range():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("downswing_sequence", phases, num_frames=60)
    assert frames == list(range(26, 35))  # 26..34 inclusive


def test_phase_frames_wrist_release_spans_top_to_impact():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("wrist_release_angle", phases, num_frames=60)
    assert frames == list(range(25, 36))  # 25..35


def test_phase_frames_head_lateral_shift_uses_swing_range():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("head_lateral_shift", phases, num_frames=60)
    assert frames == list(range(5, 56))


def test_phase_frames_finish_balance_takes_last_10_frames():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("finish_balance", phases, num_frames=60)
    # ft.end=59, tail_start = max(36, 59-9) = 50；50..59
    assert frames == list(range(50, 60))


def test_phase_frames_finish_height_window():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("finish_height", phases, num_frames=60)
    assert frames == [43, 44, 45, 46, 47]


def test_phase_frames_zero_num_frames_returns_empty():
    phases = _phases_right_handed()
    assert _feature_phase_frames("spine_angle_setup", phases, num_frames=0) == []


def test_phase_frames_unknown_feature_falls_back_to_swing():
    phases = _phases_right_handed()
    frames = _feature_phase_frames("not_a_feature", phases, num_frames=60)
    assert frames == list(range(5, 56))


# ============================================================
# Layer 1：_visibility_sub_for_feature 端到端
# ============================================================


def test_visibility_sub_shape_matches_frames_x_landmarks():
    pose = _make_pose(num_frames=60, vis=0.8)
    phases = _phases_right_handed()
    sub = _visibility_sub_for_feature(pose, phases, "spine_angle_setup")
    # frames=5, landmarks=4
    assert len(sub) == 5
    assert all(len(row) == 4 for row in sub)
    assert all(abs(v - 0.8) < 1e-5 for row in sub for v in row)


def test_visibility_sub_picks_correct_landmarks_for_finish_balance():
    """只挑脚踝两点，不应被肩腕 visibility 影响."""
    vis = np.full((60, 33), 0.2, dtype=np.float32)  # 默认低
    # 把脚踝两点提到 0.95
    vis[:, LANDMARK_LEFT_ANKLE] = 0.95
    vis[:, LANDMARK_RIGHT_ANKLE] = 0.95
    pose = _make_pose(num_frames=60, vis=vis)
    phases = _phases_right_handed()
    sub = _visibility_sub_for_feature(pose, phases, "finish_balance")
    assert sub  # 非空
    for row in sub:
        for v in row:
            assert v == pytest.approx(0.95, abs=1e-5)


def test_visibility_sub_returns_empty_on_zero_frame_pose():
    pose = _make_pose(num_frames=0, vis=0.9)
    phases = _phases_right_handed()
    assert _visibility_sub_for_feature(pose, phases, "spine_angle_setup") == []


def test_visibility_sub_returns_empty_on_none_phases():
    pose = _make_pose(num_frames=30, vis=0.9)
    assert _visibility_sub_for_feature(pose, None, "spine_angle_setup") == []


def test_visibility_sub_returns_empty_on_unknown_feature():
    pose = _make_pose(num_frames=60, vis=0.9)
    phases = _phases_right_handed()
    # unknown feature → landmark idx 列表为 [] → sub 也是 []
    assert _visibility_sub_for_feature(pose, phases, "unknown_feature_xyz") == []


# ============================================================
# Layer 2：_compute_threshold_distance
# ============================================================


def test_td_greater_operator_hits_when_value_exceeds_threshold():
    """early_extension: spine_angle_impact_delta > 8.0, scale = 18-0 = 18."""
    cond = RuleCondition(feature="spine_angle_impact_delta", operator=">", threshold=8.0)
    # value=20 → raw = 12 → td = 12/18 ≈ 0.667
    td = _compute_threshold_distance(20.0, cond)
    assert td == pytest.approx(12.0 / 18.0, abs=1e-3)


def test_td_greater_operator_zero_when_value_below_threshold():
    """触发方向相反（>: value<thr）→ td=0，避免浮报."""
    cond = RuleCondition(feature="spine_angle_impact_delta", operator=">", threshold=8.0)
    assert _compute_threshold_distance(5.0, cond) == 0.0


def test_td_less_operator_hits_when_value_below_threshold():
    """casting: wrist_release_timing < 0.40, scale = 0.85-0.45 = 0.40."""
    cond = RuleCondition(feature="wrist_release_timing", operator="<", threshold=0.40)
    # value=0.20 → signed = -(0.20-0.40) = 0.20 → td = 0.20/0.40 = 0.5
    td = _compute_threshold_distance(0.20, cond)
    assert td == pytest.approx(0.5, abs=1e-3)


def test_td_less_operator_zero_when_value_above_threshold():
    cond = RuleCondition(feature="wrist_release_timing", operator="<", threshold=0.40)
    assert _compute_threshold_distance(0.50, cond) == 0.0


def test_td_clamps_to_5_max():
    """value 远超 threshold → td 上限 5（σ(5)≈0.99 已饱和）."""
    cond = RuleCondition(feature="head_lateral_shift", operator=">", threshold=0.0)
    # head_lateral_shift scale = 0.08-0 = 0.08；value=10 → 10/0.08 = 125 → clamp 5
    assert _compute_threshold_distance(10.0, cond) == 5.0


def test_td_unknown_feature_uses_scale_1():
    cond = RuleCondition(feature="not_a_real_feature", operator=">", threshold=5.0)
    # scale=1，value=7 → td = 2.0
    assert _compute_threshold_distance(7.0, cond) == pytest.approx(2.0, abs=1e-3)


def test_td_supports_gte_lte_operators():
    cond_gte = RuleCondition(feature="spine_angle_impact_delta", operator=">=", threshold=8.0)
    cond_lte = RuleCondition(feature="spine_angle_impact_delta", operator="<=", threshold=8.0)
    assert _compute_threshold_distance(20.0, cond_gte) > 0
    assert _compute_threshold_distance(5.0, cond_lte) > 0


# ============================================================
# Layer 2：_issue_threshold_distance 多 AND 取 min
# ============================================================


def test_issue_td_single_condition_uses_that_value():
    from app.pipeline.rule_engine import Rule

    rule = Rule(
        name="casting",
        display_name_key="issues.casting.title",
        conditions=(
            RuleCondition(feature="wrist_release_timing", operator="<", threshold=0.40),
        ),
    )
    features = {"wrist_release_timing": 0.20}
    td = _issue_threshold_distance(rule, features)
    # 0.20/0.40 = 0.5
    assert td == pytest.approx(0.5, abs=1e-3)


def test_issue_td_multi_and_takes_min_short_board():
    """loss_of_posture 双条件 AND：取最小 td."""
    from app.pipeline.rule_engine import Rule

    rule = Rule(
        name="loss_of_posture",
        display_name_key="issues.loss_of_posture.title",
        conditions=(
            RuleCondition(feature="spine_angle_impact_delta", operator=">", threshold=5.0),
            RuleCondition(feature="head_lateral_shift", operator=">", threshold=0.08),
        ),
    )
    # cond1: value=20, thr=5, scale=18 → td=15/18≈0.833
    # cond2: value=0.085, thr=0.08, scale=0.08 → td=0.005/0.08≈0.0625
    # min=0.0625（head 那条是"临界"，issue 整体不够确信）
    features = {"spine_angle_impact_delta": 20.0, "head_lateral_shift": 0.085}
    td = _issue_threshold_distance(rule, features)
    assert td == pytest.approx(0.0625, abs=1e-3)


def test_issue_td_missing_feature_treated_as_zero():
    from app.pipeline.rule_engine import Rule

    rule = Rule(
        name="early_extension",
        display_name_key="issues.early_extension.title",
        conditions=(
            RuleCondition(feature="spine_angle_impact_delta", operator=">", threshold=5.0),
        ),
    )
    td = _issue_threshold_distance(rule, features={})
    assert td == 0.0


def test_issue_td_empty_rule_returns_zero():
    from app.pipeline.rule_engine import Rule

    rule = Rule(
        name="dummy", display_name_key="x", conditions=(),
    )
    assert _issue_threshold_distance(rule, {}) == 0.0


# ============================================================
# Layer 3：_enrich_v2 端到端（W9 精算路径）
# ============================================================


def _make_ctx_with_features(pose, phases, features) -> PipelineCtx:
    return PipelineCtx(
        pose_result=pose,
        phases=phases,
        features=features,
        quality_warnings=[],
        fps=30.0,
    )


def _make_result(issue_types: list[str]) -> AnalyzeResult:
    return AnalyzeResult(
        analysis_id="t",
        status="completed",
        overall_score=70,
        issues=[
            IssueItem(type=t, name=t, severity="medium", description=t)
            for t in issue_types
        ],
        recommendations=[],
    )


def test_enrich_v2_feature_conf_diverges_when_landmarks_have_different_visibility():
    """脚踝可见、肩腕被遮挡时：finish_balance 应高 confidence，
    spine_angle_setup / left_arm_straightness 应低 confidence。"""
    vis = np.full((60, 33), 0.2, dtype=np.float32)
    for lm in (LANDMARK_LEFT_ANKLE, LANDMARK_RIGHT_ANKLE):
        vis[:, lm] = 0.95
    pose = _make_pose(num_frames=60, vis=vis)
    phases = _phases_right_handed()
    features = {
        "finish_balance": 0.01,
        "spine_angle_setup": 30.0,
        "left_arm_straightness": 175.0,
    }
    ctx = _make_ctx_with_features(pose, phases, features)
    result = _make_result([])
    _enrich_v2(result, ctx)

    # finish_balance 只看脚踝：应高
    assert result.feature_confidences["finish_balance"] >= 0.85
    # spine_angle_setup 看肩 + 髋（视频里这些 visibility=0.2）：应低（vfr=0）
    assert result.feature_confidences["spine_angle_setup"] <= 0.1
    assert result.feature_confidences["left_arm_straightness"] <= 0.1


def test_enrich_v2_issue_confidence_higher_when_feature_far_from_threshold():
    """spine_angle_impact_delta = 30（远超 threshold 8）→ issue 应 confirmed；
    = 8.5（刚过 threshold）→ 应 leaning / hidden."""
    pose = _make_pose(num_frames=60, vis=0.95)
    phases = _phases_right_handed()

    # case A: 远超
    ctx_a = _make_ctx_with_features(
        pose, phases, {"spine_angle_impact_delta": 30.0}
    )
    result_a = _make_result(["early_extension"])
    _enrich_v2(result_a, ctx_a)
    conf_a = result_a.issues[0].confidence

    # case B: 临界
    ctx_b = _make_ctx_with_features(
        pose, phases, {"spine_angle_impact_delta": 8.5}
    )
    result_b = _make_result(["early_extension"])
    _enrich_v2(result_b, ctx_b)
    conf_b = result_b.issues[0].confidence

    assert conf_a is not None and conf_b is not None
    # 公式：feat_avg × (0.5 + 0.5σ(td))；feat_avg 两次相同（visibility 一致）
    # A: td=22/18≈1.22 → σ(1.22)≈0.772 → factor=0.886 → conf≈0.95×0.886≈0.84
    # B: td=0.5/18≈0.028 → σ(0.028)≈0.507 → factor=0.754 → conf≈0.95×0.754≈0.72
    assert conf_a > conf_b
    assert conf_a > ISSUE_LEANING_THRESHOLD  # 至少 leaning
    assert conf_b > ISSUE_LEANING_THRESHOLD  # 也是 leaning（feat_avg 高）


def test_enrich_v2_short_board_drops_issue_confidence_for_multi_condition():
    """loss_of_posture 双条件，其中一个仅临界：min td 拖低 issue confidence."""
    pose = _make_pose(num_frames=60, vis=0.95)
    phases = _phases_right_handed()
    # spine_angle 远超 5（→td 大），head_lateral_shift 仅 0.081（→td 小）
    features = {
        "spine_angle_impact_delta": 20.0,
        "head_lateral_shift": 0.081,
    }
    ctx = _make_ctx_with_features(pose, phases, features)
    result = _make_result(["loss_of_posture"])
    _enrich_v2(result, ctx)

    conf_short = result.issues[0].confidence

    # 对照：两个条件都远超
    features2 = {
        "spine_angle_impact_delta": 20.0,
        "head_lateral_shift": 0.30,
    }
    ctx2 = _make_ctx_with_features(pose, phases, features2)
    result2 = _make_result(["loss_of_posture"])
    _enrich_v2(result2, ctx2)
    conf_both = result2.issues[0].confidence

    assert conf_short is not None and conf_both is not None
    assert conf_both > conf_short


def test_enrich_v2_unknown_v1_issue_uses_mean_vis_fallback():
    pose = _make_pose(num_frames=30, vis=0.7)
    phases = _phases_right_handed()
    ctx = _make_ctx_with_features(pose, phases, {"x_factor": 80.0})
    result = _make_result(["v1_unknown_issue_xyz"])
    _enrich_v2(result, ctx)
    # 不在 YAML rule 表 → conf = mean_vis = 0.7
    assert result.issues[0].confidence == pytest.approx(0.7, abs=1e-3)


def test_enrich_v2_zero_visibility_yields_zero_feature_conf_but_no_crash():
    """所有 visibility=0 → feature confidence=0 → analysis_confidence=0 + retake."""
    pose = _make_pose(num_frames=30, vis=0.0)
    phases = _phases_right_handed()
    ctx = _make_ctx_with_features(
        pose, phases, {"spine_angle_impact_delta": 20.0}
    )
    result = _make_result(["early_extension"])
    _enrich_v2(result, ctx)
    assert result.feature_confidences["spine_angle_impact_delta"] == 0.0
    assert result.analysis_confidence == 0.0
    assert result.issues[0].confidence == 0.0
    assert result.issues[0].confidence_tier == "hidden"


def test_enrich_v2_handedness_left_uses_right_wrist_for_wrist_features():
    """左撇子：wrist_release_timing 应取 RIGHT_WRIST 子矩阵."""
    vis = np.full((60, 33), 0.2, dtype=np.float32)
    # 把 RIGHT_WRIST + RIGHT_ELBOW 提高
    vis[:, LANDMARK_RIGHT_WRIST] = 0.95
    vis[:, LANDMARK_RIGHT_ELBOW] = 0.95
    pose = _make_pose(num_frames=60, vis=vis)
    phases = _phases_left_handed()
    ctx = _make_ctx_with_features(pose, phases, {"wrist_release_timing": 0.30})
    result = _make_result([])
    _enrich_v2(result, ctx)
    # 取的是 right wrist + right elbow（lead），mean=0.95
    assert result.feature_confidences["wrist_release_timing"] >= 0.85


def test_enrich_v2_handedness_left_uses_right_wrist_low_when_left_visible():
    """对照：同样视频里 LEFT_WRIST 高、RIGHT_WRIST 低 → 左撇子下 confidence 应低."""
    vis = np.full((60, 33), 0.2, dtype=np.float32)
    vis[:, LANDMARK_LEFT_WRIST] = 0.95
    vis[:, LANDMARK_LEFT_ELBOW] = 0.95
    pose = _make_pose(num_frames=60, vis=vis)
    phases = _phases_left_handed()  # lead=right
    ctx = _make_ctx_with_features(pose, phases, {"wrist_release_timing": 0.30})
    result = _make_result([])
    _enrich_v2(result, ctx)
    # 取 right wrist+elbow（实际 vis=0.2）→ low
    assert result.feature_confidences["wrist_release_timing"] <= 0.1
