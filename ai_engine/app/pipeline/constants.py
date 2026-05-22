"""W6-T2：pipeline 常量与元数据。

把所有"会变的阈值 / 权重 / 职业均值 / 映射表"集中在这里，避免散落在 5 个
pipeline 模块里各自写一份。docs/05 §2.5-2.7 和 docs/14 附录 A 是唯一的
真实源（single source of truth），改这里之前先读那两份文档。

设计要点
--------
- 阶段 key 与 `docs/01` / `mock_pipeline` 完全一致（setup/backswing/top/
  downswing/impact/follow_through），前端 `PHASE_ORDER` 依赖这个顺序
- `PHASE_WEIGHTS` 必须与 `ai_engine.mock_pipeline.PHASE_WEIGHTS` **完全相同**，
  否则 mock/real 切换时 overall_score 会跳变，影响用户认知
- 特征的 `ideal_min/max` 来自 docs/05 §2.6 表格；`tolerance` 按 docs/05
  `score_feature` 函数默认 0.5
- 单位约定：角度=度，时间=帧数或比例，距离=像素或归一化比例（MediaPipe 没
  提供绝对距离转换），头部位移等"cm(估)"在 MVP 期用**归一化比例 × 视频高**
  做近似
"""

from __future__ import annotations

from typing import TypedDict

# ============================================================
# 阶段与权重
# ============================================================

PHASE_ORDER: tuple[str, ...] = (
    "setup",
    "backswing",
    "top",
    "downswing",
    "impact",
    "follow_through",
)

# 六阶段的全局权重：和 mock_pipeline.PHASE_WEIGHTS 完全一致。
# 设计逻辑（docs/05 §2.6）：下杆 25% > 上杆 20% > setup/top/impact 各 15% >
# follow_through 10%，突出"下杆质量"是击球核心。
PHASE_WEIGHTS: dict[str, float] = {
    "setup": 0.15,
    "backswing": 0.20,
    "top": 0.15,
    "downswing": 0.25,
    "impact": 0.15,
    "follow_through": 0.10,
}
assert abs(sum(PHASE_WEIGHTS.values()) - 1.0) < 1e-9, "PHASE_WEIGHTS 必须和为 1"

PHASE_LABELS: dict[str, str] = {
    "setup": "站位准备",
    "backswing": "上杆轨迹",
    "top": "顶点位置",
    "downswing": "下杆转换",
    "impact": "击球触球",
    "follow_through": "收杆平衡",
}


# ============================================================
# 特征元数据（15 个核心特征，docs/05 §2.5-2.6）
# ============================================================


class FeatureMeta(TypedDict):
    """单个特征的元数据。

    Fields:
        name:         特征键（跨模块引用，保持 snake_case）
        display_name: 前端展示用中文名
        phase:        评分时归属的阶段 key（与 PHASE_ORDER 对齐）
        unit:         "deg" / "ratio" / "frame" / "norm_px"（归一化比例像素）
        ideal_min:    理想下限（docs/05 §2.6）
        ideal_max:    理想上限
        tolerance:    `score_feature` 的 tolerance（docs/05 默认 0.5）
        weight:       在所属阶段内的权重（0-1，同阶段权重加起来 = 1）
        pro_reference: 职业均值（仅用于 issue 描述文案，不参与评分）
    """

    name: str
    display_name: str
    phase: str
    unit: str
    ideal_min: float
    ideal_max: float
    tolerance: float
    weight: float
    pro_reference: str  # 自由文本，比如 "30°" / "髋先于肩 3-5 帧"


