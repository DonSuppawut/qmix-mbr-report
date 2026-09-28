"""Area-report operations sections: truck utilisation (Section 9) and quality (Section 10).

TU (Don 2026-09-28): only the trucks REGISTERED to a plant (Google Sheet 'รถโม่กิจการตะวันออก', monthly tab,
QMix and subcontractor alike; the 'outside register' tab is never counted). A truck's TU counts everything it
did at any plant — Don wants each truck used as much as possible wherever it runs:
    TU = m³ (all plants) ÷ distinct days it ran × 28      target 380 m³ per truck
Shown only for the plants in data/config/plants.json → tu.plants (Core + ศรีราชา + แหลมฉบัง).

The registry is downloaded by the script (mbr/truck_registry.py). Snapshots Claude pulls through MCP:
- data/snapshots/<ym>/truck_tu.json         days (count_distinct production_date) and m³ per truck
- data/snapshots/<ym>/truck_dispatch.json   m³ per plant x truck (for "m³ at this plant")
Quality: each plant's strength Google Sheet — see mbr/quality_sheets.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import quality_sheets as QS
from . import svg, truck_registry
from .fmt import delta_class, esc, num, th_month_short
from .report import MonthData, _box, _table

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshots"


class SnapshotMissing(Exception):
    pass


def _load(path: Path) -> dict:
    if not path.exists():
        raise SnapshotMissing(f"ไม่พบ {path.relative_to(SNAP.parent.parent)} — ให้ Claude ดึงผ่าน MCP ก่อน (ดู README)")
    return json.loads(path.read_text(encoding="utf-8"))


def _ym(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


# ---------------------------------------------------------------- TU

def load_fleet(md: MonthData, cfg: dict, refresh: bool = False) -> dict:
    ym, lm = _ym(md.year, md.month), _ym(*md.lm_year_month)
    reg = truck_registry.load(md.year, md.month, cfg["registry_sheet"], refresh)
    cur = _load(SNAP / ym / "truck_tu.json")
    missing = sorted({t for t, *_ in reg["trucks"] if t not in cur["days"] and t not in cur["m3"]}
                     - {t for t, _, _, status, *_ in reg["trucks"] if status == "Inactive"})
    has_lm = lm in reg["sheets"]  # TU started Aug'69 — no comparison until the registry has last month's tab
    return {"reg": reg, "cur": cur, "lm": _load(SNAP / lm / "truck_tu.json") if has_lm else None, "lm_sheet": lm,
            "disp": _load(SNAP / ym / "truck_dispatch.json"), "cfg": cfg, "no_dp": missing}


def _units(reg: dict, plant: str) -> list[dict]:
    """Counted units of one plant: registered, not Inactive; a 'merged' pair (replacement truck) is one unit."""
    cols = {c: i for i, c in enumerate(reg["cols"])}
    rows = [r for r in reg["trucks"] if r[cols["plant"]] == plant and r[cols["status"]] != "Inactive"]
    merged = {t: name for name, ts in reg.get("merged", {}).items() for t in ts}
    units, seen = [], set()
    for r in rows:
        t = r[cols["truck"]]
        name = merged.get(t, t)
        if name in seen:
            continue
        seen.add(name)
        members = reg["merged"][name] if name in reg.get("merged", {}) else [t]
        notes = [x for x in dict.fromkeys(rr[cols["movement"]] for rr in rows if rr[cols["truck"]] in members)
                 if x and x != "Baseline"]
        units.append({"name": name, "members": members, "owner": r[cols["owner"]], "note": "; ".join(notes)})
    return units


def _tu(snap: dict, unit: dict, days_per_month: int) -> tuple[int, float, float | None]:
    m3 = sum(snap["m3"].get(t, 0.0) for t in unit["members"])
    if len(unit["members"]) > 1:
        days = snap.get("merged_days", {}).get(unit["name"])
        if days is None:
            raise SnapshotMissing(f"{unit['name']}: merged_days missing in truck_tu.json (union of days, not a sum)")
    else:
        days = snap["days"].get(unit["members"][0], 0)
    return days, m3, (m3 / days * days_per_month if days else None)


def section_tu(md: MonthData, fleet: dict, no: int) -> str:
    cfg = fleet["cfg"]
    target, days28 = cfg["target_m3"], cfg["days"]
    cur_s, lm_s = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    plants = [md.plants[c] for c in cfg["plants"] if c in md.plants]
    parts = [f'<h2 id="s{no}">{no}. การใช้รถโม่ (Truck Utilization — TU)</h2>',
             f'<p class="meta">TU = คิวที่รถคันนั้นส่งได้ทั้งเดือน (ทุกโรงงานที่ไปวิ่ง) ÷ จำนวนวันที่รถวิ่งจริง × {days28} วัน '
             f'(คิว/คัน/เดือน) — นับเฉพาะรถที่จดทะเบียนกับโรงงานนั้น ทั้งรถ QMix และรถร่วม — '
             f'เป้า {target:,} คิว/คัน/เดือน — แสดงเฉพาะโรง Core ศรีราชา และแหลมฉบัง</p>']
    if not plants:
        return '<section class="wrap">' + "\n".join(parts + ["<p>ไม่มีโรงงานที่ต้องแสดง TU ในเขตนี้</p>"]) + "</section>"

    # TU started in Aug'69 (Don): compare with last month only once the registry has last month's tab.
    has_lm = fleet["lm"] is not None
    tu_s = lambda v: num(v, 0) if v is not None else "—"
    pct = lambda v: f"{v / target * 100:.0f}%" if v is not None else "—"

    def lm_cells(v, v_lm) -> str:
        if not has_lm:
            return ""
        both = v is not None and v_lm is not None
        return (f"<td>{tu_s(v_lm)}</td><td class=\"{delta_class(v - v_lm) if both else ''}\">"
                f"{num(v - v_lm, 0, True) if both else '—'}</td>")

    lm_head = [f"TU {lm_s}", "Δ TU"] if has_lm else []
    summary, detail = [], []
    for i, p in enumerate(plants, 2):
        units = _units(fleet["reg"], p.code)
        at_plant = fleet["disp"]["m3"].get(p.code, {})
        rows, chart = [], []
        for u in units:
            d, m3, tu = _tu(fleet["cur"], u, days28)
            tu_lm = _tu(fleet["lm"], u, days28)[2] if has_lm else None
            u.update(days=d, m3=m3, tu=tu, tu_lm=tu_lm, here=sum(at_plant.get(t, 0.0) for t in u["members"]))
        units.sort(key=lambda u: -(u["tu"] or 0))
        for u in units:
            tu = u["tu"]
            kind = "QMix" if u["owner"] == "QMix" else "Sub"
            if tu is not None:
                chart.append((u["name"], tu, kind))
            rows.append(
                f"<tr><td>{esc(u['name'])}</td><td>{esc('QMix' if kind == 'QMix' else 'รถร่วม ' + u['owner'])}</td>"
                f"<td>{u['days']}</td><td>{num(u['m3'], 2)}</td><td>{num(u['here'], 2)}</td>"
                f"<td>{tu_s(tu)}</td>{lm_cells(tu, u['tu_lm'])}"
                f'<td class="{"" if tu is None or tu >= target else "neg"}">{pct(tu)}</td><td>{esc(u["note"])}</td></tr>')
        ran = [u for u in units if u["tu"] is not None]
        ran_lm = [u for u in units if u["tu_lm"] is not None]
        avg = sum(u["tu"] for u in ran) / len(ran) if ran else None
        avg_lm = sum(u["tu_lm"] for u in ran_lm) / len(ran_lm) if ran_lm else None
        rows.append(f'<tr class="total-row"><td colspan="2">เฉลี่ย {len(ran)} คัน</td><td></td>'
                    f"<td>{num(sum(u['m3'] for u in units), 2)}</td><td>{num(sum(u['here'] for u in units), 2)}</td>"
                    f"<td>{tu_s(avg)}</td>{lm_cells(avg, avg_lm)}<td>{pct(avg)}</td><td></td></tr>")
        n_q = sum(1 for u in units if u["owner"] == "QMix")
        below = sum(1 for u in ran if u["tu"] < target)
        summary.append(
            f"<tr><td>{esc(p.label)}</td><td>{len(units)}</td><td>{n_q}</td><td>{len(units) - n_q}</td>"
            f"<td>{num(sum(u['m3'] for u in units), 1)}</td><td>{tu_s(avg)}</td>{lm_cells(avg, avg_lm)}"
            f'<td class="{"" if avg is None or avg >= target else "neg"}">{pct(avg)}</td><td>{below}</td></tr>')
        heading = f"{no}.{i} {p.label} — TU รายคัน"
        detail += [f'<h3 data-sheet="{no}.{i} TU {esc(p.code)}">{esc(heading)}</h3>',
                   "<figure>" + svg.tu_bars(chart, target, f"TU {p.label} — {cur_s}", "คิว/คัน/เดือน",
                                            sheet=heading) + "</figure>",
                   _table(["รถ", "ประเภท", f"วันที่วิ่ง {cur_s}", "คิวทุกโรง (m³)", "คิวที่โรงนี้ (m³)",
                           f"TU {cur_s}"] + lm_head + [f"% ของเป้า {target}", "หมายเหตุ"], rows)]

    parts += [f'<h3 data-sheet="{no}.1 TU สรุป">{no}.1 สรุปรายโรงงาน</h3>',
              _table(["โรงงาน", "รถจดทะเบียน (คัน)", "รถ QMix", "รถร่วม", f"คิวรวมของรถ {cur_s} (m³)",
                      f"TU เฉลี่ย {cur_s}"] + lm_head + [f"% ของเป้า {target}", "รถต่ำกว่าเป้า (คัน)"],
                     summary)] + detail
    reg = fleet["reg"]
    notes = [f"ทะเบียนรถ: Google Sheet \"รถโม่กิจการตะวันออก\" ชีท {esc(reg['sheet'])} (ดาวน์โหลด {esc(reg['fetched'])}) — "
             "ไม่นับรถสถานะ Inactive และรถในชีท \"รถนอกทะเบียน (ไม่นับ TU)\"",
             "รถที่ถูกแทนกัน (เช่น " + ", ".join(esc(k) for k in reg.get("merged", {})) + ") นับเป็น 1 คัน "
             "วันที่วิ่งนับวันไม่ซ้ำของทั้งคู่" if reg.get("merged") else "",
             "วันที่วิ่ง = จำนวนวันที่มีใบจ่ายคอนกรีต (DP) ของรถคันนั้น — คิว = actual_vol จาก east_production_dispatches",
             (f"TU {esc(lm_s)} ใช้รายชื่อรถของเดือนนี้ (ชีท {esc(reg['sheet'])})" if has_lm else
              f"ยังไม่มีการเทียบเดือนก่อน — เริ่มเก็บ TU ตามทะเบียนรถตั้งแต่ ส.ค. 69 (ไม่มีชีท {esc(fleet['lm_sheet'])})"),
             ("รถในทะเบียนที่ไม่มีข้อมูลเที่ยวผลิตเดือนนี้ (ไม่มี DP จริง หรือยังไม่ได้ดึงข้อมูล — ตรวจ): "
              + ", ".join(esc(t) for t in fleet["no_dp"])) if fleet["no_dp"] else "",
             "เฉลี่ยของโรงงาน = ค่าเฉลี่ยธรรมดาของรถทุกคันที่มีวันวิ่ง"]
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("tu.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("tu.strategy")),
              _box("srcnote", "แหล่งข้อมูล", " — ".join(n for n in notes if n))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


# ---------------------------------------------------------------- Quality

def load_quality(md: MonthData, refresh: bool = False) -> dict:
    """plant -> [MonthSheet …] for LM then current month.

    The parsed result is cached as a small JSON snapshot (data/snapshots/<ym>/quality/<plant>.json) that IS
    committed to git — unlike the source workbook (data/snapshots/<ym>/quality/<plant>.xlsx, gitignored: it's
    the whole multi-year Google Sheet, 1-3MB per plant). The JSON keeps every row, including QC and
    production-staff names, at a fraction of the size. --refresh-sheets re-downloads and re-parses."""
    out, missing = {}, []
    for code, file_id in QS.load_config().items():
        if code not in md.plants:
            continue
        snap = QS.snapshot_path(md.year, md.month, code)
        if not refresh and snap.exists():
            sheets = [QS.from_dict(d) for d in json.loads(snap.read_text(encoding="utf-8"))]
        else:
            path = QS.workbook_path(md.year, md.month, code, file_id, refresh)
            sheets = QS.read_month(path, code, *md.lm_year_month) + QS.read_month(path, code, md.year, md.month)
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_text(json.dumps([QS.to_dict(s) for s in sheets], ensure_ascii=False, indent=1),
                            encoding="utf-8")
        out[code] = sheets
        if not any(s.month == md.month for s in sheets):
            missing.append(code)
    return {"plants": out, "missing": missing}


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return num(v, 0) if v.is_integer() else num(v, 2)
    if isinstance(v, int):
        return num(v)
    return esc(str(v))


def section_quality(md: MonthData, q: dict, no: int) -> str:
    cur_s, lm_s = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    parts = [f'<h2 id="s{no}">{no}. คุณภาพ (กำลังอัดคอนกรีต)</h2>',
             f'<p class="meta">จากตารางสรุปการเก็บข้อมูลกำลังอัดของแต่ละโรงงาน (Google Sheet) เดือน {esc(lm_s)} และ {esc(cur_s)} — '
             'กราฟต่อ 2 เดือนตามลำดับตัวอย่าง พร้อมเส้นเป้าหมายของแต่ละเดือน ตารางด้านล่างคือทุกแถวของชีทเดือนนั้น</p>']
    plants = [md.plants[c] for c in sorted(q["plants"]) if c in md.plants]
    if not plants:
        return '<section class="wrap">' + "\n".join(parts + ["<p>ไม่มีโรงงานในเขตนี้ที่มีตารางกำลังอัด</p>"]) + "</section>"
    for i, p in enumerate(plants, 1):
        sheets = q["plants"][p.code]
        heading = f"{no}.{i} {p.label}"
        parts.append(f'<h3 data-sheet="{no}.{i} QC {esc(p.code)}">{esc(heading)}</h3>')
        if not sheets:
            parts.append(f'<p class="meta">ไม่พบชีทของเดือน {esc(lm_s)} และ {esc(cur_s)} ในไฟล์ของโรงงานนี้</p>')
            continue
        # chart: both months side by side, one point per sample, target lines of each month's own tab
        labels, groups, names = [], [], [s for s, _ in sheets[0].series]
        values = [[] for _ in names]
        for s in sheets:
            ml = th_month_short(s.year, s.month).split()[0]
            groups.append((f"{ml} ({s.tab.strip()})" if len(sheets) > 2 else ml, len(s.samples)))
            labels += [f"{int(n) if isinstance(n, (int, float)) else n}" for n in s.samples]
            for k in range(len(names)):
                vals = s.series[k][1] if k < len(s.series) else [None] * len(s.samples)
                values[k] += vals
        parts.append("<figure>" + svg.quality_lines(labels, groups, list(zip(names, values)),
                                                    f"กำลังอัด {p.label} — {lm_s} ถึง {cur_s}",
                                                    sheet=heading) + "</figure>")
        # two-month summary right under the chart (also keeps the chart on its own xlsx sheet)
        smr = []
        for s in sheets:
            ms = th_month_short(s.year, s.month)
            for lab, d in s.summary:
                smr.append(f"<tr><td>{esc(ms)}</td><td>{esc(lab)}</td><td>{num(s.target, 0) if s.target else '—'}</td>"
                           f"<td>{_cell(d['avg'])}</td><td>{_cell(d['pct'])}</td>"
                           f'<td class="{delta_class(d["margin"]) if isinstance(d["margin"], (int, float)) else ""}">'
                           f"{_cell(d['margin'])}</td><td>{_cell(d['sd'])}</td><td>{_cell(d['cpk'])}</td></tr>")
        parts.append(_table(["เดือน", "รายการ", "กำลังรับรอง (ksc)", "กำลังอัดเฉลี่ย (ksc)", "% ของกำลังรับรอง",
                             "Margin (ksc)", "SD (ksc)", "Cpk"], smr))
        for s in sheets:
            ms = th_month_short(s.year, s.month)
            head = (f"{ms} — ชีท {s.tab.strip()} — รหัสสินค้า {s.product or '—'} — กำลังรับรอง "
                    f"{num(s.target, 0) if s.target else '—'} ksc — {len(s.samples)} ตัวอย่าง")
            body = [f"<tr><td>{esc(lab)}</td>" + "".join(f"<td>{_cell(v)}</td>" for v in vals) + "</tr>"
                    for lab, vals in s.rows]
            parts += [f'<div class="qc"><h4 data-sheet="{no}.{i} QC {esc(p.code)} {esc(ms.split()[0])}">{esc(head)}</h4>' + _table(["รายการ \\ ตัวอย่างชุดที่"] + [_cell(n) for n in s.samples], body) + "</div>"]
    notes = ["ไฟล์ตารางกำลังอัดรายโรงงาน (Google Sheet ที่ Don ให้ไว้ใน data/config/quality_sheets.json) ดาวน์โหลดเป็น .xlsx "
             f"เก็บไว้ที่ data/snapshots/{esc(_ym(md.year, md.month))}/quality/ — ใช้ชีทชื่อเดือน MM.2026 / MM/2026 "
             "(ชีทชื่อ 07, 08 ไม่มีปี = ปี 2025 ไม่นำมาใช้)",
             f"ผลกำลังอัด 28 วันของตัวอย่างปลายเดือน {esc(cur_s)} อาจยังไม่ครบตอนดึงข้อมูล (จุดที่ไม่มีค่าในกราฟ)"]
    if q["missing"]:
        notes.append("ไม่พบชีทเดือนนี้: " + ", ".join(esc(c) for c in q["missing"] if c in md.plants))
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("quality.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("quality.strategy")),
              _box("srcnote", "แหล่งข้อมูล", " — ".join(notes))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"
