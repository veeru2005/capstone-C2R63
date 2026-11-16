"""O2 — Reference: spend visualisation and trend analysis.

This is the *reference* every O3 contribution is compared against. It implements
what a good dashboard alone gives you:
  * daily spend series per team / namespace / workload
  * 7-day moving average, week-over-week change, linear trend (slope per day)
  * top movers (biggest week-over-week increase)
  * two reference projection methods (used as KPI-2 baseline):
        R1  moving-average     — next day = mean of last 7 days
        R2  linear-trend (OLS) — straight line fitted to the last 28 days
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from .attribution import GROUPINGS


def daily_series(conn: sqlite3.Connection, by: str = "namespace", start: str | None = None,
                 end: str | None = None, include_idle: bool = False) -> pd.DataFrame:
    """Wide frame: index = date, columns = group keys, values = daily cost (0 when absent)."""
    key = GROUPINGS[by]
    sql = f"SELECT date, {key} AS grp, SUM(total_cost) AS cost FROM cost_allocations WHERE 1=1"
    params: list = []
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    if not include_idle:
        sql += " AND namespace != '__idle__'"
    sql += " GROUP BY date, grp"
    df = pd.DataFrame([dict(r) for r in conn.execute(sql, params).fetchall()])
    if df.empty:
        return pd.DataFrame()
    wide = df.pivot(index="date", columns="grp", values="cost").sort_index()
    # Fill missing calendar days so gaps show as 0 rather than being silently skipped
    idx = pd.date_range(wide.index.min(), wide.index.max(), freq="D").strftime("%Y-%m-%d")
    return wide.reindex(idx).fillna(0.0)


def linear_slope(y: np.ndarray) -> float:
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def trend_summary(conn: sqlite3.Connection, by: str = "namespace", start: str | None = None,
                  end: str | None = None) -> dict:
    wide = daily_series(conn, by, start, end)
    if wide.empty:
        return {"by": by, "series": [], "groups": [], "total": {}}

    total = wide.sum(axis=1)
    ma7 = total.rolling(7, min_periods=1).mean()
    series = [
        {"date": d, "total": round(float(total[d]), 6), "ma7": round(float(ma7[d]), 6),
         **{g: round(float(wide.at[d, g]), 6) for g in wide.columns}}
        for d in wide.index
    ]

    groups = []
    for g in wide.columns:
        y = wide[g].to_numpy()
        last7, prev7 = y[-7:].sum(), y[-14:-7].sum() if len(y) >= 14 else np.nan
        wow = (last7 - prev7) / prev7 * 100 if prev7 and not np.isnan(prev7) else None
        groups.append({
            "key": g,
            "total_cost": round(float(y.sum()), 6),
            "avg_daily": round(float(y.mean()), 6),
            "last_7d": round(float(last7), 6),
            "wow_change_pct": round(float(wow), 2) if wow is not None else None,
            "slope_per_day": round(linear_slope(y[-28:]), 8),
            "projected_30d": round(float(max(project_linear(y, 30).sum(), 0)), 6),
        })
    groups.sort(key=lambda r: r["total_cost"], reverse=True)

    y = total.to_numpy()
    last7, prev7 = y[-7:].sum(), (y[-14:-7].sum() if len(y) >= 14 else None)
    return {
        "by": by,
        "start": wide.index[0], "end": wide.index[-1], "days": len(wide),
        "currency": "USD",
        "total": {
            "total_cost": round(float(y.sum()), 6),
            "avg_daily": round(float(y.mean()), 6),
            "last_7d": round(float(last7), 6),
            "wow_change_pct": round((last7 - prev7) / prev7 * 100, 2) if prev7 else None,
            "slope_per_day": round(linear_slope(y[-28:]), 8),
            "run_rate_monthly": round(float(y[-7:].mean() * 30), 6),
        },
        "top_movers": sorted([g for g in groups if g["wow_change_pct"] is not None],
                             key=lambda r: r["wow_change_pct"], reverse=True)[:5],
        "groups": groups,
        "series": series,
    }


# ── Reference projection methods (O2 baseline for KPI-2) ────────────────────

def project_moving_average(history: np.ndarray, horizon: int, window: int = 7) -> np.ndarray:
    level = float(np.mean(history[-window:])) if len(history) else 0.0
    return np.full(horizon, level)


def project_linear(history: np.ndarray, horizon: int, window: int = 28) -> np.ndarray:
    h = history[-window:]
    if len(h) < 2:
        return np.full(horizon, float(h[-1]) if len(h) else 0.0)
    x = np.arange(len(h), dtype=float)
    a, b = np.polyfit(x, h, 1)
    fut = np.arange(len(h), len(h) + horizon, dtype=float)
    return np.maximum(a * fut + b, 0.0)


REFERENCE_METHODS = {"R1-moving-average": project_moving_average, "R2-linear-trend": project_linear}