# 15 个特征的完整元数据。顺序与 docs/05 §2.5 表格一致，方便两边对照。
# 权重已经对每个阶段 rebalance，使同一阶段的权重加起来 = 1.0。
FEATURES: tuple[FeatureMeta, ...] = (
    # ---------- setup (2 特征，权重 0.35+0.30=0.65 → rebalance: 0.54 + 0.46) ----------
    {
        "name": "spine_angle_setup",
        "display_name": "准备脊柱前倾角",
        "phase": "setup",
        "unit": "deg",
        "ideal_min": 25.0,
        "ideal_max": 35.0,
        "tolerance": 0.6,
        "weight": 0.54,
        "pro_reference": "30°",
    },
    {
        "name": "knee_flexion_setup",
        "display_name": "准备膝弯角",
        "phase": "setup",
        "unit": "deg",
        "ideal_min": 130.0,
        "ideal_max": 170.0,
        "tolerance": 0.75,
        "weight": 0.46,
        "pro_reference": "155°",
    },
    # ---------- backswing (3 特征，0.35+0.25+0.20=0.80 → 0.44 + 0.31 + 0.25) ----------
    {
        "name": "shoulder_rotation_top",
        "display_name": "肩旋转角（上杆）",
        "phase": "backswing",
        "unit": "deg",
        "ideal_min": 30.0,
        "ideal_max": 95.0,
        "tolerance": 0.65,
        "weight": 0.44,
        "pro_reference": "90°",
    },
    {
        "name": "hip_rotation_top",
        "display_name": "髋旋转角（上杆）",
        "phase": "backswing",
        "unit": "deg",
        "ideal_min": 15.0,
        "ideal_max": 65.0,
        "tolerance": 0.65,
        "weight": 0.31,
        "pro_reference": "45°",
    },
    {
        "name": "x_factor",
        "display_name": "X-Factor",
        "phase": "backswing",
        "unit": "deg",
        "ideal_min": 20.0,
        "ideal_max": 50.0,
        "tolerance": 0.6,
        "weight": 0.25,
        "pro_reference": "45°",
    },
    # ---------- top (2 特征，0.50+0.50=1.00 保持) ----------
    {
        "name": "left_arm_straightness",
        "display_name": "左臂伸直度",
        "phase": "top",
        "unit": "deg",
        "ideal_min": 165.0,
        "ideal_max": 180.0,
        "tolerance": 0.4,
        "weight": 0.50,
        "pro_reference": "175°（接近伸直）",
    },
    {
        "name": "top_wrist_position",
        "display_name": "顶点手腕位置",
        "phase": "top",
        "unit": "ratio",  # 手腕相对于头的垂直位置，>0 表示在头上方
        "ideal_min": 0.10,
        "ideal_max": 0.40,
        "tolerance": 0.5,
        "weight": 0.50,
        "pro_reference": "头顶上方",
    },
    # ---------- downswing (3 特征，0.35+0.30+0.35=1.00 保持) ----------
    {
        "name": "downswing_sequence",
        "display_name": "下杆顺序指标",
        "phase": "downswing",
        "unit": "frame",  # 髋先于肩开始下杆的帧数差
        "ideal_min": 2.0,
        "ideal_max": 7.0,
        "tolerance": 0.6,
        "weight": 0.35,
        "pro_reference": "髋先于肩 3-5 帧",
    },
    {
        "name": "wrist_release_angle",
        "display_name": "手腕释放角",
        "phase": "downswing",
        "unit": "deg",  # Top→Impact 手腕角度变化绝对值
        "ideal_min": 40.0,
        "ideal_max": 140.0,
        "tolerance": 0.55,
        "weight": 0.30,
        "pro_reference": "70°-90°",
    },
    {
        "name": "wrist_release_timing",
        "display_name": "手腕释放时机",
        "phase": "downswing",
        "unit": "ratio",  # 手腕开始释放的时刻 / 下杆总时长
        "ideal_min": 0.45,
        "ideal_max": 0.85,
        "tolerance": 0.55,
        "weight": 0.35,
        "pro_reference": "下杆后 60%",
    },
    # ---------- impact (1 特征，权重 0.50 → rebalance: 1.00) ----------
    {
        "name": "spine_angle_impact_delta",
        "display_name": "击球脊柱前倾角变化",
        "phase": "impact",
        "unit": "deg",  # |setup_spine - impact_spine|
        "ideal_min": 0.0,
        "ideal_max": 18.0,
        "tolerance": 0.55,
        "weight": 1.00,
        "pro_reference": "与准备位偏差 <5°",
    },
    # ---------- 全程 1 特征 (分到 follow_through 评分，但数据源全程) ----------
    {
        "name": "head_lateral_shift",
        "display_name": "头部水平位移",
        "phase": "follow_through",  # docs/05 归"全程"，评分时挂 follow_through
        "unit": "ratio",  # 头部 x 坐标最大 - 最小，归一化比例
        "ideal_min": 0.0,
        "ideal_max": 0.08,  # 约对应 8cm（以视频宽 1m 估）
        "tolerance": 0.5,
        "weight": 0.30,
        "pro_reference": "< 5cm",
    },
    {
        "name": "tempo_ratio",
        "display_name": "挥杆节奏比",
        "phase": "follow_through",  # docs/05 全程特征，归 follow_through 方便评分
        "unit": "ratio",  # 上杆帧数 / 下杆帧数
        "ideal_min": 2.0,
        "ideal_max": 3.8,
        "tolerance": 0.45,
        "weight": 0.25,
        "pro_reference": "3:1",
    },
    {
        "name": "finish_height",
        "display_name": "收杆高度",
        "phase": "follow_through",
        "unit": "ratio",  # 收杆手腕 y 相对于肩的位置，负表示高于肩
        "ideal_min": -0.20,
        "ideal_max": 0.15,
        "tolerance": 0.55,
        "weight": 0.25,
        "pro_reference": "肩上方",
    },
    {
        "name": "finish_balance",
        "display_name": "收杆平衡",
        "phase": "follow_through",
        "unit": "norm_px",  # 收杆最后 10 帧脚踝关键点位置抖动的均值
        "ideal_min": 0.0,
        "ideal_max": 0.02,  # 归一化位置，约 2% 视频高
        "tolerance": 0.5,
        "weight": 0.20,
        "pro_reference": "< 0.02",
    },
)

