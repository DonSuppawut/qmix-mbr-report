"""Build one MBR report per AAO area (E1.1 / E1.2 / E2).

Usage: python build_area_report.py 2026-08 [--area E1.1] [--no-pdf] [--refresh-sheets]

Same sections and rules as the EST report, restricted to one area:
- P&L (Sections 1, 2, 4, 5, 6) from the TVC file's own AAO subtotal columns (EST1/1, EST1/1Core, EST1/1Prmt …)
- Sales (Section 3) from the Net Con rows whose AAO column is the area
- Plant tables (5.4, 6.6, 7, 8) limited to the area's plants
Not included: Cartage by vendor (6.4/6.5) and Forecast — their source files exist only at EST level.
Plus Section 9 TU of the trucks registered to each plant (MCP snapshots) and Section 10 strength charts/tables
from each plant's Google Sheet (downloaded once per report month; --refresh-sheets re-downloads) — mbr/report_ops.py.
Narrative is optional: data/narrative/<ym>_<area>.json (the EST narrative is never reused — it talks about EST totals).
"""
from __future__ import annotations

import dataclasses
import sys

from build_report import ACCOUNT, DATA, OUT, _json, load, load_netcon
from mbr import calc, netcon, plants, report, report_ops, report_plants, report_sales, report_summary, svg
from mbr.fmt import file_stem, th_month_long
from mbr.page import build_page
from mbr.pdf_out import export_pdf
from mbr.report import MonthData
from mbr.tvc import (AAO_TO_AREA, MONTH_ABBR, PLAN_ROW_OFFSET, ROWS, _norm, _sheet_rows, read_area_scope,
                     read_plants_actual)
from mbr.xlsx_out import build_xlsx

AREAS = tuple(AAO_TO_AREA.values())
CHECK_KEYS = ("volume", "prod_volume", "net_price", "rawmat", "cartage", "assign", "labour", "tfc", "ebitda", "npat")


def area_month(md: MonthData, area: str) -> MonthData:
    tvc = plants.tvc_file(ACCOUNT, md.year, md.month)
    ym = f"{md.year}-{md.month:02d}"
    area_plants = {c: p for c, p in md.plants.items() if p.area == area}
    adj = dict(md.adjustments)
    if "cartage_plant" in adj:
        adj["cartage_plant"] = [a for a in adj["cartage_plant"] if a["plant"] in area_plants]
    return dataclasses.replace(
        md, area=area,
        actual=read_area_scope(tvc, md.month, "A", area),
        plan=read_area_scope(tvc, md.month, "P", area),
        last=read_area_scope(tvc, md.month - 1, "A", area),
        plants=area_plants,
        narrative=_json(DATA / "narrative" / f"{ym}_{area}.json", {}),
        adjustments=adj,
    )


def validate(md: MonthData, areas: dict[str, MonthData], nc_cur: list, nc_lm: list) -> list[str]:
    """Stop-the-line checks — any failure means the area columns do not mean what we think."""
    errors = []
    tvc = plants.tvc_file(ACCOUNT, md.year, md.month)
    for amd in areas.values():
        for sd, what in ((amd.actual, "Actual"), (amd.plan, "AP"), (amd.last, "LM")):
            for k in CHECK_KEYS:
                gap = sd["core"][k] + sd["pmt"][k] - sd["combined"][k]
                if abs(gap) > 1:
                    errors.append(f"{amd.area} {what} {k}: Core + PMT - รวม = {gap:,.2f}")
        for label, base in (("Waterfall AP", amd.plan), ("Bridge LM", amd.last)):
            for scope in calc.SCOPES:
                res = calc.residuals(amd.actual[scope], base[scope])
                if any(abs(v) > 1 for v in res.values()):
                    errors.append(f"{amd.area} {label} {scope}: residual {res}")

    # Plant columns of each area must add up to the area column; areas + non-area plants (TDG) = EST.
    for month, attr in ((md.month, "actual"), (md.month - 1, "last")):
        all_plants = read_plants_actual(tvc, month)
        est = getattr(md, attr)["combined"]
        for k in CHECK_KEYS:
            outside = sum(p.values[k] for p in all_plants.values() if p.area not in AREAS)
            total = outside
            for area in AREAS:
                area_col = read_area_scope(tvc, month, "A", area)["combined"][k]
                plant_sum = sum(p.values[k] for p in all_plants.values() if p.area == area)
                if abs(area_col - plant_sum) > 1:
                    errors.append(f"เดือน {month} {area} {k}: คอลัมน์เขต {area_col:,.2f} != ผลรวมโรงงาน {plant_sum:,.2f}")
                total += area_col
            if abs(total - est[k]) > 1:
                errors.append(f"เดือน {month} {k}: รวม 3 เขต + โรงนอกเขต {total:,.2f} != EST {est[k]:,.2f}")

    # Plan: 3 areas (Core + PMT) + plan plant columns outside the areas (TDG) = EST plan.
    prow = _sheet_rows(tvc, f"{MONTH_ABBR[md.month - 1]}P")
    est_p = md.plan["combined"]
    for k in CHECK_KEYS:
        r = ROWS[k][0] + PLAN_ROW_OFFSET - 1
        outside = sum(float(prow[r][c]) for c in range(len(prow[3]))
                      if _norm(prow[3][c]).startswith("EST") and _norm(prow[4][c]) not in AAO_TO_AREA
                      and _norm(prow[7][c]).startswith("K")  # plant columns only, not the EST-Core/PMT totals
                      and isinstance(prow[r][c], (int, float)))
        total = outside + sum(areas[a].plan["combined"][k] for a in AREAS)
        if abs(total - est_p[k]) > 1:
            errors.append(f"AP {k}: รวม 3 เขต + โรงนอกเขต {total:,.2f} != EST {est_p[k]:,.2f}")

    # Net Con AAO must agree with the TVC area of the plant.
    plant_area = {c: p.area for c, p in read_plants_actual(tvc, md.month).items()}
    plant_area.update({c: p.area for c, p in read_plants_actual(tvc, md.month - 1).items()})
    for rows, when in ((nc_cur, "เดือนนี้"), (nc_lm, "LM")):
        for r in rows:
            area = plant_area.get(r.plant)
            if area in AREAS and r.aao not in netcon.AREA_AAO[area]:
                errors.append(f"Net Con {when}: โรง {r.plant} AAO={r.aao} แต่ TVC จัดอยู่เขต {area}")
                break
    return errors


