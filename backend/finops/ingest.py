"""Ingestion orchestration: payload -> normalise -> validate -> idempotent upsert.

Failure semantics (NT-1, NFR-2, NFR-4):
  * If OpenCost is unreachable the run is recorded as `failed`, nothing already
    stored is touched, and the API keeps serving the last good data (degraded mode).
  * Invalid rows go to `rejected_rows` with a reason; the run becomes `partial`.
  * Re-running the same payload produces exactly the same table (upsert on the
    natural key), so a retry/replay can never double-count cost.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from . import config, opencost, validation
from .db import session

COLUMNS = (
    "date", "cluster", "namespace", "workload", "workload_kind", "team",
    "cpu_request", "cpu_usage", "ram_request_gb", "ram_usage_gb",
    "cpu_cost", "ram_cost", "pv_cost", "network_cost", "other_cost", "total_cost",
    "cpu_efficiency", "ram_efficiency", "total_efficiency", "source", "run_id",
)
_UPSERT = (
    f"INSERT INTO cost_allocations ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))}) "
    "ON CONFLICT(date, cluster, namespace, workload) DO UPDATE SET "
    + ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c not in ("date", "cluster", "namespace", "workload"))
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id(source: str) -> str:
    return f"{source}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def ingest_payload(payload: dict, source: str, db_path=None, run_id: str | None = None) -> dict:
    """Validate and store an OpenCost-format payload. Returns the run summary."""
    run_id = run_id or new_run_id(source)
    sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    rows, unparseable = opencost.normalise(payload, config.load_team_map())

    accepted, rejected = [], list(unparseable)
    for r in rows:
        try:
            v = validation.validate_row(r)
            v["source"], v["run_id"] = source, run_id
            accepted.append(v)
        except validation.RowError as exc:
            rejected.append((str(exc), r))

    status = "ok" if not rejected else ("partial" if accepted else "failed")
    dates = sorted({r["date"] for r in accepted})
    summary = {
        "run_id": run_id, "source": source, "status": status,
        "rows_in": len(rows) + len(unparseable), "rows_accepted": len(accepted),
        "rows_rejected": len(rejected), "window_start": dates[0] if dates else None,
        "window_end": dates[-1] if dates else None, "input_sha256": sha,
    }

    # One transaction: either every accepted row + the run record is committed, or nothing.
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO ingest_runs (run_id, source, started_at, finished_at, status, window_start, "
            "window_end, rows_in, rows_accepted, rows_rejected, input_sha256, message) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, source, _now(), _now(), status, summary["window_start"], summary["window_end"],
             summary["rows_in"], summary["rows_accepted"], summary["rows_rejected"], sha,
             f"{len(rejected)} rows rejected" if rejected else "ok"),
        )
        conn.executemany(_UPSERT, [tuple(r.get(c) for c in COLUMNS) for r in accepted])
        conn.executemany(
            "INSERT INTO rejected_rows (run_id, reason, raw) VALUES (?,?,?)",
            [(run_id, reason, json.dumps(raw, default=str)[:2000]) for reason, raw in rejected],
        )
    summary["rejections"] = [reason for reason, _ in rejected][:20]
    return summary


def ingest_from_opencost(window: str = "7d", db_path=None, **kw) -> dict:
    """Live ingest. On any failure, record a failed run and leave stored data untouched."""
    run_id = new_run_id("opencost")
    try:
        payload = opencost.fetch_allocation(window=window, **kw)
    except opencost.OpenCostUnavailable as exc:
        with session(db_path) as conn:
            conn.execute(
                "INSERT INTO ingest_runs (run_id, source, started_at, finished_at, status, message) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, "opencost", _now(), _now(), "failed", str(exc)[:500]),
            )
        return {"run_id": run_id, "source": "opencost", "status": "failed", "message": str(exc)}
    opencost.save_raw(payload, run_id, config.BACKEND_DIR / "data" / "raw")
    return ingest_payload(payload, "opencost", db_path=db_path, run_id=run_id)
