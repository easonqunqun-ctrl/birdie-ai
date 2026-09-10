"""请求语言：客户端通过 Accept-Language 声明 UI 语言。"""

from __future__ import annotations


def reply_locale_from_accept_language(header: str | None) -> str:
    """返回教练回复语言代码：``en`` 或 ``zh``（默认）。"""
    if not header:
        return "zh"
    first = header.split(",")[0].strip().lower()
    lang = first.split(";")[0].strip()
    if lang.startswith("en"):
        return "en"
    return "zh"
