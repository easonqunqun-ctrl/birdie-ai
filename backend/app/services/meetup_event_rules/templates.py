"""M13-08 · 三种挑战赛模板（推杆 / 距离 / 综合分）.

合规：模板与 service 均不含 reward_cash / reward_item（红线 R6）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CompareMode = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class EventRuleTemplate:
    code: str
    label: str
    description: str
    default_capacity: int
    score_label: str
    compare: CompareMode
    rules_payload: dict


EVENT_RULE_TEMPLATES: dict[str, EventRuleTemplate] = {
    "putting_contest": EventRuleTemplate(
        code="putting_contest",
        label="推杆挑战赛",
        description="10 球推杆，以进洞数决胜（同分比最短推杆距离）",
        default_capacity=8,
        score_label="进洞数",
        compare="desc",
        rules_payload={
            "balls": 10,
            "metric": "makes",
            "tie_breaker": "shortest_putt_cm",
        },
    ),
    "distance_contest": EventRuleTemplate(
        code="distance_contest",
        label="距离挑战赛",
        description="5 球开球，取最远一杆成绩",
        default_capacity=8,
        score_label="最远距离（米）",
        compare="desc",
        rules_payload={
            "balls": 5,
            "metric": "max_distance_m",
        },
    ),
    "overall_score": EventRuleTemplate(
        code="overall_score",
        label="综合分挑战赛",
        description="18 洞总杆数，杆数越少越好",
        default_capacity=8,
        score_label="总杆数",
        compare="asc",
        rules_payload={
            "holes": 18,
            "metric": "total_strokes",
        },
    ),
}


def validate_score_for_template(template_code: str | None, score: float) -> None:
    """按模板校验自报成绩范围；非法抛 ValueError."""

    if score < 0:
        raise ValueError("成绩不能为负")
    tpl = EVENT_RULE_TEMPLATES.get(template_code or "")
    if tpl is None:
        return
    metric = tpl.rules_payload.get("metric")
    if metric == "makes" and score > tpl.rules_payload.get("balls", 10):
        raise ValueError(f"进洞数不能超过 {tpl.rules_payload.get('balls', 10)}")
    if metric == "max_distance_m" and score > 400:
        raise ValueError("距离成绩超出合理范围")
    if metric == "total_strokes" and (score < 18 or score > 200):
        raise ValueError("总杆数应在 18–200 之间")


def compare_scores(
    template_code: str | None,
    left: float,
    right: float,
) -> int:
    """排行榜比较：返回负数表示 left 更优."""

    tpl = EVENT_RULE_TEMPLATES.get(template_code or "")
    mode: CompareMode = tpl.compare if tpl else "asc"
    if mode == "desc":
        if left == right:
            return 0
        return -1 if left > right else 1
    if left == right:
        return 0
    return -1 if left < right else 1
