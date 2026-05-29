"""M13-08 · 自助挑战赛 rule_template 注册表."""

from __future__ import annotations

from app.services.meetup_event_rules.templates import (
    EVENT_RULE_TEMPLATES,
    EventRuleTemplate,
    compare_scores,
    validate_score_for_template,
)

__all__ = [
    "EVENT_RULE_TEMPLATES",
    "EventRuleTemplate",
    "compare_scores",
    "validate_score_for_template",
]
