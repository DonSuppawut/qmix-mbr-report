"""Section 3 — Sales Analysis from the Netcon files (current month vs last month)."""
from __future__ import annotations

from collections import defaultdict

from . import netcon as N
from .fmt import esc, num, th_month_long, th_month_short
from .report import MonthData, _box, _table

REBATE_CUSTOMERS = {"7312095": "CCP", "7310082": "สุขุมคอนสตรัคชั่นฯ"}  # request rebate on every project (Don)


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def _signed_pct(v: float) -> str:
    cls = "pos" if v > 0.05 else "neg" if v < -0.05 else ""
    return f'<td class="{cls}">{v:+.1f}%</td>'


def _name_key(r: N.Row) -> str:
    # One customer can carry two codes (e.g. ไทย แมค พรีแคซท์ 7312060/8006620) — group by name.
    return " ".join(r.cust_name.split())


def _concentration(rows: list[N.Row], n: int) -> float:
    per: dict[str, float] = defaultdict(float)
    for r in rows:
        per[_name_key(r)] += r.qty
    tot = sum(per.values())
    return sum(sorted(per.values(), reverse=True)[:n]) / tot * 100 if tot else 0.0


def _customers(rows: list[N.Row]) -> dict[str, dict]:
    per: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        per[_name_key(r)]["qty"] += r.qty
        per[_name_key(r)]["netcon"] += r.netcon
    return per


