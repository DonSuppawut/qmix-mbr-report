"""Companion .xlsx built from the generated HTML (same numbers) + native Excel charts from svg.CHART_LOG."""
from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass, field
from pathlib import Path

import xlsxwriter

from .reference_html import parse_number

FONT = "Sarabun"
HEAD_BG = "#1B3A5C"
C = {"core": "#1F6FB2", "pmt": "#E1912B", "neg": "#C0392B", "pos": "#2E9B5B", "start": "#34495E",
     "end": "#1F6FB2", "fcst": "#A9C8E6", "ap": "#E1912B"}


# ---------------------------------------------------------------- HTML table model

@dataclass
class Cell:
    text: str
    cls: str = ""
    colspan: int = 1
    rowspan: int = 1


@dataclass
class Row:
    cells: list[Cell]
    cls: str = ""
    header: bool = False


@dataclass
class Block:
    heading: str
    sheet: str = ""  # optional explicit sheet name (<h3 data-sheet="…">)
    tables: list[list[Row]] = field(default_factory=list)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def _attr(tag: str, name: str) -> str:
    m = re.search(rf'{name}="([^"]*)"', tag)
    return m.group(1) if m else ""


def parse_blocks(html: str) -> list[Block]:
    """Every <h3>/<h4> heading with the tables that follow it (before the next heading)."""
    html = re.sub(r"<svg.*?</svg>|<style.*?</style>", "", html, flags=re.S)
    parts = re.split(r"(<h[34][^>]*>.*?</h[34]>)", html, flags=re.S)
    blocks = []
    for i in range(1, len(parts), 2):
        b = Block(_clean(parts[i]), _attr(parts[i], "data-sheet"))
        for t in re.findall(r"<table.*?</table>", parts[i + 1], flags=re.S):
            rows = []
            for tr in re.finditer(r"<tr([^>]*)>(.*?)</tr>", t, flags=re.S):
                cells = [Cell(_clean(body), _attr(tag, "class"), int(_attr(tag, "colspan") or 1),
                              int(_attr(tag, "rowspan") or 1))
                         for tag, body in re.findall(r"(<t[hd][^>]*>)(.*?)</t[hd]>", tr.group(2), flags=re.S)]
                rows.append(Row(cells, _attr(tr.group(1), "class"), header="<th" in tr.group(2)))
            b.tables.append(rows)
        if b.tables:
            blocks.append(b)
    return blocks


# ---------------------------------------------------------------- sheet names

_SCOPE = (("EST รวม", "รวม"), ("รวม (Core", "รวม"), ("Core", "Core"), ("PMT", "PMT"))  # 2nd: area reports
_TOPIC = {"1": "Waterfall", "2": "Scorecard", "4": "RawMat", "5": "Assign", "6": "Cartage", "9": "Forecast",
          "11": "Summary"}  # 11 = area-report summary (EST has 10 sections)
_FIXED = {"1.4": "EBITDA Bridge", "3.1": "Segment", "3.1.1": "Segment Cost", "3.2.1": "Concentration",
          "3.2.2": "Turnover", "3.2.3": "Rebate", "3.3": "NC Quality", "5.4": "Assign by Plant",
          "6.4": "QMix vs Sub", "6.5": "Vendors", "6.6": "Cartage by Plant", "7.1": "Plants ≥AP profit",
          "7.2": "Plants <AP profit", "7.3": "Plants <AP loss", "7.4": "Plants ≥AP loss", "7.5": "Plants no AP",
          "10.1": "Summary"}


def sheet_name(heading: str, used: set[str], explicit: str = "") -> str:
    no = heading.split(" ", 1)[0]
    if explicit:
        name = explicit
    elif no in _FIXED:
        name = f"{no} {_FIXED[no]}"
    elif no.startswith("8."):
        name = f"{no} Area {heading.split()[2]}"
    else:
        scope = next((s for key, s in _SCOPE if key in heading), "")
        name = f"{no} {_TOPIC.get(no.split('.')[0], '')} {scope}".strip()
    name = re.sub(r"[\[\]:*?/\\]", "", name)[:31]
    base, n = name, 2
    while name in used:
        name = f"{base[:28]} ({n})"
        n += 1
    used.add(name)
    return name


