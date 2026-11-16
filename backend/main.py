"""
main.py — FastAPI backend for the FinOps Cloud-Cost Optimisation Dashboard (CLOUD-04).

Run:
    uvicorn main:app --reload --port 8000        # docs at http://localhost:8000/docs

Data is produced by the pipeline (python -m finops.pipeline ...). The API only reads
the database, so if ingestion fails the dashboard keeps serving the last good data and
/health reports "degraded" (NFR-2, degraded mode).
"""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

import logging
import threading
from contextlib import asynccontextmanager

from finops import __version__, attribution, config, ingest, opencost, trends
from finops.db import connect, init_db

log = logging.getLogger("finops.api")

# Live mode: when AUTO_SYNC_MINUTES > 0 the API pulls OpenCost on a timer, so a new
# pod deployed on the cluster shows up in the dashboard without running any command.
AUTO_SYNC_MINUTES = float(os.getenv("AUTO_SYNC_MINUTES", "0"))
_sync_state = {"last_attempt": None, "last_status": None, "message": None}
_stop = threading.Event()


def _sync_loop():
    from finops.pipeline import analyse
    while not _stop.is_set():
        _sync_state["last_attempt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            run = ingest.ingest_from_opencost(window="7d", retries=1)
            _sync_state["last_status"], _sync_state["message"] = run["status"], run.get("message")
            if run["status"] != "failed":
                analyse(report_dir=config.REPORT_DIR / "live")
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            _sync_state["last_status"], _sync_state["message"] = "error", str(exc)
            log.exception("auto-sync failed")
        _stop.wait(AUTO_SYNC_MINUTES * 60)


@asynccontextmanager
async def lifespan(_app):
    init_db()
    if AUTO_SYNC_MINUTES > 0:
        threading.Thread(target=_sync_loop, daemon=True, name="opencost-sync").start()
    yield
    _stop.set()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SHOW_DOCS = os.getenv("ENABLE_DOCS", "true").lower() in ("true", "1", "yes") and ENVIRONMENT != "production"
API_KEY = os.getenv("FINOPS_API_KEY")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

app = FastAPI(
    title="FinOps Cloud-Cost Optimisation API (CLOUD-04)",
    description="Kubernetes cost attribution, trend analysis, anomaly detection, forecasting and savings recommendations on OpenCost data.",
    version=__version__,
    docs_url="/docs" if SHOW_DOCS else None,
    redoc_url="/redoc" if SHOW_DOCS else None,
    openapi_url="/openapi.json" if SHOW_DOCS else None,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

# ─── Telemetry: per-route latency + error counters (NFR-6, KPI-5, KPI-6) ─────
_LAT: dict[str, deque] = defaultdict(lambda: deque(maxlen=2000))
_COUNT: dict[tuple[str, int], int] = defaultdict(int)


@app.middleware("http")
async def telemetry(request: Request, call_next):
    t0 = time.perf_counter()
    route = request.url.path
    status = 500
    try:
        resp = await call_next(request)
        status = resp.status_code
        return resp
    finally:
        ms = (time.perf_counter() - t0) * 1000
        _LAT[route].append(ms)
        _COUNT[(route, status)] += 1
        if status != 500:
            resp.headers["X-Response-Time-ms"] = f"{ms:.2f}"


def db():
    if not config.DB_PATH.exists():
        init_db()
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def require_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


# ─── Models (legacy fields kept so the existing React components keep working) ─

class CostRecord(BaseModel):
    date: str
    app_name: str
    namespace: str
    team: str
    cpu_requested: Optional[float] = None
    cpu_used: Optional[float] = None
    ram_requested: Optional[float] = None
    ram_used: Optional[float] = None
    total_cost: Optional[float] = None
    efficiency_pct: Optional[float] = None


class AppCostBreakdown(BaseModel):
    app_name: str
    cost: Optional[float] = None


class CostSummary(BaseModel):
    total_cost: Optional[float] = None
    allocated_cost: Optional[float] = None
    idle_cost: Optional[float] = None
    avg_efficiency: Optional[float] = None
    start: Optional[str] = None
    end: Optional[str] = None
    currency: str = "USD"
    by_app: List[AppCostBreakdown] = []


class AnomalyRecord(BaseModel):
    date: str
    app_name: str
    namespace: str
    method: str
    total_cost: Optional[float] = None
    baseline_mean: Optional[float] = None
    z_score: Optional[float] = None


class ForecastRecord(BaseModel):
    date: str
    app_name: str
    namespace: str
    model: str
    forecast_value: float
    lower: Optional[float] = None
    upper: Optional[float] = None


class RecommendationRecord(BaseModel):
    app_name: str
    namespace: str
    recommendation: str
    detail: Optional[str] = None
    current_monthly_cost: Optional[float] = None
    estimated_savings: Optional[float] = None
    confidence: Optional[str] = None
    safety_note: Optional[str] = None


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api", tags=["Root"])
def root():
    return {"service": "FinOps CLOUD-04 API", "version": __version__, "docs": "/docs" if SHOW_DOCS else None,
            "endpoints": ["/health", "/costs", "/costs/summary", "/attribution", "/attribution/reconcile",
                          "/trends", "/anomalies", "/forecast", "/recommendations", "/kpis",
                          "/ingest-runs", "/export/focus.csv", "/metrics", "/live"]}


@app.get("/health", tags=["Health"])
def health(conn: sqlite3.Connection = Depends(db)):
    """ok | degraded (last ingest failed or data stale) | no-data."""
    last_ok = conn.execute("SELECT * FROM ingest_runs WHERE status IN ('ok','partial') ORDER BY finished_at DESC LIMIT 1").fetchone()
    last = conn.execute("SELECT * FROM ingest_runs ORDER BY finished_at DESC LIMIT 1").fetchone()
    data_end = conn.execute("SELECT MAX(date) FROM cost_allocations").fetchone()[0]
    if not data_end:
        return {"status": "no-data", "message": "Run: python -m finops.pipeline --source simulator"}
    reasons = []
    if last and last["status"] == "failed":
        reasons.append(f"last ingest failed: {last['message']}")
    if last_ok and last_ok["source"] == "opencost":
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_ok["finished_at"])).total_seconds() / 3600
        if age_h > config.STALE_AFTER_HOURS:
            reasons.append(f"data is {age_h:.0f} h old")
    return {
        "status": "degraded" if reasons else "ok",
        "reasons": reasons,
        "data_source": last_ok["source"] if last_ok else None,
        "data_start": conn.execute("SELECT MIN(date) FROM cost_allocations").fetchone()[0],
        "data_end": data_end,
        "last_successful_ingest": last_ok["finished_at"] if last_ok else None,
        "last_run": dict(last) if last else None,
    }


