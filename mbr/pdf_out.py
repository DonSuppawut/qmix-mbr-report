"""PDF export via headless Chromium (Microsoft Edge that ships with Windows; bundled Chromium as fallback)."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Error, sync_playwright

FOOTER = ('<div style="font-family:Sarabun,sans-serif;font-size:8px;color:#7A8580;width:100%;'
          'padding:0 10mm;display:flex;justify-content:space-between">'
          '<span>{title}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def export_pdf(html_path: Path, pdf_path: Path, title: str) -> int:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Error:
            browser = p.chromium.launch()  # needs `python -m playwright install chromium`
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri())
            page.emulate_media(media="print")
            page.evaluate("document.fonts.ready")
            page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True,
                     display_header_footer=True, header_template="<span></span>",
                     footer_template=FOOTER.format(title=title),
                     margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"})
        finally:
            browser.close()
    from pypdf import PdfReader
    return len(PdfReader(str(pdf_path)).pages)