assert len(FEATURES) == 15, f"FEATURES 必须恰好 15 个，实际 {len(FEATURES)}"

# 每个阶段的特征列表（从 FEATURES 派生，避免重复维护）
FEATURES_BY_PHASE: dict[str, list[FeatureMeta]] = {p: [] for p in PHASE_ORDER}
for _feat in FEATURES:
    FEATURES_BY_PHASE[_feat["phase"]].append(_feat)

# 每阶段权重和必须 = 1.0（score_phase 才不会偏置）
for _phase, _feats in FEATURES_BY_PHASE.items():
    if _feats:
        _s = sum(f["weight"] for f in _feats)
        assert abs(_s - 1.0) < 1e-6, f"phase {_phase} 权重和 {_s}，应为 1.0"


# ============================================================
# Issue 类型定义（docs/14 附录 A · 15 种 MVP 期覆盖）
# ============================================================


class IssueMeta(TypedDict):
    """单个 issue 类型的元数据。"""

    type: str
    name: str
    default_severity: str  # "high" / "medium" / "low"（真实 severity 由 diagnose 动态算）
    description_template: str


ISSUE_TYPES: tuple[IssueMeta, ...] = (
    {
        "type": "casting",
        "name": "抛杆（Casting）",
        "default_severity": "high",
        "description_template": "下杆时手腕过早释放，容易产生右曲球。",
    },
    {
        "type": "over_the_top",
        "name": "由外到内下杆（Over-the-Top）",
        "default_severity": "high",
        "description_template": "下杆路径偏外，容易拉左或切右。",
    },
    {
        "type": "early_extension",
        "name": "提前伸展（Early Extension）",
        "default_severity": "medium",
        "description_template": "下杆时髋部过早前移，破坏脊柱角度。",
    },
    {
        "type": "sway_slide",
        "name": "侧移（Sway/Slide）",
        "default_severity": "medium",
        "description_template": "上杆时重心过度右移，影响一致性。",
    },
    {
        "type": "loss_of_posture",
        "name": "失去身体姿势（Loss of Posture）",
        "default_severity": "low",
        "description_template": "挥杆过程中头部/脊柱角度变化过大，影响击球点稳定。",
    },
    {
        "type": "reverse_spine",
        "name": "反向脊柱角（Reverse Spine）",
        "default_severity": "medium",
        "description_template": "顶点脊柱向目标侧倾斜，容易伤腰。",
    },
    {
        "type": "chicken_wing",
        "name": "鸡翅（Chicken Wing）",
        "default_severity": "medium",
        "description_template": "跟进时左臂过度弯曲，影响击球质量和距离。",
    },
    {
        "type": "sway_lead",
        "name": "下杆侧移（Sway Lead）",
        "default_severity": "medium",
        "description_template": "下杆重心过度左移但髋部未打开，易致拉击。",
    },
    {
        "type": "hanging_back",
        "name": "留身（Hanging Back）",
        "default_severity": "low",
        "description_template": "击球后重心仍偏后脚，无法完成重心转移。",
    },
    {
        "type": "over_rotation",
        "name": "过度转肩（Over Rotation）",
        "default_severity": "low",
        "description_template": "顶点肩旋转超过 100°，可能影响节奏。",
    },
    {
        "type": "under_rotation",
        "name": "转肩不足（Under Rotation）",
        "default_severity": "medium",
        "description_template": "顶点肩旋转不足 75°，力量传递受限。",
    },
    {
        "type": "flat_shoulder",
        "name": "肩平面过平（Flat Shoulder）",
        "default_severity": "low",
        "description_template": "肩旋转平面过水平，上杆路径偏内。",
    },
    {
        "type": "steep_shoulder",
        "name": "肩平面过陡（Steep Shoulder）",
        "default_severity": "low",
        "description_template": "肩旋转平面过陡，上杆路径偏外。",
    },
    {
        "type": "open_stance",
        "name": "开放站位（Open Stance）",
        "default_severity": "low",
        "description_template": "Setup 阶段双脚连线相对目标线偏开过多。",
    },
    {
        "type": "grip_weak",
        "name": "弱握（Weak Grip）",
        "default_severity": "low",
        "description_template": "手腕姿态偏离标准握杆，视频判断置信度较低。",
    },
)

