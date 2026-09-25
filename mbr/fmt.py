"""Number/label formatting shared by HTML and xlsx output."""
from __future__ import annotations

import html

TH_MONTH_ABBR = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
TH_MONTH_FULL = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
                 "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
EN_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def be_year(year: int) -> int:
    return year + 543


def th_month_short(year: int, month: int) -> str:
    """e.g. 'ส.ค. 69'"""
    return f"{TH_MONTH_ABBR[month - 1]} {be_year(year) % 100:02d}"


def th_month_long(year: int, month: int) -> str:
    """e.g. 'สิงหาคม 2569'"""
    return f"{TH_MONTH_FULL[month - 1]} {be_year(year)}"


def file_stem(year: int, month: int) -> str:
    """e.g. 'MBR_EST_Aug69'"""
    return f"MBR_EST_{EN_MONTH_ABBR[month - 1]}{be_year(year) % 100:02d}"


def num(v: float, dec: int = 0, signed: bool = False) -> str:
    s = f"{v:+,.{dec}f}" if signed else f"{v:,.{dec}f}"
    return s.replace("+-", "-")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def delta_class(v: float, higher_is_better: bool = True, eps: float = 1e-9) -> str:
    if abs(v) < eps:
        return ""
    good = v > 0 if higher_is_better else v < 0
    return "pos" if good else "neg"


def mb(v: float, signed: bool = False) -> str:
    """Millions of baht with 2 decimals, e.g. '+7.03'."""
    return num(v / 1e6, 2, signed)
