"""Reader for `เตรียมข้อมูล คจ. EST <month> 69.xlsx` (sheet AP26): monthly AP / ACT(+forecast) / LY by scope."""
from __future__ import annotations

from pathlib import Path

import openpyxl

BLOCK_TITLES = {"core": "EAST CORE", "pmt": "EAST PMT", "combined": "EAST"}
METRICS = {"ebitda": "Ebitda (B)", "revenue": "Revenue (B)", "volume": "Vol (m3)", "price": "Price (B/m3)",
           "netcon": "Netcon (B/m3)"}
MONTH_COLS = range(2, 14)  # 0-based columns C..N = Jan..Dec


class ForecastLayoutError(Exception):
    pass


def read_forecast(path: Path) -> dict:
    """-> {scope: {metric: {"AP"|"ACT"|"LY": [12 monthly values]}}}"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb["AP26"].iter_rows(min_row=1, max_row=110, max_col=20, values_only=True))
    finally:
        wb.close()
    out: dict = {}
    starts = {}
    for i, r in enumerate(rows):
        title = str(r[0] or "").strip()
        for scope, t in BLOCK_TITLES.items():
            if title == t:
                starts[scope] = i
    if set(starts) != set(BLOCK_TITLES):
        raise ForecastLayoutError(f"{path.name}: blocks found {sorted(starts)} (expected {sorted(BLOCK_TITLES)})")
    for scope, s in starts.items():
        block: dict = {}
        metric = None
        for r in rows[s + 1:s + 24]:
            label = str(r[0] or "").strip()
            if label in METRICS.values():
                metric = next(k for k, v in METRICS.items() if v == label)
            elif label and not label.startswith("("):
                metric = None  # e.g. "TFC (B)" — its AP row must not overwrite the previous metric
            kind = str(r[1] or "").strip().upper()
            if metric and kind in ("AP", "ACT", "LY"):
                block.setdefault(metric, {})[kind] = [float(r[c] or 0) for c in MONTH_COLS]
        missing = [m for m in ("ebitda", "volume", "price", "netcon") if m not in block]
        if missing:
            raise ForecastLayoutError(f"{path.name}/{BLOCK_TITLES[scope]}: missing {missing}")
        out[scope] = block
    return out


def summary(fc: dict, scope: str, month: int) -> dict:
    """YTD actual, remaining forecast, full year, AP and LY totals for EBITDA and volume."""
    s = {}
    for metric in ("ebitda", "volume"):
        act, ap, ly = fc[scope][metric]["ACT"], fc[scope][metric]["AP"], fc[scope][metric]["LY"]
        s[metric] = {"ytd": sum(act[:month]), "rest": sum(act[month:]), "year": sum(act),
                     "ap": sum(ap), "ly": sum(ly)}
    return s
