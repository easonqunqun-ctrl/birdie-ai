"""P-02：教练话题边界 — 启发式分类 + 定量测评夹具.

MVP 策略：
- LLM system prompt 仍承担主拒答（见 ``chat_prompt.ROLE_AND_STYLE``）；
- 本模块提供 **无外链 LLM** 的回归门槛：对用户输入做轻量分类，
  CI 跑 labeled cases 统计 precision/recall 下限。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TopicCategory(StrEnum):
    GOLF = "golf"
    OFF_TOPIC = "off_topic"
    MEDICAL = "medical"
    GAMBLING = "gambling"


@dataclass(frozen=True)
class TopicEvalCase:
    content: str
    expected: TopicCategory
    note: str = ""


# 非高尔夫 / 敏感话题关键词（中文为主，少量英文）
_MEDICAL_KEYWORDS = (
    "疼",
    "痛",
    "受伤",
    "骨折",
    "手术",
    "医生",
    "医院",
    "康复师",
    "吃药",
    "处方",
)
_GAMBLING_KEYWORDS = ("赌球", "博彩", "下注", "庄家", "赔率", "彩票")
_OFF_TOPIC_KEYWORDS = (
    "股票",
    "基金",
    "比特币",
    "量子物理",
    "政治",
    "选举",
    "总统",
    "做饭",
    "菜谱",
    "Python 编程",
    "python",
    "爬虫",
    "编程",
    "写代码",
    "王者荣耀",
)
_GOLF_KEYWORDS = (
    "挥杆",
    "击球",
    "球杆",
    "开球",
    "推杆",
    "右曲",
    "左曲",
    "抛杆",
    "下杆",
    "上杆",
    "站位",
    "握杆",
    "果岭",
    "沙坑",
    "一号木",
    "driver",
    "iron",
    "wedge",
    "高尔夫",
    "球场",
    "练习",
    "drill",
    "毛巾",
    "髋部",
)


def classify_user_message(content: str) -> TopicCategory:
    """对用户输入做轻量话题分类（供 P-02 定量测评与后续 pre-check 扩展）."""
    text = (content or "").strip().lower()
    if not text:
        return TopicCategory.GOLF

    if any(k in text for k in _GAMBLING_KEYWORDS):
        return TopicCategory.GAMBLING
    if any(k in text for k in _MEDICAL_KEYWORDS):
        return TopicCategory.MEDICAL

    golf_hit = any(k.lower() in text for k in _GOLF_KEYWORDS)
    off_hit = any(k.lower() in text for k in _OFF_TOPIC_KEYWORDS)

    if off_hit and not golf_hit:
        return TopicCategory.OFF_TOPIC
    return TopicCategory.GOLF


OFF_TOPIC_EVAL_CASES: tuple[TopicEvalCase, ...] = (
    TopicEvalCase("用量子物理解释股票涨跌", TopicCategory.OFF_TOPIC),
    TopicEvalCase("今晚吃什么菜谱推荐", TopicCategory.OFF_TOPIC),
    TopicEvalCase("帮我写一段 Python 爬虫", TopicCategory.OFF_TOPIC),
    TopicEvalCase("美国总统选举怎么看", TopicCategory.OFF_TOPIC),
    TopicEvalCase("比特币还能涨吗", TopicCategory.OFF_TOPIC),
    TopicEvalCase("我想赌球赢钱有什么技巧", TopicCategory.GAMBLING),
    TopicEvalCase("下场打球怎么下注", TopicCategory.GAMBLING),
    TopicEvalCase("挥杆后腰疼要不要去看医生", TopicCategory.MEDICAL),
    TopicEvalCase("肩膀受伤还能练球吗", TopicCategory.MEDICAL),
    TopicEvalCase("我的右曲球怎么纠正", TopicCategory.GOLF),
    TopicEvalCase("推荐一个修复抛杆的练习", TopicCategory.GOLF),
    TopicEvalCase("一号木开球总是 slice", TopicCategory.GOLF),
    TopicEvalCase("果岭上推杆节奏怎么练", TopicCategory.GOLF),
    TopicEvalCase("半挥杆和全挥杆的区别", TopicCategory.GOLF),
    TopicEvalCase("毛巾夹臂练习怎么做", TopicCategory.GOLF),
    TopicEvalCase("髋部旋转不够怎么办", TopicCategory.GOLF),
)


def eval_classifier_accuracy(
    cases: tuple[TopicEvalCase, ...] = OFF_TOPIC_EVAL_CASES,
) -> tuple[int, int]:
    """返回 (correct, total)。"""
    correct = sum(
        1 for case in cases if classify_user_message(case.content) == case.expected
    )
    return correct, len(cases)


REFUSAL_HINTS: tuple[str, ...] = (
    "高尔夫",
    "专长",
    "挥杆",
    "球场",
    "练习",
)


def reply_matches_refusal_hint(reply: str) -> bool:
    """FakeLLM / 回归用：拒答回复是否含引导回高尔夫的提示."""
    body = (reply or "").strip()
    return any(h in body for h in REFUSAL_HINTS)
