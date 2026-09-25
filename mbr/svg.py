"""Hand-written SVG charts (no raster, text stays text so it pastes sharp into PowerPoint)."""
from __future__ import annotations

import math

from .fmt import esc, mb

C_START = "#34495E"
C_POS = "#2E9B5B"
C_NEG = "#C0392B"
C_END = "#1F6FB2"
C_AXIS = "#4E5A56"
C_GRID = "#E0DED6"
FONT = "Sarabun, sans-serif"

# Every chart drawn is also logged here so the xlsx writer can rebuild it as a native Excel chart
# from exactly the same numbers. build_report clears it before each build.
CHART_LOG: list[dict] = []


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo or abs(hi) or 1.0
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    return ticks


def _wrap(label: str, width: int = 10) -> list[str]:
    if "|" in label:  # explicit break points for Thai labels (no spaces to wrap on)
        return label.split("|")[:2]
    words, lines, cur = label.split(" "), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return lines[:2]


C_CORE = "#1F6FB2"
C_PMT = "#E1912B"


def _fmt_short(v: float, unit: str) -> str:
    if unit == "THB":
        return f"{v / 1e6:,.2f}M" if abs(v) >= 1e5 else f"{v / 1e3:,.0f}k"
    return f"{v:,.0f}"


def tornado(rows: list[dict], title: str, cur_label: str, ytd_label: str, width: int = 820, sheet: str = "") -> str:
    CHART_LOG.append({"kind": "tornado", "sheet": sheet, "title": title, "rows": rows, "cur": cur_label, "ytd": ytd_label})
    """rows: dicts with label, kind ('Core'/'PMT'), e_cur, v_cur, e_ytd, v_ytd — already sorted.
    2x2 panels: top = current month, bottom = YTD; left = EBITDA, right = Volume.
    Bar colour follows the sign of the value in that panel only."""
    name_w, gap, pad_top, row_h, head_h = 232, 22, 8, 24, 30
    panel_w = (width - name_w - gap - 16) / 2
    block_h = head_h + row_h * len(rows) + 22
    height = pad_top + 2 * block_h + 12
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height:.0f}" width="100%" role="img" '
           f'font-family="{FONT}" class="chart"><title>{esc(title)}</title>']

    def panel(x0: float, y0: float, key: str, unit: str, head: str) -> None:
        vals = [r[key] for r in rows]
        lo, hi = min(0.0, *vals), max(0.0, *vals)
        span = (hi - lo) or 1.0
        inner = panel_w - 96
        sx = lambda v: x0 + 48 + (v - lo) / span * inner
        out.append(f'<text x="{x0 + panel_w / 2:.1f}" y="{y0 + 18:.1f}" font-size="14" font-weight="700" '
                   f'text-anchor="middle" fill="#1B2624">{esc(head)}</text>')
        zx = sx(0)
        top = y0 + head_h
        out.append(f'<line x1="{zx:.1f}" x2="{zx:.1f}" y1="{top - 2:.1f}" y2="{top + row_h * len(rows) + 2:.1f}" '
                   f'stroke="{C_AXIS}" stroke-width="1"/>')
        for i, r in enumerate(rows):
            v = r[key]
            y = top + i * row_h + 3
            color = C_NEG if v < 0 else (C_CORE if r["kind"] == "Core" else C_PMT)
            x1, x2 = sorted((zx, sx(v)))
            out.append(f'<rect x="{x1:.1f}" y="{y:.1f}" width="{max(x2 - x1, 0.8):.1f}" height="{row_h - 6}" fill="{color}"/>')
            tx, anchor = (x2 + 4, "start") if v >= 0 else (x1 - 4, "end")
            out.append(f'<text x="{tx:.1f}" y="{y + row_h - 10:.1f}" font-size="12.5" text-anchor="{anchor}" '
                       f'fill="{C_AXIS}">{_fmt_short(v, unit)}</text>')

    for b, (label, ek, vk) in enumerate(((cur_label, "e_cur", "v_cur"), (ytd_label, "e_ytd", "v_ytd"))):
        y0 = pad_top + b * block_h
        for i, r in enumerate(rows):
            y = y0 + head_h + i * row_h + row_h - 8
            out.append(f'<text x="{name_w - 8}" y="{y:.1f}" font-size="13" text-anchor="end" fill="#1B2624">'
                       f'{esc(r["label"])}</text>')
        panel(name_w, y0, ek, "THB", f"EBITDA (บาท) — {label}")
        panel(name_w + panel_w + gap, y0, vk, "m3", f"Volume (m³) — {label}")
    out.append(f'<text x="{name_w}" y="{height - 4:.0f}" font-size="12.5" fill="{C_AXIS}">'
               f'<tspan fill="{C_CORE}">■</tspan> Core   <tspan fill="{C_PMT}">■</tspan> PMT   '
               f'<tspan fill="{C_NEG}">■</tspan> ค่าติดลบ</text>')
    out.append("</svg>")
    return "\n".join(out)


