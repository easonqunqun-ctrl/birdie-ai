"""P-02 precheck 阈值评估纯逻辑单测。"""

from __future__ import annotations

from app.pipeline.precheck_eval import (
    PrecheckEvalSample,
    evaluate,
    tuning_hint,
)


def _s(label: str, decision: str, code: int | None = None, note: str = "") -> PrecheckEvalSample:
    return PrecheckEvalSample(
        video_url=f"u_{label}_{decision}",
        label=label,  # type: ignore[arg-type]
        decision=decision,  # type: ignore[arg-type]
        error_code=code,
        note=note,
    )


def test_sample_classification_flags() -> None:
    assert _s("block", "blocked").is_true_positive
    assert _s("pass", "blocked").is_false_positive
    assert _s("block", "passed").is_false_negative
    assert _s("pass", "passed").is_true_negative


def test_perfect_eval() -> None:
    samples = [_s("block", "blocked"), _s("pass", "passed")]
    rep = evaluate(samples)
    assert rep.tp == 1 and rep.tn == 1 and rep.fp == 0 and rep.fn == 0
    assert rep.precision == 1.0 and rep.recall == 1.0 and rep.f1 == 1.0
    assert rep.false_positive_rate == 0.0
    assert "✅" in tuning_hint(rep)


def test_false_positive_tracked_with_code() -> None:
    samples = [
        _s("pass", "blocked", code=50101),  # 误杀
        _s("pass", "blocked", code=50101),
        _s("pass", "passed"),
        _s("block", "blocked"),
    ]
    rep = evaluate(samples)
    assert rep.fp == 2
    assert rep.false_positive_codes == {50101: 2}
    assert rep.precision == 1 / 3  # tp=1, fp=2
    assert "误杀" in tuning_hint(rep)
    assert "50101" in tuning_hint(rep)


def test_false_negative_tracked() -> None:
    samples = [
        _s("block", "passed", note="该拦没拦"),  # 漏拦
        _s("block", "blocked"),
    ]
    rep = evaluate(samples)
    assert rep.fn == 1
    assert rep.recall == 0.5
    assert rep.false_negatives[0].note == "该拦没拦"
    assert "漏拦" in tuning_hint(rep)


def test_false_positive_rate() -> None:
    samples = [
        _s("pass", "blocked"),  # fp
        _s("pass", "passed"),  # tn
        _s("pass", "passed"),  # tn
    ]
    rep = evaluate(samples)
    assert rep.false_positive_rate == 1 / 3


def test_empty_eval() -> None:
    rep = evaluate([])
    assert rep.total == 0
    assert rep.precision == 0.0
    assert "无样本" in tuning_hint(rep)
