"""O1 — Cost attribution by team / namespace / workload.

Answers "who is spending how much?" for any date range, including the share of
cluster cost that is idle (paid for but allocated to nobody) — the number a plain
cloud bill never shows.
"""

from __future__ import annotations

import sqlite3

GROUPINGS = {"team": "team", "namespace": "namespace", "workload": "namespace || '/' || workload"}


def _where(start: str | None, end: str | None, include_idle: bool) -> tuple[str, list]:
    sql, params = " WHERE 1=1", []
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    if not include_idle:
        sql += " AND namespace != '__idle__'"
    return sql, params


def attribute(conn: sqlite3.Connection, by: str = "namespace", start: str | None = None,
              end: str | None = None, include_idle: bool = True) -> dict:
    if by not in GROUPINGS:
        raise ValueError(f"by must be one of {sorted(GROUPINGS)}")
    key = GROUPINGS[by]
    where, params = _where(start, end, include_idle)
    rows = conn.execute(
        f"SELECT {key} AS grp, SUM(total_cost) AS cost, SUM(cpu_cost) AS cpu_cost, "
        f"SUM(ram_cost) AS ram_cost, SUM(pv_cost + network_cost + other_cost) AS other_cost, "
        f"SUM(total_efficiency * total_cost) / NULLIF(SUM(CASE WHEN total_efficiency IS NOT NULL "
        f"THEN total_cost END), 0) AS efficiency, COUNT(DISTINCT namespace || '/' || workload) AS workloads "
        f"FROM cost_allocations{where} GROUP BY grp ORDER BY cost DESC",
        params,
    ).fetchall()
    total = sum(r["cost"] or 0 for r in rows) or 0.0
    idle = sum(r["cost"] for r in rows if r["grp"] in ("__idle__", "__idle__/__idle__"))
    items = [
        {
            "key": r["grp"],
            "cost": round(r["cost"] or 0, 6),
            "share_pct": round(100 * (r["cost"] or 0) / total, 2) if total else 0.0,
            "cpu_cost": round(r["cpu_cost"] or 0, 6),
            "ram_cost": round(r["ram_cost"] or 0, 6),
            "other_cost": round(r["other_cost"] or 0, 6),
            "efficiency_pct": round(r["efficiency"], 2) if r["efficiency"] is not None else None,
            "workloads": r["workloads"],
        }
        for r in rows
    ]
    return {
        "by": by, "start": start, "end": end, "currency": "USD",
        "total_cost": round(total, 6), "idle_cost": round(idle, 6),
        "idle_share_pct": round(100 * idle / total, 2) if total else 0.0,
        "items": items,
    }


def reconcile(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict:
    """Attribution accuracy check (AC-2 / NT-2): every grouping must sum to the same
    cluster total. Returns the max absolute difference — must be ~0."""
    totals = {by: attribute(conn, by, start, end)["total_cost"] for by in GROUPINGS}
    where, params = _where(start, end, True)
    raw = conn.execute(f"SELECT COALESCE(SUM(total_cost),0) FROM cost_allocations{where}", params).fetchone()[0]
    diff = max(abs(v - raw) for v in totals.values())
    return {"raw_total": round(raw, 6), "by_grouping": totals, "max_abs_diff": round(diff, 9),
            "reconciled": diff < 1e-6}
