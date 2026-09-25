"""Section 9 (Forecast) and Section 10 (summary)."""
from __future__ import annotations

from . import calc, svg
from .fmt import TH_MONTH_ABBR, delta_class, esc, num, th_month_long, th_month_short
from .forecast import summary
from .report import SCOPE_TITLES, MonthData, _box, _table

FC_TITLES = {"combined": "EST รวม (Core + PMT)", "core": "EST Core", "pmt": "EST PMT"}


def check_forecast_month(md: MonthData, fc: dict) -> None:
    """The forecast file must carry this month's actual — catches a wrong-month file (spec section 2)."""
    for scope in calc.SCOPES:
        got = fc[scope]["ebitda"]["ACT"][md.month - 1]
        want = md.actual[scope]["ebitda"]
        if abs(got - want) > 1.0:
            raise ValueError(f"Forecast file ACT EBITDA {scope} for month {md.month} = {got:,.0f}, "
                             f"TVC says {want:,.0f} — wrong month file? stop and check with Don")


def section9(md: MonthData, fc: dict, source_name: str) -> str:
    check_forecast_month(md, fc)
    m = md.month
    yy = f"{(md.year + 543) % 100:02d}"
    first, last = TH_MONTH_ABBR[0], TH_MONTH_ABBR[m - 1]
    rest = f"{TH_MONTH_ABBR[m]}-{TH_MONTH_ABBR[11]}" if m < 12 else ""
    parts = ['<h2 id="s9">9. Forecast</h2>',
             f'<p class="meta">คาดการณ์ทั้งปี {md.year + 543} จากไฟล์ "{esc(source_name)}" — {first}-{last} เป็น Actual, '
             f'{rest} เป็น Forecast ณ รอบรายงาน {esc(th_month_short(md.year, m))} เทียบแผน (AP) และปีก่อน (LY) — '
             'กราฟ: แท่งเข้ม = Actual, แท่งอ่อน = Forecast, เส้นส้ม = AP</p>']
    labels = [f"{a}" for a in TH_MONTH_ABBR]
    for i, scope in enumerate(calc.SCOPES, 1):
        s = summary(fc, scope, m)
        e, v = s["ebitda"], s["volume"]
        rows = [
            (f"YTD Actual ({first}-{last} {yy})", e["ytd"], v["ytd"], ""),
            (f"Forecast ที่เหลือ ({rest} {yy})", e["rest"], v["rest"], ""),
            ("รวมทั้งปี (Actual+Forecast)", e["year"], v["year"], "category-row"),
            ("แผนทั้งปี (AP)", e["ap"], v["ap"], ""),
            ("เทียบ AP ทั้งปี", e["year"] - e["ap"], v["year"] - v["ap"], "delta"),
            ("ปีก่อน (LY) ทั้งปี", e["ly"], v["ly"], ""),
            ("เทียบ LY ทั้งปี", e["year"] - e["ly"], v["year"] - v["ly"], "delta"),
        ]
        html_rows = []
        for label, ev, vv, cls in rows:
            if cls == "delta":
                html_rows.append(f'<tr><td>{esc(label)}</td><td class="{delta_class(ev)}">{num(ev, 0, True)}</td>'
                                 f'<td class="{delta_class(vv)}">{num(vv, 1, True)}</td></tr>')
            else:
                attr = f' class="{cls}"' if cls else ""
                html_rows.append(f"<tr{attr}><td>{esc(label)}</td><td>{num(ev)}</td><td>{num(vv, 1)}</td></tr>")
        f = fc[scope]
        panels = [("EBITDA (บาท)", f["ebitda"]["ACT"], f["ebitda"]["AP"], "THB"),
                  ("Volume (m³)", f["volume"]["ACT"], f["volume"]["AP"], "m3"),
                  ("Net Price (บาท/m³)", f["price"]["ACT"], f["price"]["AP"], "rate"),
                  ("Net Contribution (บาท/m³)", f["netcon"]["ACT"], f["netcon"]["AP"], "rate")]
        parts += [f"<h3>9.{i} {esc(FC_TITLES[scope])}</h3>",
                  "<figure>" + svg.forecast_panels(f"Forecast {FC_TITLES[scope]}", labels, m, panels,
                                                        sheet=f"9.{i} {FC_TITLES[scope]}") + "</figure>",
                  _table(["รายการ", "EBITDA (บาท)", "Volume (m³)"], html_rows)]
    parts += [_box("watch", "เรื่องที่ควรระวัง", md.narrative.get("s9.watch")),
              _box("strategy", "กลยุทธ์เดือนถัดไป", md.narrative.get("s9.strategy")),
              _box("srcnote", "แหล่งข้อมูล",
                   f'ไฟล์ "{esc(source_name)}" ชีท AP26 — ยอดรวมคำนวณจากตัวเลขรายเดือนในไฟล์ (ไม่ใช้คอลัมน์ Total ของไฟล์) '
                   f'ตรวจแล้วว่า EBITDA Actual เดือน{esc(th_month_long(md.year, m))} ในไฟล์ตรงกับไฟล์ TVC ทั้ง 3 scope '
                   'ตัวเลขเดือนที่เหลือเป็นค่าคาดการณ์จากไฟล์โดยตรง ไม่ได้ปรับเพิ่ม')]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"


def section10(md: MonthData) -> str:
    rows = []
    for scope, label in (("combined", "EST รวม (Combined)"), ("core", "EST Core"), ("pmt", "EST PMT")):
        a, p = md.actual[scope], md.plan[scope]
        diff = a["npat"] - p["npat"]
        pct = a["volume"] / p["volume"] * 100 if p["volume"] else 0.0
        rows.append(f"<tr><td>{esc(label)}</td><td>{num(a['npat'])}</td><td>{num(p['npat'])}</td>"
                    f'<td class="{delta_class(diff)}">{num(diff, 0, True)}</td>'
                    f'<td class="{delta_class(pct - 100)}">{pct:.1f}%</td></tr>')
    n = md.narrative
    parts = ['<h2 id="s10">10. สรุปและข้อเสนอแนะ</h2>',
             '<p class="meta">สรุปภาพรวมจากหัวข้อ 1–9 พร้อมข้อเสนอแนะเชิงปฏิบัติการสำหรับเดือนถัดไป — '
             'อ้างอิงเฉพาะตัวเลขที่ยืนยันแล้วในแต่ละหัวข้อ</p>',
             "<h3>10.1 สรุปภาพรวมผลประกอบการ</h3>",
             _table(["รายการ", "NPAT Actual (บาท)", "NPAT AP (บาท)", "ผลต่าง", "ปริมาณขาย % ของแผน"], rows),
             f"<p>{n['s10.overview']}</p>" if n.get("s10.overview") else ""]
    if n.get("s10.points"):
        parts += ["<h3>10.2 ประเด็นสำคัญรายหัวข้อ</h3>",
                  "<ul>" + "".join(f"<li>{x}</li>" for x in n["s10.points"]) + "</ul>"]
    if n.get("s10.actions"):
        parts += ["<h3>10.3 ข้อเสนอแนะเชิงปฏิบัติการเดือนถัดไป (เรียงตามลำดับความสำคัญ)</h3>",
                  "<ol>" + "".join(f"<li>{x}</li>" for x in n["s10.actions"]) + "</ol>"]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"