# ---------------------------------------------------------------- number parsing

def _decimals(text: str) -> int:
    m = re.search(r"\d\.(\d+)", text)
    return len(m.group(1)) if m else 0


def to_value(text: str):
    """-> (value, number_format) or (text, None) when the cell is not a single number."""
    t = text.strip()
    if not t or t in ("—", "-"):
        return t, None
    v = parse_number(t.replace(" จุด", ""))
    if v is None:
        return t, None
    d = _decimals(t)
    body = "#,##0" + ("." + "0" * d if d else "")
    signed = t.startswith(("+", "-", "−"))
    if t.endswith("%"):
        fmt = ("+" if signed else "") + ("0." + "0" * d if d else "0") + "%"
        return v / 100, fmt + (";-" + fmt.lstrip("+") if signed else "")
    suffix = ""
    for unit in (" บาท/m³", " บาท", " m³", " จุด"):
        if t.endswith(unit.strip()) or t.endswith(unit):
            suffix = f' "{unit.strip()}"'
            break
    if t.endswith("*"):
        suffix = ' "*"'
    fmt = (f"+{body}{suffix};-{body}{suffix};0{suffix}" if signed else f"{body}{suffix}")
    return v, fmt


# ---------------------------------------------------------------- workbook

class Book:
    def __init__(self, path: Path):
        self.wb = xlsxwriter.Workbook(str(path))
        self.wb.formats[0].set_font_name(FONT)
        self._fmt: dict = {}

    def fmt(self, **kw):
        key = tuple(sorted(kw.items()))
        if key not in self._fmt:
            self._fmt[key] = self.wb.add_format({"font_name": FONT, "font_size": 11, **kw})
        return self._fmt[key]

    def close(self):
        self.wb.close()


def write_table(book: Book, ws, rows: list[Row], r0: int) -> int:
    """Write one HTML table at row r0; returns the next free row."""
    taken: set[tuple[int, int]] = set()
    r = r0
    for row in rows:
        c = 0
        for cell in row.cells:
            while (r, c) in taken:
                c += 1
            style: dict = {"valign": "vcenter"}
            if row.header:
                style.update(bold=True, font_color="#FFFFFF", bg_color=HEAD_BG, text_wrap=True,
                             align="center" if c else "left", border=1, border_color="#FFFFFF")
            else:
                if row.cls == "category-row":
                    style.update(bold=True, bg_color="#F7F6F2")
                elif row.cls == "total-row":
                    style.update(bold=True, top=2)
                elif row.cls == "memo-row":
                    style.update(italic=True, font_color="#7A8580")
                if row.cls == "sub-row" and c == 0:
                    style.update(indent=2, font_color="#4E5A56")
                if "pos" in cell.cls:
                    style.update(font_color=C["pos"], bold=True)
                elif "neg" in cell.cls:
                    style.update(font_color=C["neg"], bold=True)
                style.setdefault("bottom", 1)
                style["bottom_color"] = "#E0DED6"
            value, numfmt = (cell.text, None) if row.header or c == 0 else to_value(cell.text)
            if numfmt:
                style["num_format"] = numfmt
            f = book.fmt(**style)
            if cell.colspan > 1 or cell.rowspan > 1:
                ws.merge_range(r, c, r + cell.rowspan - 1, c + cell.colspan - 1, value, f)
            elif isinstance(value, float):
                ws.write_number(r, c, value, f)
            else:
                ws.write_string(r, c, value, f)
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    taken.add((r + dr, c + dc))
            c += cell.colspan
        r += 1
    return r


# ---------------------------------------------------------------- native charts

