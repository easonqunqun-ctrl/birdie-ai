"""AI 教练首屏快捷问题（MVP §5.1 的 4-6 条引导问题）.

设计约定
--------
- 这些问题是**静态配置**，不进数据库。运营想改就改代码 + 重发布，
  比走 admin CMS 便宜得多（MVP 一周一次发版可接受）。
- `requires_analysis=True` 表示点击前需要校验用户至少有 1 次挥杆分析；
  前端收到该标记后，若用户无分析记录则点击不发送，改为引导"先分析一次"。
- 顺序即展示顺序：从用户**最可能有兴趣**的问题起。
"""

from __future__ import annotations

from typing import TypedDict


class QuickQuestion(TypedDict):
    id: str
    text: str
    requires_analysis: bool


QUICK_QUESTIONS: list[QuickQuestion] = [
    {
        "id": "qq_001",
        "text": "我的挥杆有什么问题？",
        "requires_analysis": True,
    },
    {
        "id": "qq_002",
        "text": "推荐今天练什么",
        "requires_analysis": False,
    },
    {
        "id": "qq_003",
        "text": "怎么打好沙坑球？",
        "requires_analysis": False,
    },
    {
        "id": "qq_004",
        "text": "上杆时身体怎么转？",
        "requires_analysis": False,
    },
    {
        "id": "qq_005",
        "text": "为什么我总打出右曲球？",
        "requires_analysis": False,
    },
    {
        "id": "qq_006",
        "text": "什么是 X-Factor？",
        "requires_analysis": False,
    },
]
