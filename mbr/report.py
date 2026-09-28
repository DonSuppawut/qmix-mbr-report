"""HTML builders for each report section."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import calc, svg
from .fmt import delta_class, esc, mb, num, th_month_long, th_month_short
from .tvc import ScopeData

SCOPE_TITLES = {"combined": "EST รวม (Core + PMT)", "core": "EST Core", "pmt": "EST PMT (รวม Insource)"}
SCOPE_SHORT = {"combined": "EST รวม", "core": "Core", "pmt": "PMT"}

WF_LABELS = {
    "volume": "ปริมาณขาย", "net_price": "ราคาขาย", "rawmat": "วัตถุดิบ", "assign": "Assign Costs",
    "cartage": "ค่าขนส่ง", "exbtrd": "Exbatch & Trading", "tfc": "TFC", "extraordinary": "รายการพิเศษ",
    "depreciation": "ค่าเสื่อมราคา", "finance": "ดอกเบี้ยจ่าย", "tax": "ภาษีเงินได้",
}

# Chart x-axis labels with explicit break points ('|') — Thai has no spaces to wrap on.
CHART_LABELS = {
    "volume": "ปริมาณ|ขาย", "net_price": "ราคา|ขาย", "rawmat": "วัตถุดิบ", "assign": "Assign|Costs",
    "cartage": "ค่า|ขนส่ง", "exbtrd": "Exbatch &|Trading", "tfc": "TFC", "extraordinary": "รายการ|พิเศษ",
    "depreciation": "ค่าเสื่อม|ราคา", "finance": "ดอกเบี้ย|จ่าย", "tax": "ภาษี|เงินได้",
}

# (label, key, decimals, higher_is_better, main_row)
SCORE_ROWS = [
    ("NPAT (บาท)", "npat", 0, True, True),
    ("EBITDA (บาท)", "ebitda", 0, True, True),
    ("EBITDA (บาท/m³)", "ebitda_m3", 2, True, False),
    ("ปริมาณขาย (m³)", "volume", 1, True, False),
    ("Net Price (บาท/m³)", "net_price_m3", 2, True, False),
    ("Net Contribution (บาท/m³)", "netcon_m3", 2, True, False),
    ("TVC (บาท/m³)", "tvc_m3", 2, False, False),
    ("Raw Material (บาท/m³)", "rawmat_m3", 2, False, False),
    ("Assign Costs (บาท/m³)", "assign_m3", 2, False, False),
    ("Cartage (บาท/m³)", "cartage_m3", 2, False, False),
    ("TFC (บาท/m³)", "tfc_m3", 2, False, False),
]


@dataclass
class MonthData:
    year: int
    month: int
    actual: ScopeData
    plan: ScopeData
    last: ScopeData
    narrative: dict = field(default_factory=dict)
    plants: dict = field(default_factory=dict)          # code -> plants.PlantRow
    hidden_plants: set = field(default_factory=set)
    trading_plants: set = field(default_factory=set)
    adjustments: dict = field(default_factory=dict)
    area: str = ""  # "" = whole EST; "E1.1" / "E1.2" / "E2" = one AAO area (build_area_report.py)

    @property
    def unit_th(self) -> str:
        return f"เขต {self.area}" if self.area else "ภาคตะวันออก"

    @property
    def lm_year_month(self) -> tuple[int, int]:
        return (self.year, self.month - 1) if self.month > 1 else (self.year - 1, 12)


def scope_title(md: MonthData, scope: str) -> str:
    if not md.area:
        return SCOPE_TITLES[scope]
    return {"combined": f"เขต {md.area} รวม (Core + PMT)", "core": f"เขต {md.area} Core",
            "pmt": f"เขต {md.area} PMT"}[scope]


def scope_short(md: MonthData, scope: str) -> str:
    return f"{md.area} รวม" if md.area and scope == "combined" else SCOPE_SHORT[scope]


def _box(cls: str, title: str, body: str | None) -> str:
    return f'<div class="{cls}"><b>{title}:</b> {body}</div>' if body else ""


def _table(header: list[str], rows: list[str]) -> str:
    ths = "".join(f"<th>{esc(h)}</th>" for h in header)
    return f'<div class="tscroll"><table><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _wf_act_cell(key: str, d: dict) -> str:
    v = d["volume"]
    rate = lambda x: x / v if v else 0.0
    if key == "volume":
        return f"{num(v, 1)} m³"
    if key == "net_price":
        return f"{num(rate(d['net_price']), 2)} บาท/m³"
    if key == "rawmat":
        return f"{num(rate(d['rawmat']), 2)} บาท/m³"
    if key == "assign":
        return f"{num(rate(calc.assign_total(d)), 2)} บาท/m³"
    if key == "cartage":
        return f"{num(rate(d['cartage']), 2)} บาท/m³"
    return f"{num(d[key], 0)} บาท"


def _wf_table(start_label: str, start: float, steps, end_label: str, end: float, act: dict, act_head: str) -> str:
    rows = [f'<tr class="category-row"><td>{esc(start_label)}</td><td>{num(start)} บาท</td><td></td></tr>']
    for key, val in steps:
        rows.append(f"<tr><td>{esc(WF_LABELS[key])}</td><td>{_wf_act_cell(key, act)}</td>"
                    f'<td class="{delta_class(val)}">{num(val, signed=True)}</td></tr>')
    rows.append(f'<tr class="total-row"><td>{esc(end_label)}</td><td>{num(end)} บาท</td><td></td></tr>')
    return _table(["รายการ", act_head, "ผลกระทบต่อ NPAT (บาท)"], rows)


def _drivers(steps, n: int = 2) -> tuple[str, str]:
    pos = sorted((s for s in steps if s[1] > 0), key=lambda s: -s[1])[:n]
    neg = sorted((s for s in steps if s[1] < 0), key=lambda s: s[1])[:n]
    fmt = lambda ss: " และ ".join(f"{WF_LABELS[k]} ({mb(v, signed=True)} ล้านบาท)" for k, v in ss) or "-"
    return fmt(pos), fmt(neg)


def _override_note(md: MonthData) -> str:
    if not md.plan.overrides:
        return ""
    items = ", ".join(f"{esc(WF_LABELS.get(k, k.upper()))} ไฟล์ {num(f)} → ใช้ {num(u)}" for k, (f, u) in md.plan.overrides.items())
    return (f"— AP รวมเขตใช้ Core + PMT ของไฟล์ (เท่ากับผลรวมรายโรงงาน) เพราะคอลัมน์รวมเขตของ AP "
            f"ไม่ได้ลงบางแถว: {items} ")


_SCOPE_COLS_NOTE = ("(Actual: EST-Core=คอลัมน์ 16, EST-PMT=คอลัมน์ 21, EST-Core&amp;Pmt=คอลัมน์ 26 | "
                    "AP: คอลัมน์ 35 / 36 / 25) ")


def section1(md: MonthData) -> str:
    cur = th_month_short(md.year, md.month)
    lm = th_month_short(*md.lm_year_month)
    a, p = md.actual["combined"], md.plan["combined"]
    wf_comb = calc.waterfall_npat(a, p)
    diff = a["npat"] - p["npat"]
    up, down = _drivers(wf_comb["steps"])
    vol_pct = lambda s: md.actual[s]["volume"] / md.plan[s]["volume"] * 100 if md.plan[s]["volume"] else 0.0

    parts = [
        '<h2 id="s1">1. Executive Summary</h2>',
        f"<p><b>ภาพรวม:</b> เดือน{th_month_long(md.year, md.month)} {md.unit_th}{" " if md.area else ""}ทำ NPAT ได้ <b>{num(a['npat'])} บาท</b> "
        f"เทียบกับแผน (AP) {num(p['npat'])} บาท ผลต่าง <b class=\"{delta_class(diff)}\">{num(diff, signed=True)} บาท</b></p>",
        f"<p><b>สาระสำคัญ:</b> ปัจจัยหนุนหลักคือ {up} ในขณะที่ปัจจัยฉุดคือ {down}</p>",
        f"<p><b>ข้อสังเกตเชิงบริหาร:</b> ปริมาณขายทำได้ {num(a['volume'], 1)} m³ จากแผน {num(p['volume'], 1)} m³ "
        f"(<span class=\"{delta_class(vol_pct('combined') - 100)}\">{vol_pct('combined'):.0f}%</span> ของแผน) — "
        f"Core ทำได้ {vol_pct('core'):.1f}% ของแผน ส่วน PMT ทำได้ {vol_pct('pmt'):.1f}% ของแผน "
        f"{md.narrative.get('s1.observation', '')}</p>",
    ]

    for i, scope in enumerate(calc.SCOPES, 1):
        a_s, p_s = md.actual[scope], md.plan[scope]
        wf = calc.waterfall_npat(a_s, p_s)
        title = f"1.{i} Waterfall NPAT: AP → Actual — {scope_title(md, scope)}"
        steps_lbl = [(CHART_LABELS[k], v) for k, v in wf["steps"]]
        parts += [
            f"<h3>{esc(title)}</h3>",
            f"<p class=\"meta\">ปริมาณขาย: AP {num(p_s['volume'], 0)} m³ → Actual {num(a_s['volume'], 1)} m³ | "
            f"EBITDA: AP {num(p_s['ebitda'])} → Actual {num(a_s['ebitda'])} บาท</p>",
            '<figure>' + svg.waterfall("NPAT|AP", wf["start"], steps_lbl, "NPAT|Actual", wf["end"], title, sheet=title) + '</figure>',
            _wf_table("NPAT ตามแผน (AP)", wf["start"], wf["steps"], "NPAT จริง (Actual)", wf["end"], a_s, f"Act {cur}"),
        ]

    # 1.4 EBITDA Bridge (LM → current), all three scopes
    bridges = {s: calc.ebitda_bridge(md.actual[s], md.last[s]) for s in calc.SCOPES}
    keys = [k for k, _ in bridges["combined"]["steps"]]
    rows = [f'<tr class="category-row"><td>EBITDA {esc(lm)}</td>'
            + "".join(f"<td>{num(bridges[s]['start'])}</td>" for s in calc.SCOPES) + "</tr>"]
    for k in keys:
        cells = "".join(f'<td class="{delta_class(dict(bridges[s]["steps"])[k])}">'
                        f'{num(dict(bridges[s]["steps"])[k], signed=True)}</td>' for s in calc.SCOPES)
        rows.append(f"<tr><td>{esc(WF_LABELS[k])}</td>{cells}</tr>")
    rows.append(f'<tr class="total-row"><td>EBITDA {esc(cur)}</td>'
                + "".join(f"<td>{num(bridges[s]['end'])}</td>" for s in calc.SCOPES) + "</tr>")
    parts += [
        f"<h3>1.4 EBITDA Bridge: {esc(lm)} → {esc(cur)}</h3>",
        f"<p class=\"meta\">ผลกระทบต่อ EBITDA (บาท) เทียบเดือนก่อน — ฐานคำนวณแบบเดียวกับ Waterfall (อัตราต่อคิวคิดจากปริมาณขาย)</p>",
        _table(["รายการ"] + [scope_short(md, s) for s in calc.SCOPES], rows),
    ]
    for s in calc.SCOPES:
        b = bridges[s]
        title = f"EBITDA Bridge {lm} → {cur} — {scope_title(md, s)}"
        parts.append('<figure><figcaption>' + esc(scope_title(md, s)) + '</figcaption>'
                     + svg.waterfall(f"EBITDA {lm}", b["start"], [(CHART_LABELS[k], v) for k, v in b["steps"]],
                                     f"EBITDA {cur}", b["end"], title, height=340,
                                     sheet=f"1.4 EBITDA Bridge: {lm} → {cur}") + '</figure>')

    parts += [
        _box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s1.watch")),
        _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s1.strategy")),
        _box("srcnote", "แหล่งข้อมูล",
             f"บล็อก OUTPUT ของไฟล์ {esc(md.actual.source.split('/')[0])} ใช้คอลัมน์รวมของไฟล์เอง "
             + (_SCOPE_COLS_NOTE if not md.area else
                f"(คอลัมน์รวมราย AAO ของเขต {esc(md.area)}: รวม / Core / PMT — หาจากชื่อหัวคอลัมน์ทั้ง Actual และ AP) "
                + _override_note(md))
             + "Waterfall และ EBITDA Bridge คิดอัตราต่อคิวจากปริมาณขาย ทำให้ผลต่างที่อธิบายไม่ได้ (residual) = 0 ทุกระดับ "
             "ทั้ง 3 scope — Assign Costs รวมค่าแรง OT และผู้รับเหมา (Labour Cost) ไว้ในบรรทัดเดียว "
             "ส่วนค่าแรงพนักงานขับรถอยู่ในค่าขนส่ง"),
    ]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


def _per_prod(d: dict, x: float) -> float:
    return x / d["prod_volume"] if d["prod_volume"] else 0.0


def _compare_rows(md: MonthData, scope: str, spec: list[tuple], dec: int = 2) -> list[str]:
    """spec rows: (label, fn(d)->value, row_class). All rows are cost-type (lower is better)."""
    a, p, l = md.actual[scope], md.plan[scope], md.last[scope]
    rows = []
    for label, fn, cls in spec:
        va, vp, vl = fn(a), fn(p), fn(l)
        dap, dlm = va - vp, va - vl
        attr = f' class="{cls}"' if cls else ""
        rows.append(
            f"<tr{attr}><td>{esc(label)}</td><td>{num(va, dec)}</td><td>{num(vp, dec)}</td><td>{num(vl, dec)}</td>"
            f'<td class="{delta_class(dap, False)}">{num(dap, dec, True)}</td>'
            f'<td class="{delta_class(dlm, False)}">{num(dlm, dec, True)}</td></tr>')
    return rows


def _compare_header(md: MonthData) -> list[str]:
    return ["รายการ", th_month_short(md.year, md.month), "AP", th_month_short(*md.lm_year_month), "เทียบ AP", "เทียบ LM"]


def _sorted_items(md: MonthData, scope: str, items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Order sub-items by current-month value per m³, largest first (stable for ties)."""
    a = md.actual[scope]
    return sorted(items, key=lambda it: -_per_prod(a, a[it[1]]))