def _label(s: str) -> str:
    return s.replace("|", " ")


def waterfall_chart(book: Book, ws, spec: dict, data_col: int, data_row: int):
    """Floating bars as stacked columns; four series so bars may cross zero. Values in THB millions."""
    bars = [(_label(spec["start"][0]), 0.0, spec["start"][1], C["start"])]
    level = spec["start"][1]
    for lab, d in spec["steps"]:
        bars.append((_label(lab), level, level + d, C["pos"] if d >= 0 else C["neg"]))
        level += d
    bars.append((_label(spec["end"][0]), 0.0, spec["end"][1], C["end"]))
    head = ["รายการ", "pos_base", "pos_bar", "neg_base", "neg_bar", "ผลกระทบ (ล้านบาท)"]
    ws.write_row(data_row, data_col, head, book.fmt(bold=True, font_color="#7A8580"))
    n = len(bars)
    for i, (lab, a, b, _) in enumerate(bars):
        lo, hi = min(a, b) / 1e6, max(a, b) / 1e6
        pos_base = lo if lo > 0 else 0.0
        pos_bar = hi - pos_base if hi > 0 else 0.0
        neg_base = hi if hi < 0 else 0.0
        neg_bar = lo - neg_base if lo < 0 else 0.0
        step = 0 < i < n - 1
        shown = (b - a) / 1e6 if step else b / 1e6
        fmt = book.fmt(font_color="#7A8580", num_format="0.00")
        ws.write_row(data_row + 1 + i, data_col, [lab, pos_base, pos_bar, neg_base, neg_bar, shown], fmt)
    sheet = ws.get_name()
    ref = lambda col: [sheet, data_row + 1, data_col + col, data_row + n, data_col + col]
    chart = book.wb.add_chart({"type": "column", "subtype": "stacked"})
    for col, visible in ((1, False), (2, True), (3, False), (4, True)):
        s = {"name": head[col], "categories": ref(0), "values": ref(col), "gap": 40}
        if visible:
            s["points"] = [{"fill": {"color": color}, "border": {"none": True}} for *_, color in bars]
            # Excel rejects per-label fonts and column+line combos with custom labels (chart renders empty),
            # so labels stay on the bars with one dark font that also reads on short bars.
            custom = []
            for i, (_, a, b, _c) in enumerate(bars):
                step = 0 < i < n - 1
                shown = (b - a) / 1e6 if step else b / 1e6
                owner = 2 if max(a, b) > 0 else 4
                custom.append({"value": f"{shown:+.2f}" if step else f"{shown:.2f}"} if owner == col
                              else {"delete": True})
            s["data_labels"] = {"value": True, "custom": custom, "position": "inside_end",
                                "font": {"name": FONT, "size": 9, "bold": True, "color": "#1B2624"}}
        else:
            s["fill"] = {"none": True}
            s["border"] = {"none": True}
        chart.add_series(s)
    chart.set_title({"name": spec["title"], "name_font": {"name": FONT, "size": 12}})
    chart.set_legend({"none": True})
    chart.set_y_axis({"name": "ล้านบาท", "num_format": "0.00", "name_font": {"name": FONT, "size": 9},
                      "num_font": {"name": FONT, "size": 9}, "major_gridlines": {"visible": True, "line": {"color": "#E0DED6"}}})
    chart.set_x_axis({"num_font": {"name": FONT, "size": 9}, "label_position": "low"})
    chart.set_size({"width": 900, "height": 380})
    chart.show_hidden_data()
    return chart


