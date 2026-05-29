"""M8-08 · 内容安全审核（mock / 腾讯云占位）."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("content_safety")

# 测试 / 本地联调标记（单测 AC-1/2/3）
MOCK_REJECT_TOKEN = "BLOCK_TEST"
MOCK_MANUAL_REVIEW_TOKEN = "REVIEW_TEST"
MOCK_PROVIDER_FAIL_TOKEN = "FAIL_TEST"


class ModerationDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"
    PENDING = "pending"


@dataclass(frozen=True)
class ModerationOutcome:
    decision: ModerationDecision
    risk_label: str | None = None
    risk_score: float | None = None
    provider_error: bool = False


async def moderate_text(text: str) -> ModerationOutcome:
    """审核文本 UGC。provider=mock 时使用标记词；tencent 暂回落 mock。"""
    normalized = (text or "").strip()
    if not normalized:
        return ModerationOutcome(decision=ModerationDecision.APPROVED)

    provider = (settings.CONTENT_MODERATION_PROVIDER or "mock").strip().lower()
    if provider == "tencent":
        logger.info("content_moderation_tencent_fallback_mock")
    return _moderate_text_mock(normalized)


def _moderate_text_mock(text: str) -> ModerationOutcome:
    upper = text.upper()
    if MOCK_PROVIDER_FAIL_TOKEN in upper:
        return ModerationOutcome(
            decision=ModerationDecision.PENDING,
            risk_label="provider_error",
            provider_error=True,
        )
    if MOCK_REJECT_TOKEN in upper:
        return ModerationOutcome(
            decision=ModerationDecision.REJECTED,
            risk_label="porn_violence",
            risk_score=0.99,
        )
    if MOCK_MANUAL_REVIEW_TOKEN in upper:
        return ModerationOutcome(
            decision=ModerationDecision.MANUAL_REVIEW,
            risk_label="ambiguous",
            risk_score=0.55,
        )
    return ModerationOutcome(decision=ModerationDecision.APPROVED, risk_score=0.05)
