"""Live monitor: spike / growth detection on 2-minute series (finops/live.py)."""

import numpy as np

from finops import live


def _tl(rates_by_name):
    series = []
    for name, rates in rates_by_name.items():
        pts = [{"t": f"2026-11-16T08:{2 * i:02d}:00Z", "rate": r, "cpu_request": 0.1, "cpu_usage": 0.05}
               for i, r in enumerate(rates)]
        series.append({"namespace": "demo", "workload": name, "team": "demo-team", "points": pts})
    return {"start": "s", "end": "e", "step_minutes": 2, "series": series}


def test_spike_detected_and_flat_not():
    rng = np.random.default_rng(0)
    flat = list(0.01 * rng.normal(1, 0.02, 20))
    spike = flat[:16] + [0.06, 0.06, 0.06, 0.06]  # replicas scaled 1 -> 6
    res = live.analyse(_tl({"steady": flat, "spiky": spike}))
    by = {w["workload"]: w for w in res["workloads"]}
    assert by["spiky"]["status"] == "SPIKE"
    assert by["spiky"]["ratio"] > 4
    assert by["steady"]["status"] is None
    assert [e["workload"] for e in res["events"]] == ["spiky"]
    assert res["workloads"][0]["workload"] == "spiky"  # alarms first


def test_resolved_after_spike_ends():
    rng = np.random.default_rng(1)
    base = list(0.01 * rng.normal(1, 0.02, 14))
    series = base + [0.06, 0.06, 0.06] + [0.01, 0.01, 0.01, 0.01]  # spike, then fixed
    res = live.analyse(_tl({"fixed": series}))
    w = res["workloads"][0]
    assert w["status"] == "RESOLVED"
    ev = res["events"][0]
    assert ev["type"] == "RESOLVED" and ev["peak_ratio"] > 4
    assert ev["since"] == w["series"][14]["t"] and ev["resolved_at"] == w["series"][17]["t"]


def test_growth_detected_and_forecast_rises():
    ramp = [0.01 + 0.002 * i for i in range(20)]  # steady climb
    res = live.analyse(_tl({"growing": ramp}))
    w = res["workloads"][0]
    assert w["status"] == "GROWING"
    assert w["forecast"][-1]["rate"] > w["latest_rate"]
    assert len(w["forecast"]) == live.FORECAST_POINTS


def test_short_series_is_safe():
    res = live.analyse(_tl({"new": [0.01, 0.01]}))
    w = res["workloads"][0]
    assert w["status"] is None and all(f["rate"] == 0.01 for f in w["forecast"])