RAWMAT_ITEMS = [  # fixed order, never sorted by cost
    ("ปูนซีเมนต์ (Cement)", "rm_cement", ("cement_kg", "kg/m³", "cement_price", "บาท/ตัน")),
    ("เถ้าลอย (Fly Ash / PFA)", "rm_pfa", ("pfa_kg", "kg/m³", "pfa_price", "บาท/ตัน")),
    ("หิน (Rock & Gravel)", "rm_rock", ("rock_kg", "kg/m³", "rock_price", "บาท/ตัน")),
    ("ทราย (Sand)", "rm_sand", ("sand_kg", "kg/m³", "sand_price", "บาท/ตัน")),
    ("น้ำยา Admixture Normal", "rm_admix_normal", None),
    ("น้ำยา Admixture Special", "rm_admix_special", None),
    ("Other r/m (Slag, LSP)", "rm_other", None),
    ("Internal Use", "rm_internal", None),
]


def section4(md: MonthData) -> str:
    parts = ['<h2 id="s4">4. Raw Material</h2>',
             '<p class="meta">บาท/m³ คิดต่อปริมาณผลิต (Production Volume) — แสดง 8 รายการในลำดับคงที่ '
             'แต่ละรายการมีแถวย่อย Usage และราคา</p>']
    for i, scope in enumerate(calc.SCOPES, 1):
        spec = []
        for label, key, sub in RAWMAT_ITEMS:
            spec.append((f"{label} (บาท/m³)", lambda d, k=key: _per_prod(d, d[k]), "category-row"))
            if sub:
                uk, uu, pk, pu = sub
                spec.append((f"Usage ({uu})", lambda d, k=uk: d[k], "sub-row"))
                spec.append((f"Price ({pu})", lambda d, k=pk: d[k], "sub-row"))
        spec.append(("รวม Raw Material (บาท/m³)", lambda d: _per_prod(d, d["rawmat"]), "total-row"))
        parts += [f"<h3>4.{i} {esc(scope_title(md, scope))}</h3>",
                  _table(_compare_header(md), _compare_rows(md, scope, spec))]
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s4.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s4.strategy")),
              _box("srcnote", "แหล่งข้อมูล", "แถวยอดรวม scope ของไฟล์ TVC ทั้ง Actual และ Plan — บาทจากบล็อก OUTPUT, "
                   "Usage/ราคาจากบล็อก INPUT (รายละเอียดวัตถุดิบ) — สีในคอลัมน์เทียบ: ต้นทุน/ปริมาณใช้/ราคาเพิ่ม = แดง")]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


