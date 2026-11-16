"""KPI measurement: O2 reference vs O3/O4 candidate on identical evidence (AC-4).

Writes kpi_measurements + reports/baseline_kpis.{json,md}. These frozen O2 values are
the Sem-VII (CP1 Gate 2) baseline; Sem-VIII must beat them by the CLOUD-04 targets:
  KPI-1 savings          >= 5 % relative improvement (or non-inferior + safer)
  KPI-2 forecast acc.    >= O2 + 3 percentage points
  KPI-3 anomaly prec.    >= O2 + 3 percentage points
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import anomaly, attribution, config, forecast, recommend, simulator


def measure(conn: sqlite3.Connection, truth_path: Path | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res: dict = {"measured_at": now, "kpis": {}}

    # KPI-2 forecast accuracy
    bt = forecast.backtest(conn, by="workload", horizon=7, test_days=28)
    if bt:
        ref_name = max(("R1-moving-average", "R2-linear-trend"), key=lambda m: bt[m]["accuracy_pct"])
        cand = {k: v for k, v in bt.items() if k.startswith("O3")}
        cand_name = max(cand, key=lambda m: cand[m]["accuracy_pct"])
        res["kpis"]["KPI-2 cost-forecast accuracy"] = {
            "unit": "%", "O2-reference": bt[ref_name]["accuracy_pct"], "O2-method": ref_name,
            "O3-candidate": bt[cand_name]["accuracy_pct"], "O3-method": cand_name,
            "delta_pp": round(bt[cand_name]["accuracy_pct"] - bt[ref_name]["accuracy_pct"], 3),
            "target": "O3 >= O2 + 3 pp",
            "all_models": {k: {"mape_pct": v["mape_pct"], "accuracy_pct": v["accuracy_pct"]} for k, v in bt.items()},
        }

    # KPI-3 anomaly precision (needs an oracle -> simulator ground truth)
    truth_path = truth_path or (config.FIXTURE_DIR / "ground_truth_anomalies.csv")
    src = conn.execute("SELECT source FROM cost_allocations LIMIT 1").fetchone()
    if truth_path.exists() and src and src[0] in ("simulator", "fixture"):
        truth = simulator.read_ground_truth(truth_path)
        ref = anomaly.evaluate(anomaly.detect(conn, "reference-threshold", store=False), truth)
        cand = anomaly.evaluate(anomaly.detect(conn, "zscore", store=False), truth)
        res["kpis"]["KPI-3 anomaly-detection precision"] = {
            "unit": "%", "O2-reference": round(ref["precision"] * 100, 2),
            "O2-method": f"cost > {config.REFERENCE_SPIKE_RATIO} x 7-day avg",
            "O3-candidate": round(cand["precision"] * 100, 2),
            "O3-method": f"z-score, window {config.ANOMALY_WINDOW_DAYS}d, threshold {config.ANOMALY_Z_THRESHOLD}",
            "delta_pp": round((cand["precision"] - ref["precision"]) * 100, 2),
            "reference_detail": ref, "candidate_detail": cand, "target": "O3 >= O2 + 3 pp",
        }

    # KPI-1 estimated savings (monthly, USD)
    recs = recommend.generate(conn)
    safe = sum(r["est_monthly_savings"] for r in recs)
    naive = recommend.naive_waste_estimate(conn)
    res["kpis"]["KPI-1 estimated savings (monthly)"] = {
        "unit": "USD/month", "O2-reference": round(naive, 4),
        "O2-method": "naive unused-request waste (upper bound, not actionable)",
        "O3-candidate": round(safe, 4), "O3-method": "O4 safe recommendations (p95 x 1.3 headroom, no system deletes)",
        "by_category": {c: round(sum(r["est_monthly_savings"] for r in recs if r["category"] == c), 4)
                        for c in ("IDLE", "RIGHT-SIZE", "COMMITMENT")},
        "note": "Reference over-states savings because it ignores headroom and system pods; "
                "compare on realised savings in Sem VIII (AC-1).",
    }

    # Attribution accuracy (AC-2 / NT-2)
    res["attribution_reconciliation"] = attribution.reconcile(conn)

    conn.execute("DELETE FROM kpi_measurements")
    for name, k in res["kpis"].items():
        for variant in ("O2-reference", "O3-candidate"):
            conn.execute(
                "INSERT INTO kpi_measurements (kpi, variant, value, unit, detail, measured_at) VALUES (?,?,?,?,?,?)",
                (name, variant, k.get(variant), k["unit"], k.get(variant.split("-")[0] + "-method"), now))
    return res


def write_report(res: dict, out_dir: Path | None = None) -> tuple[Path, Path]:
    out_dir = out_dir or config.REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = out_dir / "baseline_kpis.json", out_dir / "baseline_kpis.md"
    jp.write_text(json.dumps(res, indent=2, default=str))
    lines = ["# CLOUD-04 — KPI baseline (O2 reference vs O3/O4 candidate)", "",
             f"Measured: {res['measured_at']}", "",
             "| KPI | O2 reference | O3/O4 candidate | Target |", "|---|---|---|---|"]
    for name, k in res["kpis"].items():
        lines.append(f"| {name} | {k['O2-reference']} {k['unit']} ({k['O2-method']}) | "
                     f"{k['O3-candidate']} {k['unit']} ({k['O3-method']}) | {k.get('target', '—')} |")
    rec = res.get("attribution_reconciliation", {})
    lines += ["", f"Attribution reconciliation: max difference between groupings = "
              f"{rec.get('max_abs_diff')} USD -> {'PASS' if rec.get('reconciled') else 'FAIL'}"]
    if "KPI-2 cost-forecast accuracy" in res["kpis"]:
        lines += ["", "## Forecast backtest (rolling origin, 7-day horizon, last 28 days)", "",
                  "| Model | MAPE % | Accuracy % |", "|---|---|---|"]
        for m, v in res["kpis"]["KPI-2 cost-forecast accuracy"]["all_models"].items():
            lines.append(f"| {m} | {v['mape_pct']} | {v['accuracy_pct']} |")
    if "KPI-3 anomaly-detection precision" in res["kpis"]:
        k = res["kpis"]["KPI-3 anomaly-detection precision"]
        for label, d in (("O2 reference", k["reference_detail"]), ("O3 z-score", k["candidate_detail"])):
            lines += ["", f"### {label}: TP {d['tp']} / FP {d['fp']} / FN {d['fn']} — "
                      f"precision {d['precision']}, recall {d['recall']}, F1 {d['f1']}",
                      f"Missed: {d['missed']}"]
    mp.write_text("\n".join(lines) + "\n")
    return jp, mp
