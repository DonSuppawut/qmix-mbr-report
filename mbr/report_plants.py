"""Plant-level sections: 5.4, 6.6, 7, 8."""
from __future__ import annotations

from . import svg
from .fmt import delta_class, esc, num, th_month_short
from .plants import unit_cost
from .report import MonthData, _box, _table


def _kind_label(md: MonthData, p) -> str:
    if p.kind.startswith("TDG"):
        return f"Core ({p.kind})"
    if p.code in md.trading_plants or (p.cur["volume"] > 0 and p.cur["prod_volume"] == 0):
        return f"{p.kind} (TDG)"
    return p.kind


def _producing(md: MonthData) -> list:
    return [p for p in md.plants.values()
            if p.cur["prod_volume"] > 0 or (p.lm and p.lm["prod_volume"] > 0)]


def plant_unit_table(md: MonthData, key: str, title: str, adjust: dict[str, float] | None = None) -> str:
    cur, lm = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    rows = []
    for p in _producing(md):
        va = unit_cost(p.cur, key)
        star = ""
        if adjust and p.code in adjust and p.cur["prod_volume"]:
            va = (p.cur[key] + adjust[p.code]) / p.cur["prod_volume"]
            star = " *"
        vl = unit_cost(p.lm, key) if p.lm else 0.0
        rows.append((abs(va - vl), p, va, vl, star))
    rows.sort(key=lambda r: -r[0])
    html_rows = [
        f"<tr><td>{esc(p.label)}</td><td>{esc(p.area)}</td><td>{esc(p.kind)}</td>"
        f"<td>{num(p.cur['volume'], 1)}</td><td>{num(p.lm['volume'] if p.lm else 0, 1)}</td>"
        f"<td>{num(va, 2)}{star}</td><td>{num(vl, 2)}</td>"
        f'<td class="{delta_class(va - vl, False)}">{num(va - vl, 2, True)}</td></tr>'
        for _, p, va, vl, star in rows]
    return _table(["โรงงาน", "เขต", "Core/PMT", f"ปริมาณ {cur}", f"ปริมาณ {lm}",
                   f"{title} {cur} (บาท/m³)", f"{title} {lm} (บาท/m³)", "Δ"], html_rows)


def section5_plants(md: MonthData) -> list[str]:
    cur, lm = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    return [f"<h3>5.4 รายโรงงาน: Assign Cost {esc(cur.split()[0])} เทียบ {esc(lm)}</h3>",
            '<p class="meta">Assign Costs ต่อ m³ ผลิต รายโรงงาน (หลักการจัดหมวดเดียวกับ 5.1–5.3) เฉพาะโรงงานที่ผลิตเอง '
            'ในเดือนนี้หรือเดือนก่อน เรียงตามขนาดการเปลี่ยนแปลง</p>',
            plant_unit_table(md, "assign", "Assign Cost"),
            _box("watch", "ข้อสังเกต", md.narrative.get("s5.plants"))]


def section6_plants(md: MonthData) -> list[str]:
    cur, lm = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    adj: dict[str, float] = {}
    for a in md.adjustments.get("cartage_plant", []):
        adj[a["plant"]] = adj.get(a["plant"], 0.0) + a["amount"]
    note = ""
    if adj:
        items = "; ".join(f"{esc(a['plant'])} Cost Center {esc(a['cost_center'])} {num(a['amount'], 2, True)} บาท "
                          f"({esc(a['reason'])})" for a in md.adjustments["cartage_plant"])
        note = ('<p class="footnote">* ปรับปรุง GL ตามที่ Don ระบุ — ' + items +
                ' — ใช้เฉพาะตารางนี้ ไม่กระทบ EBITDA/NPAT หรือหัวข้ออื่น</p>')
    title = f"6.6 รายโรงงาน: Cartage {cur.split()[0]} เทียบ {lm}" + (" (รวมการแก้ไข GL)" if adj else "")
    return [f"<h3>{esc(title)}</h3>",
            '<p class="meta">Cartage ต่อ m³ ผลิต รายโรงงาน เรียงตามขนาดการเปลี่ยนแปลง</p>',
            plant_unit_table(md, "cartage", "Cartage", adj), note,
            _box("watch", "ข้อสังเกต", md.narrative.get("s6.plants"))]


PLANT_GROUPS = [
    ("7.1", "กลุ่มทำได้ตามแผนหรือดีกว่าแผน และมีกำไร", lambda e, ap: ap is not None and e >= ap and e > 0, -1),
    ("7.2", "กลุ่มต่ำกว่าแผน แต่ยังมีกำไร", lambda e, ap: ap is not None and e < ap and e > 0, -1),
    ("7.3", "กลุ่มต่ำกว่าแผนและขาดทุน — ต้องวิเคราะห์สาเหตุ", lambda e, ap: ap is not None and e < ap and e <= 0, 1),
    ("7.4", "กลุ่มขาดทุนแต่ดีกว่าแผน", lambda e, ap: ap is not None and e >= ap and e <= 0, 1),
    ("7.5", "กลุ่มที่ไม่มี AP อ้างอิง", lambda e, ap: ap is None, 0),
]


def shown_plants(md: MonthData) -> list:
    return [p for p in md.plants.values() if p.code not in md.hidden_plants]