ASSIGN_ITEMS = [
    ("ค่าใช้จ่ายรถตัก (FEL Expense)", "a_fel"),
    ("ค่าซ่อมแซมและบำรุงรักษา (REPAIR & MAINTENANCE)", "a_repair"),
    ("วัสดุคลังและอุปกรณ์ (STORES & EQUIPMENT ไม่รวมค่าน้ำ)", "a_stores_ex_water"),
    ("ค่าน้ำ (Water)", "water"),
    ("ผู้รับเหมาช่วง (Sub-contract)", "sub_contractor"),
    ("ค่าไฟฟ้า (POWER)", "a_power"),
    ("ค่าล่วงเวลา (OT)", "labour_ot"),
    ("โสหุ้ยการผลิต (Overhead Cost)", "a_overhead"),
    ("เครื่องมือและอุปกรณ์ (TOOLS & EQUIPMENT)", "a_tools"),
    ("ค่าเดินทาง (TRANSPORT & TRAVEL)", "a_transport"),
    ("วัสดุอื่นๆ (OTHER MATERIAL SUPPLIES)", "a_other_mat"),
    ("เบ็ดเตล็ด (MISCELLANEOUS)", "a_misc"),
    ("ค่ากำจัดเศษคอนกรีต (Waste Concrete)", "a_waste"),
    ("รถเครน+รถขนกากปูน", "a_crane"),
    ("FREIGHT & HANDLING", "a_freight"),
    ("ของเสีย (Spoiled)", "a_spoiled"),
]


