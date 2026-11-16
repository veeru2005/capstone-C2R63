import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from finops import config  # noqa: E402
from finops.db import init_db  # noqa: E402


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", p)
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    init_db(p)
    return p


def alloc(ns, wl, day, cpu_req, cpu_use, ram_req_gb, ram_use_gb, cpu_cost, ram_cost, team=None, pv=0.0):
    """Build one allocation exactly as the OpenCost API returns it."""
    labels = {"team": team} if team else {}
    return {
        "name": f"{ns}/{wl}",
        "properties": {"cluster": "c1", "namespace": ns, "controller": wl, "controllerKind": "deployment",
                       "labels": labels},
        "window": {"start": f"{day}T00:00:00Z", "end": f"{day}T23:59:59Z"},
        "start": f"{day}T00:00:00Z", "end": f"{day}T23:59:59Z",
        "cpuCoreRequestAverage": cpu_req, "cpuCoreUsageAverage": cpu_use,
        "ramByteRequestAverage": ram_req_gb * 1024 ** 3, "ramByteUsageAverage": ram_use_gb * 1024 ** 3,
        "cpuCost": cpu_cost, "ramCost": ram_cost, "pvCost": pv, "networkCost": 0.0,
        "totalCost": cpu_cost + ram_cost + pv, "totalEfficiency": None,
    }


@pytest.fixture
def oracle_payload():
    """Hand-built 2-day payload. Expected values below were worked out by hand
    (independent oracle for FR-2)."""
    d1, d2 = "2026-10-01", "2026-10-02"
    return {"code": 200, "data": [
        {
            "payments/api": alloc("payments", "api", d1, 1.0, 0.5, 2, 1, 0.75, 0.20, team="payments-team"),
            "catalog/web": alloc("catalog", "web", d1, 0.5, 0.01, 1, 0.1, 0.38, 0.10),  # team from teams.json
            "__idle__": {"name": "__idle__", "properties": {"cluster": "c1"},
                         "start": f"{d1}T00:00:00Z", "end": f"{d1}T23:59:59Z",
                         "cpuCost": 0.30, "ramCost": 0.10, "totalCost": 0.40},
        },
        {
            "payments/api": alloc("payments", "api", d2, 1.0, 0.6, 2, 1, 0.75, 0.20, team="payments-team"),
            "catalog/web": alloc("catalog", "web", d2, 0.5, 0.01, 1, 0.1, 0.38, 0.10),
        },
    ]}


def write_json(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj))
    return path