def section3(md: MonthData, cur_rows: list[N.Row], lm_rows: list[N.Row]) -> str:
    cur, lm = th_month_short(md.year, md.month), th_month_short(*md.lm_year_month)
    cm, lmm = cur.split()[0], lm.split()[0]
    n = md.narrative
    sa, sl = N.by_segment(cur_rows), N.by_segment(lm_rows)
    ta, tl = N.total(cur_rows), N.total(lm_rows)

    rows = []
    for key, d_a, d_l, label in [(s, sa[s], sl[s], N.SEGMENT_LABELS[s]) for s in N.SEGMENTS] + [("total", ta, tl, "รวมทั้งเขต")]:
        qa, ql = d_a["qty"], d_l["qty"]
        pa, pl = (d_a["total_net"] / qa if qa else 0), (d_l["total_net"] / ql if ql else 0)
        na, nl = (d_a["netcon"] / qa if qa else 0), (d_l["netcon"] / ql if ql else 0)
        cls = ' class="total-row"' if key == "total" else ""
        rows.append(f"<tr{cls}><td>{esc(label)}</td><td>{num(qa)}</td><td>{num(ql)}</td>{_signed_pct(_pct(qa, ql))}"
                    f"<td>{num(pa)}</td><td>{num(pl)}</td>{_signed_pct(_pct(pa, pl))}"
                    f"<td>{num(na)}</td><td>{num(nl)}</td>{_signed_pct(_pct(na, nl))}</tr>")
    parts = ['<h2 id="s3">3. การวิเคราะห์ด้านการขาย (Sales Analysis)</h2>',
             f'<p class="meta">จากไฟล์ Netcon ระดับ Mix/Site Code (เดือน {esc(cm)} และ {esc(lmm)}) เฉพาะ Director=EST '
             + (f'เขต {esc(md.area)} (คอลัมน์ AAO ของไฟล์) ' if md.area else '') +
             'ครอบคลุม Core+PMT — Segment ตามปริมาณโครงการ (≤200 Tiny, 201–1,000 Small, 1,001–5,000 Medium, '
             '5,001–20,000 Large, 20,001+ Mega) ใช้กับแถวที่ tag "ส่วนลดพิเศษ" เท่านั้น แถวที่มี Segment ระบุอยู่แล้วคงเดิม — '
             'ไชน่า สเตท คอนสตรัคชั่นนับเป็น Mega ทุกโครงการ (Don) — เรียง Mega→Large→Medium→Small→Tiny เสมอ '
             '— ปริมาณรวมจากไฟล์ Netcon จึงต่างจากปริมาณขายในไฟล์ TVC เล็กน้อย</p>',
             "<h3>3.1 วิเคราะห์ราย Segment</h3>",
             _table(["Segment", f"Vol {cm}", f"Vol {lmm}", "ΔVol%", f"Price {cm}", f"Price {lmm}", "ΔPrice%",
                     f"NC {cm}", f"NC {lmm}", "ΔNetcon%"], rows),
             '<p class="footnote">หน่วย: ปริมาณเป็น m³ ราคาและ Net Contribution เป็นบาท/m³ — Price = Net Price</p>']

    cost_rows = []
    for s in N.SEGMENTS:
        d = sa[s]
        q = d["qty"] or 1
        cost_rows.append(
            f"<tr><td>{esc(N.SEGMENT_LABELS[s])}</td><td>{num(d['list'] / q)}</td><td>{num(d['total_net'] / q)}</td>"
            f"<td>{(1 - d['total_net'] / d['list']) * 100 if d['list'] else 0:.1f}%</td><td>{num(d['rawmat'] / q)}</td>"
            f"<td>{num(d['cartage'] / q)}</td><td>{num(d['tvc'] / q)}</td><td>{num(d['netcon'] / q)}</td>"
            f"<td>{num(d['qty'] / d['projects'] if d['projects'] else 0, 1)}</td></tr>")
    parts += [f"<h4>3.1.1 โครงสร้างต้นทุนราย Segment เดือน{esc(th_month_long(md.year, md.month).split()[0])}</h4>",
              _table(["Segment", "List Price", "Net Price", "ส่วนลด %", "วัตถุดิบ", "ขนส่ง", "TVC", "NetCon",
                      "m³/โครงการ"], cost_rows),
              '<p class="footnote">บาท/m³ ถ่วงน้ำหนักตามปริมาณ — m³/โครงการ = ปริมาณ ÷ จำนวนหน่วยงาน (Site Code)</p>']
    if n.get("s3.segment_notes"):
        parts += ["<h4>3.1.2 ข้อสังเกตจาก Segment</h4>", n["s3.segment_notes"]]

    conc = []
    for k in (5, 10, 20):
        a, b = _concentration(cur_rows, k), _concentration(lm_rows, k)
        conc.append(f"<tr><td>ลูกค้า {k} รายแรก</td><td>{a:.1f}%</td><td>{b:.1f}%</td><td>{a - b:+.1f} จุด</td></tr>")
    ca, cl = _customers(cur_rows), _customers(lm_rows)
    conc.append(f"<tr><td>จำนวนลูกค้าทั้งหมด</td><td>{len(ca)}</td><td>{len(cl)}</td><td>{len(ca) - len(cl):+d}</td></tr>")
    new_c, lost_c = set(ca) - set(cl), set(cl) - set(ca)
    sa_, sl_ = N.sites(cur_rows), N.sites(lm_rows)
    new_s, end_s = set(sa_) - set(sl_), set(sl_) - set(sa_)
    turn = [
        f"<tr><td>ลูกค้าใหม่ในเดือน {esc(cm)}</td><td>{len(new_c)}</td><td>{num(sum(ca[c]['qty'] for c in new_c))}</td>"
        f"<td>{num(sum(ca[c]['netcon'] for c in new_c))}</td></tr>",
        f"<tr><td>ลูกค้าที่หายไปจาก {esc(lmm)}</td><td>{len(lost_c)}</td><td>{num(sum(cl[c]['qty'] for c in lost_c))}</td>"
        f"<td>{num(sum(cl[c]['netcon'] for c in lost_c))}</td></tr>",
        f"<tr><td>หน่วยงาน/โครงการใหม่</td><td>{len(new_s)}</td><td>{num(sum(sa_[s] for s in new_s))}</td><td>—</td></tr>",
        f"<tr><td>หน่วยงาน/โครงการที่จบไป</td><td>{len(end_s)}</td><td>{num(sum(sl_[s] for s in end_s))}</td><td>—</td></tr>",
    ]
    parts += ["<h3>3.2 วิเคราะห์ลูกค้า</h3>", "<h4>3.2.1 การกระจุกตัวของลูกค้า</h4>",
              _table(["สัดส่วนปริมาณขาย", cur, lm, "การเปลี่ยนแปลง"], conc),
              '<p class="footnote">นับลูกค้าตามชื่อ (ลูกค้ารายเดียวกันที่มีหลายรหัสนับเป็นรายเดียว)</p>',
              n.get("s3.customer_notes", ""),
              "<h4>3.2.2 การหมุนเวียนของฐานลูกค้าและโครงการ</h4>",
              _table(["รายการ", "จำนวนราย", "ปริมาณ (m³)", "Net Contribution (บาท)"], turn),
              f'<p class="footnote">ลูกค้า/หน่วยงานใหม่ = มีปริมาณใน {esc(cm)} แต่ไม่มีใน {esc(lmm)} (วัดปริมาณเดือนนี้); '
              f'ที่หายไป/จบไป = มีใน {esc(lmm)} แต่ไม่มีใน {esc(cm)} (วัดปริมาณของ {esc(lmm)})</p>',
              n.get("s3.turnover_notes", "")]

    reb = [r for r in cur_rows if r.cust_code in REBATE_CUSTOMERS]
    reb.sort(key=lambda r: (r.cust_code, -r.qty))
    reb_rows = [f"<tr><td>{esc(REBATE_CUSTOMERS[r.cust_code])}</td><td>{esc(r.site)}</td><td>{esc(r.site_name[:60])}</td>"
                f"<td>{num(r.qty, 2)}</td><td>{num(r.rebate_bt, 1)}</td></tr>" for r in reb]
    missing = [r for r in reb if r.rebate_bt <= 0]
    lowmargin = [r for r in cur_rows if r.segment in ("Large", "Mega") and r.cust_code not in REBATE_CUSTOMERS
                 and r.qty and r.netcon / r.qty < 250]
    parts += ["<h4>3.2.3 ตรวจสอบ Rebate Cement พิเศษ (CCP / สุขุมคอนสตรัคชั่นฯ)</h4>",
              f'<p class="meta">ลูกค้ารหัส 7312095 (CCP) และ 7310082 (สุขุมคอนสตรัคชั่นฯ) ต้องขอ Rebate ทุกโครงการ — '
              f'พบ {len(reb)} รายการในเดือน {esc(cm)}, ไม่มีอัตรา Rebate {len(missing)} รายการ</p>',
              _table(["ลูกค้า", "หน่วยงาน", "ชื่อโครงการ", "ปริมาณ (m³)", "อัตรา Rebate (บาท/ตัน)"], reb_rows)
              if reb_rows else "<p>ไม่มีรายการของลูกค้าทั้งสองรายในเดือนนี้</p>"]
    if lowmargin:
        lm_rows_html = [f"<tr><td>{esc(r.cust_name[:40])}</td><td>{esc(r.site)}</td><td>{esc(r.segment)}</td>"
                        f"<td>{num(r.qty, 2)}</td><td>{num(r.netcon / r.qty)}</td><td>{num(r.rebate_bt, 1)}</td></tr>"
                        for r in sorted(lowmargin, key=lambda r: r.netcon / r.qty)]
        parts += ['<p class="meta">Segment Large/Mega ที่ NetCon &lt; 250 บาท/m³ — พิจารณาขอ Rebate เพิ่ม '
                  '(คนละเรื่องกับ Segment "ส่วนลดพิเศษ")</p>',
                  _table(["ลูกค้า", "หน่วยงาน", "Segment", "ปริมาณ (m³)", "NetCon (บาท/m³)", "Rebate ปัจจุบัน (บาท/ตัน)"],
                         lm_rows_html)]
    parts.append(n.get("s3.rebate_notes", ""))

    bucket_rows = []
    for rows_ in (cur_rows, lm_rows):
        tot = sum(r.qty for r in rows_) or 1
        g: dict = defaultdict(float)
        for r in rows_:
            g[(N.nc_bucket(r), r.segment)] += r.qty
        bucket_rows.append((g, tot))
    body = []
    for label, _, _ in N.NC_BUCKETS:
        cells = []
        sums = []
        for g, tot in bucket_rows:
            vals = [g[(label, s)] / tot * 100 for s in N.SEGMENTS]
            cells += [f"<td>{v:.1f}%</td>" for v in vals] + [f"<td>{sum(vals):.1f}%</td>"]
            sums.append(sum(vals))
        chg = sums[0] - sums[1]
        good = chg < 0 if label.startswith(("<150", "151")) else chg > 0
        cls = "" if abs(chg) < 0.05 else ("pos" if good else "neg")
        body.append(f"<tr><td>{esc(label)}</td>{''.join(cells)}<td class=\"{cls}\">{chg:+.1f} จุด</td></tr>")
    segs = "".join(f"<th>{s}</th>" for s in N.SEGMENTS) + "<th>รวม%</th>"
    table = ('<div class="tscroll"><table><thead><tr><th rowspan="2">ระดับ NetCon ต่อ m³</th>'
             f'<th colspan="6" style="text-align:center">% ของปริมาณที่เทเดือน {esc(cur)}</th>'
             f'<th colspan="6" style="text-align:center">% ของปริมาณที่เทเดือน {esc(lm)}</th>'
             f'<th rowspan="2">การเปลี่ยนแปลง (รวม%)</th></tr><tr>{segs}{segs}</tr></thead>'
             f"<tbody>{''.join(body)}</tbody></table></div>")
    parts += ["<h3>3.3 คุณภาพของยอดขาย</h3>", table,
              '<p class="footnote">NetCon/m³ ต่อแถว Mix/Site Code — ช่วง: ≤150, 151–250, 251–350, &gt;350 บาท/m³ × Segment</p>',
              _box("watch", "เรื่องที่ควรระวัง", n.get("s3.watch")),
              _box("strategy", "Game Plan / กลยุทธ์เดือนถัดไป", n.get("s3.strategy"))]
    return '<section class="wrap">' + "\n".join(p for p in parts if p) + "</section>"
