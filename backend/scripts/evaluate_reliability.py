"""KPI-4 (recovery under fault injection), KPI-5 (error rate), KPI-6 (p95 latency).

    cd backend && venv/bin/python scripts/evaluate_reliability.py

Runs against a throw-away copy of the database, so it never touches your demo data.
Writes reports/reliability.json and reports/reliability.md.
"""

from __future__ import annotations

import copy
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from finops import config, ingest, simulator  # noqa: E402
from finops.db import connect, init_db  # noqa: E402
from finops.pipeline import analyse  # noqa: E402


def total(db):
    return connect(db).execute("SELECT ROUND(SUM(total_cost), 6), COUNT(*) FROM cost_allocations").fetchone()


def fault_campaign(db: Path) -> list[dict]:
    payload, _ = simulator.generate(days=60, seed=11)
    ingest.ingest_payload(payload, "simulator", db_path=db)
    analyse(db, report=False)
    base = tuple(total(db))
    results = []

    def record(fid, name, fn, check):
        t0 = time.perf_counter()
        try:
            out = fn()
            ok, note = check(out)
        except Exception as exc:  # noqa: BLE001
            ok, note = False, f"unhandled exception: {exc}"
        results.append({"id": fid, "fault": name, "recovered": bool(ok), "note": note,
                        "recovery_ms": round((time.perf_counter() - t0) * 1000, 1)})

    record("F1", "OpenCost unreachable (connection refused)",
           lambda: ingest.ingest_from_opencost(db_path=db, base_url="http://127.0.0.1:9", retries=2, timeout=0.3),
           lambda r: (r["status"] == "failed" and tuple(total(db)) == base, "failed run recorded, data intact"))
    record("F2", "OpenCost timeout (non-routable host)",
           lambda: ingest.ingest_from_opencost(db_path=db, base_url="http://10.255.255.1:9003", retries=1, timeout=0.5),
           lambda r: (r["status"] == "failed" and tuple(total(db)) == base, "timeout handled, data intact"))
    record("F3", "Malformed payload (garbage JSON structure)",
           lambda: ingest.ingest_payload({"code": 200, "data": ["x", {"a/b": {"oops": 1}}]}, "fixture", db_path=db),
           lambda r: (r["rows_accepted"] == 0 and tuple(total(db)) == base, "all rows rejected with reasons"))
    record("F4", "Duplicate replay of a full payload",
           lambda: ingest.ingest_payload(payload, "simulator", db_path=db),
           lambda r: (tuple(total(db)) == base, "idempotent upsert, no double-count"))

    def corrupt():
        p = copy.deepcopy(payload)
        k = next(iter(p["data"][-1]))
        p["data"][-1][k]["totalCost"] = -5
        p["data"][-1][k]["cpuCost"] = -5
        return ingest.ingest_payload(p, "simulator", db_path=db)
    record("F5", "Corrupt record (negative cost) inside valid payload", corrupt,
           lambda r: (r["status"] == "partial" and r["rows_rejected"] == 1, "bad row quarantined, rest accepted"))

    def gaps():
        conn = connect(db)
        conn.execute("DELETE FROM cost_allocations WHERE date BETWEEN date((SELECT MAX(date) FROM cost_allocations), '-20 days') "
                     "AND date((SELECT MAX(date) FROM cost_allocations), '-15 days')")
        conn.commit()
        return analyse(db, report=False)
    record("F6", "6-day gap in cost history (collector outage)", gaps,
           lambda r: (r["forecast_rows"] > 0, "gaps zero-filled, forecast + recommendations still produced"))

    def recover():
        ingest.ingest_payload(payload, "simulator", db_path=db)  # replay from source of truth
        return analyse(db, report=False)
    record("F7", "Recovery: replay after gap", recover,
           lambda r: (tuple(total(db)) == base, "state reconciled to the original totals"))
    return results


def latency(db: Path, trials: int = 50) -> list[dict]:
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    paths = ["/health", "/costs", "/costs/summary", "/attribution?by=team", "/trends?by=team",
             "/anomalies", "/forecast", "/recommendations"]
    out = []
    for p in paths:
        for _ in range(5):
            client.get(p)  # warm-up
        ms, errors = [], 0
        for _ in range(trials):
            t0 = time.perf_counter()
            r = client.get(p)
            ms.append((time.perf_counter() - t0) * 1000)
            errors += r.status_code >= 500
        ms.sort()
        q = statistics.quantiles(ms, n=100)
        out.append({"endpoint": p, "trials": trials, "p50_ms": round(q[49], 2), "p95_ms": round(q[94], 2),
                    "p99_ms": round(q[98], 2), "error_rate_pct": round(100 * errors / trials, 2)})
    return out


def main():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "eval.db"
    config.DB_PATH = db
    init_db(db)
    faults = fault_campaign(db)
    lat = latency(db)
    rec_rate = 100 * sum(f["recovered"] for f in faults) / len(faults)
    res = {"KPI-4 recovery rate under fault injection (%)": round(rec_rate, 1),
           "KPI-5 service error rate (%)": round(statistics.mean(l["error_rate_pct"] for l in lat), 3),
           "KPI-6 worst endpoint p95 latency (ms)": max(l["p95_ms"] for l in lat),
           "faults": faults, "latency": lat}
    config.REPORT_DIR.mkdir(exist_ok=True)
    (config.REPORT_DIR / "reliability.json").write_text(json.dumps(res, indent=2))
    md = ["# CLOUD-04 — Reliability baseline (KPI-4, KPI-5, KPI-6)", "",
          f"- KPI-4 recovery rate: **{res['KPI-4 recovery rate under fault injection (%)']} %**",
          f"- KPI-5 error rate: **{res['KPI-5 service error rate (%)']} %**",
          f"- KPI-6 worst p95 latency: **{res['KPI-6 worst endpoint p95 latency (ms)']} ms** (in-process, 60-day dataset)", "",
          "| Fault | Description | Recovered | Note | Time (ms) |", "|---|---|---|---|---|"]
    md += [f"| {f['id']} | {f['fault']} | {'yes' if f['recovered'] else 'NO'} | {f['note']} | {f['recovery_ms']} |" for f in faults]
    md += ["", "| Endpoint | p50 ms | p95 ms | p99 ms | errors % |", "|---|---|---|---|---|"]
    md += [f"| {l['endpoint']} | {l['p50_ms']} | {l['p95_ms']} | {l['p99_ms']} | {l['error_rate_pct']} |" for l in lat]
    (config.REPORT_DIR / "reliability.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
