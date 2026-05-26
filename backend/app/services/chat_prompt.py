"""AI 教练 system prompt 构造器.

模板版本化
----------
- `SYSTEM_PROMPT_VERSION` 在每次改模板**语义**（而非改几个字）时升一版；
  升版时把 `ChatSession.system_prompt_version` 作为只读审计字段保留下来，
  方便后续数据分析时按版本切片看"v1 vs v2 用户满意度"。
- 为什么不存完整 prompt 快照？——prompt 里注入的是"用户最近 3 次分析摘要"
  （已经落库，可反向重建），存整段会把 chat_sessions 表膨胀到 MB 级，得不偿失。

注意事项
--------
1. 不把 **openid / user_id** 写到 system prompt 里。LLM 供应商出于合规会记录
   prompt 做安全审计，泄露内部主键是没意义的风险。只用 nickname / 球龄等画像。
2. 注入的分析是**只读摘要**（score + 主要 issue），不把完整 issue 列表塞进去：
   一次 chat 只需要"大致画像"，太长反而让 LLM 抓不住重点，也增加 token 成本。
3. 字数控制回复"≤300 字"在 prompt 里硬性要求；DeepSeek / Qwen 对这种格式指令
   遵从较好，OpenAI 稍差但差别可接受。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.models.user import User
from app.services.profile_v2_prompt_context import build_v2_context

# 模板版本号；改动模板语义时一定要升版
# v1 → v2 升版：P2-M9-04 引入画像 2.0 prompt 注入（差点 / 目标 / 训练偏好）；
# 旧 ChatSession 的 system_prompt_version 仍保留 'v1' 作审计字段。
SYSTEM_PROMPT_VERSION = "v2"

# 最近分析摘要条数：3 条已能呈现短期趋势；太多会挤占 LLM 上下文
RECENT_ANALYSES_COUNT = 3

GOLF_LEVEL_LABELS = {
    "beginner": "初学（球龄 <1 年）",
    "elementary": "入门（球龄 1-3 年）",
    "intermediate": "进阶（球龄 3-5 年）",
    "advanced": "高阶（球龄 >5 年）",
}

CLUB_LABELS = {
    "driver": "一号木",
    "fairway_wood": "球道木",
    "iron_3": "3 号铁",
    "iron_4": "4 号铁",
    "iron_5": "5 号铁",
    "iron_6": "6 号铁",
    "iron_7": "7 号铁",
    "iron_8": "8 号铁",
    "iron_9": "9 号铁",
    "wedge": "挖起杆",
    "putter": "推杆",
    "unknown": "未知球杆",
}


ROLE_AND_STYLE = """你是"领翼golf 高尔夫教练"，为业余球手提供技术指导。

回复规范（严格遵守）：
1. 全程使用简体中文；
2. 单次回复不超过 300 字，分 2-3 段，重点突出；
3. 必要时用数字标号列出 2-3 个要点；
4. 专业术语首次出现时用一句话解释（例：X-Factor=上下半身旋转差）；
5. 若用户问题与高尔夫无关（如医疗、政治、金融），礼貌拒绝并引导回高尔夫话题；
6. 不要假装你看过用户的视频；只基于我给你的"分析摘要"和用户描述作答；
7. 推荐训练动作时，优先从以下 drill_id 集合里挑：
   drill_towel_arm（修复抛杆）、drill_hip_rotation（修复提前伸展）、drill_half_swing（改善节奏）。
"""


async def load_recent_analyses(
    db: AsyncSession, user: User, *, limit: int = RECENT_ANALYSES_COUNT
) -> list[SwingAnalysis]:
    """拉取用户最近 N 次**已完成**的分析；按 analyzed_at 降序。

    排除 `is_sample=True`（示例报告不代表用户真实水平）。
    返回时已 eager-load issues 用于生成摘要。
    """
    stmt = (
        select(SwingAnalysis)
        .where(SwingAnalysis.user_id == user.id)
        .where(SwingAnalysis.status == "completed")
        .where(SwingAnalysis.is_sample.is_(False))
        .where(SwingAnalysis.deleted_at.is_(None))
        .options(selectinload(SwingAnalysis.issues))
        .order_by(SwingAnalysis.analyzed_at.desc().nullslast())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


def _format_user_profile(user: User) -> str:
    parts = []
    if user.nickname:
        parts.append(f"昵称：{user.nickname}")
    else:
        parts.append("昵称：未填写")
    level_label = GOLF_LEVEL_LABELS.get(user.golf_level or "", user.golf_level or "未填写")
    parts.append(f"水平：{level_label}")
    if user.primary_goals:
        parts.append(f"目标：{'、'.join(user.primary_goals[:3])}")
    parts.append(f"总分析次数：{user.total_analyses}")
    if user.best_score:
        parts.append(f"历史最佳：{user.best_score} 分")
    return " / ".join(parts)


def _format_analysis_brief(a: SwingAnalysis) -> str:
    """把一条分析压成 ~60 字的一行摘要。"""
    club = CLUB_LABELS.get(a.club_type, a.club_type)
    score = a.overall_score or 0
    when = a.analyzed_at.strftime("%m-%d") if a.analyzed_at else "时间未知"
    # 取最高优先级的 issue（sort_order=0 或 severity=high）做"主要问题"
    key_issues: list[AnalysisIssue] = sorted(
        a.issues or [],
        key=lambda x: ({"high": 0, "medium": 1, "low": 2}.get(x.severity, 3), x.sort_order),
    )
    issue_names = "、".join(i.name for i in key_issues[:2]) or "无明显问题"
    return f"{when} · {club} · 综合 {score} 分 · 主要问题：{issue_names}"


def build_system_prompt(
    user: User,
    recent_analyses: list[SwingAnalysis],
    profile_v2=None,
) -> str:
    """合成 system prompt 文本。

    结构：
    - ROLE_AND_STYLE（固定）
    - 用户画像（一行）
    - 【画像 2.0】行（**P2-M9-04**，仅当 profile_v2 非空且字段非空时；
      由 ``build_v2_context`` 渲染，伤病字段经 docs/06 隔离白名单硬过滤）
    - 最近 3 次分析摘要（0-3 行）

    profile_v2 参数
    ---------------
    - 可传 ``UserProfileV2`` ORM 行 / dict / None
    - 调用方应在 ``PHASE2_PROFILE_V2_ENABLED=false`` 时传 None，保持 V1 行为
    - 任何 LLM 透传新字段必须经 ``profile_v2_prompt_context.build_v2_context``
      统一渲染，避免绕过敏感字段白名单
    """
    profile = _format_user_profile(user)
    v2_block = build_v2_context(profile_v2)
    if recent_analyses:
        analyses_section = "\n".join(
            f"- {_format_analysis_brief(a)}" for a in recent_analyses
        )
        context_block = (
            f"【用户画像】{profile}\n"
            + (f"{v2_block}\n" if v2_block else "")
            + f"\n【最近 {len(recent_analyses)} 次挥杆分析】\n{analyses_section}\n"
        )
    else:
        context_block = (
            f"【用户画像】{profile}\n"
            + (f"{v2_block}\n" if v2_block else "")
            + "\n【最近挥杆分析】暂无分析记录，请基于通用高尔夫知识回答。\n"
        )

    return f"{ROLE_AND_STYLE}\n{context_block}"
