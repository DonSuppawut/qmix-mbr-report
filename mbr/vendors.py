"""Sub-contractor cartage by vendor, from `รายงานต้นทุน <Mon>'26 All Area.xlsx` sheet Exp&REV (spec 3.4)."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import openpyxl

from .fmt import EN_MONTH_ABBR

SUP_GROUP_TRUCK_RENT = "07"
# Vendor tag -> text patterns. Order matters: first match wins. TMP counts as QMix trucks (60 THB/m³ contract).
VENDORS = [
    ("TMP", "QMix", ("ไทย แมค พรีแคชท์",)),
    ("Indear99", "Sub", ("อินเดียร์99", "อินเดียร์ 99")),
    ("CCP", "Sub", ("Sub-CCP", "รถโม่ CCP", "ผลิตภัณฑ์คอนกรีตชลบุรี", "รถโม่พร้อมคนขับ")),
    ("UMO", "Sub", ("UMO",)),
    ("F-Transport", "Sub", ("F-Transport",)),
    ("Act Forward", "Sub", ("แอ็คท ฟอร์เวิร์ค", "Act Forward")),
]
_VOL = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m3|M3|m³|คิว)")


def cost_report_path(account: Path, year: int, month: int) -> Path:
    return account / f"รายงานต้นทุน {EN_MONTH_ABBR[month - 1]}'{year % 100:02d} All Area.xlsx"


def _vendor(text: str) -> tuple[str, str] | None:
    for name, kind, pats in VENDORS:
        if any(p in text for p in pats):
            return name, kind
    return None


def vendor_month(path: Path, year: int, month: int) -> dict:
    """Amount = every vendor-tagged EST row of Sup.Group 07 (accruals, reversals, true-ups included) so the
    total ties to TVC row 164; volume = only rows whose text names the current month (e.g. "Aug'26")."""
    tag = f"{EN_MONTH_ABBR[month - 1]}'{year % 100:02d}".lower()
    amount: dict[str, float] = defaultdict(float)
    volume: dict[str, float] = defaultdict(float)
    kinds: dict[str, str] = {}
    untagged = 0.0
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Exp&REV"]
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        ix = {h: header.index(h) for h in ("Amount", "Text", "AO", "Sup. Group", "Ref.Doc")}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if "EST" not in str(row[ix["AO"]] or "") or not str(row[ix["Sup. Group"]] or "").startswith(SUP_GROUP_TRUCK_RENT):
                continue
            text = str(row[ix["Text"]] or "")
            v = _vendor(text) or _vendor(str(row[ix["Ref.Doc"]] or ""))
            amt = float(row[ix["Amount"]] or 0)
            if v is None:
                untagged += amt
                continue
            name, kind = v
            kinds[name] = kind
            amount[name] += amt
            if tag in text.lower().replace(" ", ""):
                m = _VOL.search(text)
                if m:
                    volume[name] += float(m.group(1).replace(",", ""))
    finally:
        wb.close()
    return {"amount": dict(amount), "volume": dict(volume), "kind": kinds, "untagged": untagged}