def plant_groups(md: MonthData) -> list[tuple[str, str, list]]:
    shown = shown_plants(md)
    order = list(md.plants)
    out = []
    for no, title, test, direction in PLANT_GROUPS:
        members = [p for p in shown if test(p.cur["ebitda"], p.ap["ebitda"] if p.ap else None)]
        if direction == 0:
            members.sort(key=lambda p: p.code)
        else:
            members.sort(key=lambda p: (direction * p.cur["ebitda"], order.index(p.code)))
        out.append((no, title, members))
    return out


def section7(md: MonthData) -> str:
    shown = shown_plants(md)
    total = len(md.plants)
    parts = ['<h2 id="s7">7. ผลประกอบการรายโรงงาน</h2>',
             f'<p class="meta">จัดกลุ่มตามผลเทียบแผน (AP) และกำไร/ขาดทุนเดือน {esc(th_month_short(md.year, md.month))} '
             f'แสดง {len(shown)} จาก {total} โรงงาน (ไม่รวม Insource และร่วมมิตร {total - len(shown)} แห่ง — '
             'EBITDA ของโรงที่ตัดออกยังอยู่ในยอด Combined) — EBITDA สะสม (YTD) = ม.ค. ถึงเดือนปัจจุบัน ยังไม่มี AP สะสม</p>']
    cases = md.narrative.get("s7.cases", {})
    for no, title, members in plant_groups(md):
        if not members:
            continue
        rows = []
        for p in members:
            ap = p.ap["ebitda"] if p.ap else None
            diff = p.cur["ebitda"] - ap if ap is not None else None
            rows.append(
                f"<tr><td>{esc(p.label)}</td><td>{esc(p.area)}</td><td>{esc(_kind_label(md, p))}</td>"
                f"<td>{num(p.cur['volume'], 1)}</td><td>{num(p.cur['ebitda'])}</td>"
                f"<td>{num(ap) if ap is not None else '—'}</td>"
                f'<td class="{delta_class(diff) if diff is not None else ""}">'
                f"{num(diff, signed=True) if diff is not None else '—'}</td><td>{num(p.ytd_ebitda)}</td></tr>")
        rows.append(f'<tr class="total-row"><td colspan="3">รวม {esc(title)}</td>'
                    f"<td>{num(sum(p.cur['volume'] for p in members), 1)}</td>"
                    f"<td>{num(sum(p.cur['ebitda'] for p in members))}</td><td></td><td></td><td></td></tr>")
        parts += [f"<h3>{no} {esc(title)} ({len(members)} โรงงาน)</h3>",
                  _table(["โรงงาน", "เขต", "ประเภท", "Vol (m³)", "EBITDA (บาท)", "AP (บาท)", "เทียบ AP",
                          "EBITDA สะสม YTD (บาท)"], rows)]
        if no == "7.3":
            for p in members:
                if p.cur["ebitda"] < 0 and p.cur["volume"] > 0:
                    parts.append(_box("watch", f"Plant Case {esc(p.label)}",
                                      cases.get(p.code, "ต้องวิเคราะห์สาเหตุ — ยังไม่มีข้อความวิเคราะห์ในไฟล์ narrative")))
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s7.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s7.strategy"))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


AREAS = ("E1.1", "E1.2", "E2")


def area_members(md: MonthData, area: str) -> list:
    members = [p for p in shown_plants(md) if p.area == area and p.ytd_volume > 0]
    return sorted(members, key=lambda p: -p.cur["ebitda"])


def section8(md: MonthData) -> str:
    cur = th_month_short(md.year, md.month)
    ytd = f"สะสม ม.ค.–{cur}"
    parts = ['<h2 id="s8">8. ผลประกอบการรายโรงงานแยกตามเขต</h2>',
             f'<p class="meta">แสดงเฉพาะโรงงานที่มีปริมาณขายสะสม (YTD) มากกว่า 0 m³ และไม่รวม Insource/ร่วมมิตร '
             f'(เกณฑ์เดียวกับหัวข้อ 7) เรียงตาม EBITDA เดือน {esc(cur)} จากมากไปน้อย — แถวบน = เดือนนี้, แถวล่าง = สะสม</p>']
    for i, area in enumerate(AREAS, 1):
        members = area_members(md, area)
        if not members:
            continue
        rows = [{"label": p.label, "kind": "Core" if p.kind == "Core" else "PMT",
                 "e_cur": p.cur["ebitda"], "v_cur": p.cur["volume"], "e_ytd": p.ytd_ebitda, "v_ytd": p.ytd_volume}
                for p in members]
        tot = [sum(r[k] for r in rows) for k in ("e_cur", "v_cur", "e_ytd", "v_ytd")]
        heading = f"8.{i} เขต {area} ({len(members)} โรงงาน)"
        parts += [f"<h3>{heading}</h3>",
                  "<figure>" + svg.tornado(rows, f"เขต {area}", cur, ytd, sheet=heading) + "</figure>",
                  _table(["รายการ", f"EBITDA {cur} (บาท)", f"Volume {cur} (m³)", "EBITDA สะสม YTD (บาท)",
                          "Volume สะสม YTD (m³)"],
                         [f'<tr class="total-row"><td>รวมเขต {area}</td><td>{num(tot[0])}</td><td>{num(tot[1], 1)}</td>'
                          f"<td>{num(tot[2])}</td><td>{num(tot[3], 1)}</td></tr>"])]
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s8.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s8.strategy"))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"