def tornado_charts(book: Book, ws, spec: dict, data_col: int, data_row: int) -> list:
    rows = spec["rows"]
    head = ["โรงงาน", "ประเภท", "EBITDA เดือนนี้", "Volume เดือนนี้", "EBITDA สะสม", "Volume สะสม"]
    ws.write_row(data_row, data_col, head, book.fmt(bold=True, font_color="#7A8580"))
    for i, r in enumerate(rows):
        ws.write_row(data_row + 1 + i, data_col, [r["label"], r["kind"], r["e_cur"], r["v_cur"], r["e_ytd"], r["v_ytd"]],
                     book.fmt(font_color="#7A8580", num_format="#,##0"))
    sheet, n = ws.get_name(), len(rows)
    charts = []
    for col, key, title in ((2, "e_cur", f"EBITDA (บาท) — {spec['cur']}"), (3, "v_cur", f"Volume (m³) — {spec['cur']}"),
                            (4, "e_ytd", f"EBITDA (บาท) — {spec['ytd']}"), (5, "v_ytd", f"Volume (m³) — {spec['ytd']}")):
        ch = book.wb.add_chart({"type": "bar"})
        ch.add_series({
            "name": title,
            "categories": [sheet, data_row + 1, data_col, data_row + n, data_col],
            "values": [sheet, data_row + 1, data_col + col, data_row + n, data_col + col],
            "points": [{"fill": {"color": C["neg"] if r[key] < 0 else (C["core"] if r["kind"] == "Core" else C["pmt"])}}
                       for r in rows],
            "data_labels": {"value": True, "num_format": "#,##0", "font": {"name": FONT, "size": 8}},
            "gap": 50,
        })
        ch.set_title({"name": title, "name_font": {"name": FONT, "size": 11}})
        ch.set_legend({"none": True})
        ch.set_y_axis({"reverse": True, "num_font": {"name": FONT, "size": 9}})
        ch.set_x_axis({"num_format": "#,##0", "num_font": {"name": FONT, "size": 8},
                       "major_gridlines": {"visible": True, "line": {"color": "#E0DED6"}}})
        ch.set_size({"width": 520, "height": 90 + 26 * n})
        ch.show_hidden_data()
        charts.append(ch)
    return charts


def forecast_charts(book: Book, ws, spec: dict, data_col: int, data_row: int) -> list:
    months, n_act = spec["months"], spec["n_actual"]
    sheet = ws.get_name()
    charts = []
    r = data_row
    for head, vals, ap, unit in spec["panels"]:
        ws.write_row(r, data_col, [head, "Actual/Forecast", "AP"], book.fmt(bold=True, font_color="#7A8580"))
        for i, (m, v, a) in enumerate(zip(months, vals, ap)):
            ws.write_row(r + 1 + i, data_col, [m, v, a], book.fmt(font_color="#7A8580", num_format="#,##0.0"))
        cats = [sheet, r + 1, data_col, r + 12, data_col]
        col = book.wb.add_chart({"type": "column"})
        col.add_series({"name": "Actual / Forecast", "categories": cats, "values": [sheet, r + 1, data_col + 1, r + 12, data_col + 1],
                        "points": [{"fill": {"color": (C["end"] if i < n_act else C["fcst"]) if v >= 0 else C["neg"]}}
                                   for i, v in enumerate(vals)], "gap": 60})
        line = book.wb.add_chart({"type": "line"})
        line.add_series({"name": "AP", "categories": cats, "values": [sheet, r + 1, data_col + 2, r + 12, data_col + 2],
                         "line": {"color": C["ap"], "width": 2}, "marker": {"type": "circle", "size": 4,
                                                                          "fill": {"color": C["ap"]}, "border": {"color": C["ap"]}}})
        col.combine(line)
        col.set_title({"name": head, "name_font": {"name": FONT, "size": 11}})
        col.set_legend({"position": "bottom", "font": {"name": FONT, "size": 9}})
        col.set_y_axis({"num_format": "#,##0", "num_font": {"name": FONT, "size": 9},
                        "major_gridlines": {"visible": True, "line": {"color": "#E0DED6"}}})
        col.set_x_axis({"num_font": {"name": FONT, "size": 9}})
        col.set_size({"width": 520, "height": 300})
        col.show_hidden_data()
        charts.append(col)
        r += 14
    return charts


