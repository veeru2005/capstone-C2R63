"""API contract tests (FR-7) — every endpoint the dashboard uses."""

import pytest
from fastapi.testclient import TestClient

from finops import ingest, simulator
from finops.pipeline import analyse


@pytest.fixture
def client(db_path):
    payload, truth = simulator.generate(days=60, seed=3)
    ingest.ingest_payload(payload, "simulator", db_path=db_path)
    analyse(db_path)
    import main
    return TestClient(main.app)


def test_health_ok(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["data_source"] == "simulator"


@pytest.mark.parametrize("path", ["/", "/costs", "/costs/summary", "/attribution?by=team", "/attribution/reconcile",
                                  "/trends?by=namespace", "/anomalies", "/anomalies?method=reference-threshold",
                                  "/forecast", "/recommendations", "/kpis", "/ingest-runs", "/export/focus.csv",
                                  "/metrics"])
def test_endpoints_200(client, path):
    assert client.get(path).status_code == 200


def test_legacy_fields_for_frontend(client):
    c = client.get("/costs").json()[0]
    assert {"date", "app_name", "total_cost", "efficiency_pct", "cpu_requested", "ram_used"} <= set(c)
    r = client.get("/recommendations").json()[0]
    assert {"app_name", "recommendation", "estimated_savings"} <= set(r)
    s = client.get("/costs/summary").json()
    assert s["total_cost"] == pytest.approx(s["allocated_cost"] + s["idle_cost"], rel=1e-6)


def test_bad_query_rejected(client):
    assert client.get("/attribution?by=planet").status_code == 422


def test_live_reports_disconnected(client, monkeypatch):
    from finops import config
    monkeypatch.setattr(config, "OPENCOST_URL", "http://127.0.0.1:9")
    j = client.get("/live").json()
    assert j["connected"] is False and j["workloads"] == []