def section5_scopes(md: MonthData) -> list[str]:
    parts = []
    for i, scope in enumerate(calc.SCOPES, 1):
        spec = [("Assign Costs รวม (บาท/m³)", lambda d: _per_prod(d, calc.assign_total(d)), "category-row")]
        for label, key in _sorted_items(md, scope, ASSIGN_ITEMS):
            spec.append((f"{label} (บาท/m³)", lambda d, k=key: _per_prod(d, d[k]), ""))
        parts += [f"<h3>5.{i} {esc(scope_title(md, scope))}</h3>",
                  _table(_compare_header(md), _compare_rows(md, scope, spec))]
    return parts


CARTAGE_ITEMS = [
    ("Cartage รถผู้รับเหมา (Sub-contractor)", "cartage_sub"),
    ("ค่าน้ำมัน+น้ำมันหล่อลื่น (Oil & Lube)", "c_oil_lube"),
    ("ค่าแรงพนักงานขับรถ+ค่าเที่ยว (Direct Labour)", "direct_labour"),
    ("ค่าซ่อมรถ+ซ่อมโม่ (Mixer Repair & Maintenance)", "c_mixer_rm"),
    ("ยางรถ (Mixer Tyre)", "c_tyre"),
    ("ค่าเช่าที่จอดรถปันส่วน (Allocation Truck Park)", "c_truck_park"),
    ("เบ็ดเตล็ด (Miscellaneous)", "c_misc"),
    ("ค่าประกันภัย (Insurance)", "c_insurance"),
    ("ภาษี/ค่าธรรมเนียม (Tax & License)", "c_tax_license"),
    ("สวัสดิการพนักงาน (Employee Welfare)", "c_welfare"),
    ("ค่าสื่อสาร (Communication)", "c_communication"),
    ("รายได้ค่ารถบรรทุกฯ (หักลบ)", "c_truck_revenue"),
    ("ค่าตำรวจ", "c_police"),
]


