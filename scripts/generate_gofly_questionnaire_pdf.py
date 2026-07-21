#!/usr/bin/env python3
"""Generate Gofly vendor technical questionnaire PDF from HTML via PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs/release-notes/gofly-vendor-technical-questionnaire-2026-06-13.html"
OUTPUT = ROOT / "docs/release-notes/gofly-vendor-technical-questionnaire-2026-06-13.pdf"

USER_CSS = """
body {
  font-family: pingfang sc, hiragino sans gb, microsoft yahei, sans-serif;
  font-size: 10.5pt;
  line-height: 1.65;
  color: #222;
}
h1 { font-size: 16pt; color: #1a237e; margin: 0 0 4px; }
.subtitle { font-size: 13pt; margin-bottom: 14px; }
h2 { font-size: 12pt; color: #1a237e; margin: 16px 0 8px; }
h3 { font-size: 11pt; margin: 12px 0 6px; }
.meta { margin: 2px 0; }
p { margin: 0 0 8px; text-align: justify; }
ul, ol { margin: 4px 0 10px; padding-left: 1.4em; }
li { margin: 3px 0; }
code {
  font-family: menlo, consolas, monospace;
  font-size: 9.5pt;
  background: #f4f5f7;
  padding: 0 3px;
}
.scope-item { margin-bottom: 4px; }
.scope-dep { color: #555; margin: 0 0 10px 0; }
.footer { margin-top: 18px; }
"""


def build_pdf() -> Path:
    if not HTML.is_file():
        raise FileNotFoundError(f"Missing HTML source: {HTML}")

    html = HTML.read_text(encoding="utf-8")
    story = fitz.Story(html=html, user_css=USER_CSS, archive=str(HTML.parent))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    writer = fitz.DocumentWriter(str(OUTPUT))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (56, 50, -56, -50)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev, None)
        writer.end_page()
    writer.close()
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(path)
