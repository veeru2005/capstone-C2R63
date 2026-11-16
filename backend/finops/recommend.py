"""O4 — Savings recommendations: IDLE, RIGHT-SIZE, COMMITMENT.

Safety rules (AC-2 'recommendations must be safe/actionable', NT-3):
  * system namespaces (kube-system, monitoring, opencost) are never recommended
    for deletion — at most RIGHT-SIZE with a warning;
  * right-size targets use p95 usage x 1.3 headroom, never the mean, and never
    below a 10m CPU / 32 MiB floor;
  * a recommendation needs >= 7 days of data, otherwise confidence = low.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np

from . import config

CPU_FLOOR, RAM_FLOOR_GB = 0.01, 32 / 1024


def generate(conn: sqlite3.Connection, lookback_days: int = 30) -> list[dict]:
    last = conn.execute("SELECT MAX(date) FROM cost_allocations").fetchone()[0]
    if not last:
        return []
    rows = conn.execute(
        "SELECT namespace, workload, date, cpu_request, cpu_usage, ram_request_gb, ram_usage_gb, "
        "cpu_cost, ram_cost, total_cost, total_efficiency FROM cost_allocations "
        "WHERE namespace != '__idle__' AND date > date(?, ?) ORDER BY date",
        (last, f"-{lookback_days} days"),
    ).fetchall()
    groups: dict[tuple[str, str], list] = {}
    for r in rows:
        groups.setdefault((r["namespace"], r["workload"]), []).append(r)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    recs = []
    for (ns, wl), rs in groups.items():
        cost = np.array([r["total_cost"] for r in rs])
        monthly = float(cost.mean() * 30)
        eff = np.array([r["total_efficiency"] or 0 for r in rs])
        cpu_req = np.array([r["cpu_request"] or 0 for r in rs])
        cpu_use = np.array([r["cpu_usage"] or 0 for r in rs])
        ram_req = np.array([r["ram_request_gb"] or 0 for r in rs])
        ram_use = np.array([r["ram_usage_gb"] or 0 for r in rs])
        med_eff = float(np.median(eff))
        conf = "high" if len(rs) >= 14 else ("medium" if len(rs) >= 7 else "low")
        system = ns in config.SYSTEM_NAMESPACES
        cpu_price_day = 24 * config.CPU_PRICE_PER_CORE_HOUR
        ram_price_day = 24 * config.RAM_PRICE_PER_GB_HOUR

        def rightsize():
            tgt_cpu = max(float(np.percentile(cpu_use, 95)) * config.RIGHTSIZE_HEADROOM, CPU_FLOOR)
            tgt_ram = max(float(np.percentile(ram_use, 95)) * config.RIGHTSIZE_HEADROOM, RAM_FLOOR_GB)
            cur_cpu, cur_ram = float(np.median(cpu_req)), float(np.median(ram_req))
            save = (max(cur_cpu - tgt_cpu, 0) * cpu_price_day + max(cur_ram - tgt_ram, 0) * ram_price_day) * 30
            return tgt_cpu, tgt_ram, cur_cpu, cur_ram, min(save, monthly)

        if med_eff < config.IDLE_EFFICIENCY_PCT and not system:
            recs.append(_rec(ns, wl, "IDLE",
                             f"Median efficiency {med_eff:.2f}% over {len(rs)} days. Scale to 0 replicas "
                             f"or delete after confirming with the owning team.",
                             monthly, monthly * 0.95, conf,
                             "Scale to zero first (reversible) and keep the manifest; delete only after 7 quiet days.", now))
            continue
        if med_eff < config.RIGHTSIZE_EFFICIENCY_PCT:
            tc, tr, cc, cr, save = rightsize()
            if save > 0:
                recs.append(_rec(ns, wl, "RIGHT-SIZE",
                                 f"CPU request {cc:.3f} -> {tc:.3f} cores, RAM {cr:.2f} -> {tr:.2f} GB "
                                 f"(p95 usage x {config.RIGHTSIZE_HEADROOM}). Median efficiency {med_eff:.1f}%.",
                                 monthly, save, conf,
                                 ("System component — change only via its Helm values and watch for OOMKills."
                                  if system else "Apply in staging first; roll back if p95 latency or restarts rise."),
                                 now))
                continue
        # COMMITMENT: stable, well-utilised spend -> committed-use discount
        cv = float(cost.std() / cost.mean()) if cost.mean() else 1.0
        if len(rs) >= config.COMMITMENT_MIN_DAYS and cv <= config.COMMITMENT_MAX_CV and med_eff >= config.RIGHTSIZE_EFFICIENCY_PCT:
            recs.append(_rec(ns, wl, "COMMITMENT",
                             f"Spend is stable (CV {cv:.2f}) and efficient ({med_eff:.0f}%). Cover the baseline "
                             f"with a 1-year committed-use / reserved instance (~{int(config.COMMITMENT_DISCOUNT*100)}% discount).",
                             monthly, monthly * config.COMMITMENT_DISCOUNT, conf,
                             "Commit only to the stable baseline (min daily cost), not the peak.", now))
            continue
        recs.append(_rec(ns, wl, "OK", f"Efficiency {med_eff:.0f}% — no action needed.", monthly, 0.0, conf, "", now))

    conn.execute("DELETE FROM recommendations")
    conn.executemany(
        "INSERT INTO recommendations (namespace, workload, category, detail, current_monthly_cost, "
        "est_monthly_savings, confidence, safety_note, generated_at) VALUES "
        "(:namespace,:workload,:category,:detail,:current_monthly_cost,:est_monthly_savings,:confidence,:safety_note,:generated_at)",
        recs,
    )
    return recs


def _rec(ns, wl, cat, detail, monthly, save, conf, note, now) -> dict:
    return {"namespace": ns, "workload": wl, "category": cat, "detail": detail,
            "current_monthly_cost": round(monthly, 6), "est_monthly_savings": round(save, 6),
            "confidence": conf, "safety_note": note, "generated_at": now}


def naive_waste_estimate(conn: sqlite3.Connection, lookback_days: int = 30) -> float:
    """O2-reference 'savings' figure: what a dashboard alone suggests — every unused
    requested core/GB is waste. Upper bound and NOT safe to act on (no headroom,
    includes system pods) — kept only as the KPI-1 baseline."""
    last = conn.execute("SELECT MAX(date) FROM cost_allocations").fetchone()[0]
    r = conn.execute(
        "SELECT AVG(day_waste) FROM (SELECT date, SUM("
        " MAX(COALESCE(cpu_request,0) - COALESCE(cpu_usage,0), 0) * ? + "
        " MAX(COALESCE(ram_request_gb,0) - COALESCE(ram_usage_gb,0), 0) * ?) AS day_waste "
        " FROM cost_allocations WHERE namespace != '__idle__' AND date > date(?, ?) GROUP BY date)",
        (24 * config.CPU_PRICE_PER_CORE_HOUR, 24 * config.RAM_PRICE_PER_GB_HOUR, last, f"-{lookback_days} days"),
    ).fetchone()[0]
    return float((r or 0) * 30)
