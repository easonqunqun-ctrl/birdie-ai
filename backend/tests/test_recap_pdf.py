"""M8-07 · recap PDF 单元测试."""

from app.services.pdf.recap_pdf import build_watermark_line, render_recap_pdf


def test_render_recap_pdf_bytes() -> None:
    pdf = render_recap_pdf(
        title="教学报告 · 2026-05-29",
        body_markdown="## 课程概述\n测试内容",
        watermark_line=build_watermark_line(
            coach_display_name="王教练",
            coach_user_id="usr_coach123456",
        ),
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
