"""Reader for `MM.26 TVC by Plant by Month.xlsx` — scope-level OUTPUT/INPUT rows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Scope aggregate columns (1-based). Plan col 16/21 belong to CNT&NE — never use them.
SCOPE_COLS = {
    "A": {"core": 16, "pmt": 21, "combined": 26},
    "P": {"core": 35, "pmt": 36, "combined": 25},
}
SCOPE_HEADERS = {"core": ("EST-Core", "ESTCore"), "pmt": ("EST-PMT", "ESTPMT"), "combined": ("EST-Core&Pmt",)}

# key -> (Actual row, label prefix in col C). Plan row = Actual row - 4.
ROWS = {
    "prod_volume": (96, "Production Volume"),
    "cement_kg": (99, "Cement Usage (kg/m3)"),
    "cement_price": (100, "Cement Price (THB/ton)"),
    "pfa_kg": (103, "PFA Usage (kg/m3)"),
    "pfa_price": (104, "PFA Price (THB/ton)"),
    "rock_kg": (108, "Rock Usage (kg/m3)"),
    "rock_price": (109, "Rock Price (THB/ton)"),
    "sand_kg": (113, "Sand Usage (kg/m3)"),
    "sand_price": (114, "Sand Price (THB/ton)"),
    "admix_l": (118, "Additive Usage (Litre/m3)"),
    "admix_price": (119, "Additive Price (THB/Litre)"),
    "volume": (138, "Sales Volume (m3)"),
    "lp": (139, "LP"),
    "discount": (140, "DISCOUNT"),
    "net_price": (141, "NET PRICE"),
    "rm_cement": (142, "Cement"),
    "rm_pfa": (143, "Fly Ash"),
    "rm_rock": (144, "Rock & Graval"),
    "rm_sand": (145, "Sand"),
    "rm_admix_normal": (146, "Admixture  Normal"),
    "rm_admix_special": (147, "Admixture  Special"),
    "rm_other": (148, "Other r/m"),
    "rm_internal": (150, "Internal Use"),
    "rawmat": (152, "Raw Materials Cost"),
    "direct_labour": (153, "DIRECT LABOUR"),
    "c_oil_lube": (156, "OTHER MATERIAL SUPPLIES"),
    "c_welfare": (159, "EMPLOYEE' WELFARE"),
    "c_insurance": (160, "INSURANCE & COMPULSORY"),
    "c_communication": (161, "COMMUNICATION"),
    "c_tax_license": (162, "TAX LICENSES & FEE"),
    "c_misc": (163, "MISCELLANEOUS"),
    "cartage_sub": (164, "Cartage รถผู้รับเหมา"),
    "c_truck_revenue": (165, "รายได้ค่ารถบรรทุกคอนกรีตรับจ้า"),
    "c_mixer_rm": (166, "MIXER REPAIR & MAINTENANCE"),
    "c_tyre": (169, "MIXER TYRE"),
    "c_police": (170, "ค่าตำรวจ"),
    "c_truck_park": (171, "Allocation Truck Park"),
    "cartage": (172, "Cartgage Costs"),
    "a_fuel_oil": (173, "FUEL OIL"),
    "a_power": (174, "POWER"),
    "a_tools": (175, "TOOLS AND EQUIPMENT"),
    "a_stores": (176, "STORES & EQUIPMENT"),
    "water": (177, "ค่าน้ำ"),
    "a_freight": (178, "FREIGHT & HANDLING"),
    "a_repair": (179, "REPAIR & MAINTENANCE"),
    "a_other_mat": (180, "OTHER MATERIAL SUPPLIES"),
    "a_transport": (181, "TRANSPORT & TRAVEL"),
    "a_misc": (182, "MISCELLANEOUS"),
    "a_overhead": (183, "Overhead Cost"),
    "a_waste": (184, "Waste Concrete Clearing"),
    "a_spoiled": (185, "Spoiled"),
    "a_crane": (186, "รถเครน+รถขนกากปูน"),
    "a_fel": (187, "FEL Expense"),
    "assign": (192, "Assign Costs"),
    "labour_ot": (193, "Labour Cost  -  OT"),
    "sub_contractor": (194, "Sub-Contractor"),
    "labour": (195, "Labour Cost"),
    "exbtrd": (199, "Exbatch&Trading Goods"),
    "tvc": (200, "TVC"),
    "netcon": (201, "NET CONTRIBUTION"),
    "tfc_fo": (202, "FO"),
    "tfc_admin": (203, "Admin"),
    "tfc_mkt": (204, "MKT"),
    "tfc": (205, "TFC"),
    "extraordinary": (206, "EXTRAORDINARY"),
    "ebitda": (207, "EBITDA"),
    "depreciation": (212, "Depreciation"),
    "finance": (250, "FINANCE COSTS"),
    "tax": (254, "INCOME TAX EXPENSE"),
    "npat": (255, "PROFIT (LOSS) FOR THE PERIOD"),
}
PLAN_ROW_OFFSET = -4
MAX_ROW = 260
MAX_COL = 40


class TVCLayoutError(Exception):
    """File layout differs from the confirmed Aug'69 layout — stop and ask Don."""


