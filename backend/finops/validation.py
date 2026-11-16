"""Quality gates applied to every normalised allocation row before it is stored
(FR-1: validate schema, units, provenance before use; NT-1 billing-data complexity).

A row that fails is NOT silently dropped: it goes to `rejected_rows` with a reason,
and the ingest run is marked `partial`.
"""

import math
import re
from datetime import date

REQUIRED = ("date", "namespace", "workload", "total_cost")
NUMERIC = (
    "cpu_request", "cpu_usage", "ram_request_gb", "ram_usage_gb",
    "cpu_cost", "ram_cost", "pv_cost", "network_cost", "other_cost", "total_cost",
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A single workload costing more than this per day on a sandbox is treated as a
# unit error (e.g. bytes interpreted as GB) rather than real spend.
MAX_DAILY_COST_USD = 10_000.0
COST_SUM_TOLERANCE = 0.01  # 1 % — components must add up to total_cost


class RowError(ValueError):
    pass


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_row(row: dict) -> dict:
    """Return the row (with derived efficiency filled in) or raise RowError."""
    for k in REQUIRED:
        if row.get(k) in (None, ""):
            raise RowError(f"missing required field '{k}'")

    if not _DATE_RE.match(str(row["date"])):
        raise RowError(f"bad date format '{row['date']}'")
    try:
        date.fromisoformat(row["date"])
    except ValueError as exc:
        raise RowError(f"invalid date '{row['date']}'") from exc

    for k in NUMERIC:
        v = row.get(k)
        if v is None:
            continue
        if not _is_num(v):
            raise RowError(f"field '{k}' is not a finite number: {v!r}")
        if v < 0:
            raise RowError(f"negative value in '{k}': {v}")

    if row["total_cost"] > MAX_DAILY_COST_USD:
        raise RowError(f"total_cost {row['total_cost']} exceeds sanity limit (unit error?)")

    parts = sum(row.get(k) or 0.0 for k in ("cpu_cost", "ram_cost", "pv_cost", "network_cost", "other_cost"))
    if parts > 0 and abs(parts - row["total_cost"]) > max(COST_SUM_TOLERANCE * row["total_cost"], 1e-6):
        raise RowError(f"cost components ({parts:.6f}) do not add up to total_cost ({row['total_cost']:.6f})")

    out = dict(row)
    out["cpu_efficiency"] = _eff(row.get("cpu_usage"), row.get("cpu_request"))
    out["ram_efficiency"] = _eff(row.get("ram_usage_gb"), row.get("ram_request_gb"))
    if out.get("total_efficiency") is None:
        out["total_efficiency"] = _weighted_eff(out)
    return out


def _eff(used, requested):
    if used is None or requested in (None, 0):
        return None
    return round(min(used / requested, 10.0) * 100.0, 4)


def _weighted_eff(r: dict):
    """Cost-weighted efficiency, same idea as OpenCost's totalEfficiency."""
    cpu_c, ram_c = r.get("cpu_cost") or 0.0, r.get("ram_cost") or 0.0
    ce, re_ = r.get("cpu_efficiency"), r.get("ram_efficiency")
    if cpu_c + ram_c == 0:
        return None
    num = (ce or 0.0) * cpu_c + (re_ or 0.0) * ram_c
    return round(num / (cpu_c + ram_c), 4)
