"""M10-02 · 切杆 mode 报告维度标签（与 ai_engine chipping/constants 对齐）."""

CHIPPING_FEATURE_ORDER: list[str] = [
    "half_swing_amplitude",
    "face_open_angle",
    "contact_point_quality",
]

CHIPPING_FEATURE_LABELS: dict[str, str] = {
    "half_swing_amplitude": "半挥幅度",
    "face_open_angle": "杆面开角",
    "contact_point_quality": "触球质量",
}

CHIPPING_PHASE_ORDER: list[str] = ["setup", "backswing", "impact", "follow"]

CHIPPING_PHASE_LABELS: dict[str, str] = {
    "setup": "瞄准准备",
    "backswing": "上杆",
    "impact": "击球",
    "follow": "收杆",
}

CHIPPING_FEATURE_PRIMARY_PHASE: dict[str, str] = {
    "half_swing_amplitude": "backswing",
    "face_open_angle": "impact",
    "contact_point_quality": "impact",
}
