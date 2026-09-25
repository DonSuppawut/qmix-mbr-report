"""Regression: Section 1 (Waterfall) + Section 2 (Scorecard) of Aug'69 vs delivered HTML."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mbr import calc
from mbr.reference_html import decimals, parse_number, tables_by_heading
from mbr.tvc import read_scope

ACCOUNT = Path(r"D:\QMix\Account")
REF = Path(r"D:\QMix\คจ\08 ส.ค. 69\MBR_EST_Aug69_edited_v2.html")

SCORE_LABELS = {
    "NPAT (บาท)": "npat",
    "EBITDA (บาท)": "ebitda",
    "EBITDA (บาท/m³)": "ebitda_m3",
    "ปริมาณขาย (m³)": "volume",
    "Net Price (บาท/m³)": "net_price_m3",
    "Net Contribution (บาท/m³)": "netcon_m3",
    "TVC (บาท/m³)": "tvc_m3",
    "Raw Material (บาท/m³)": "rawmat_m3",
    "Assign Costs (บาท/m³)": "assign_m3",
    "Cartage (บาท/m³)": "cartage_m3",
    "TFC (บาท/m³)": "tfc_m3",
}
WF_LABELS = {
    "ปริมาณขาย": "volume", "ราคาขาย": "net_price", "วัตถุดิบ": "rawmat", "Assign Costs": "assign",
    "ค่าขนส่ง": "cartage", "Exbatch & Trading": "exbtrd", "TFC": "tfc", "รายการพิเศษ": "extraordinary",
    "ค่าเสื่อมราคา": "depreciation", "ดอกเบี้ยจ่าย": "finance", "ภาษีเงินได้": "tax",
}
SCOPE_HEADINGS = {
    "combined": ("2.1 EST รวม", "1.1 Waterfall"),
    "core": ("2.2 EST Core", "1.2 Waterfall"),
    "pmt": ("2.3 EST PMT", "1.3 Waterfall"),
}


def find(tables: dict, prefix: str) -> list[list[str]]:
    return next(v for k, v in tables.items() if k.startswith(prefix))


def check(results: list, where: str, expected_text: str, got: float) -> None:
    exp = parse_number(expected_text)
    if exp is None:
        results.append((False, where, expected_text, got, "unparseable"))
        return
    tol = 0.5 * 10 ** -decimals(expected_text) + 1e-9
    results.append((abs(got - exp) <= tol, where, expected_text, got, f"tol {tol:g}"))


def main() -> int:
    aug = ACCOUNT / "08.26 TVC by Plant by Month.xlsx"
    A = read_scope(aug, 8, "A")
    P = read_scope(aug, 8, "P")
    LM = read_scope(aug, 7, "A")  # JulA sheet inside the Aug file
    tables = tables_by_heading(REF)
    results: list = []

    for scope, (sc_head, wf_head) in SCOPE_HEADINGS.items():
        a, p, lm = A[scope], P[scope], LM[scope]
        sa, sp, slm = calc.scorecard_row(a), calc.scorecard_row(p), calc.scorecard_row(lm)
        for row in find(tables, sc_head)[1:]:
            key = SCORE_LABELS.get(row[0])
            if not key:
                results.append((False, f"{scope}/{row[0]}", "", 0, "unmapped row"))
                continue
            check(results, f"2 {scope} {key} Act", row[1], sa[key])
            check(results, f"2 {scope} {key} AP", row[2], sp[key])
            check(results, f"2 {scope} {key} LM", row[3], slm[key])
            check(results, f"2 {scope} {key} vsAP", row[4], sa[key] - sp[key])
            check(results, f"2 {scope} {key} vsLM", row[5], sa[key] - slm[key])

        wf = calc.waterfall_npat(a, p)
        steps = dict(wf["steps"])
        for row in find(tables, wf_head)[1:]:
            if row[0].startswith("NPAT ตามแผน"):
                check(results, f"1 {scope} start", row[1], wf["start"])
            elif row[0].startswith("NPAT จริง"):
                check(results, f"1 {scope} end", row[1], wf["end"])
            else:
                check(results, f"1 {scope} {WF_LABELS[row[0]]}", row[2], steps[WF_LABELS[row[0]]])

        res = calc.residuals(a, p)
        for lvl, v in res.items():
            results.append((abs(v) < 0.01, f"residual {scope} {lvl}", "0", v, "abs<0.01"))

    fails = [r for r in results if not r[0]]
    for ok, where, exp, got, note in results:
        if not ok:
            print(f"FAIL {where:32} expected {exp:>16}  got {got:,.4f}  ({note})")
    print(f"{len(results) - len(fails)}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
