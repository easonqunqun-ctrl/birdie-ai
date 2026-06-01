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
PHASE_ENCOURAGEMENT_MIN_SCORE = 70
MAX_PHASE_HIGHLIGHTS = 3
WARN_ANGLE_LIMITED_SCORING = "angle_limited_scoring"


def build_phase_highlights(
    phase_scores: dict[str, int] | None,
    *,
    quality_warnings: list[str] | None = None,
) -> list[str]:
    if not phase_scores:
        return []

    lines: list[str] = []
    if quality_warnings and WARN_ANGLE_LIMITED_SCORING in quality_warnings:
        lines.append(
            "当前机位下，系统主要依据下杆顺序、击球与手臂轨迹等「画面可测」维度计分；"
            "转肩类指标仅供参考，同机位多拍几次看趋势更有意义。"
        )

    ranked = sorted(
        ((p, int(phase_scores[p])) for p in PHASE_ORDER if p in phase_scores),
        key=lambda x: (-x[1], PHASE_ORDER.index(x[0])),
    )
    praise_count = 0
    for phase, score in ranked:
        if praise_count >= MAX_PHASE_HIGHLIGHTS:
            break
        label = PHASE_LABELS.get(phase, phase)
        if score >= PHASE_HIGHLIGHT_MIN_SCORE:
            lines.append(
                f"「{label}」这一环表现不错（{score} 分），是您本次挥杆的亮点，值得保持。"
            )
            praise_count += 1
        elif score >= PHASE_ENCOURAGEMENT_MIN_SCORE:
            lines.append(
                f"「{label}」这一段节奏与形态较稳（{score} 分），"
                "说明您在这个环节已经有不错的基础，可以在此基础上继续打磨其它环节。"
            )
            praise_count += 1

    if praise_count == 0 and ranked:
        weakest_phase, weakest_score = ranked[-1]
        if weakest_score < 65:
            label = PHASE_LABELS.get(weakest_phase, weakest_phase)
            lines.append(
                f"本次「{label}」相对最弱（{weakest_score} 分），建议优先打磨这一环；"
                "下方训练建议会给出对应练习。"
            )
    return lines
