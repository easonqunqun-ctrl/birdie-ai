"""P2-M11-04 · 阶段考核 service（W30 mock 实现）.

设计目标
--------
本 PR 是 W30 起跑包，落地"考核 lesson + M7 评分 ≥ 阈值自动升阶"的**纯函数核心**：

- Parse / validate `lesson.pass_criteria` JSONB
- Check swing_analysis score 是否满足通关阈值
- engine_mode 匹配校验（防"用 putter 通关 full_swing"作弊）
- 计算 attempts_used / 当日上限
- 输出 `AssessmentOutcome` 给 API 层 / 通关动画消费

为什么独立成 service
--------------------
- M11-01 `user_course_progress` 表已就位（`attempts` / `last_score` / `passed_at`
  / `failed_reasons` JSONB），状态机 `not_started → in_progress → passed/failed`
- M11-03 学习路径 UI 已规划升阶后刷新 hook
- M7 一期评分（score）字段已就位
- 本任务只新增"考核判定"这一中间层，不动表结构、不动 API 主流程

Hook 顺序（kickoff §3.3）
------------------------
```
swing_analysis 完成回调
  → assessment_service.evaluate_attempt(lesson, analysis, current_progress, today_attempts)
  → AssessmentOutcome → upsert user_course_progress
  → 满足 → maybe_award_certificate / 升阶事件
```

W30+ 落地范围
------------
- `evaluate_attempt(...)` 纯函数 + `parse_pass_criteria`：本 PR
- 集成到 POST /v1/lessons/{lesson_id}/attempt 路由：W30 后续 PR
- 通关动画 / 推送 / 证书：M11-04/05 后续 PR
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# kickoff §3.2 阈值默认值
DEFAULT_MIN_SCORE = 80
DEFAULT_MAX_ATTEMPTS_PER_DAY = 3
ALLOWED_ENGINE_MODES = ("full_swing", "putting", "chipping", "drive")
ALLOWED_PHASES = (
    "overall",
    "setup",
    "takeaway",
    "top",
    "downswing",
    "impact",
    "follow_through",
)
ALLOWED_CRITERIA_TYPES = ("engine_score",)  # 一期仅支持 score；后续扩展 quiz_score 等


class AssessmentError(ValueError):
    """考核校验失败的统一异常。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# 错误码（与 docs/02 §error_codes 对齐；占段 50200-50299 留给 M11）
ERR_INVALID_PASS_CRITERIA = 50201
ERR_ENGINE_MODE_MISMATCH = 50202
ERR_LESSON_NOT_ASSESSMENT = 50203
ERR_MAX_ATTEMPTS_REACHED = 50204
ERR_ANALYSIS_INCOMPLETE = 50205


@dataclass(frozen=True)
class PassCriteria:
    """解析后的 lesson.pass_criteria。"""

    criteria_type: str  # 当前固定为 'engine_score'
    engine_mode: str  # 'full_swing' / 'putting' / ...
    phase: str  # 'overall' / 'impact' / ...
    min_score: int
    max_attempts_per_day: int

    @property
    def is_engine_score(self) -> bool:
        return self.criteria_type == "engine_score"


@dataclass(frozen=True)
class AnalysisInput:
    """从 SwingAnalysis ORM / dict 提炼的考核输入，避免 service 强耦合 ORM。"""

    analysis_id: str
    score: int | None
    engine_mode: str | None
    status: str  # 'pending' / 'processing' / 'completed' / 'failed'


@dataclass(frozen=True)
class AssessmentOutcome:
    """考核结果，落库到 user_course_progress + 推给客户端。"""

    passed: bool
    score: int
    min_score: int
    attempts_used: int
    max_attempts: int
    failure_reason: str | None  # 'score_below_threshold' / 'engine_mode_mismatch' / ...
    feedback: str  # ≤80 字客户端展示


def parse_pass_criteria(raw: Mapping[str, Any] | None) -> PassCriteria:
    """从 lesson.pass_criteria JSONB 解析；缺/异常字段走默认值并校验白名单。"""
    if not raw or not isinstance(raw, Mapping):
        raise AssessmentError(
            ERR_LESSON_NOT_ASSESSMENT,
            "lesson 未配置 pass_criteria；不是考核 lesson",
        )
    criteria_type = raw.get("type") or "engine_score"
    if criteria_type not in ALLOWED_CRITERIA_TYPES:
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            f"pass_criteria.type {criteria_type!r} 未支持",
        )
    engine_mode = raw.get("engine_mode") or "full_swing"
    if engine_mode not in ALLOWED_ENGINE_MODES:
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            f"pass_criteria.engine_mode {engine_mode!r} 不合法",
        )
    phase = raw.get("phase") or "overall"
    if phase not in ALLOWED_PHASES:
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            f"pass_criteria.phase {phase!r} 不合法",
        )
    try:
        min_score = int(raw.get("min_score", DEFAULT_MIN_SCORE))
    except (TypeError, ValueError):
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            "pass_criteria.min_score 必须是整数",
        ) from None
    if not 0 <= min_score <= 100:
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            f"pass_criteria.min_score={min_score} 越界 [0, 100]",
        )
    try:
        max_attempts = int(raw.get("max_attempts_per_day", DEFAULT_MAX_ATTEMPTS_PER_DAY))
    except (TypeError, ValueError):
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            "pass_criteria.max_attempts_per_day 必须是整数",
        ) from None
    if max_attempts < 1:
        raise AssessmentError(
            ERR_INVALID_PASS_CRITERIA,
            f"max_attempts_per_day={max_attempts} 必须 ≥1",
        )
    return PassCriteria(
        criteria_type=criteria_type,
        engine_mode=engine_mode,
        phase=phase,
        min_score=min_score,
        max_attempts_per_day=max_attempts,
    )