C_FCST = "#A9C8E6"
C_AP = "#E1912B"


def forecast_panels(title: str, month_labels: list[str], n_actual: int, panels: list[tuple[str, list, list, str]],
                    width: int = 820, sheet: str = "") -> str:
    CHART_LOG.append({"kind": "forecast", "sheet": sheet, "title": title, "months": month_labels,
                      "n_actual": n_actual, "panels": panels})
    """2x2 grid; each panel = (heading, actual+forecast values, AP values, unit). Actual dark, forecast light,
    AP as an orange line."""
    cols, pw, ph, gx, gy = 2, (width - 24) / 2, 250, 24, 22
    height = 2 * ph + gy + 28
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" '
           f'font-family="{FONT}" class="chart"><title>{esc(title)}</title>']
    for k, (head, vals, ap, unit) in enumerate(panels):
        x0 = (k % cols) * (pw + gx)
        y0 = (k // cols) * (ph + gy)
        ml, mt, mb_ = 62, 30, 30
        iw, ih = pw - ml - 8, ph - mt - mb_
        lo = min(0.0, *vals, *ap)
        hi = max(0.0, *vals, *ap)
        ticks = _nice_ticks(lo, hi, 4)
        lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
        y = lambda v: y0 + mt + (hi - v) / ((hi - lo) or 1) * ih
        slot = iw / len(vals)
        out.append(f'<text x="{x0 + ml}" y="{y0 + 18}" font-size="14" font-weight="700" fill="#1B2624">{esc(head)}</text>')
        for t in ticks:
            lbl = f"{t / 1e6:,.1f}M" if unit == "THB" else f"{t:,.0f}"
            out.append(f'<line x1="{x0 + ml}" x2="{x0 + pw - 8:.1f}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{C_GRID}"/>')
            out.append(f'<text x="{x0 + ml - 6}" y="{y(t) + 4:.1f}" font-size="12" text-anchor="end" fill="{C_AXIS}">{lbl}</text>')
        for i, v in enumerate(vals):
            bx = x0 + ml + i * slot + slot * 0.18
            top, bot = sorted((y(v), y(0)))
            color = (C_END if i < n_actual else C_FCST) if v >= 0 else C_NEG
            out.append(f'<rect x="{bx:.1f}" y="{top:.1f}" width="{slot * 0.64:.1f}" height="{max(bot - top, 0.8):.1f}" fill="{color}"/>')
            out.append(f'<text x="{bx + slot * 0.32:.1f}" y="{y0 + ph - 9}" font-size="12" text-anchor="middle" '
                       f'fill="{C_AXIS}">{esc(month_labels[i])}</text>')
        pts = " ".join(f"{x0 + ml + (i + 0.5) * slot:.1f},{y(v):.1f}" for i, v in enumerate(ap))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{C_AP}" stroke-width="2"/>')
        for i, v in enumerate(ap):
            out.append(f'<circle cx="{x0 + ml + (i + 0.5) * slot:.1f}" cy="{y(v):.1f}" r="2.6" fill="{C_AP}"/>')
    # AP legend key is drawn as a line — U+2501 is not in Sarabun and would pull a fallback font into the PDF.
    out.append(f'<text x="{62}" y="{height - 6}" font-size="12.5" fill="{C_AXIS}"><tspan fill="{C_END}">■</tspan> Actual   '
               f'<tspan fill="{C_FCST}">■</tspan> Forecast</text>')
    out.append(f'<line x1="262" x2="282" y1="{height - 10}" y2="{height - 10}" stroke="{C_AP}" stroke-width="2.5"/>'
               f'<text x="288" y="{height - 6}" font-size="12.5" fill="{C_AXIS}">AP</text>')
    out.append("</svg>")
    return "\n".join(out)


def waterfall(start_label: str, start: float, steps: list[tuple[str, float]], end_label: str, end: float,
              title: str, width: int = 820, height: int = 380, sheet: str = "") -> str:
    """Values in THB; labels shown in millions of baht."""
    CHART_LOG.append({"kind": "waterfall", "sheet": sheet, "title": title, "start": (start_label, start),
                      "steps": steps, "end": (end_label, end)})
    bars = [(start_label, 0.0, start, "start")]
    level = start
    for label, delta in steps:
        bars.append((label, level, level + delta, "pos" if delta >= 0 else "neg"))
        level += delta
    bars.append((end_label, 0.0, end, "end"))

    lo = min(0.0, *(min(a, b) for _, a, b, _ in bars))
    hi = max(0.0, *(max(a, b) for _, a, b, _ in bars))
    ticks = _nice_ticks(lo, hi)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])

    ml, mr, mt, mbm = 58, 8, 30, 50
    pw, ph = width - ml - mr, height - mt - mbm
    y = lambda v: mt + (hi - v) / (hi - lo) * ph
    slot = pw / len(bars)
    bw = slot * 0.62
    color = {"start": C_START, "pos": C_POS, "neg": C_NEG, "end": C_END}

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
           f'role="img" font-family="{FONT}" class="chart">',
           f"<title>{esc(title)}</title>"]
    for t in ticks:
        out.append(f'<line x1="{ml}" x2="{width - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{C_GRID}" stroke-width="1"/>')
        out.append(f'<text x="{ml - 8}" y="{y(t) + 4:.1f}" font-size="12.5" text-anchor="end" fill="{C_AXIS}">{mb(t)}</text>')
    out.append(f'<text x="{ml - 8}" y="{mt - 14}" font-size="12.5" text-anchor="end" fill="{C_AXIS}">ล้านบาท</text>')
    out.append(f'<line x1="{ml}" x2="{width - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{C_AXIS}" stroke-width="1.2"/>')

    for i, (label, a, b, kind) in enumerate(bars):
        x = ml + i * slot + (slot - bw) / 2
        top, bot = y(max(a, b)), y(min(a, b))
        out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bot - top, 0.8):.1f}" fill="{color[kind]}"/>')
        value = b - a if kind in ("pos", "neg") else b
        txt = mb(value, signed=kind in ("pos", "neg"))
        above = b >= a if kind in ("pos", "neg") else b >= 0
        ty = top - 6 if above else bot + 15
        out.append(f'<text x="{x + bw / 2:.1f}" y="{ty:.1f}" font-size="13" font-weight="600" text-anchor="middle" '
                   f'fill="{C_AXIS}">{txt}</text>')
        if i < len(bars) - 1:
            nx = ml + (i + 1) * slot + (slot - bw) / 2
            out.append(f'<line x1="{x + bw:.1f}" x2="{nx:.1f}" y1="{y(b):.1f}" y2="{y(b):.1f}" stroke="{C_AXIS}" '
                       f'stroke-width="1" stroke-dasharray="3,3"/>')
        for j, line in enumerate(_wrap(label)):
            out.append(f'<text x="{x + bw / 2:.1f}" y="{height - mbm + 18 + j * 16}" font-size="12.5" '
                       f'text-anchor="middle" fill="#1B2624">{esc(line)}</text>')
    out.append("</svg>")
    return "\n".join(out)