def build_sections(md: MonthData, nc_cur: list, nc_lm: list, fleet: dict, quality: dict) -> list[str]:
    return [
        report.section1(md),
        report.section2(md),
        report_sales.section3(md, netcon.area_rows(nc_cur, md.area), netcon.area_rows(nc_lm, md.area)),
        report.section4(md),
        report.section5(md, report_plants.section5_plants(md)),
        report.section6(md, report_plants.section6_plants(md)),
        report_plants.section7(md),
        report_plants.section8(md),
        report_ops.section_tu(md, fleet, 9),
        report_ops.section_quality(md, quality, 10),
        report_summary.section10(md, 11),
    ]


def main(ym: str, areas: tuple[str, ...] = AREAS, pdf: bool = True, refresh_sheets: bool = False) -> None:
    year, month = map(int, ym.split("-"))
    md = load(year, month)
    nc_cur, nc_lm = load_netcon(md)
    fleet = report_ops.load_fleet(md, plants.load_config()["tu"], refresh=refresh_sheets)
    quality = report_ops.load_quality(md, refresh=refresh_sheets)
    area_mds = {a: area_month(md, a) for a in AREAS}
    errors = validate(md, area_mds, nc_cur, nc_lm)
    if errors:
        print("VALIDATION FAILED — ห้ามส่งรายงาน แจ้ง Don:")
        for e in errors:
            print("  -", e)
        raise SystemExit(1)
    print("validate: OK (Core+PMT = รวมเขต, residual = 0, คอลัมน์เขต = ผลรวมโรงงาน, 3 เขต + นอกเขต = EST, AAO ใน Net Con ตรง TVC)")

    OUT.mkdir(exist_ok=True)
    for area in areas:
        amd = area_mds[area]
        if not amd.narrative:
            print(f"WARNING: no narrative file data/narrative/{ym}_{area}.json — watch/strategy boxes omitted")
        svg.CHART_LOG.clear()
        html = build_page(year, month, build_sections(amd, nc_cur, nc_lm, fleet, quality), area=area)
        stem = f"{file_stem(year, month)}_{area}"
        path = OUT / f"{stem}.html"
        path.write_text(html, encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
        title = f"MBR EST เขต {area} — {th_month_long(year, month)}"
        info = build_xlsx(html, svg.CHART_LOG, OUT / f"{stem}.xlsx", title)
        print(f"wrote {OUT / f'{stem}.xlsx'} ({info['sheets']} sheets, {info['charts']} native charts)")
        if pdf:
            pages = export_pdf(path, OUT / f"{stem}.pdf", title)
            print(f"wrote {OUT / f'{stem}.pdf'} ({pages} pages)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--area"), None)
    if only and only not in AREAS:
        raise SystemExit(f"--area must be one of {AREAS}")
    ym_args = [a for a in args if a != only]
    main(ym_args[0] if ym_args else "2026-08", (only,) if only else AREAS, pdf="--no-pdf" not in sys.argv,
         refresh_sheets="--refresh-sheets" in sys.argv)
