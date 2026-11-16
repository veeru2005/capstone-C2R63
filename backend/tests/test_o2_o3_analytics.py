"""O2 trends, O3 anomaly + forecast, O4 recommendation safety, simulator reproducibility."""

import numpy as np
import pytest

from finops import anomaly, forecast, ingest, recommend, simulator, trends
from finops.db import connect


@pytest.fixture
def sim_db(db_path):
    payload, truth = simulator.generate(days=90, seed=42)
    ingest.ingest_payload(payload, "simulator", db_path=db_path)
    return db_path, truth


def test_simulator_is_deterministic():
    a, ta = simulator.generate(days=30, seed=1)
    b, tb = simulator.generate(days=30, seed=1)
    c, _ = simulator.generate(days=30, seed=2)
    assert a == b and ta == tb and a != c


def test_linear_slope_and_projections():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert trends.linear_slope(y) == pytest.approx(1.0)
    assert trends.project_linear(y, 2).tolist() == pytest.approx([5.0, 6.0])
    assert trends.project_moving_average(np.array([2.0] * 7), 3).tolist() == [2.0, 2.0, 2.0]


def test_trend_summary_shapes(sim_db):
    conn = connect(sim_db[0])
    t = trends.trend_summary(conn, "team")
    assert t["days"] == 90 and len(t["series"]) == 90
    assert {g["key"] for g in t["groups"]} == {"payments-team", "catalog-team", "data-team", "platform-team"}
    s = t["series"][-1]
    assert s["total"] == pytest.approx(sum(s[g["key"]] for g in t["groups"]), rel=1e-6)


def test_zscore_hand_example():
    # 14 days alternating 10/12 -> mean 11, std 1 ; day 15 = 20 -> z = 9
    y = np.array([10.0, 12.0] * 7 + [20.0])
    flags = anomaly.zscore_flags(y, 14, 2.5)
    assert len(flags) == 1 and flags[0][0] == 14 and flags[0][1] == pytest.approx(9.0)


def test_detectors_against_planted_truth(sim_db):
    db_path, truth = sim_db
    gt = {(t["date"], t["namespace"], t["workload"]) for t in truth}
    conn = connect(db_path)
    z = anomaly.evaluate(anomaly.detect(conn, "zscore", store=False), gt)
    ref = anomaly.evaluate(anomaly.detect(conn, "reference-threshold", store=False), gt)
    assert z["recall"] >= 0.75
    assert z["precision"] > ref["precision"]  # O3 must beat the O2 rule on precision


def test_backtest_runs_all_models(sim_db):
    bt = forecast.backtest(connect(sim_db[0]), horizon=7, test_days=28)
    assert {"R1-moving-average", "R2-linear-trend", "O3-seasonal-trend"} <= set(bt)
    for v in bt.values():
        assert 0 <= v["accuracy_pct"] <= 100 and v["origins"] >= 3


def test_recommendations_are_safe(sim_db):
    conn = connect(sim_db[0])
    recs = recommend.generate(conn)
    by = {(r["namespace"], r["workload"]): r for r in recs}
    assert by[("catalog", "overprovisioned-app")]["category"] == "IDLE"
    assert by[("analytics", "idle-app")]["category"] == "IDLE"
    # NT-3: system components are never recommended for deletion
    for r in recs:
        if r["namespace"] in ("kube-system", "monitoring", "opencost"):
            assert r["category"] != "IDLE"
        assert 0 <= r["est_monthly_savings"] <= r["current_monthly_cost"] + 1e-9
    # Safe savings can never exceed the naive upper bound
    assert sum(r["est_monthly_savings"] for r in recs if r["category"] != "COMMITMENT") <= recommend.naive_waste_estimate(conn) + 1e-6
