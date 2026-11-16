"""Deterministic sandbox simulator (CLOUD-04 'fallback': isolated local cluster or
deterministic simulator that preserves workload shape, failure semantics and telemetry).

Why: a laptop kind cluster only has a few days of OpenCost history and never produces
real cost spikes, so the detector / forecaster cannot be evaluated on it. The simulator
produces N days of history *in the exact OpenCost Allocation API format*, so the same
normaliser + validator path is used as for live data, and a ground-truth file of planted
anomalies acts as the independent oracle.

Workload profiles mirror the ones deployed on the kind cluster (k8s/workloads.yaml):
overprovisioned-app, rightsized-app, idle-app, plus a few realistic services.
Cost model = OpenCost's: allocation = max(request, usage) x hours x unit price.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config

GB = 1024 ** 3


@dataclass(frozen=True)
class Workload:
    namespace: str
    name: str
    team: str
    cpu_req: float        # cores
    ram_req_gb: float
    cpu_use: float        # mean cores used
    ram_use_gb: float
    weekly_amp: float = 0.0   # weekday/weekend seasonality on usage (0..1)
    growth_per_day: float = 0.0  # fractional growth of usage per day
    replicas: int = 1
    kind: str = "deployment"
    hpa: bool = False            # HorizontalPodAutoscaler: replica count follows load
    load_noise: float = 0.06     # day-to-day load noise (std, fraction)
    job_weekday: int = -1        # weekly batch job day (0=Mon), -1 = none
    job_mult: float = 1.0        # cost multiplier on the batch-job day (legitimate, NOT an anomaly)


WORKLOADS: tuple[Workload, ...] = (
    Workload("payments", "api-gateway", "payments-team", 0.50, 1.0, 0.38, 0.80, weekly_amp=0.35, replicas=3, hpa=True, load_noise=0.12),
    Workload("payments", "payment-service", "payments-team", 0.75, 1.5, 0.55, 1.10, weekly_amp=0.30, growth_per_day=0.004, replicas=2, hpa=True, load_noise=0.10),
    Workload("catalog", "overprovisioned-app", "catalog-team", 1.00, 2.0, 0.0023, 0.06, replicas=2),
    Workload("catalog", "rightsized-app", "catalog-team", 0.10, 0.25, 0.08, 0.20, weekly_amp=0.20),
    Workload("catalog", "search-service", "catalog-team", 0.50, 2.0, 0.30, 1.60, weekly_amp=0.25, replicas=2, hpa=True, load_noise=0.15),
    Workload("analytics", "idle-app", "data-team", 0.75, 1.0, 0.004, 0.02),
    Workload("analytics", "batch-reporter", "data-team", 0.25, 0.5, 0.20, 0.40, weekly_amp=0.60, job_weekday=0, job_mult=2.5),
    Workload("kube-system", "metrics-server", "platform-team", 0.10, 0.2, 0.003, 0.03),
    Workload("monitoring", "prometheus-server", "platform-team", 0.20, 1.0, 0.15, 0.90),
    Workload("opencost", "opencost", "platform-team", 0.10, 0.25, 0.02, 0.15),
)

# Planted anomalies: (day index, namespace, workload, cost multiplier, label).
# Deliberately mixed sizes so the evaluation is honest — Review-2 limitation #2
# ("spikes were all 3.8-4.5x, too easy") is addressed by including 1.6x-2x spikes.
PLANTED = (
    (25, "catalog", "overprovisioned-app", 4.2, "large"),
    (40, "analytics", "idle-app", 3.8, "large"),
    (50, "catalog", "overprovisioned-app", 4.5, "large"),
    (58, "payments", "payment-service", 2.0, "medium"),
    (63, "catalog", "search-service", 1.8, "medium"),
    (71, "payments", "api-gateway", 2.2, "medium"),
    (79, "analytics", "batch-reporter", 1.6, "small"),   # a Wednesday, not the Monday job
    (84, "catalog", "rightsized-app", 1.7, "small"),
    (87, "payments", "api-gateway", 1.5, "small"),
)


def generate(days: int = 90, seed: int = 42, end: date | None = None,
             cluster: str = "cluster-one") -> tuple[dict, list[dict]]:
    """Return (opencost_payload, ground_truth_rows)."""
    rng = np.random.default_rng(seed)
    end = end or date(2026, 10, 31)
    start = end - timedelta(days=days - 1)
    planted = {(d, ns, wl): (m, lbl) for d, ns, wl, m, lbl in PLANTED if d < days}

    sets = []
    for i in range(days):
        day = start + timedelta(days=i)
        weekend = day.weekday() >= 5
        alloc_set = {}
        total_alloc_cpu = total_alloc_ram = 0.0
        for w in WORKLOADS:
            season = (1 - w.weekly_amp) if weekend else 1.0
            growth = (1 + w.growth_per_day) ** i
            load = max(season * growth * rng.normal(1.0, w.load_noise), 0.05)
            noise_r = rng.normal(1.0, 0.03)
            if w.hpa:
                # HPA keeps per-pod utilisation roughly constant; the *daily average*
                # replica count follows load (fractional because it changes within the day).
                reps = max(w.replicas * load, 1.0)
                per_pod = rng.normal(1.0, 0.05)
                cpu_use, ram_use = w.cpu_use * reps * per_pod, w.ram_use_gb * reps * noise_r
            else:
                reps = float(w.replicas)
                cpu_use = w.cpu_use * load * reps
                ram_use = max(w.ram_use_gb * min(load, 1.5) * noise_r, 0.0) * reps
            if w.job_weekday == day.weekday():
                reps *= w.job_mult
                cpu_use, ram_use = cpu_use * w.job_mult, ram_use * w.job_mult
            cpu_req = w.cpu_req * reps
            ram_req = w.ram_req_gb * reps

            mult, _ = planted.get((i, w.namespace, w.name), (1.0, None))
            if mult != 1.0:
                # a spike = a runaway scale-out: more replicas requested AND used
                cpu_req, ram_req = cpu_req * mult, ram_req * mult
                cpu_use, ram_use = cpu_use * mult, ram_use * mult

            cpu_alloc, ram_alloc = max(cpu_req, cpu_use), max(ram_req, ram_use)
            total_alloc_cpu += cpu_alloc
            total_alloc_ram += ram_alloc
            cpu_cost = round(cpu_alloc * 24 * config.CPU_PRICE_PER_CORE_HOUR, 6)
            ram_cost = round(ram_alloc * 24 * config.RAM_PRICE_PER_GB_HOUR, 6)
            pv_cost = round(0.0008 * w.replicas if w.namespace in ("monitoring", "payments") else 0.0, 6)
            total = round(cpu_cost + ram_cost + pv_cost, 6)
            cpu_eff = cpu_use / cpu_alloc if cpu_alloc else 0
            ram_eff = ram_use / ram_alloc if ram_alloc else 0
            tot_eff = (cpu_eff * cpu_cost + ram_eff * ram_cost) / (cpu_cost + ram_cost)
            name = f"{w.namespace}/{w.name}"
            alloc_set[name] = _alloc(name, day, cluster, w, cpu_req, cpu_use, ram_req, ram_use,
                                     cpu_cost, ram_cost, pv_cost, total, tot_eff)

        # Cluster idle: 2 nodes x 2 cores x 4 GB minus what is allocated
        idle_cpu = max(4.0 - total_alloc_cpu, 0.4)
        idle_ram = max(8.0 - total_alloc_ram, 0.8)
        ic = round(idle_cpu * 24 * config.CPU_PRICE_PER_CORE_HOUR, 6)
        ir = round(idle_ram * 24 * config.RAM_PRICE_PER_GB_HOUR, 6)
        alloc_set["__idle__"] = {
            "name": "__idle__", "properties": {"cluster": cluster},
            "window": _win(day), "start": _win(day)["start"], "end": _win(day)["end"],
            "cpuCost": ic, "ramCost": ir, "pvCost": 0.0, "networkCost": 0.0,
            "totalCost": round(ic + ir, 6), "totalEfficiency": 0.0,
        }
        sets.append(alloc_set)

    truth = [
        {"date": (start + timedelta(days=d)).isoformat(), "namespace": ns, "workload": wl,
         "multiplier": m, "size": lbl}
        for (d, ns, wl), (m, lbl) in sorted(planted.items())
    ]
    return {"code": 200, "status": "success", "data": sets}, truth


def _win(day: date) -> dict:
    s = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    e = s + timedelta(days=1)
    return {"start": s.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": e.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _alloc(name, day, cluster, w, cpu_req, cpu_use, ram_req, ram_use,
           cpu_cost, ram_cost, pv_cost, total, eff) -> dict:
    win = _win(day)
    return {
        "name": name,
        "properties": {
            "cluster": cluster, "namespace": w.namespace, "controller": w.name,
            "controllerKind": w.kind, "labels": {"team": w.team, "app": w.name},
        },
        "window": win, "start": win["start"], "end": win["end"],
        "cpuCoreRequestAverage": round(cpu_req, 6),
        "cpuCoreUsageAverage": round(cpu_use, 6),
        "ramByteRequestAverage": round(ram_req * GB),
        "ramByteUsageAverage": round(ram_use * GB),
        "cpuCost": cpu_cost, "ramCost": ram_cost, "pvCost": pv_cost,
        "networkCost": 0.0, "totalCost": total, "totalEfficiency": round(eff, 6),
    }


def write_ground_truth(truth: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["date", "namespace", "workload", "multiplier", "size"])
        wr.writeheader()
        wr.writerows(truth)


def read_ground_truth(path: Path) -> set[tuple[str, str, str]]:
    with path.open() as f:
        return {(r["date"], r["namespace"], r["workload"]) for r in csv.DictReader(f)}
