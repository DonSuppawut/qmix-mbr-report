"""Build the monthly MBR EST report.  Usage: python build_report.py 2026-08"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mbr import netcon, plants, report, report_cartage, report_plants, report_sales, report_summary, svg
from mbr.fmt import TH_MONTH_ABBR, file_stem, th_month_long
from mbr.forecast import read_forecast
from mbr.page import build_page
from mbr.pdf_out import export_pdf
from mbr.xlsx_out import build_xlsx
from mbr.tvc import read_scope

ACCOUNT = Path(r"D:\QMix\Account")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
DATA = ROOT / "data"


def _json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load(year: int, month: int) -> report.MonthData:
    if month == 1:
        raise SystemExit("January needs the previous year's TVC file for LM — not wired up yet")
    ym = f"{year}-{month:02d}"
    tvc = plants.tvc_file(ACCOUNT, year, month)
    narrative = _json(DATA / "narrative" / f"{ym}.json", {})
    if not narrative:
        print(f"WARNING: no narrative file for {ym} — watch/strategy boxes will be omitted")
    cfg = plants.load_config()
    known = {r["plant_code"] for r in _json(DATA / "snapshots" / "east_plants.json", {"rows": []})["rows"]}
    return report.MonthData(
        year=year, month=month,
        actual=read_scope(tvc, month, "A"), plan=read_scope(tvc, month, "P"), last=read_scope(tvc, month - 1, "A"),
        narrative=narrative,
        plants=plants.load_plants(ACCOUNT, year, month, known),
        hidden_plants=plants.hidden_codes(cfg),
        trading_plants=set(cfg["trading_goods"]),
        adjustments=_json(DATA / "adjustments" / f"{ym}.json", {}),
    )


def build_sections(md: report.MonthData) -> list[str]:
    fc_path = forecast_path(md.year, md.month)
    return [
        report.section1(md),
        report.section2(md),
        report_sales.section3(md, *load_netcon(md)),
        report.section4(md),
        report.section5(md, report_plants.section5_plants(md)),
        report.section6(md, report_cartage.section6_extra(
            md, report_cartage.load_cartage_months(ACCOUNT, plants.tvc_file(ACCOUNT, md.year, md.month),
                                                   md.year, md.month)) + report_plants.section6_plants(md)),
        report_plants.section7(md),
        report_plants.section8(md),
        report_summary.section9(md, read_forecast(fc_path), fc_path.name),
        report_summary.section10(md),
    ]


def load_netcon(md: report.MonthData):
    ly, lm = md.lm_year_month
    return (netcon.read_netcon(netcon.netcon_path(ACCOUNT, md.year, md.month), md.year, md.month),
            netcon.read_netcon(netcon.netcon_path(ACCOUNT, ly, lm), ly, lm))


def forecast_path(year: int, month: int) -> Path:
    inputs = _json(DATA / "inputs" / f"{year}-{month:02d}.json", {})
    if inputs.get("forecast_file"):
        return Path(inputs["forecast_file"])
    return ACCOUNT / f"เตรียมข้อมูล คจ. EST {TH_MONTH_ABBR[month - 1]} {(year + 543) % 100:02d}.xlsx"


def main(ym: str, pdf: bool = True) -> Path:
    year, month = map(int, ym.split("-"))
    md = load(year, month)
    svg.CHART_LOG.clear()
    html = build_page(year, month, build_sections(md))
    OUT.mkdir(exist_ok=True)
    stem = file_stem(year, month)
    path = OUT / f"{stem}.html"
    path.write_text(html, encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")

    title = f"MBR EST — {th_month_long(year, month)}"
    info = build_xlsx(html, svg.CHART_LOG, OUT / f"{stem}.xlsx", title)
    print(f"wrote {OUT / f'{stem}.xlsx'} ({info['sheets']} sheets, {info['charts']} native charts)")
    if pdf:
        pages = export_pdf(path, OUT / f"{stem}.pdf", title)
        print(f"wrote {OUT / f'{stem}.pdf'} ({pages} pages)")
    return path


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "2026-08", pdf="--no-pdf" not in sys.argv)