def _filters(app_name, namespace, team, start_date, end_date, include_idle=False):
    sql, params = " WHERE 1=1", []
    for col, val in (("workload", app_name), ("namespace", namespace), ("team", team)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    if not include_idle:
        sql += " AND namespace != '__idle__'"
    return sql, params


@app.get("/live", tags=["Live"])
def live(window: str = Query("10m", pattern="^[0-9]+[mhd]$")):
    """What is running on the cluster *right now* (straight from OpenCost, not the DB)."""
    try:
        items = opencost.fetch_live(window=window)
        return {"connected": True, "opencost_url": config.OPENCOST_URL, "window": window,
                "auto_sync_minutes": AUTO_SYNC_MINUTES, "sync": _sync_state, "workloads": items}
    except opencost.OpenCostUnavailable as exc:
        return {"connected": False, "opencost_url": config.OPENCOST_URL, "window": window,
                "auto_sync_minutes": AUTO_SYNC_MINUTES, "sync": _sync_state, "error": str(exc)[:300],
                "workloads": []}


@app.get("/costs", response_model=List[CostRecord], tags=["Costs"])
def get_costs(app_name: Optional[str] = None, namespace: Optional[str] = None, team: Optional[str] = None,
              start_date: Optional[str] = None, end_date: Optional[str] = None,
              conn: sqlite3.Connection = Depends(db)):
    where, params = _filters(app_name, namespace, team, start_date, end_date)
    rows = conn.execute(
        "SELECT date, workload AS app_name, namespace, team, cpu_request AS cpu_requested, cpu_usage AS cpu_used, "
        "ram_request_gb AS ram_requested, ram_usage_gb AS ram_used, total_cost, total_efficiency AS efficiency_pct "
        f"FROM cost_allocations{where} ORDER BY date, namespace, workload", params).fetchall()
    return [dict(r) for r in rows]


@app.get("/costs/summary", response_model=CostSummary, tags=["Costs"])
def cost_summary(start_date: Optional[str] = None, end_date: Optional[str] = None,
                 conn: sqlite3.Connection = Depends(db)):
    a = attribution.attribute(conn, "workload", start_date, end_date, include_idle=True)
    alloc = [i for i in a["items"] if i["key"] != "__idle__/__idle__"]
    where, params = _filters(None, None, None, start_date, end_date)
    eff = conn.execute(f"SELECT SUM(total_efficiency*total_cost)/NULLIF(SUM(total_cost),0), MIN(date), MAX(date) "
                       f"FROM cost_allocations{where}", params).fetchone()
    return {"total_cost": a["total_cost"], "allocated_cost": round(sum(i["cost"] for i in alloc), 6),
            "idle_cost": a["idle_cost"], "avg_efficiency": round(eff[0], 2) if eff[0] is not None else None,
            "start": eff[1], "end": eff[2],
            "by_app": [{"app_name": i["key"].split("/", 1)[1], "cost": i["cost"]} for i in alloc]}


@app.get("/attribution", tags=["Attribution (O1)"])
def get_attribution(by: str = Query("namespace", pattern="^(team|namespace|workload)$"),
                    start_date: Optional[str] = None, end_date: Optional[str] = None,
                    include_idle: bool = True, conn: sqlite3.Connection = Depends(db)):
    return attribution.attribute(conn, by, start_date, end_date, include_idle)


@app.get("/attribution/reconcile", tags=["Attribution (O1)"])
def get_reconcile(conn: sqlite3.Connection = Depends(db)):
    return attribution.reconcile(conn)


@app.get("/trends", tags=["Trends (O2)"])
def get_trends(by: str = Query("team", pattern="^(team|namespace|workload)$"),
               start_date: Optional[str] = None, end_date: Optional[str] = None,
               conn: sqlite3.Connection = Depends(db)):
    return trends.trend_summary(conn, by, start_date, end_date)


@app.get("/anomalies", response_model=List[AnomalyRecord], tags=["Anomalies (O3)"])
def get_anomalies(method: str = Query("zscore", pattern="^(zscore|reference-threshold)$"),
                  conn: sqlite3.Connection = Depends(db)):
    rows = conn.execute(
        "SELECT date, workload AS app_name, namespace, method, total_cost, baseline_mean, score AS z_score "
        "FROM anomalies WHERE method = ? ORDER BY date DESC", (method,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/forecast", response_model=List[ForecastRecord], tags=["Forecast (O3)"])
def get_forecast(model: str = "O3-seasonal-trend", conn: sqlite3.Connection = Depends(db)):
    rows = conn.execute(
        "SELECT target_date AS date, workload AS app_name, namespace, model, value AS forecast_value, lower, upper "
        "FROM forecasts WHERE model = ? ORDER BY namespace, workload, target_date", (model,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/recommendations", response_model=List[RecommendationRecord], tags=["Recommendations (O4)"])
def get_recommendations(conn: sqlite3.Connection = Depends(db)):
    rows = conn.execute(
        "SELECT workload AS app_name, namespace, category AS recommendation, detail, current_monthly_cost, "
        "est_monthly_savings AS estimated_savings, confidence, safety_note FROM recommendations "
        "ORDER BY est_monthly_savings DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/config", tags=["Settings"])
def get_config():
    """Read-only view of the active settings (shown on the dashboard's Settings page).
    They are changed in backend/finops/config.py or with environment variables."""
    return {
        "billing_currency": config.BILLING_CURRENCY,
        "opencost_url": config.OPENCOST_URL,
        "auto_sync_minutes": AUTO_SYNC_MINUTES,
        "stale_after_hours": config.STALE_AFTER_HOURS,
        "pricing": {"cpu_per_core_hour": config.CPU_PRICE_PER_CORE_HOUR, "ram_per_gb_hour": config.RAM_PRICE_PER_GB_HOUR},
        "anomaly": {"window_days": config.ANOMALY_WINDOW_DAYS, "z_threshold": config.ANOMALY_Z_THRESHOLD,
                    "reference_spike_ratio": config.REFERENCE_SPIKE_RATIO},
        "recommendations": {"idle_below_pct": config.IDLE_EFFICIENCY_PCT, "rightsize_below_pct": config.RIGHTSIZE_EFFICIENCY_PCT,
                            "rightsize_headroom": config.RIGHTSIZE_HEADROOM, "commitment_min_days": config.COMMITMENT_MIN_DAYS,
                            "commitment_discount": config.COMMITMENT_DISCOUNT},
        "system_namespaces": sorted(config.SYSTEM_NAMESPACES),
        "api_key_required_for_ingest": bool(API_KEY),
    }


@app.get("/kpis", tags=["Evaluation"])
def get_kpis():
    p = config.REPORT_DIR / "baseline_kpis.json"
    if not p.exists():
        raise HTTPException(404, "No KPI report yet — run the pipeline.")
    return json.loads(p.read_text())


@app.get("/ingest-runs", tags=["Evaluation"])
def get_runs(limit: int = 20, conn: sqlite3.Connection = Depends(db)):
    return [dict(r) for r in conn.execute("SELECT * FROM ingest_runs ORDER BY finished_at DESC LIMIT ?", (limit,))]


@app.post("/ingest/opencost", tags=["Ingestion"], dependencies=[Depends(require_key)])
def trigger_ingest(window: str = "1d"):
    """Pull from OpenCost now. Failure never deletes stored data."""
    from finops.pipeline import analyse
    run = ingest.ingest_from_opencost(window=window, retries=1)
    if run["status"] != "failed":
        analyse(report_dir=config.REPORT_DIR / "live")
    return run


FOCUS_COLUMNS = ["ChargePeriodStart", "ChargePeriodEnd", "BilledCost", "EffectiveCost", "BillingCurrency",
                 "ProviderName", "ServiceCategory", "ServiceName", "SubAccountId", "ResourceId",
                 "ResourceName", "ResourceType", "Tags"]


@app.get("/export/focus.csv", tags=["Export"])
def export_focus(conn: sqlite3.Connection = Depends(db)):
    """Allocations exported with FinOps FOCUS column names (subset relevant to Kubernetes)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(FOCUS_COLUMNS)
    for r in conn.execute("SELECT * FROM cost_allocations ORDER BY date, namespace, workload"):
        w.writerow([f"{r['date']}T00:00:00Z", f"{r['date']}T23:59:59Z", r["total_cost"], r["total_cost"],
                    "USD", "OpenCost", "Compute", "Kubernetes", r["namespace"],
                    f"{r['cluster']}/{r['namespace']}/{r['workload']}", r["workload"], r["workload_kind"],
                    json.dumps({"team": r["team"], "cluster": r["cluster"]})])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=focus_export.csv"})


@app.get("/metrics", response_class=PlainTextResponse, tags=["Health"])
def metrics():
    """Prometheus-style metrics: request counts by status, latency p50/p95/p99 per route."""
    lines = []
    for (route, status), n in sorted(_COUNT.items()):
        lines.append(f'finops_http_requests_total{{route="{route}",status="{status}"}} {n}')
    for route, d in sorted(_LAT.items()):
        s = sorted(d)
        if not s:
            continue
        for q in (0.5, 0.95, 0.99):
            lines.append(f'finops_http_latency_ms{{route="{route}",quantile="{q}"}} {s[min(int(q * len(s)), len(s) - 1)]:.3f}')
    return "\n".join(lines) + "\n"


# ─── Single-service deployment: serve the built React app from the same server ──
# If FRONTEND_DIST points at `frontend/dist` (the root Dockerfile does this), the
# dashboard is served at "/" and calls the API on the same origin. Otherwise "/"
# just returns the API index, as before.
from pathlib import Path as _Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = _Path(os.getenv("FRONTEND_DIST", config.BACKEND_DIR.parent / "frontend" / "dist"))
if (_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
else:
    app.get("/", tags=["Root"])(root)
