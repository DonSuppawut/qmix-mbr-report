"""Plant-level dataset used by Sections 5.4, 6.6, 7 and 8."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import calc
from .tvc import Plant, read_plants_actual, read_plants_plan

ROOT = Path(__file__).resolve().parents[1]


def tvc_file(account: Path, year: int, month: int) -> Path:
    return account / f"{month:02d}.{year % 100:02d} TVC by Plant by Month.xlsx"


def load_config() -> dict:
    return json.loads((ROOT / "data" / "config" / "plants.json").read_text(encoding="utf-8"))


def hidden_codes(cfg: dict) -> set[str]:
    h = cfg["hidden_in_plant_sections"]
    return set(h["insource"]) | set(h["insource_other"])


@dataclass
class PlantRow:
    code: str
    name: str
    area: str
    kind: str
    cur: dict
    lm: dict | None
    ap: dict | None
    ytd_ebitda: float
    ytd_volume: float

    @property
    def label(self) -> str:
        return f"{self.code} {self.name}".strip()


def load_plants(account: Path, year: int, month: int, known_codes: set[str]) -> dict[str, PlantRow]:
    """known_codes: plants present in east_plants/P&L (the '48 plants' universe)."""
    cur_file = tvc_file(account, year, month)
    cur = read_plants_actual(cur_file, month)
    lm = read_plants_actual(cur_file, month - 1) if month > 1 else {}
    ap = read_plants_plan(cur_file, month, set(cur))

    # YTD uses the restated months inside the current TVC file (Don 2026-09-24), not each month's own file —
    # later files restate earlier months, e.g. K461 Jan 154,103 (Jan file) vs 165,424 (Aug file).
    ytd_e: dict[str, float] = {}
    ytd_v: dict[str, float] = {}
    for m in range(1, month + 1):
        for code, p in read_plants_actual(cur_file, m).items():
            ytd_e[code] = ytd_e.get(code, 0.0) + p.values["ebitda"]
            ytd_v[code] = ytd_v.get(code, 0.0) + p.values["volume"]

    out = {}
    for code, p in cur.items():
        if code not in known_codes:
            continue
        out[code] = PlantRow(
            code=code, name=p.name, area=p.area, kind=p.kind, cur=p.values,
            lm=lm[code].values if code in lm else None, ap=ap.get(code),
            ytd_ebitda=ytd_e.get(code, 0.0), ytd_volume=ytd_v.get(code, 0.0),
        )
    return out


def unit_cost(values: dict, key: str) -> float:
    """Per production m³ (Assign includes OT + Sub-contract, as in the scope tables)."""
    amount = calc.assign_total(values) if key == "assign" else values[key]
    return amount / values["prod_volume"] if values["prod_volume"] else 0.0
