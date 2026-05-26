"""P2-M7-07 · 阶段分割 V2：多信号融合 + V1 fallback 链路骨架。

详 docs/release-notes/p2-m7-07-phase-segmentation-v2-kickoff.md v0.1。

本 PR 范围（W22 起跑前置）
-------------------------
- ✅ 模块骨架 + Fallback 链路（V1 行为冻结）
- ✅ `segmentation_method` 字段语义 + JSONB schema
- ✅ 启发式硬约束 validator（§3.5）
- ✅ 配置项 `M7_V2_SEGMENT_NN_ENABLED` / `M7_V2_SEGMENT_MIN_DURATION_SEC`
- ❌ 实际 NN 推理（W23-W26 训练后接入；本 PR `infer()` raise NotImplementedError）
- ❌ ECS 训练数据 pipeline（W22 单独 PR）
- ❌ 1D CNN 模型实现（W23-W26）

为什么独立模块
--------------
- V1 `phases.py` 行为冻结：测试 / 灰度回滚必须能"切换 router 不改算法"
- V2 NN 模型尚未训练，未来 6 PW 工作；先把 schema + fallback + 硬约束就位，
  W26 训练完只需替换 `_infer_nn()` 实现，无需动 pipeline 集成

V2 选择路径（§3.4 状态机）
---------------------------
1. M7_V2_SEGMENT_NN_ENABLED=False（默认） → 总走 V1
2. NN 推理成功且 confidence >= NN_CONFIDENCE_THRESHOLD 且通过硬约束 → V2_NN
3. NN 推理失败 / 低置信 / 硬约束失败 → fallback V1 + 写 engine_warning
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from app.pipeline.engine_warnings import EngineWarning

log = logging.getLogger("ai_engine.phases_v2")

SegmentationMethod = Literal["v1_heuristic", "v2_nn", "v2_nn_fallback_v1"]

# ============================================================
# 配置常量（kickoff §4.2）
# ============================================================

# 默认关闭；W28 灰度起 ai_engine config 覆盖为 True
M7_V2_SEGMENT_NN_ENABLED_DEFAULT = False
# 一期 MIN_DURATION_SEC = 2.0；V2 降至 1.5 以兼容慢挥（kickoff R-03）
M7_V2_SEGMENT_MIN_DURATION_SEC = 1.5

# NN 接受门槛：低于此 confidence 触发 fallback（§3.4）
NN_CONFIDENCE_THRESHOLD = 0.6

# 硬约束最小帧数：1s @30fps（kickoff §3.5）
HARD_MIN_FRAMES_SETUP_TO_IMPACT = 30


# ============================================================
# 数据结构
# ============================================================


@dataclass
class V2PhaseFrames:
    """V2 NN 输出的六阶段帧边界 + per-阶段 confidence。

    与 V1 `PhaseSegmentResult` 字段语义对齐，但增加 `confidence` 与
    `segmentation_method`，并保留 NN 原始 logits 摘要供 W26 调试用。
    """

    setup_start: int
    setup_end: int
    top_frame: int
    impact_frame: int
    follow_end: int
    confidence: float
    method: SegmentationMethod = "v2_nn"
    per_phase_confidence: dict[str, float] = field(default_factory=dict)
    engine_warnings: list[EngineWarning] = field(default_factory=list)


# ============================================================
# 硬约束 validator（kickoff §3.5）
# ============================================================


def validate_hard_constraints(result: V2PhaseFrames) -> tuple[bool, str | None]:
    """启发式硬约束：
    1. 帧序：setup_end < top_frame < impact_frame < follow_end
    2. 时长：impact_frame - setup_end >= HARD_MIN_FRAMES_SETUP_TO_IMPACT（≥1s @30fps）

    Returns:
        (passed, fail_reason)；passed=True 时 reason=None
    """
    if not (result.setup_end < result.top_frame):
        return False, f"setup_end({result.setup_end}) >= top_frame({result.top_frame})"
    if not (result.top_frame < result.impact_frame):
        return False, f"top_frame({result.top_frame}) >= impact_frame({result.impact_frame})"
    if not (result.impact_frame < result.follow_end):
        return False, f"impact_frame({result.impact_frame}) >= follow_end({result.follow_end})"
    if result.impact_frame - result.setup_end < HARD_MIN_FRAMES_SETUP_TO_IMPACT:
        return False, (
            f"setup→impact={result.impact_frame - result.setup_end} frames "
            f"< {HARD_MIN_FRAMES_SETUP_TO_IMPACT}"
        )
    return True, None


# ============================================================
# NN 推理（W23-W26 实现；本 PR 留接口 + raise）
# ============================================================


class SegmenterNNNotReadyError(NotImplementedError):
    """W23-W26 NN 模型训练完成前调用 _infer_nn 会触发此异常。

    pipeline 必须捕获并 fallback 到 V1（§3.4 fallback 链路）。
    """


def _infer_nn(pose_summary: object) -> V2PhaseFrames:
    """NN 推理桩，W23-W26 训练完成后替换实现。

    Args:
        pose_summary: 任意结构（W23 定义具体 schema 后替换）

    Raises:
        SegmenterNNNotReadyError：模型未就绪
    """
    raise SegmenterNNNotReadyError(
        "P2-M7-07 NN 模型 W23-W26 训练中；本 PR 仅提供 fallback 链路骨架"
    )


# ============================================================
# 主入口：fallback 链路（kickoff §3.4）
# ============================================================


def segment_phases_v2(
    pose_summary: object,
    *,
    v1_fallback: Callable[[object], object],
    nn_enabled: bool = M7_V2_SEGMENT_NN_ENABLED_DEFAULT,
    nn_inference: Callable[[object], V2PhaseFrames] = _infer_nn,
) -> tuple[object, SegmentationMethod, list[EngineWarning]]:
    """V2 主入口：NN 优先 + V1 fallback。

    Args:
        pose_summary: PoseResult 或预提取摘要（由调用方决定 schema）
        v1_fallback: V1 启发式入口（避免本模块直接依赖 phases.py，便于单测）
        nn_enabled: 总闸；False → 直接走 V1
        nn_inference: NN 推理函数注入点（单测时可 mock；默认 raise NotImplementedError）

    Returns:
        (result, method, engine_warnings)
        - result: V1 返回类型 或 V2PhaseFrames
        - method: 'v1_heuristic' / 'v2_nn' / 'v2_nn_fallback_v1'
        - engine_warnings: 触发的诊断信息列表
    """
    warnings: list[EngineWarning] = []

    # Branch 1：总闸关闭 → V1
    if not nn_enabled:
        v1_result = v1_fallback(pose_summary)
        return v1_result, "v1_heuristic", warnings

    # Branch 2：NN 推理
    try:
        nn_result = nn_inference(pose_summary)
    except SegmenterNNNotReadyError:
        # 模型未就绪：不算异常（W22 起跑前置正常状态）
        warnings.append(
            EngineWarning(
                code="phase_seg_nn_not_ready",
                level="info",
                detail="NN model not ready; fallback to V1 heuristic",
            )
        )
        v1_result = v1_fallback(pose_summary)
        return v1_result, "v1_heuristic", warnings
    except Exception as exc:  # noqa: BLE001 — 故意宽捕获保证 fallback 链路鲁棒
        log.warning("phase_seg_v2 nn inference failed", exc_info=exc)
        warnings.append(
            EngineWarning(
                code="phase_seg_v2_nn_failure",
                level="warn",
                detail=f"NN inference failed ({type(exc).__name__}); fallback v1",
            )
        )
        v1_result = v1_fallback(pose_summary)
        return v1_result, "v2_nn_fallback_v1", warnings

    # Branch 3：NN 置信度判定
    if nn_result.confidence < NN_CONFIDENCE_THRESHOLD:
        warnings.append(
            EngineWarning(
                code="phase_seg_v2_low_confidence",
                level="warn",
                detail=(
                    f"NN confidence={nn_result.confidence:.2f} "
                    f"< {NN_CONFIDENCE_THRESHOLD}; fallback v1"
                ),
            )
        )
        v1_result = v1_fallback(pose_summary)
        return v1_result, "v2_nn_fallback_v1", warnings

    # Branch 4：硬约束校验
    passed, reason = validate_hard_constraints(nn_result)
    if not passed:
        warnings.append(
            EngineWarning(
                code="phase_seg_v2_hard_constraint_fail",
                level="warn",
                detail=f"NN result rejected: {reason}; fallback v1",
            )
        )
        v1_result = v1_fallback(pose_summary)
        return v1_result, "v2_nn_fallback_v1", warnings

    # Branch 5：NN 通过 → 返回 V2
    return nn_result, "v2_nn", warnings


# ============================================================
# 字段语义辅助（kickoff §4.1 JSONB 追加）
# ============================================================


def with_segmentation_method(
    phase_scores: dict, method: SegmentationMethod
) -> dict:
    """把 `segmentation_method` 字段写进 phase_scores JSONB（无 migration）。

    保证：
    - 原 dict 不被破坏（返回新 dict）
    - method 取值受 SegmentationMethod literal 约束
    """
    if method not in ("v1_heuristic", "v2_nn", "v2_nn_fallback_v1"):
        raise ValueError(f"invalid segmentation_method: {method!r}")
    out = dict(phase_scores)
    out["segmentation_method"] = method
    return out


def get_segmentation_method(phase_scores: dict | None) -> SegmentationMethod:
    """从 phase_scores JSONB 反查 segmentation_method；缺失 → v1_heuristic 兜底。"""
    if not phase_scores:
        return "v1_heuristic"
    method = phase_scores.get("segmentation_method", "v1_heuristic")
    if method not in ("v1_heuristic", "v2_nn", "v2_nn_fallback_v1"):
        return "v1_heuristic"
    return method  # type: ignore[return-value]
