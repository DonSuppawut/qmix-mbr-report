"""Run all Phase-1 data validations for one month.  Usage: python validate_month.py 2026-08"""
from __future__ import annotations

import sys
from pathlib import Path

from mbr import validate
from mbr.tvc import MONTH_ABBR, read_scope

ACCOUNT = Path(r"D:\QMix\Account")
ROOT = Path(__file__).resolve().parent


def tvc_path(month: int) -> Path:
    return ACCOUNT / f"{month:02d}.26 TVC by Plant by Month.xlsx"


def main(ym: str) -> int:
    year, month = map(int, ym.split("-"))
    if year != 2026:
        raise SystemExit("Only 2026 file naming is wired up so far")
    tvc = tvc_path(month)
    actual = read_scope(tvc, month, "A")
    plan = read_scope(tvc, month, "P")
    last = read_scope(tvc, month - 1, "A")
    jul = read_scope(tvc, 7, "A")

    checks = []
    checks += validate.golden_jul69(jul)
    checks += validate.reconcile_cost_report(actual, ACCOUNT / f"รายงานต้นทุน {MONTH_ABBR[month - 1]}'26 All Area.xlsx")
    snap = ROOT / "data" / "snapshots"
    pnl = snap / ym / "east_plant_pnl_monthly_actual.json"
    if pnl.exists():
        checks += validate.plant_sum_vs_scope(actual, pnl, snap / "east_plants.json")
    else:
        checks.append((False, "plant sum vs scope", f"missing snapshot {pnl}"))
    checks += validate.residual_checks(actual, plan, "Waterfall AP→Act")
    checks += validate.residual_checks(actual, last, "Bridge LM→Act")

    for ok, name, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:55} {detail}")
    fails = sum(not ok for ok, *_ in checks)
    print(f"\n{len(checks) - fails}/{len(checks)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "2026-08"))