def tu_chart(book: Book, ws, spec: dict, data_col: int, data_row: int):
    """TU per truck as columns (QMix blue / subcontractor orange) + target as a line."""
    rows = spec["rows"]
    head = ["รถ", spec["unit"], "เป้า"]
    ws.write_row(data_row, data_col, head, book.fmt(bold=True, font_color="#7A8580"))
    for i, (lab, v, _kind) in enumerate(rows):
        ws.write_row(data_row + 1 + i, data_col, [lab, v, spec["target"]], book.fmt(font_color="#7A8580", num_format="#,##0"))
    sheet, n = ws.get_name(), len(rows)
    cats = [sheet, data_row + 1, data_col, data_row + n, data_col]
    col = book.wb.add_chart({"type": "column"})
    col.add_series({"name": spec["unit"], "categories": cats,
                    "values": [sheet, data_row + 1, data_col + 1, data_row + n, data_col + 1],
                    "points": [{"fill": {"color": C["core"] if kind == "QMix" else C["pmt"]}} for *_, kind in rows],
                    "gap": 60})
    line = book.wb.add_chart({"type": "line"})
    line.add_series({"name": f"เป้า {spec['target']:,.0f}", "categories": cats,
                     "values": [sheet, data_row + 1, data_col + 2, data_row + n, data_col + 2],
                     "line": {"color": C["neg"], "width": 2.5}, "marker": {"type": "none"}})
    col.combine(line)
    col.set_title({"name": spec["title"], "name_font": {"name": FONT, "size": 11}})
    col.set_legend({"position": "bottom", "font": {"name": FONT, "size": 9}})
    col.set_y_axis({"num_format": "#,##0", "num_font": {"name": FONT, "size": 9},
                    "major_gridlines": {"visible": True, "line": {"color": "#E0DED6"}}})
    col.set_x_axis({"num_font": {"name": FONT, "size": 9}})
    col.set_size({"width": 900, "height": 320})
    col.show_hidden_data()
    return col


def quality_chart(book: Book, ws, spec: dict, data_col: int, data_row: int):
    """Strength per sample (actual 7/28-day + target lines); empty cells leave gaps."""
    labels, series = spec["labels"], spec["series"]
    ws.write_row(data_row, data_col, ["ตัวอย่าง"] + [name for name, _ in series], book.fmt(bold=True, font_color="#7A8580"))
    fmt = book.fmt(font_color="#7A8580", num_format="#,##0.0")
    for i, lab in enumerate(labels):
        ws.write_string(data_row + 1 + i, data_col, lab, fmt)
        for k, (_, vs) in enumerate(series):
            if vs[i] is not None:
                ws.write_number(data_row + 1 + i, data_col + 1 + k, vs[i], fmt)
    sheet, n = ws.get_name(), len(labels)
    ch = book.wb.add_chart({"type": "line"})
    colors = ["#1F6FB2", "#2E9B5B", "#E1912B", "#C0392B", "#7A8580"]
    dashes = [None, None, "dash", None, "round_dot"]
    for k, (name, _) in enumerate(series):
        line = {"color": colors[k % 5], "width": 2}
        if dashes[k % 5]:
            line["dash_type"] = dashes[k % 5]
        ch.add_series({"name": name, "categories": [sheet, data_row + 1, data_col, data_row + n, data_col],
                       "values": [sheet, data_row + 1, data_col + 1 + k, data_row + n, data_col + 1 + k],
                       "line": line,
                       "marker": {"type": "circle", "size": 4, "fill": {"color": colors[k]}, "border": {"color": colors[k]}}
                       if k < 2 else {"type": "none"}})
    ch.show_blanks_as("gap")
    ch.set_title({"name": spec["title"], "name_font": {"name": FONT, "size": 11}})
    ch.set_legend({"position": "bottom", "font": {"name": FONT, "size": 9}})
    ch.set_y_axis({"name": "ksc", "num_format": "#,##0", "num_font": {"name": FONT, "size": 9},
                   "name_font": {"name": FONT, "size": 9}, "major_gridlines": {"visible": True, "line": {"color": "#E0DED6"}}})
    ch.set_x_axis({"num_font": {"name": FONT, "size": 8}})
    ch.set_size({"width": 900, "height": 340})
    ch.show_hidden_data()
    return ch


