"""Section 6.4 (QMix vs sub-contractor trucks) and 6.5 (vendor movement) — 3-month movement."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .fmt import esc, num, th_month_short
from .report import MonthData
from .tvc import read_scope
from .vendors import cost_report_path, vendor_month


@dataclass
class CartageMonth:
    year: int
    month: int
    cartage: float        # TVC row 172 (combined)
    sub_row164: float     # TVC row 164 (combined)
    volume: float         # sales volume (combined)
    vendors: dict


def _prev(year: int, month: int, n: int) -> tuple[int, int]:
    m = month - n
    return (year, m) if m >= 1 else (year - 1, m + 12)


def load_cartage_months(account: Path, tvc_current: Path, year: int, month: int, n: int = 3) -> list[CartageMonth]:
    out = []
    for i in range(n):
        y, m = _prev(year, month, i)
        if y != year:
            break  # earlier-year months live in another year's TVC file — not wired up yet
        d = read_scope(tvc_current, m, "A")["combined"]
        v = vendor_month(cost_report_path(account, y, m), y, m)
        total = sum(v["amount"].values())
        if abs(total - d["cartage_sub"]) > 1.0:
            raise ValueError(f"{y}-{m:02d}: vendor total {total:,.2f} != TVC row 164 {d['cartage_sub']:,.2f} — "
                             "a vendor text pattern is missing; stop and check with Don")
        out.append(CartageMonth(y, m, d["cartage"], d["cartage_sub"], d["volume"], v))
    return out


def _header(months: list[CartageMonth], first: str, extra_first: list[str], sub: list[str]) -> str:
    top = "".join(f'<th rowspan="2">{esc(h)}</th>' for h in [first] + extra_first)
    top += "".join(f'<th colspan="3" style="text-align:center">{esc(th_month_short(c.year, c.month))}</th>' for c in months)
    return f"<thead><tr>{top}</tr><tr>{''.join(f'<th>{esc(s)}</th>' for s in sub * len(months))}</tr></thead>"


def section6_4(months: list[CartageMonth]) -> list[str]:
    rows = {"qmix": [], "sub": [], "total": []}
    for c in months:
        tmp_amt = c.vendors["amount"].get("TMP", 0.0)
        tmp_vol = c.vendors["volume"].get("TMP", 0.0)
        sub_amt = c.sub_row164 - tmp_amt
        sub_vol = sum(c.vendors["volume"].values()) - tmp_vol
        qmix_amt = c.cartage - sub_amt
        qmix_vol = c.volume - sub_vol
        for key, amt, vol in (("qmix", qmix_amt, qmix_vol), ("sub", sub_amt, sub_vol)):
            rows[key].append(f"<td>{num(amt)} ({amt / c.cartage * 100:.1f}%)</td><td>{num(vol, 2)}</td>"
                             f"<td>{num(amt / vol if vol else 0, 2)}</td>")
        rows["total"].append(f"<td>{num(c.cartage)}</td><td>{num(c.volume, 2)}</td><td>{num(c.cartage / c.volume, 2)}</td>")
    span = f"{th_month_short(months[0].year, months[0].month).split()[0]}-{th_month_short(months[-1].year, months[-1].month)}"
    body = (f"<tr><td>รถ QMix (รวม TMP ตามสัญญา)</td>{''.join(rows['qmix'])}</tr>"
            f"<tr><td>รถ Sub-contractor</td>{''.join(rows['sub'])}</tr>"
            f'<tr class="total-row"><td>รวมทั้งหมด</td>{"".join(rows["total"])}</tr>')
    table = (f'<div class="tscroll"><table>{_header(months, "ประเภท", [], ["ยอดเงิน (สัดส่วน)", "ปริมาณ", "บาท/m³"])}'
             f"<tbody>{body}</tbody></table></div>")
    return [f"<h3>6.4 สรุป Cartage ถ่วงน้ำหนัก: รถ QMix เทียบ รถผู้รับเหมา — Movement {esc(span)} (EST รวม)</h3>",
            '<p class="meta">รถ QMix = Cartage รวม (แถว 172) − Cartage รถผู้รับเหมา (แถว 164) + TMP (สัญญา 60 บาท/m³ นับเป็นรถ QMix); '
            'ปริมาณรถ Sub = ปริมาณรายเวนเดอร์ (ไม่รวม TMP) ปริมาณรถ QMix = ปริมาณขายที่เหลือ — บาท/m³ คิดต่อปริมาณขาย</p>',
            table]


def section6_5(months: list[CartageMonth]) -> list[str]:
    cur = months[0].vendors
    names = sorted(cur["amount"], key=lambda k: -cur["amount"][k])
    for c in months[1:]:
        names += [k for k in c.vendors["amount"] if k not in names]
    body = []
    for name in names:
        kind = next((c.vendors["kind"][name] for c in months if name in c.vendors["kind"]), "")
        cells = []
        for c in months:
            a, v = c.vendors["amount"].get(name, 0.0), c.vendors["volume"].get(name, 0.0)
            cells.append(f"<td>{num(a)}</td><td>{num(v, 2)}</td><td>{num(a / v if v else 0, 2)}</td>")
        body.append(f"<tr><td>{esc(name)}</td><td>{esc(kind)}</td>{''.join(cells)}</tr>")
    tot = []
    for c in months:
        a, v = sum(c.vendors["amount"].values()), sum(c.vendors["volume"].values())
        tot.append(f"<td>{num(a)}</td><td>{num(v, 2)}</td><td>{num(a / v if v else 0, 2)}</td>")
    body.append(f'<tr class="total-row"><td colspan="2">รวม</td>{"".join(tot)}</tr>')
    span = f"{th_month_short(months[0].year, months[0].month).split()[0]}-{th_month_short(months[-1].year, months[-1].month)}"
    table = (f'<div class="tscroll"><table>{_header(months, "Vendor", ["ประเภท"], ["ยอดเงิน", "ปริมาณ", "บาท/m³"])}'
             f"<tbody>{''.join(body)}</tbody></table></div>")
    return [f"<h3>6.5 รายละเอียดผู้รับเหมาขนส่ง แยกตาม Vendor — Movement {esc(span)}</h3>", table,
            '<div class="srcnote"><b>ข้อจำกัดของตัวเลข (disclosure):</b> ยอดเงินรายเวนเดอร์รวมทุกรายการใน Sup.Group '
            '"07.ค่าเช่ารถบรรทุกคอนกรีต" ของ EST (Accrue/Reverse/ปรับปรุงยอดเดือนก่อนที่ลงในเดือนนี้) เพื่อให้ยอดรวมตรงกับ '
            'Cartage รถผู้รับเหมาในไฟล์ TVC พอดี แต่ปริมาณ (m³) นับเฉพาะรายการที่ระบุเดือนปัจจุบันในข้อความ GL — '
            'อัตราบาท/m³ รายเวนเดอร์จึงเป็นอัตราผสม (blended) ไม่ใช่ต้นทุนต่อหน่วยของเดือนนี้ล้วน ๆ — '
            'CCP รวม "บมจ.ผลิตภัณฑ์คอนกรีตชลบุรี" และ "ค่าบริการ(เช่า)รถโม่พร้อมคนขับ" (บางรายการไม่มี m³ ในข้อความ) — '
            'TMP ราคาสัญญา 60 บาท/m³ นับเป็นรถ QMix — อินเดียร์99 เป็น pass-through ไม่กระทบ EBITDA สุทธิ</div>']


def section6_extra(md: MonthData, months: list[CartageMonth]) -> list[str]:
    return section6_4(months) + section6_5(months)
