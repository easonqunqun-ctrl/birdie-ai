"""源片早检跳过 stability 硬拦。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.errors import PoorQualityError
from app.pipeline.preprocess import (
    MIN_STABILITY_HARD_BLOCK,
    enforce_quality_gates,
)


def _stats(*, stability: float, clarity: float = 200.0) -> MagicMock:
    s = MagicMock()
    s.clarity_score = clarity
    s.frame_loss_ratio = 0.0
    s.low_clarity_frame_ratio = 0.0
    s.stability_score = stability
    return s


def test_stability_hard_block_on_full_gate() -> None:
    bad = _stats(stability=max(0.0, MIN_STABILITY_HARD_BLOCK - 0.01))
    with pytest.raises(PoorQualityError):
        enforce_quality_gates(bad, skip_stability=False)


def test_early_gate_skips_stability() -> None:
    bad_stab = _stats(stability=max(0.0, MIN_STABILITY_HARD_BLOCK - 0.01))
    # 不应因抖动在早检阶段硬拦
    enforce_quality_gates(bad_stab, skip_stability=True)


def test_early_gate_still_blocks_blur() -> None:
    blur = _stats(stability=1.0, clarity=1.0)
    with pytest.raises(PoorQualityError):
        enforce_quality_gates(blur, skip_stability=True)
