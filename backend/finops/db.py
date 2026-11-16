"""SQLite storage layer.

Design rules (from Review-2 feedback + CLOUD-04 NFR-4):
  * One row per (date, cluster, namespace, workload) -> re-ingesting the same day
    is idempotent (upsert), never duplicates cost.
  * Forecasts live in their own table, so future dates never pollute actual cost.
  * Every ingest is recorded in `ingest_runs` with its source and input hash
    (provenance / evidence manifest).
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id          TEXT PRIMARY KEY,
    source          TEXT NOT NULL,          -- opencost | simulator | fixture
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,          -- running | ok | partial | failed
    window_start    TEXT,
    window_end      TEXT,
    rows_in         INTEGER DEFAULT 0,
    rows_accepted   INTEGER DEFAULT 0,
    rows_rejected   INTEGER DEFAULT 0,
    input_sha256    TEXT,
    message         TEXT
);

CREATE TABLE IF NOT EXISTS cost_allocations (
    date            TEXT NOT NULL,          -- YYYY-MM-DD (ChargePeriodStart)
    cluster         TEXT NOT NULL DEFAULT 'cluster-one',
    namespace       TEXT NOT NULL,
    workload        TEXT NOT NULL,          -- controller name (deployment/statefulset)
    workload_kind   TEXT,
    team            TEXT NOT NULL DEFAULT 'unassigned',
    cpu_request     REAL,                   -- cores (average over the day)
    cpu_usage       REAL,                   -- cores
    ram_request_gb  REAL,
    ram_usage_gb    REAL,
    cpu_cost        REAL NOT NULL DEFAULT 0,
    ram_cost        REAL NOT NULL DEFAULT 0,
    pv_cost         REAL NOT NULL DEFAULT 0,
    network_cost    REAL NOT NULL DEFAULT 0,
    other_cost      REAL NOT NULL DEFAULT 0,
    total_cost      REAL NOT NULL,          -- USD (BilledCost)
    cpu_efficiency  REAL,                   -- 0-100 %
    ram_efficiency  REAL,
    total_efficiency REAL,
    source          TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    PRIMARY KEY (date, cluster, namespace, workload)
);
CREATE INDEX IF NOT EXISTS idx_alloc_date ON cost_allocations(date);
CREATE INDEX IF NOT EXISTS idx_alloc_team ON cost_allocations(team);

CREATE TABLE IF NOT EXISTS rejected_rows (
    run_id   TEXT NOT NULL,
    reason   TEXT NOT NULL,
    raw      TEXT
);

CREATE TABLE IF NOT EXISTS anomalies (
    date          TEXT NOT NULL,
    namespace     TEXT NOT NULL,
    workload      TEXT NOT NULL,
    method        TEXT NOT NULL,            -- zscore | reference-threshold
    total_cost    REAL,
    baseline_mean REAL,
    baseline_std  REAL,
    score         REAL,                     -- z-score or ratio
    PRIMARY KEY (date, namespace, workload, method)
);

CREATE TABLE IF NOT EXISTS forecasts (
    model         TEXT NOT NULL,
    namespace     TEXT NOT NULL,
    workload      TEXT NOT NULL,
    target_date   TEXT NOT NULL,
    value         REAL NOT NULL,
    lower         REAL,
    upper         REAL,
    generated_at  TEXT NOT NULL,
    PRIMARY KEY (model, namespace, workload, target_date)
);

CREATE TABLE IF NOT EXISTS recommendations (
    namespace               TEXT NOT NULL,
    workload                TEXT NOT NULL,
    category                TEXT NOT NULL,  -- IDLE | RIGHT-SIZE | COMMITMENT | OK
    detail                  TEXT,
    current_monthly_cost    REAL,
    est_monthly_savings     REAL,
    confidence              TEXT,           -- high | medium | low
    safety_note             TEXT,
    generated_at            TEXT NOT NULL,
    PRIMARY KEY (namespace, workload, category)
);

CREATE TABLE IF NOT EXISTS kpi_measurements (
    kpi           TEXT NOT NULL,
    variant       TEXT NOT NULL,            -- O2-reference | O3-candidate
    value         REAL,
    unit          TEXT,
    detail        TEXT,
    measured_at   TEXT NOT NULL,
    PRIMARY KEY (kpi, variant)
);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = str(db_path or config.DB_PATH)
    # check_same_thread=False: FastAPI may close a request's connection on a different
    # worker thread than the one that opened it. Each request still gets its own connection.
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session(db_path: Path | str | None = None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with session(db_path) as conn:
        conn.executescript(SCHEMA)


def reset_derived(conn: sqlite3.Connection) -> None:
    """Clear tables that are fully recomputed from cost_allocations."""
    for t in ("anomalies", "forecasts", "recommendations", "kpi_measurements"):
        conn.execute(f"DELETE FROM {t}")
