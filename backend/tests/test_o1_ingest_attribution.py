"""O1 — ingestion, validation and cost attribution (FR-1, NT-1, NT-2)."""

import copy
import math

import pytest

from finops import attribution, ingest, opencost, validation
from finops.db import connect


def test_normalise_maps_opencost_fields(oracle_payload):
    rows, bad = opencost.normalise(oracle_payload, {"catalog": "catalog-team"})
    assert not bad
    api = next(r for r in rows if r["workload"] == "api" and r["date"] == "2026-10-01")
    assert api["namespace"] == "payments" and api["team"] == "payments-team"
    assert api["ram_request_gb"] == pytest.approx(2.0)       # bytes -> GB
    assert api["total_cost"] == pytest.approx(0.95)
    web = next(r for r in rows if r["workload"] == "web")
    assert web["team"] == "catalog-team"                      # namespace fallback mapping
    idle = next(r for r in rows if r["namespace"] == "__idle__")
    assert idle["team"] == "__idle__" and idle["total_cost"] == pytest.approx(0.40)


def test_attribution_matches_hand_oracle(db_path, oracle_payload):
    run = ingest.ingest_payload(oracle_payload, "fixture", db_path=db_path)
    assert run["status"] == "ok" and run["rows_accepted"] == 5
    conn = connect(db_path)
    by_ns = {i["key"]: i["cost"] for i in attribution.attribute(conn, "namespace")["items"]}
    # Hand oracle: payments = 2 x 0.95 = 1.90 ; catalog = 2 x 0.48 = 0.96 ; idle = 0.40
    assert by_ns["payments"] == pytest.approx(1.90)
    assert by_ns["catalog"] == pytest.approx(0.96)
    assert by_ns["__idle__"] == pytest.approx(0.40)
    a = attribution.attribute(conn, "team")
    assert a["total_cost"] == pytest.approx(3.26)
    assert a["idle_share_pct"] == pytest.approx(round(100 * 0.40 / 3.26, 2))
    rec = attribution.reconcile(conn)
    assert rec["reconciled"], rec  # NT-2: every grouping sums to the same total


def test_efficiency_is_cost_weighted(db_path, oracle_payload):
    ingest.ingest_payload(oracle_payload, "fixture", db_path=db_path)
    r = connect(db_path).execute(
        "SELECT cpu_efficiency, ram_efficiency, total_efficiency FROM cost_allocations "
        "WHERE workload='api' AND date='2026-10-01'").fetchone()
    assert r["cpu_efficiency"] == pytest.approx(50.0)
    assert r["ram_efficiency"] == pytest.approx(50.0)
    assert r["total_efficiency"] == pytest.approx(50.0)


def test_replay_is_idempotent(db_path, oracle_payload):
    """NT-1 recovery: replaying the same payload must not duplicate cost."""
    ingest.ingest_payload(oracle_payload, "fixture", db_path=db_path)
    ingest.ingest_payload(oracle_payload, "fixture", db_path=db_path)
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM cost_allocations").fetchone()[0] == 5
    assert conn.execute("SELECT SUM(total_cost) FROM cost_allocations").fetchone()[0] == pytest.approx(3.26)


@pytest.mark.parametrize("mutate, reason", [
    (lambda a: a.update(totalCost=-1.0, cpuCost=-1.0, ramCost=0.0), "negative"),
    (lambda a: a.update(totalCost=float("nan")), "finite"),
    (lambda a: a.update(totalCost=50_000.0, cpuCost=50_000.0, ramCost=0.0), "sanity"),
    (lambda a: a.update(cpuCost=5.0), "add up"),  # components larger than total = corrupt record
])
def test_bad_rows_rejected_not_silently_dropped(db_path, oracle_payload, mutate, reason):
    p = copy.deepcopy(oracle_payload)
    mutate(p["data"][1]["catalog/web"])
    run = ingest.ingest_payload(p, "fixture", db_path=db_path)
    conn = connect(db_path)
    assert run["status"] == "partial"
    assert run["rows_rejected"] == 1 and run["rows_accepted"] == 4
    assert any(reason in r for r in run["rejections"])
    assert conn.execute("SELECT COUNT(*) FROM rejected_rows").fetchone()[0] == 1


def test_validation_rejects_bad_date():
    with pytest.raises(validation.RowError):
        validation.validate_row({"date": "2026-13-40", "namespace": "a", "workload": "b", "total_cost": 1.0})
    assert math.isclose(validation.validate_row(
        {"date": "2026-01-01", "namespace": "a", "workload": "b", "total_cost": 1.0})["total_cost"], 1.0)


def test_opencost_down_keeps_existing_data(db_path, oracle_payload):
    """NFR-2 / degraded mode: unreachable OpenCost -> failed run, stored data untouched."""
    ingest.ingest_payload(oracle_payload, "fixture", db_path=db_path)
    run = ingest.ingest_from_opencost(db_path=db_path, base_url="http://127.0.0.1:9", retries=1, timeout=0.5)
    assert run["status"] == "failed"
    conn = connect(db_path)
    assert conn.execute("SELECT SUM(total_cost) FROM cost_allocations").fetchone()[0] == pytest.approx(3.26)
    assert conn.execute("SELECT status FROM ingest_runs ORDER BY rowid DESC LIMIT 1").fetchone()[0] == "failed"


def test_garbage_payload_is_rejected(db_path):
    run = ingest.ingest_payload({"code": 200, "data": ["not-a-dict", {"x/y": {"bad": 1}}]}, "fixture", db_path=db_path)
    assert run["status"] == "failed" and run["rows_accepted"] == 0 and run["rows_rejected"] == 2


def test_unlabelled_pod_goes_to_unallocated(db_path, oracle_payload):
    """A pod without namespace/controller is still counted (no silent loss)."""
    p = copy.deepcopy(oracle_payload)
    orphan = p["data"][1].pop("catalog/web")
    orphan["properties"] = {"cluster": "c1"}
    p["data"][1]["orphan-pod"] = orphan
    ingest.ingest_payload(p, "fixture", db_path=db_path)
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM cost_allocations WHERE namespace='__unallocated__'").fetchone()[0] == 1
    assert conn.execute("SELECT SUM(total_cost) FROM cost_allocations").fetchone()[0] == pytest.approx(3.26)
