"""chat_service 回复附件 heuristic 单测（v1.1.1 video_card 成对）."""

from __future__ import annotations

from app.services.chat_service import _DRILL_KEYWORDS, _detect_reply_attachments


def test_detect_reply_attachments_pairs_video_after_each_drill() -> None:
    attachments = _detect_reply_attachments(
        "建议加强髋部旋转练习，另外可以试试毛巾夹臂练习。",
    )
    types = [a["type"] for a in attachments]
    assert types == [
        "drill_card",
        "video_card",
        "drill_card",
        "video_card",
    ]
    drill_ids = [a["drill_id"] for a in attachments if a["type"] == "drill_card"]
    video_ids = [a["drill_id"] for a in attachments if a["type"] == "video_card"]
    assert drill_ids == ["drill_towel_arm", "drill_hip_rotation"]
    assert video_ids == drill_ids
    assert attachments[1]["title"] == "毛巾夹臂练习 · 教练示范"


def test_detect_reply_attachments_empty_when_no_drill_keywords() -> None:
    assert _detect_reply_attachments("今天天气不错") == []


def test_all_thirteen_drills_have_keyword_coverage() -> None:
    assert len(_DRILL_KEYWORDS) == 13
    covered: set[str] = set()
    for keywords, drill_id, _name in _DRILL_KEYWORDS:
        sample = keywords[0]
        attachments = _detect_reply_attachments(f"建议你试试{sample}。")
        ids = [a["drill_id"] for a in attachments if a["type"] == "drill_card"]
        assert drill_id in ids
        covered.add(drill_id)
    assert len(covered) == 13


def test_video_card_title_uses_coach_demo_suffix() -> None:
    """P2-M7-N1 D-6：后端 title 后缀对齐前端 `DRILL_VIDEO_TITLE_SUFFIX`。"""
    attachments = _detect_reply_attachments("可以先做瞄准杆站位练习。")
    video = next(a for a in attachments if a["type"] == "video_card")
    assert video["title"] == "瞄准杆站位练习 · 教练示范"
