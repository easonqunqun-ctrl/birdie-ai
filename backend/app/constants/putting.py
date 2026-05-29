"""M10-01 · 推杆 mode 报告维度标签（与 ai_engine putting/constants 展示名对齐）."""

PUTTING_FEATURE_ORDER: list[str] = [
    "pendulum_stability",
    "head_stability",
    "face_alignment",
    "tempo_ratio",
]

PUTTING_FEATURE_LABELS: dict[str, str] = {
    "pendulum_stability": "钟摆稳定度",
    "head_stability": "头部稳定",
    "face_alignment": "推杆面方正",
    "tempo_ratio": "节奏比",
}

PUTTING_PHASE_ORDER: list[str] = ["setup", "backstroke", "impact", "follow"]

PUTTING_PHASE_LABELS: dict[str, str] = {
    "setup": "瞄准准备",
    "backstroke": "回摆",
    "impact": "击球",
    "follow": "送杆",
}

# 特征 → 主展示阶段（mode_feature_scores 缺失时从 phase_scores 兜底）
PUTTING_FEATURE_PRIMARY_PHASE: dict[str, str] = {
    "pendulum_stability": "backstroke",
    "head_stability": "setup",
    "face_alignment": "impact",
    "tempo_ratio": "backstroke",
}