@dataclass
class ScopeData:
    month: int
    kind: str  # "A" actual / "P" plan
    values: dict[str, dict[str, float]]  # scope -> key -> value
    source: str

    def __getitem__(self, scope: str) -> dict[str, float]:
        return self.values[scope]


def _norm(s) -> str:
    return " ".join(str(s or "").split())


_SHEET_CACHE: dict[tuple[str, str], list[tuple]] = {}


def _sheet_rows(path: Path, sheet: str) -> list[tuple]:
    """All rows 1..MAX_ROW (every column) of one sheet; cached so each sheet is read once per run."""
    key = (str(path), sheet)
    if key not in _SHEET_CACHE:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            _SHEET_CACHE[key] = list(wb[sheet].iter_rows(min_row=1, max_row=MAX_ROW, values_only=True))
        finally:
            wb.close()
    return _SHEET_CACHE[key]


def read_scope(path: Path, month: int, kind: str) -> ScopeData:
    sheet = f"{MONTH_ABBR[month - 1]}{kind}"
    rows = _sheet_rows(path, sheet)

    offset = 0 if kind == "A" else PLAN_ROW_OFFSET
    cols = SCOPE_COLS[kind]
    header_row = rows[137 + offset - 1]
    for scope, col in cols.items():
        if _norm(header_row[col - 1]) not in SCOPE_HEADERS[scope]:
            raise TVCLayoutError(
                f"{path.name}/{sheet}: col {col} header is {header_row[col - 1]!r}, expected {SCOPE_HEADERS[scope]}"
            )

    values: dict[str, dict[str, float]] = {s: {} for s in cols}
    for key, (arow, label) in ROWS.items():
        r = arow + offset
        candidates = [_norm(rows[r - 1][2]), _norm(rows[r - 1][1])]
        if not any(c.startswith(_norm(label)) for c in candidates):
            raise TVCLayoutError(f"{path.name}/{sheet} row {r}: labels {candidates!r}, expected {label!r}")
        for scope, col in cols.items():
            v = rows[r - 1][col - 1]
            values[scope][key] = float(v) if isinstance(v, (int, float)) else 0.0
    for d in values.values():
        # Don 2026-09-24: show water as its own Assign line, not inside STORES & EQUIPMENT (Assign total unchanged).
        d["a_stores_ex_water"] = d["a_stores"] - d["water"]
    return ScopeData(month=month, kind=kind, values=values, source=f"{path.name}/{sheet}")


# Plant-level columns. Actual sheets: row 8 AAO, 9 AO, 10 Core/PMT, 11 K-code, 14 Thai name (confirmed 10 Sep).
# Plan sheets carry the K-code on row 8 and no AO filter row, so plan plants are looked up by code only.
AAO_TO_AREA = {"EST1/1": "E1.1", "EST1/2": "E1.2", "EST2/1": "E2"}
PLANT_KEYS = ("prod_volume", "volume", "net_price", "rawmat", "cartage", "assign", "labour", "tfc", "ebitda", "npat")


@dataclass
class Plant:
    code: str
    name: str
    area: str       # E1.1 / E1.2 / E2 / EST
    kind: str       # Core / PMT / TDG-กลาง
    values: dict[str, float]


def _plant_values(rows: list[tuple], col: int, offset: int) -> dict[str, float]:
    out = {}
    for key in PLANT_KEYS:
        v = rows[ROWS[key][0] + offset - 1][col]
        out[key] = float(v) if isinstance(v, (int, float)) else 0.0
    return out


def read_plants_actual(path: Path, month: int, strict: bool = True) -> dict[str, Plant]:
    sheet = f"{MONTH_ABBR[month - 1]}A"
    rows = _sheet_rows(path, sheet)
    plants: dict[str, Plant] = {}
    for c, ao in enumerate(rows[8]):
        if "EST" not in str(ao or ""):
            continue
        code = _norm(rows[10][c])
        aao = _norm(rows[7][c])
        plants[code] = Plant(
            code=code,
            name=_norm(rows[13][c]),
            area=AAO_TO_AREA.get(aao, aao),
            kind=_norm(rows[9][c]),
            values=_plant_values(rows, c, 0),
        )
    total = sum(p.values["volume"] for p in plants.values())
    scope_total = read_scope(path, month, "A")["combined"]["volume"]
    if strict and abs(total - scope_total) > 0.01:
        raise TVCLayoutError(f"{path.name}/{sheet}: EST plant volumes sum to {total}, scope total is {scope_total}")
    return plants


def read_plants_plan(path: Path, month: int, codes: set[str]) -> dict[str, dict[str, float]]:
    rows = _sheet_rows(path, f"{MONTH_ABBR[month - 1]}P")
    out = {}
    for c, code in enumerate(rows[7]):
        code = _norm(code)
        if code in codes and code not in out:
            out[code] = _plant_values(rows, c, PLAN_ROW_OFFSET)
    return out
