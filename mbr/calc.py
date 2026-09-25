"""Scorecard, Waterfall (AP→Actual, to NPAT) and EBITDA Bridge (LM→current)."""
from __future__ import annotations

SCOPES = ("combined", "core", "pmt")


def assign_total(d: dict) -> float:
    # Aug'69 reviewed report: Assign = TVC Assign row + Labour OT + Sub-Contractor (row 195).
    return d["assign"] + d["labour"]


def scorecard_row(d: dict) -> dict:
    vol, prod = d["volume"], d["prod_volume"]
    per_sale = lambda x: x / vol if vol else 0.0
    per_prod = lambda x: x / prod if prod else 0.0
    return {
        "npat": d["npat"],
        "ebitda": d["ebitda"],
        "ebitda_m3": per_sale(d["ebitda"]),
        "volume": vol,
        "net_price_m3": per_sale(d["net_price"]),
        "netcon_m3": per_sale(d["netcon"]),
        "tvc_m3": per_sale(d["tvc"]),
        "rawmat_m3": per_prod(d["rawmat"]),
        "assign_m3": per_prod(assign_total(d)),
        "cartage_m3": per_prod(d["cartage"]),
        "tfc_m3": per_sale(d["tfc"]),
    }


def _rate(d: dict, x: float) -> float:
    return x / d["volume"] if d["volume"] else 0.0


def _operating_steps(a: dict, b: dict) -> list[tuple[str, float]]:
    """Steps from base `b` to actual `a` down to EBITDA. All rates on sales volume so residual is 0."""
    va = a["volume"]
    steps = [
        ("volume", (va - b["volume"]) * _rate(b, b["netcon"])),
        ("net_price", (_rate(a, a["net_price"]) - _rate(b, b["net_price"])) * va),
    ]
    for key, fn in (
        ("rawmat", lambda d: d["rawmat"]),
        ("assign", assign_total),
        ("cartage", lambda d: d["cartage"]),
        ("exbtrd", lambda d: d["exbtrd"]),
    ):
        steps.append((key, -(_rate(a, fn(a)) - _rate(b, fn(b))) * va))
    steps.append(("tfc", -(a["tfc"] - b["tfc"])))
    steps.append(("extraordinary", -(a["extraordinary"] - b["extraordinary"])))
    return steps


def waterfall_npat(actual: dict, plan: dict) -> dict:
    steps = _operating_steps(actual, plan) + [
        ("depreciation", -(actual["depreciation"] - plan["depreciation"])),
        ("finance", actual["finance"] - plan["finance"]),  # added directly, not sign-flipped
        ("tax", actual["tax"] - plan["tax"]),
    ]
    return {"start": plan["npat"], "end": actual["npat"], "steps": steps}


def ebitda_bridge(current: dict, last_month: dict) -> dict:
    return {"start": last_month["ebitda"], "end": current["ebitda"], "steps": _operating_steps(current, last_month)}


def residuals(actual: dict, base: dict) -> dict:
    """Residual (explained − actual change) at NetCon, EBITDA and NPAT levels."""
    wf = dict(waterfall_npat(actual, base)["steps"])
    netcon_expl = sum(wf[k] for k in ("volume", "net_price", "rawmat", "assign", "cartage", "exbtrd"))
    ebitda_expl = netcon_expl + wf["tfc"] + wf["extraordinary"]
    npat_expl = ebitda_expl + wf["depreciation"] + wf["finance"] + wf["tax"]
    return {
        "netcon": netcon_expl - (actual["netcon"] - base["netcon"]),
        "ebitda": ebitda_expl - (actual["ebitda"] - base["ebitda"]),
        "npat": npat_expl - (actual["npat"] - base["npat"]),
    }
