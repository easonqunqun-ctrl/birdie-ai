"""P2-M7-11 · 推杆 mode 常量（特征 meta + 阶段/特征权重）。

详 ``docs/release-notes/p2-m7-11-putting-pipeline-kickoff.md`` §3。上游真源 docs/23 §3.11。

与一期 full_swing 的关系
------------------------
- **完全独立**：putting 自带 4 个专属特征与 4 阶段，不复用 full_swing 的 15 特征/6 阶段。
- 共享的是更底层的视频读取 + MediaPipe pose（keypoints 仍是 ``(F, 33, 3)`` 归一化坐标）。

单位口径（重要）
----------------
kickoff §3.2 草案用 px 阈值（如 ``<5px`` / ``<100px²``），但本 pipeline 自一期起统一用
**MediaPipe 归一化坐标 [0,1]**（features.py 同口径）。因此本表 ideal 阈值按归一化重写，
为 **v0.1 占位**，待 ECS putting 标定（kickoff AC-3：与教练人评 r≥0.7）回填。
"""

from __future__ import annotations

from typing import TypedDict

# 4 阶段（kickoff §3.3）：setup → backstroke → impact → follow
PUTTING_PHASE_ORDER: list[str] = ["setup", "backstroke", "impact", "follow"]


class PuttingFeatureMeta(TypedDict):
    name: str
    display_name: str
    phase: str
    unit: str
    ideal_min: float
    ideal_max: float
    tolerance: float
    weight: float
    # 是否「越小越好」单边特征（稳定度类）；scoring W23 据此处理单边评分语义
    lower_is_better: bool


# 4 个推杆专属特征（kickoff §3.2）。weight 之和 = 1.0（= PUTTING_FEATURE_WEIGHTS）。
# ideal 为归一化 v0.1 占位（见模块 docstring「单位口径」）。
PUTTING_FEATURES: list[PuttingFeatureMeta] = [
    {
        "name": "pendulum_stability",
        "display_name": "钟摆稳定度",
        "phase": "backstroke",  # 整个挥动窗口，归到 backstroke 便于展示
        "unit": "norm_var",  # 双肩中点 y 在整段挥动的方差（归一化²）
        "ideal_min": 0.0,
        "ideal_max": 0.0004,  # ~ (0.02 归一化抖动)²，v0.1 占位
        "tolerance": 1.0,
        "weight": 0.30,
        "lower_is_better": True,
    },
    {
        "name": "head_stability",
        "display_name": "头部稳定度",
        "phase": "backstroke",
        "unit": "norm_var",  # 鼻关键点 2D 位移方差（var_x + var_y，归一化²）
        "ideal_min": 0.0,
        "ideal_max": 0.0009,  # ~ (0.03 归一化位移)²，v0.1 占位
        "tolerance": 1.0,
        "weight": 0.30,
        "lower_is_better": True,
    },
    {
        "name": "face_alignment",
        "display_name": "杆面对准",
        "phase": "impact",
        "unit": "deg",  # 击球点处「握把线」偏离「与击球方向垂直（方正）」的角度
        "ideal_min": 0.0,
        "ideal_max": 5.0,
        "tolerance": 1.0,
        "weight": 0.25,
        "lower_is_better": True,
    },
    {
        "name": "tempo_ratio",
        "display_name": "节奏比",
        "phase": "backstroke",
        "unit": "ratio",  # backstroke 时长 / forward stroke 时长
        "ideal_min": 2.0,
        "ideal_max": 2.5,
        "tolerance": 0.5,
        "weight": 0.15,
        "lower_is_better": False,
    },
]

# 阶段权重（kickoff §3.4）：推杆击球点精度最重，钟摆稳定靠 backstroke/follow
PUTTING_PHASE_WEIGHTS: dict[str, float] = {
    "setup": 0.15,
    "backstroke": 0.25,
    "impact": 0.35,
    "follow": 0.25,
}

# 特征权重（kickoff §3.4）：钟摆 + 头部稳定占 60%
PUTTING_FEATURE_WEIGHTS: dict[str, float] = {
    f["name"]: f["weight"] for f in PUTTING_FEATURES
}


def putting_feature_meta(name: str) -> PuttingFeatureMeta:
    for f in PUTTING_FEATURES:
        if f["name"] == name:
            return f
    raise KeyError(f"未知推杆特征 {name}；全集见 PUTTING_FEATURES")


# ---- 启动期一致性守门（与 full_swing constants 同款 assert） ----
_pw = sum(PUTTING_PHASE_WEIGHTS.values())
assert abs(_pw - 1.0) < 1e-9, f"PUTTING_PHASE_WEIGHTS 和={_pw}，应为 1.0"
assert set(PUTTING_PHASE_WEIGHTS) == set(PUTTING_PHASE_ORDER), (
    "PUTTING_PHASE_WEIGHTS keys != PUTTING_PHASE_ORDER"
)
_fw = sum(PUTTING_FEATURE_WEIGHTS.values())
assert abs(_fw - 1.0) < 1e-9, f"PUTTING_FEATURE_WEIGHTS 和={_fw}，应为 1.0"
