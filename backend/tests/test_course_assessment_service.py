"""P2-M11-04 · course_assessment_service 单测。

覆盖 kickoff §3.2-3.5 全部判定路径 + AC-1/2/3。
"""

from __future__ import annotations

import pytest

from app.services.course_assessment_service import (
    ALLOWED_ENGINE_MODES,
    ALLOWED_PHASES,
    DEFAULT_MAX_ATTEMPTS_PER_DAY,
    DEFAULT_MIN_SCORE,
    ERR_ANALYSIS_INCOMPLETE,
    ERR_INVALID_PASS_CRITERIA,
    ERR_LESSON_NOT_ASSESSMENT,
    ERR_MAX_ATTEMPTS_REACHED,
    AnalysisInput,
    AssessmentError,
    PassCriteria,
    evaluate_attempt,
    maybe_upgrade_stage,
    parse_pass_criteria,
)


# ============================================================
# 1. parse_pass_criteria
# ============================================================


def test_parse_returns_defaults_when_only_type_given():
    pc = parse_pass_criteria({"type": "engine_score"})
    assert pc.engine_mode == "full_swing"
    assert pc.phase == "overall"
    assert pc.min_score == DEFAULT_MIN_SCORE
    assert pc.max_attempts_per_day == DEFAULT_MAX_ATTEMPTS_PER_DAY


def test_parse_full_payload():
    pc = parse_pass_criteria(
        {
            "type": "engine_score",
            "engine_mode": "putting",
            "phase": "impact",
            "min_score": 75,
            "max_attempts_per_day": 5,
        }
    )
    assert pc == PassCriteria(
        criteria_type="engine_score",
        engine_mode="putting",
        phase="impact",
        min_score=75,
        max_attempts_per_day=5,
    )


def test_parse_rejects_empty_or_none():
    with pytest.raises(AssessmentError) as exc:
        parse_pass_criteria(None)
    assert exc.value.code == ERR_LESSON_NOT_ASSESSMENT
    with pytest.raises(AssessmentError):
        parse_pass_criteria({})


def test_parse_rejects_unknown_type():
    with pytest.raises(AssessmentError) as exc:
        parse_pass_criteria({"type": "quiz_score"})
    assert exc.value.code == ERR_INVALID_PASS_CRITERIA


def test_parse_rejects_invalid_engine_mode():
    with pytest.raises(AssessmentError):
        parse_pass_criteria({"type": "engine_score", "engine_mode": "skating"})


def test_parse_rejects_invalid_phase():
    with pytest.raises(AssessmentError):
        parse_pass_criteria({"type": "engine_score", "phase": "warmup"})


def test_parse_rejects_min_score_out_of_range():
    for bad in (-1, 101, 200):
        with pytest.raises(AssessmentError):
            parse_pass_criteria({"type": "engine_score", "min_score": bad})


def test_parse_rejects_non_int_min_score():
    with pytest.raises(AssessmentError):
        parse_pass_criteria({"type": "engine_score", "min_score": "high"})


def test_parse_rejects_max_attempts_below_one():
    with pytest.raises(AssessmentError):
        parse_pass_criteria({"type": "engine_score", "max_attempts_per_day": 0})


def test_allowed_constants_self_consistent():
    """白名单常量与 schema literal 一致（防漂移）。"""
    assert "full_swing" in ALLOWED_ENGINE_MODES
    assert "putting" in ALLOWED_ENGINE_MODES
    assert "overall" in ALLOWED_PHASES
    assert "impact" in ALLOWED_PHASES


# ============================================================
# 2. evaluate_attempt 主流程
# ============================================================


def _criteria(**overrides) -> PassCriteria:
    base = dict(
        criteria_type="engine_score",
        engine_mode="full_swing",
        phase="overall",
        min_score=80,
        max_attempts_per_day=3,
    )
    base.update(overrides)
    return PassCriteria(**base)


def _analysis(**overrides) -> AnalysisInput:
    base = dict(
        analysis_id="ana_test",
        score=85,
        engine_mode="full_swing",
        status="completed",
    )
    base.update(overrides)
    return AnalysisInput(**base)


def test_ac1_passes_when_score_meets_threshold():
    """AC-1：score ≥ min_score → passed=True。"""
    out = evaluate_attempt(
        criteria=_criteria(min_score=80),
        analysis=_analysis(score=85),
        today_attempts=0,
    )
    assert out.passed is True
    assert out.score == 85
    assert out.min_score == 80
    assert out.attempts_used == 1
    assert out.failure_reason is None
    assert "通过" in out.feedback


