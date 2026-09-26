"""Compare every table in a generated report against the delivered reference report, plus HTML checks.

Usage: python tests/regress_html.py out/MBR_EST_Aug69.html "D:\\QMix\\คจ\\08 ส.ค. 69\\MBR_EST_Aug69_edited_v2.html"
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mbr.reference_html import parse_number, tables_by_heading

# Headings that exist only in the new report format (no counterpart in Aug'69).
NEW_ONLY = ("1.4 EBITDA Bridge",
            # Aug'69 listed only 8 of the 13 CCP line items; the script lists all, plus customer 7310082 (spec 4).
            "3.2.3 ตรวจสอบ Rebate Cement พิเศษ (CCP")
# Row labels intentionally changed after Aug'69 (Don 2026-09-24: water split out of STORES & EQUIPMENT).
ALLOWED_NEW_ROWS = {"วัสดุคลังและอุปกรณ์ (STORES & EQUIPMENT ไม่รวมค่าน้ำ) (บาท/m³)", "ค่าน้ำ (Water) (บาท/m³)"}
# Cells where the delivered Aug'69 report itself is wrong/rounded differently — (heading prefix, plant code, col): why
KNOWN_REF_DIFFS = {
    ("6.6", "K4A5", 5): "same K4A5 GL-adjustment denominator issue as col 7",
    ("6.6", "K4A5", 7): "Aug'69 divided the GL adjustment by sales volume (1,342.75) but the base by production "
                        "volume (1,345.75); the script uses production volume for both",
    ("7.2", "K4A9", 7): "1-baht rounding in the delivered YTD figure",
    ("3.1.1", "Large", 5): "exact value 231.4987 — Aug'69 double-rounded to 232",
    ("3.2.1", "ลูกค้า 10", 1): "top-10 share exact 48.55% (by customer name) — Aug'69 shows 48.5",
    ("3.3", "<150", 10): "Jul Small share ≈0.15% — rounding boundary",
}
# Cells changed on purpose by Don's decisions after Aug'69 — (heading prefix, row label prefix or "*", cols): why
INTENTIONAL = [
    ("7.", "*", {7}, "YTD EBITDA uses restated months of the current TVC file (Don 2026-09-24)"),
    ("8.", "รวมเขต", {3}, "YTD EBITDA uses restated months of the current TVC file (Don 2026-09-24)"),
    ("3.1", "Mega", "*", "China State counted as Mega on every row (Don 2026-09-24)"),
    ("3.1", "Medium", "*", "China State counted as Mega on every row (Don 2026-09-24)"),
    ("3.3", "*", {1, 3, 7, 9}, "Mega/Medium columns — China State counted as Mega (Don 2026-09-24)"),
    # Jun/Jul columns: CCP invoices without m³ (1-15 มิ.ย., 1-15 ก.ค.) now take volume from production dispatches
    # (Approval request 3, 2026-09-26) — Aug'69 left them at 0 m³, overstating the CCP/sub-contractor rate.
    ("6.4", "*", {5, 6, 8, 9}, "CCP volume without m³ in the invoice taken from production dispatches (2026-09-26)"),
    ("6.5", "CCP", {6, 7, 9, 10}, "CCP volume without m³ in the invoice taken from production dispatches (2026-09-26)"),
    ("6.5", "รวม", {5, 6, 8, 9}, "CCP volume without m³ in the invoice taken from production dispatches (2026-09-26)"),
]
ALLOWED_DROPPED_ROWS = {"วัสดุคลังและอุปกรณ์ (STORES & EQUIPMENT) (บาท/m³)", "ค่าน้ำ (บาท/m³ — ไม่รวมใน Assign Costs รวม*)"}
TAGS = ("table", "tr", "td", "th", "thead", "tbody", "section", "figure", "svg", "div", "p", "h2", "h3")


def compare_tables(gen: dict, ref: dict) -> list[str]:
    errors, compared = [], 0
    intended_count: dict[str, int] = {}
    for heading, grows in gen.items():
        if heading.startswith(NEW_ONLY):
            continue
        ref_heading = heading
        if heading not in ref and heading.startswith("9.") and heading.split(" ", 1)[1] in ref:
            ref_heading = heading.split(" ", 1)[1]  # Aug'69 Section 9 sub-headings were un-numbered
        if heading.startswith("9.3") and "EST PMT" in ref:
            ref_heading = "EST PMT"
        if ref_heading not in ref:
            errors.append(f"[missing in reference] {heading}")
            continue
        rrows = ref[ref_heading]
        ga = [r for r in grows[1:] if r[0] not in ALLOWED_NEW_ROWS]
        ra = [r for r in rrows[1:] if r[0] not in ALLOWED_DROPPED_ROWS]
        # Aug'69 Section 7 names were hand-typed (e.g. 'บางปะกง', bare K-codes) — compare plant codes only.
        key = (lambda s: s.split()[0] if s else s) if heading.startswith("7.") else (lambda s: s)
        if [key(r[0]) for r in ga] != [key(r[0]) for r in ra]:
            errors.append(f"[row labels/order] {heading}: {[r[0] for r in ga]} vs {[r[0] for r in ra]}")
            continue
        for gr, rr in zip(ga, ra):
            for c, (g, r) in enumerate(zip(gr[1:], rr[1:]), 1):
                gv, rv = parse_number(g), parse_number(r)
                compared += 1
                known = next((why for (h, code, col), why in KNOWN_REF_DIFFS.items()
                              if heading.startswith(h) and (gr[0] + " ").startswith(code + " ") and col == c), None)
                intended = next((why for h, lab, cols, why in INTENTIONAL
                                 if heading.startswith(h) and (lab == "*" or gr[0].startswith(lab))
                                 and (cols == "*" or c in cols)), None)
                if (gv is None) != (rv is None) or (gv is not None and abs(gv - rv) > 1e-9):
                    if intended:
                        intended_count[intended] = intended_count.get(intended, 0) + 1
                        continue
                    if known:
                        print(f"KNOWN {heading[:40]} / {gr[0]} / col {c}: {g!r} vs {r!r} — {known}")
                        continue
                    errors.append(f"[value] {heading} / {gr[0]} / col {c}: {g!r} vs {r!r}")
    print(f"compared {compared} cells across {len(gen)} tables")
    for why, n in intended_count.items():
        print(f"CHANGED {n:3d} cell(s) on purpose — {why}")
    return errors


def structure_checks(html: str) -> list[str]:
    errors = []
    if "data:image" in html:
        errors.append("raster data:image found")
    if "<canvas" in html:
        errors.append("<canvas> found")
    for t in TAGS:
        opened = len(re.findall(rf"<{t}[\s>]", html))
        closed = len(re.findall(rf"</{t}>", html))
        if opened != closed:
            errors.append(f"tag <{t}> unbalanced: {opened} open vs {closed} close")
    anchors = re.findall(r'href="#(s\d+)"', html)
    ids = re.findall(r'<h2 id="(s\d+)"', html)
    if not anchors or anchors != ids:
        errors.append(f"TOC anchors {anchors} != section ids {ids}")
    if re.search(r">\s*K[0-9A-Z]{3}\s*<", html):
        errors.append("bare K-code cell without plant name")
    # Section balance (spec 5): visible text length between <h2> headings
    body = re.sub(r"<svg.*?</svg>|<style.*?</style>", "", html, flags=re.S)
    chunks = re.split(r'<h2 id="s\d+">', body)[1:]
    lengths = [len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))) for c in chunks]
    print("section text length:", dict(zip(ids, lengths)))
    if lengths:
        med = sorted(lengths)[len(lengths) // 2]
        for sid, n in zip(ids, lengths):
            if n < med * 0.25:
                errors.append(f"section {sid} is unusually short ({n} chars vs median {med})")
    return errors


def main(gen_path: str, ref_path: str) -> int:
    gen_html = Path(gen_path).read_text(encoding="utf-8")
    errors = compare_tables(tables_by_heading(Path(gen_path)), tables_by_heading(Path(ref_path)))
    errors += structure_checks(gen_html)
    print(f"svg charts: {gen_html.count('<svg')}")
    for e in errors:
        print("FAIL", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