def section6_scopes(md: MonthData) -> list[str]:
    parts = []
    for i, scope in enumerate(calc.SCOPES, 1):
        spec = [("Cartage รวม (บาท/m³)", lambda d: _per_prod(d, d["cartage"]), "category-row")]
        for label, key in _sorted_items(md, scope, CARTAGE_ITEMS):
            spec.append((f"{label} (บาท/m³)", lambda d, k=key: _per_prod(d, d[k]), ""))
        parts += [f"<h3>6.{i} {esc(scope_title(md, scope))}</h3>",
                  _table(_compare_header(md), _compare_rows(md, scope, spec))]
    return parts


def section5(md: MonthData, extra: list[str] | None = None) -> str:
    parts = ['<h2 id="s5">5. Assign Costs</h2>',
             '<p class="meta">Assign Costs = แถว Assign ของไฟล์ TVC + ค่าแรง OT + ผู้รับเหมาช่วง (Sub-contract) '
             '— บาท/m³ คิดต่อปริมาณผลิต รายการย่อยเรียงตามบาท/m³ เดือนนี้จากมากไปน้อย</p>']
    parts += section5_scopes(md)
    parts.append('<p class="footnote">ค่าน้ำแยกออกจากบรรทัด STORES &amp; EQUIPMENT ของไฟล์ TVC มาแสดงเป็นบรรทัดของตัวเอง '
                 'และยังนับรวมอยู่ใน Assign Costs รวม</p>')
    parts += extra or []
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s5.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s5.strategy"))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


