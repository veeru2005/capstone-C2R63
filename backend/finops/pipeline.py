"""One-command pipeline (FR-2: one-command reference path).

    python -m finops.pipeline --source simulator            # reproducible 90-day sandbox
    python -m finops.pipeline --source opencost --window 7d # live kind / cloud cluster
    python -m finops.pipeline --source fixture --file fixtures/opencost_sample.json

Steps: init DB -> ingest -> anomalies (O2 rule + O3 z-score) -> forecast -> recommendations
-> KPI baseline report (reports/baseline_kpis.md).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import anomaly, config, forecast, ingest, kpi, recommend, simulator
from .db import init_db, session


def analyse(db_path=None, report: bool = True) -> dict:
    with session(db_path) as conn:
        a_ref = anomaly.detect(conn, "reference-threshold")
        a_z = anomaly.detect(conn, "zscore")
        n_fc = forecast.forecast_and_store(conn, horizon=14)
        recs = recommend.generate(conn)
        res = kpi.measure(conn) if report else {}
    if report:
        kpi.write_report(res)
    return {"anomalies_reference": len(a_ref), "anomalies_zscore": len(a_z),
            "forecast_rows": n_fc, "recommendations": len(recs), "kpis": res.get("kpis", {})}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="FinOps CLOUD-04 pipeline")
    p.add_argument("--source", choices=["simulator", "opencost", "fixture"], default="simulator")
    p.add_argument("--days", type=int, default=90, help="simulator: days of history")
    p.add_argument("--seed", type=int, default=42, help="simulator: random seed")
    p.add_argument("--window", default="7d", help="opencost: allocation window, e.g. 7d, 30d")
    p.add_argument("--file", type=Path, help="fixture: OpenCost-format JSON file")
    p.add_argument("--fresh", action="store_true", help="delete the database before running")
    p.add_argument("--db", type=Path, default=None)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    db = args.db or config.DB_PATH
    if args.fresh and Path(db).exists():
        Path(db).unlink()
    init_db(db)

    if args.source == "simulator":
        payload, truth = simulator.generate(days=args.days, seed=args.seed)
        simulator.write_ground_truth(truth, config.FIXTURE_DIR / "ground_truth_anomalies.csv")
        run = ingest.ingest_payload(payload, "simulator", db_path=db)
    elif args.source == "fixture":
        if not args.file:
            p.error("--file is required for --source fixture")
        run = ingest.ingest_payload(json.loads(args.file.read_text()), "fixture", db_path=db)
    else:
        run = ingest.ingest_from_opencost(window=args.window, db_path=db)

    print(json.dumps({k: v for k, v in run.items() if k != "rejections"}, indent=2))
    if run.get("rejections"):
        print("Rejected rows (first 20):", *run["rejections"], sep="\n  - ")
    if run["status"] == "failed":
        print("Ingest failed — existing data left untouched; dashboard will show degraded mode.", file=sys.stderr)
        return 2

    out = analyse(db)
    print(json.dumps({k: v for k, v in out.items() if k != "kpis"}, indent=2))
    for name, k in out["kpis"].items():
        print(f"{name}: O2={k['O2-reference']} {k['unit']}  vs  O3={k['O3-candidate']} {k['unit']}")
    print(f"Report: {config.REPORT_DIR / 'baseline_kpis.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
