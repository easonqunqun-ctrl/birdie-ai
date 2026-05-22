"""W6 真实姿态分析 pipeline 模块。

完成度：
  - T1: `preprocess` + `pose`
  - T2: `constants` / `phases` / `features` / `scoring` / `diagnose` / `recommend` / `real_pipeline`
  - T3: `visualize`（待实现）
"""

from app.pipeline.constants import (
    FEATURES,
    FEATURES_BY_PHASE,
    ISSUE_DRILL_MAP,
    ISSUE_TYPES,
    MAX_RECOMMENDATIONS_PER_ANALYSIS,
    PHASE_LABELS,
    PHASE_ORDER,
    PHASE_WEIGHTS,
    feature_meta,
    issue_meta,
)
from app.pipeline.diagnose import (
    MIN_DISPLAY_CONFIDENCE,
    DiagnosedIssue,
    diagnose,
)
from app.pipeline.features import extract_features
from app.pipeline.phases import (
    MIN_MOTION_SPEED,
    MIN_SWING_FRAMES,
    PhaseInfo,
    PhaseSegmentResult,
    segment_phases,
)
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
    NUM_LANDMARKS,
    PoseResult,
    estimate_poses,
)
from app.pipeline.scoring import (
    score_all_phases,
    score_feature,
    score_overall,
    score_phase,
    weakest_phase,
)

# 重依赖（preprocess / real_pipeline / visualize / recommend→schemas）延迟导入，
# 避免 ECS 回归等仅需 scoring 子链路的场景拉起 cv2 / pydantic / minio。
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "MAX_DURATION_SEC": ("app.pipeline.preprocess", "MAX_DURATION_SEC"),
    "MAX_FRAME_LOSS_RATIO": ("app.pipeline.preprocess", "MAX_FRAME_LOSS_RATIO"),
    "MIN_CLARITY_SCORE": ("app.pipeline.preprocess", "MIN_CLARITY_SCORE"),
    "MIN_DURATION_SEC": ("app.pipeline.preprocess", "MIN_DURATION_SEC"),
    "TARGET_FPS": ("app.pipeline.preprocess", "TARGET_FPS"),
    "TARGET_SHORT_SIDE": ("app.pipeline.preprocess", "TARGET_SHORT_SIDE"),
    "PreprocessResult": ("app.pipeline.preprocess", "PreprocessResult"),
    "preprocess_video": ("app.pipeline.preprocess", "preprocess_video"),
    "run_real_analysis": ("app.pipeline.real_pipeline", "run_real_analysis"),
    "recommend": ("app.pipeline.recommend", "recommend"),
    "VisualizeArtifacts": ("app.pipeline.visualize", "VisualizeArtifacts"),
    "dump_pose_parquet": ("app.pipeline.visualize", "dump_pose_parquet"),
    "extract_issue_keyframes": ("app.pipeline.visualize", "extract_issue_keyframes"),
    "extract_keyframe": ("app.pipeline.visualize", "extract_keyframe"),
    "render_skeleton_video": ("app.pipeline.visualize", "render_skeleton_video"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = target
    import importlib

    mod = importlib.import_module(module_path)
    val = getattr(mod, attr)
    globals()[name] = val
    return val


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))

__all__ = [
    # constants
    "FEATURES",
    "FEATURES_BY_PHASE",
    "ISSUE_DRILL_MAP",
    "ISSUE_TYPES",
    "MAX_RECOMMENDATIONS_PER_ANALYSIS",
    "PHASE_LABELS",
    "PHASE_ORDER",
    "PHASE_WEIGHTS",
    "feature_meta",
    "issue_meta",
    # diagnose
    "DiagnosedIssue",
    "MIN_DISPLAY_CONFIDENCE",
    "diagnose",
    # features
    "extract_features",
    # phases
    "MIN_MOTION_SPEED",
    "MIN_SWING_FRAMES",
    "PhaseInfo",
    "PhaseSegmentResult",
    "segment_phases",
    # pose
    "LANDMARK_LEFT_ANKLE",
    "LANDMARK_LEFT_ELBOW",
    "LANDMARK_LEFT_HIP",
    "LANDMARK_LEFT_KNEE",
    "LANDMARK_LEFT_SHOULDER",
    "LANDMARK_LEFT_WRIST",
    "LANDMARK_NOSE",
    "LANDMARK_RIGHT_ANKLE",
    "LANDMARK_RIGHT_ELBOW",
    "LANDMARK_RIGHT_HIP",
    "LANDMARK_RIGHT_KNEE",
    "LANDMARK_RIGHT_SHOULDER",
    "LANDMARK_RIGHT_WRIST",
    "NUM_LANDMARKS",
    "PoseResult",
    "estimate_poses",
    # preprocess
    "MAX_DURATION_SEC",
    "MAX_FRAME_LOSS_RATIO",
    "MIN_CLARITY_SCORE",
    "MIN_DURATION_SEC",
    "PreprocessResult",
    "TARGET_FPS",
    "TARGET_SHORT_SIDE",
    "preprocess_video",
    # real pipeline
    "run_real_analysis",
    # recommend
    "recommend",
    # visualize
    "VisualizeArtifacts",
    "dump_pose_parquet",
    "extract_issue_keyframes",
    "extract_keyframe",
    "render_skeleton_video",
    # scoring
    "score_all_phases",
    "score_feature",
    "score_overall",
    "score_phase",
    "weakest_phase",
]
