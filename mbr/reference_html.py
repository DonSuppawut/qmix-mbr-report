"""Parse tables out of a delivered MBR HTML report (regression baseline)."""
from __future__ import annotations

import html
import re
from pathlib import Path

_NUM = re.compile(r"^[+\-−]?[\d,]+(\.\d+)?$")


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_number(text: str) -> float | None:
    t = text.replace("บาท/m³", "").replace("บาท", "").replace("m³", "").replace("%", "").strip()
    t = t.replace("−", "-").rstrip(" *")
    return float(t.replace(",", "")) if _NUM.match(t) else None


def decimals(text: str) -> int:
    m = re.search(r"\.(\d+)", text)
    return len(m.group(1)) if m else 0


def tables_by_heading(path: Path) -> dict[str, list[list[str]]]:
    """Map each <h3>/<h4> heading to the first <table> after it (rows of cleaned cell text)."""
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    out: dict[str, list[list[str]]] = {}
    parts = re.split(r"(<h[34][^>]*>.*?</h[34]>)", s, flags=re.S)
    for i in range(1, len(parts), 2):
        heading = _clean(parts[i])
        m = re.search(r"<table.*?</table>", parts[i + 1], flags=re.S)
        if not m:
            continue
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", m.group(0), flags=re.S):
            rows.append([_clean(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S)])
        out[heading] = rows
    return out
