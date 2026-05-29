"""M8-07 · 教练教学报告 LLM prompt 构建."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.llm import Message


@dataclass(frozen=True)
class RecapIssueBrief:
    name: str
    issue_type: str
    severity: str
    score: int | None


@dataclass(frozen=True)
class RecapStudentContext:
    student_user_id: str
    display_name: str
    analysis_id: str
    overall_score: int | None
    club_type: str | None
    issues: list[RecapIssueBrief]


SYSTEM_PROMPT = """你是领翼golf的专业高尔夫教练助手，负责把一次课程中多位学员的挥杆分析数据整理成教学报告。

硬性要求：
1. 必须为每位学员单独写 2-3 句具体观察，必须提到 issue 名称或 issue_type，并引用分数/数据。
2. 禁止空泛套话（如「整体表现不错」「继续加油」）。
3. 使用 Markdown，结构固定：
   ## 课程概述
   ## {学员名} 的本次表现 + 改进建议
   ...
   ## 下次课程建议
4. 全程中文。"""


def build_recap_messages(contexts: list[RecapStudentContext], *, session_date: str) -> list[Message]:
    lines = [f"课程日期：{session_date}", "学员分析数据："]
    for ctx in contexts:
        lines.append(f"\n### 学员：{ctx.display_name}（analysis_id={ctx.analysis_id}）")
        lines.append(
            f"- 球杆：{ctx.club_type or '未知'}；总分：{ctx.overall_score if ctx.overall_score is not None else '—'}"
        )
        if ctx.issues:
            for issue in ctx.issues:
                score_part = f"score:{issue.score}" if issue.score is not None else "score:—"
                lines.append(
                    f"- issue {issue.issue_type} / {issue.name}（{issue.severity}，{score_part}）"
                )
        else:
            lines.append("- issues: （无诊断项）")
    lines.append("\n请按系统要求输出 Markdown 教学报告。")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


def build_fallback_summary(contexts: list[RecapStudentContext], *, session_date: str) -> str:
    parts = [
        "## 课程概述",
        f"{session_date} 本次课程共 {len(contexts)} 位学员参与，以下为基于分析数据的要点汇总。",
    ]
    for ctx in contexts:
        parts.append(f"\n## {ctx.display_name} 的本次表现 + 改进建议")
        if ctx.overall_score is not None:
            parts.append(f"- 本次挥杆综合得分 {ctx.overall_score} 分。")
        if ctx.issues:
            top = ctx.issues[0]
            score_txt = f"{top.score} 分" if top.score is not None else "待量化"
            parts.append(
                f"- 重点关注 {top.name}（{top.issue_type}，{top.severity}，{score_txt}），建议下一课针对性练习。"
            )
        else:
            parts.append("- 本次分析未检出明显 issue，建议保持节奏并录制对比视频。")
    parts.append("\n## 下次课程建议")
    parts.append("- 复习本次 issue 对应 drill，并各录 1 段对比视频便于追踪。")
    return "\n".join(parts)


def summary_passes_quality_gate(summary: str, contexts: list[RecapStudentContext]) -> bool:
    text = summary.strip()
    if len(text) < 80:
        return False
    for ctx in contexts:
        if ctx.display_name not in text:
            return False
        if not ctx.issues:
            continue
        if not any(issue.name in text or issue.issue_type in text for issue in ctx.issues):
            return False
    return True
