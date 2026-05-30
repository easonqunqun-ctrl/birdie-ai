"""报告正向话术（与 ai_engine scoring_narrative 对齐）。"""

from __future__ import annotations

PHASE_LABELS: dict[str, str] = {
    "setup": "站位准备",
    "backswing": "上杆轨迹",
    "top": "顶点位置",
    "downswing": "下杆转换",
    "impact": "击球触球",
    "follow_through": "收杆平衡",
}

PHASE_ORDER = [
    "setup",
    "backswing",
    "top",
    "downswing",
    "impact",
    "follow_through",
]

PHASE_HIGHLIGHT_MIN_SCORE = 78
MAX_PHASE_HIGHLIGHTS = 3


def build_phase_highlights(phase_scores: dict[str, int] | None) -> list[str]:
    if not phase_scores:
        return []
    ranked = sorted(
        ((p, int(phase_scores[p])) for p in PHASE_ORDER if p in phase_scores),
        key=lambda x: (-x[1], PHASE_ORDER.index(x[0])),
    )
    lines: list[str] = []
    for phase, score in ranked:
        if score < PHASE_HIGHLIGHT_MIN_SCORE:
            continue
        label = PHASE_LABELS.get(phase, phase)
        lines.append(
            f"「{label}」这一环表现不错（{score} 分），是您本次挥杆的亮点，值得保持。"
        )
        if len(lines) >= MAX_PHASE_HIGHLIGHTS:
            break
    return lines
