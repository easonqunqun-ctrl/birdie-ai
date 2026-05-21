"""进步曲线数据源：phase_scores 扁平化与 API 契约."""

from __future__ import annotations

from app.services.analysis_service import _flatten_phase_scores


def test_flatten_phase_scores_from_nested_dict() -> None:
    raw = {
        "setup": {"score": 82, "label": "站位", "is_weakest": False},
        "impact": {"score": 91, "label": "击球", "is_weakest": False},
    }
    assert _flatten_phase_scores(raw) == {"setup": 82, "impact": 91}


def test_flatten_phase_scores_accepts_int_values() -> None:
    assert _flatten_phase_scores({"setup": 70, "top": 88}) == {"setup": 70, "top": 88}


def test_flatten_phase_scores_empty_or_invalid() -> None:
    assert _flatten_phase_scores(None) is None
    assert _flatten_phase_scores({}) is None
    assert _flatten_phase_scores("bad") is None