assert len(ISSUE_TYPES) == 15, f"ISSUE_TYPES 必须恰好 15 个，实际 {len(ISSUE_TYPES)}"


# ============================================================
# Issue → Drill 映射（docs/14 附录 A.2）
# ============================================================

# 每个 issue 映射到 1-2 个 drill_id；high severity 的 issue 推 2 条，其余 1 条。
# 这个映射与 `client/src/constants/drillLibrary.ts` 必须保持一致
# （T2-drills 子任务会同步扩充前端 drillLibrary）。
ISSUE_DRILL_MAP: dict[str, list[str]] = {
    "casting": ["drill_towel_arm", "drill_impact_bag"],
    "over_the_top": ["drill_half_swing", "drill_inside_path"],
    "early_extension": ["drill_wall_butt"],
    "sway_slide": ["drill_hip_rotation"],
    "loss_of_posture": ["drill_mirror_spine"],
    "reverse_spine": ["drill_wall_butt"],
    "chicken_wing": ["drill_towel_arm"],
    "sway_lead": ["drill_hip_rotation"],
    "hanging_back": ["drill_weight_shift"],
    "over_rotation": ["drill_backswing_stop"],
    "under_rotation": ["drill_shoulder_turn"],
    "flat_shoulder": ["drill_plane_board"],
    "steep_shoulder": ["drill_plane_board"],
    "open_stance": ["drill_alignment_stick"],
    "grip_weak": ["drill_grip_checkpoint"],
}

assert set(ISSUE_DRILL_MAP.keys()) == {it["type"] for it in ISSUE_TYPES}, (
    "ISSUE_DRILL_MAP 和 ISSUE_TYPES 不同步；检查 docs/14 附录 A"
)

# 推荐算法约束
MAX_RECOMMENDATIONS_PER_ANALYSIS = 3  # docs/01 §4.3


# ============================================================
# 便捷查询函数
# ============================================================


def feature_meta(name: str) -> FeatureMeta:
    """按名字找特征元数据；找不到抛 KeyError（调用方 bug，应该快速失败）。"""
    for f in FEATURES:
        if f["name"] == name:
            return f
    raise KeyError(f"未知特征名：{name}；全集见 constants.FEATURES")


def issue_meta(issue_type: str) -> IssueMeta:
    for it in ISSUE_TYPES:
        if it["type"] == issue_type:
            return it
    raise KeyError(f"未知 issue type：{issue_type}；全集见 constants.ISSUE_TYPES")
