"""M8-07 · 教学报告 PDF 生成（reportlab + 水印）."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
FONT = "STSong-Light"


def render_recap_pdf(
    *,
    title: str,
    body_markdown: str,
    watermark_line: str,
) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    _draw_watermark(c, watermark_line, width, height)
    c.setFont(FONT, 16)
    c.drawString(20 * mm, height - 25 * mm, title)
    c.setFont(FONT, 11)
    y = height - 35 * mm
    for raw_line in body_markdown.splitlines():
        line = raw_line.strip()
        if not line:
            y -= 5 * mm
            continue
        if line.startswith("## "):
            y -= 4 * mm
            c.setFont(FONT, 13)
            c.drawString(18 * mm, y, line.removeprefix("## ").strip())
            c.setFont(FONT, 11)
            y -= 7 * mm
            continue
        wrapped = _wrap_line(line, max_chars=34)
        for part in wrapped:
            if y < 25 * mm:
                c.showPage()
                _draw_watermark(c, watermark_line, width, height)
                c.setFont(FONT, 11)
                y = height - 20 * mm
            c.drawString(20 * mm, y, part)
            y -= 5.5 * mm
    c.save()
    return buffer.getvalue()


def _wrap_line(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + max_chars])
        start += max_chars
    return parts


def _draw_watermark(c: canvas.Canvas, text: str, width: float, height: float) -> None:
    c.saveState()
    c.setFillAlpha(0.12)
    c.setFont(FONT, 10)
    step_x = 55 * mm
    step_y = 40 * mm
    y = 10 * mm
    while y < height:
        x = 5 * mm
        while x < width:
            c.saveState()
            c.translate(x + 20 * mm, y + 10 * mm)
            c.rotate(45)
            c.drawString(0, 0, text)
            c.restoreState()
            x += step_x
        y += step_y
    c.restoreState()


def build_watermark_line(*, coach_display_name: str, coach_user_id: str, generated_at: datetime | None = None) -> str:
    ts = (generated_at or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    tail = coach_user_id[-6:] if len(coach_user_id) >= 6 else coach_user_id
    return f"{coach_display_name} · {tail} · 领翼golf · {ts}"