def evaluate_attempt(
    *,
    criteria: PassCriteria,
    analysis: AnalysisInput,
    today_attempts: int,
) -> AssessmentOutcome:
    """考核纯逻辑：返回是否通关、分数、剩余次数、文案。

    顺序（kickoff §3.5 防作弊优先）：
    1. analysis.status != 'completed' → ERR_ANALYSIS_INCOMPLETE
    2. analysis.engine_mode != criteria.engine_mode → 视为失败 + engine_mode_mismatch
    3. 当日 attempts >= max → ERR_MAX_ATTEMPTS_REACHED
    4. score 未达 → 失败 + score_below_threshold
    5. score 达标 → passed

    `today_attempts` 由调用方查 user_course_progress.attempts 当日累加得出
    （本 service 不做查询，保持纯函数可测）。
    """
    if analysis.status != "completed":
        raise AssessmentError(
            ERR_ANALYSIS_INCOMPLETE,
            f"swing_analysis {analysis.analysis_id} 状态={analysis.status!r}，非 completed 不可考核",
        )

    # 防作弊：mode 不一致直接失败（不消耗当日 attempts？kickoff 未明确，本实现仍计 1 次）
    if analysis.engine_mode and analysis.engine_mode != criteria.engine_mode:
        return AssessmentOutcome(
            passed=False,
            score=analysis.score or 0,
            min_score=criteria.min_score,
            attempts_used=today_attempts + 1,
            max_attempts=criteria.max_attempts_per_day,
            failure_reason="engine_mode_mismatch",
            feedback=(
                f"考核要求 {criteria.engine_mode} 模式，"
                f"本次为 {analysis.engine_mode}；请重新提交对应模式视频。"
            ),
        )

    if today_attempts >= criteria.max_attempts_per_day:
        raise AssessmentError(
            ERR_MAX_ATTEMPTS_REACHED,
            f"今日已尝试 {today_attempts}/{criteria.max_attempts_per_day} 次，"
            "请明天再试或先看相关 drill 视频复盘。",
        )

    score = int(analysis.score or 0)
    if score < criteria.min_score:
        gap = criteria.min_score - score
        return AssessmentOutcome(
            passed=False,
            score=score,
            min_score=criteria.min_score,
            attempts_used=today_attempts + 1,
            max_attempts=criteria.max_attempts_per_day,
            failure_reason="score_below_threshold",
            feedback=(
                f"本次 {score} 分，距通关阈值 {criteria.min_score} 分还差 {gap} 分；"
                "可看推荐 drill 后再考。"
            ),
        )

    return AssessmentOutcome(
        passed=True,
        score=score,
        min_score=criteria.min_score,
        attempts_used=today_attempts + 1,
        max_attempts=criteria.max_attempts_per_day,
        failure_reason=None,
        feedback=f"通过！{score} 分（阈值 {criteria.min_score}）。已解锁下一节。",
    )


def maybe_upgrade_stage(
    *,
    course_lesson_ids: list[str],
    user_progress_statuses: Mapping[str, str],
) -> bool:
    """阶段升阶判定：本 course 所有 lesson 都已 passed → True。

    course_lesson_ids: 本 course 所有 lesson 的 id 列表
    user_progress_statuses: lesson_id → 用户当前 status（'passed' / 'failed' / ...）
                            缺失视为 'not_started'

    返回 True 表示触发升阶事件（颁发证书 + 解锁下阶；由调用方负责副作用）。
    """
    if not course_lesson_ids:
        return False
    for lesson_id in course_lesson_ids:
        if user_progress_statuses.get(lesson_id) != "passed":
            return False
    return True


__all__ = [
    "DEFAULT_MIN_SCORE",
    "DEFAULT_MAX_ATTEMPTS_PER_DAY",
    "ALLOWED_ENGINE_MODES",
    "ALLOWED_PHASES",
    "ERR_INVALID_PASS_CRITERIA",
    "ERR_ENGINE_MODE_MISMATCH",
    "ERR_LESSON_NOT_ASSESSMENT",
    "ERR_MAX_ATTEMPTS_REACHED",
    "ERR_ANALYSIS_INCOMPLETE",
    "AssessmentError",
    "PassCriteria",
    "AnalysisInput",
    "AssessmentOutcome",
    "parse_pass_criteria",
    "evaluate_attempt",
    "maybe_upgrade_stage",
]
