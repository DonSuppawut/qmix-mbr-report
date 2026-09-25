"""Self-contained page shell: embedded Sarabun, standard table CSS, TOC, print layout for PDF export."""
from __future__ import annotations

import base64
import re
from pathlib import Path

from .fmt import esc, th_month_long

ASSETS = Path(__file__).resolve().parents[1] / "assets"

# Table CSS is fixed by the spec (section 6) — do not tweak per month.
STANDARD_TABLE_CSS = """
table{ width:100%; border-collapse:collapse; font-size:14px; margin:16px 0 24px; }
th{ text-align:left; font-weight:600; font-size:12.5px; letter-spacing:.02em; color:#4E5A56; border-bottom:2px solid #1B2624; padding:8px 12px; }
td{ padding:8px 12px; border-bottom:1px solid #E0DED6; }
td:not(:first-child), th:not(:first-child){ text-align:right; }
tr.category-row td{ font-weight:700; background:#F7F6F2; }
tr.total-row td{ font-weight:700; border-top:2px solid #1B2624; border-bottom:none; }
.pos{ color:#2E9B5B; font-weight:600; }
.neg{ color:#C0392B; font-weight:600; }
"""

LAYOUT_CSS = """
body{ font-family:'Sarabun',sans-serif; color:#1B2624; background:#fff; margin:0; line-height:1.55; }
.wrap{ max-width:1100px; margin:0 auto; padding:8px 24px 24px; }
.cover h1{ color:#1F6FB2; font-size:26px; margin:24px 0 4px; }
.cover .line2{ margin-top:0; }
.cover .scope{ color:#4E5A56; margin:4px 0 16px; }
h2{ color:#1F6FB2; border-bottom:2px solid #1F6FB2; padding-bottom:4px; margin-top:36px; }
h3{ color:#2c3e50; margin:28px 0 6px; }
p.meta{ color:#4E5A56; font-style:italic; margin:4px 0; }
figure{ margin:8px 0 4px; }
figcaption{ font-weight:600; color:#2c3e50; margin:12px 0 2px; }
svg.chart{ display:block; max-width:100%; height:auto; }
.tscroll{ overflow-x:auto; }
tr.sub-row td:first-child{ padding-left:32px; color:#4E5A56; }
tr.memo-row td{ font-style:italic; color:#7A8580; }
.footnote{ font-size:12.5px; color:#4E5A56; margin:4px 0 12px; }
.cover h1{ overflow-wrap:anywhere; }
.toc{ background:#F7F6F2; padding:14px 22px; border-radius:6px; }
.toc a{ color:#1F6FB2; text-decoration:none; display:block; padding:2px 0; }
.srcnote{ background:#eef4fa; border-left:4px solid #1F6FB2; padding:10px 14px; margin:12px 0; font-size:12.5px; }
.strategy{ background:#f0f9f2; border-left:4px solid #2E9B5B; padding:10px 14px; margin:12px 0; font-size:13.5px; }
.watch{ background:#fdf0ef; border-left:4px solid #C0392B; padding:10px 14px; margin:12px 0; font-size:13.5px; }
@page{ size:A4; margin:12mm 10mm; }
@media print{
  .wrap{ max-width:none; padding:0; }
  section.wrap{ break-before:page; }
  h2, h3{ break-after:avoid; }
  table, figure, .watch, .strategy, .srcnote{ break-inside:avoid; }
  .tscroll{ overflow:visible; }
}
"""


def _font_face() -> str:
    faces = []
    for weight, name in ((400, "Sarabun-Regular.ttf"), (700, "Sarabun-Bold.ttf")):
        b64 = base64.b64encode((ASSETS / name).read_bytes()).decode("ascii")
        faces.append(f"@font-face{{font-family:'Sarabun';font-weight:{weight};font-style:normal;"
                     f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")
    return "\n".join(faces)


def build_page(year: int, month: int, sections: list[str]) -> str:
    toc = []
    for s in sections:
        m = re.search(r'<h2 id="(s\d+)">(.*?)</h2>', s)
        if m:
            toc.append(f'<a href="#{m.group(1)}">{m.group(2)}</a>')
    title = f"MBR EST {th_month_long(year, month)}"
    cover = (
        '<div class="wrap cover">'
        '<h1>รายงานผลประกอบการประจำเดือน (MBR)</h1>'
        f'<h1 class="line2">ธุรกิจคอนกรีตผสมเสร็จ ภาคตะวันออก (EST) — เดือน{esc(th_month_long(year, month))}</h1>'
        '<p class="scope">ขอบเขต: Core + PMT (รวม Insource ฝั่ง PMT)</p>'
        f'<nav class="toc">{"".join(toc)}</nav></div>'
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"th\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{esc(title)}</title><style>{_font_face()}{LAYOUT_CSS}{STANDARD_TABLE_CSS}</style></head>"
        f"<body>{cover}{''.join(sections)}</body></html>\n"
    )