# ---------------------------------------------------------------- build

def build_xlsx(html: str, charts: list[dict], out: Path, title: str) -> dict:
    blocks = parse_blocks(html)
    book = Book(out)
    used: set[str] = set()
    info = {"sheets": 0, "charts": 0}
    cover = book.wb.add_worksheet("สารบัญ")
    used.add("สารบัญ")
    cover.write(0, 0, title, book.fmt(bold=True, font_size=16, font_color="#1F6FB2"))
    cover.write(1, 0, "ตัวเลขทุกตารางสร้างจากข้อมูลชุดเดียวกับไฟล์ HTML/PDF ของเดือนนี้ — กราฟเป็น native Excel chart "
                      "(copy ไป PowerPoint แล้วแก้ไขได้)", book.fmt(italic=True, font_color="#4E5A56"))
    cover.set_column(0, 0, 60)
    cover.set_column(1, 1, 90)
    for i, b in enumerate(blocks):
        name = sheet_name(b.heading, used, b.sheet)
        ws = book.wb.add_worksheet(name)
        cover.write_url(3 + i, 0, f"internal:'{name}'!A1", book.fmt(font_color="#1F6FB2", underline=1), name)
        cover.write_string(3 + i, 1, b.heading, book.fmt())
        ws.write(0, 0, b.heading, book.fmt(bold=True, font_size=13, font_color="#1F6FB2"))
        r = 2
        width = 0
        for t in b.tables:
            r = write_table(book, ws, t, r) + 2
            width = max(width, sum(c.colspan for c in t[0].cells))
        ws.set_column(0, 0, 44)
        ws.set_column(1, max(width - 1, 1), 16)
        ws.freeze_panes(1, 0)
        mine = [c for c in charts if c["sheet"] == b.heading]
        data_col = max(width, 1) + 2
        data_row = 2
        chart_row = r + 1
        for spec in mine:
            if spec["kind"] == "waterfall":
                ch = waterfall_chart(book, ws, spec, data_col, data_row)
                ws.insert_chart(chart_row, 0, ch)
                chart_row += 21
                data_row += len(spec["steps"]) + 5
                info["charts"] += 1
            elif spec["kind"] == "tornado":
                chs = tornado_charts(book, ws, spec, data_col, data_row)
                h = 7 + (26 * len(spec["rows"])) // 20
                for k, ch in enumerate(chs):
                    ws.insert_chart(chart_row + (k // 2) * h, (k % 2) * 4, ch)
                chart_row += 2 * h + 2
                data_row += len(spec["rows"]) + 3
                info["charts"] += len(chs)
            elif spec["kind"] in ("tu", "quality"):
                ch = (tu_chart if spec["kind"] == "tu" else quality_chart)(book, ws, spec, data_col, data_row)
                ws.insert_chart(chart_row, 0, ch)
                chart_row += 18
                data_row += (len(spec["rows"]) if spec["kind"] == "tu" else len(spec["labels"])) + 3
                info["charts"] += 1
            elif spec["kind"] == "forecast":
                chs = forecast_charts(book, ws, spec, data_col, data_row)
                for k, ch in enumerate(chs):
                    ws.insert_chart(chart_row + (k // 2) * 16, (k % 2) * 4, ch)
                chart_row += 34
                data_row += 14 * len(chs)
                info["charts"] += len(chs)
        if mine:
            ws.set_column(data_col, data_col + 6, 14, None, {"level": 1, "hidden": True})
        info["sheets"] += 1
    book.close()
    return info
