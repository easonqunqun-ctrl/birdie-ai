"""chat_service 回复附件 heuristic 单测（v1.1.1 video_card 成对）."""

from __future__ import annotations

from app.services.chat_service import _detect_reply_attachments


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
    assert attachments[1]["title"] == "毛巾夹臂练习示范"


def test_detect_reply_attachments_empty_when_no_drill_keywords() -> None:
    assert _detect_reply_attachments("今天天气不错") == []