def section6(md: MonthData, extra: list[str] | None = None) -> str:
    parts = ['<h2 id="s6">6. Cartage</h2>',
             '<p class="meta">Cartage รวมค่าแรงพนักงานขับรถ (Direct Labour) — บาท/m³ คิดต่อปริมาณผลิต '
             'รายการย่อยเรียงตามบาท/m³ เดือนนี้จากมากไปน้อย</p>']
    parts += section6_scopes(md)
    parts += extra or []
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s6.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s6.strategy"))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


def section2(md: MonthData) -> str:
    cur = th_month_short(md.year, md.month)
    lm = th_month_short(*md.lm_year_month)
    parts = ['<h2 id="s2">2. ผลประกอบการหลัก</h2>',
             '<p class="meta">NPAT แสดงเป็นบรรทัดแรก ตามด้วย EBITDA และตัวขับเคลื่อนหลัก</p>']
    for i, scope in enumerate(calc.SCOPES, 1):
        sa = calc.scorecard_row(md.actual[scope])
        sp = calc.scorecard_row(md.plan[scope])
        sl = calc.scorecard_row(md.last[scope])
        rows = []
        for label, key, dec, better_up, main in SCORE_ROWS:
            dap, dlm = sa[key] - sp[key], sa[key] - sl[key]
            cls = ' class="category-row"' if main else ""
            rows.append(
                f"<tr{cls}><td>{esc(label)}</td><td>{num(sa[key], dec)}</td><td>{num(sp[key], dec)}</td>"
                f"<td>{num(sl[key], dec)}</td>"
                f'<td class="{delta_class(dap, better_up)}">{num(dap, dec, True)}</td>'
                f'<td class="{delta_class(dlm, better_up)}">{num(dlm, dec, True)}</td></tr>')
        parts += [f"<h3>2.{i} {esc(scope_title(md, scope))}</h3>",
                  _table(["รายการ", cur, "AP", lm, "เทียบ AP", "เทียบ LM"], rows)]
    parts += [
        _box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s2.watch")),
        _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s2.strategy")),
        _box("srcnote", "หมายเหตุหน่วย",
             "Raw Material / Assign Costs (รวมค่าแรงแล้ว) / Cartage คำนวณต่อ <b>Production Volume</b> "
             "(แถว Production Volume ในไฟล์ TVC) ส่วน NPAT/EBITDA/Net Price/Net Contribution/TVC/TFC คำนวณต่อ "
             "<b>Sales Volume</b> — สีในคอลัมน์เทียบ: รายได้/กำไร/ปริมาณเพิ่ม = เขียว, ต้นทุนเพิ่ม = แดง"),
    ]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"