def test_passes_at_exact_threshold():
    out = evaluate_attempt(
        criteria=_criteria(min_score=80),
        analysis=_analysis(score=80),
        today_attempts=2,
    )
    assert out.passed is True
    assert out.attempts_used == 3


def test_ac3_below_threshold_returns_failure_with_retry_info():
    """AC-3：未达标返回失败 + attempts++ + 友好文案。"""
    out = evaluate_attempt(
        criteria=_criteria(min_score=80, max_attempts_per_day=3),
        analysis=_analysis(score=72),
        today_attempts=0,
    )
    assert out.passed is False
    assert out.failure_reason == "score_below_threshold"
    assert out.score == 72
    assert out.attempts_used == 1
    assert out.max_attempts == 3
    assert "8 分" in out.feedback  # gap = 80 - 72 = 8


def test_engine_mode_mismatch_returns_failure_not_exception():
    """防作弊：模式不一致视为失败（仍计 attempts++），便于客户端展示重考引导。"""
    out = evaluate_attempt(
        criteria=_criteria(engine_mode="full_swing"),
        analysis=_analysis(engine_mode="putting", score=99),
        today_attempts=0,
    )
    assert out.passed is False
    assert out.failure_reason == "engine_mode_mismatch"
    assert out.score == 99  # 高分也不算通过
    assert "full_swing" in out.feedback


def test_max_attempts_reached_raises():
    with pytest.raises(AssessmentError) as exc:
        evaluate_attempt(
            criteria=_criteria(max_attempts_per_day=3),
            analysis=_analysis(score=72),
            today_attempts=3,
        )
    assert exc.value.code == ERR_MAX_ATTEMPTS_REACHED


def test_analysis_not_completed_raises():
    for bad_status in ("pending", "processing", "failed"):
        with pytest.raises(AssessmentError) as exc:
            evaluate_attempt(
                criteria=_criteria(),
                analysis=_analysis(status=bad_status),
                today_attempts=0,
            )
        assert exc.value.code == ERR_ANALYSIS_INCOMPLETE


def test_missing_score_treated_as_zero():
    out = evaluate_attempt(
        criteria=_criteria(min_score=80),
        analysis=_analysis(score=None),
        today_attempts=0,
    )
    assert out.passed is False
    assert out.score == 0


def test_mode_mismatch_takes_priority_over_max_attempts():
    """先校验 mode 再校验 attempts；防作弊优先（kickoff §3.5）。"""
    out = evaluate_attempt(
        criteria=_criteria(engine_mode="full_swing", max_attempts_per_day=3),
        analysis=_analysis(engine_mode="putting"),
        today_attempts=10,  # 远超 max
    )
    assert out.passed is False
    assert out.failure_reason == "engine_mode_mismatch"  # 没抛 ERR_MAX_ATTEMPTS_REACHED


# ============================================================
# 3. maybe_upgrade_stage
# ============================================================


def test_upgrade_true_when_all_lessons_passed():
    """AC-1：course 内所有 lesson 都 passed → 触发升阶。"""
    assert maybe_upgrade_stage(
        course_lesson_ids=["lsn_a", "lsn_b", "lsn_c"],
        user_progress_statuses={"lsn_a": "passed", "lsn_b": "passed", "lsn_c": "passed"},
    )


def test_upgrade_false_when_any_lesson_not_passed():
    for incomplete_status in ("not_started", "in_progress", "failed"):
        assert not maybe_upgrade_stage(
            course_lesson_ids=["lsn_a", "lsn_b"],
            user_progress_statuses={"lsn_a": "passed", "lsn_b": incomplete_status},
        )


def test_upgrade_false_when_lesson_missing_from_progress_map():
    """缺失视为 not_started。"""
    assert not maybe_upgrade_stage(
        course_lesson_ids=["lsn_a", "lsn_b"],
        user_progress_statuses={"lsn_a": "passed"},
    )


def test_upgrade_false_for_empty_course():
    """边界：course 没 lesson → 不算升阶（避免 vacuous truth）。"""
    assert not maybe_upgrade_stage(course_lesson_ids=[], user_progress_statuses={})


# ============================================================
# 4. AssessmentError 携带 code/message
# ============================================================


def test_assessment_error_exposes_code_and_message():
    err = AssessmentError(50204, "今日次数已用完")
    assert err.code == 50204
    assert err.message == "今日次数已用完"
    assert str(err) == "今日次数已用完"
