"""OpenCost ingestion (O1 / FR-1).

Calls the OpenCost Allocation API:
    GET {OPENCOST_URL}/allocation/compute?window=7d&aggregate=namespace,controller&step=1d

and normalises each allocation into a FOCUS-aligned row:
    date (ChargePeriodStart), namespace (SubAccount), workload (ResourceName),
    total_cost (BilledCost, USD) + cost components + request/usage.

The raw response is always saved before parsing, so every number in the DB can
be traced back to the exact API payload (evidence manifest / provenance).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config

log = logging.getLogger("finops.opencost")

GB = 1024 ** 3


class OpenCostUnavailable(RuntimeError):
    """Raised when OpenCost cannot be reached or returns an unusable payload."""


def fetch_allocation(window: str = "7d", base_url: str | None = None,
                     retries: int | None = None, timeout: float | None = None) -> dict:
    """Fetch daily allocation for every (namespace, controller). Retries with backoff."""
    import requests  # imported lazily so tests that never hit the network don't need it

    url = f"{(base_url or config.OPENCOST_URL).rstrip('/')}/allocation/compute"
    params = {
        "window": window,
        "aggregate": "namespace,controller",
        "step": "1d",
        "accumulate": "false",
        "includeIdle": "true",
        "shareIdle": "false",
    }
    retries = config.OPENCOST_RETRIES if retries is None else retries
    timeout = config.OPENCOST_TIMEOUT_S if timeout is None else timeout
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict) or payload.get("code", 200) != 200 or "data" not in payload:
                raise OpenCostUnavailable(f"unexpected payload: {str(payload)[:200]}")
            return payload
        except Exception as exc:  # noqa: BLE001 — any failure triggers retry
            last_err = exc
            log.warning("OpenCost attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise OpenCostUnavailable(f"OpenCost unreachable at {url}: {last_err}")


def save_raw(payload: dict, run_id: str, raw_dir: Path) -> tuple[Path, str]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True).encode()
    path = raw_dir / f"{run_id}.json"
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def _day(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()


def normalise(payload: dict, team_map: dict | None = None) -> tuple[list[dict], list[tuple[str, dict]]]:
    """Convert an OpenCost allocation payload to rows. Returns (rows, unparseable)."""
    team_map = team_map or {}
    rows, bad = [], []
    sets = payload.get("data") or []
    if isinstance(sets, dict):  # accumulate=true returns a single set
        sets = [sets]
    for alloc_set in sets:
        if not isinstance(alloc_set, dict):
            bad.append(("allocation set is not an object", {"raw": str(alloc_set)[:200]}))
            continue
        for name, a in alloc_set.items():
            try:
                rows.append(_to_row(name, a, team_map))
            except Exception as exc:  # noqa: BLE001
                bad.append((f"parse error: {exc}", {"name": name, "raw": str(a)[:500]}))
    return rows, bad


def _to_row(name: str, a: dict, team_map: dict) -> dict:
    props = a.get("properties") or {}
    labels = props.get("labels") or {}
    if name in ("__idle__", "__unallocated__") or name.endswith("__idle__"):
        namespace, workload, kind = "__idle__", "__idle__", "idle"
    else:
        namespace = props.get("namespace") or (name.split("/")[0] if "/" in name else "__unallocated__")
        workload = props.get("controller") or (name.split("/", 1)[1] if "/" in name else name)
        kind = props.get("controllerKind") or "unknown"
        if workload.startswith("__unallocated__"):
            workload = "__unallocated__"
    team = labels.get("team") or labels.get("app_kubernetes_io_part_of") or team_map.get(namespace, "unassigned")
    if namespace == "__idle__":
        team = "__idle__"

    cpu_cost = float(a.get("cpuCost", 0)) + float(a.get("cpuCostAdjustment", 0) or 0)
    ram_cost = float(a.get("ramCost", 0)) + float(a.get("ramCostAdjustment", 0) or 0)
    pv_cost = float(a.get("pvCost", 0)) + float(a.get("pvCostAdjustment", 0) or 0)
    net_cost = float(a.get("networkCost", 0)) + float(a.get("networkCostAdjustment", 0) or 0)
    total = float(a["totalCost"])
    other = max(round(total - (cpu_cost + ram_cost + pv_cost + net_cost), 9), 0.0)

    eff = a.get("totalEfficiency")
    return {
        "date": _day(a.get("start") or a["window"]["start"]),
        "cluster": props.get("cluster") or "cluster-one",
        "namespace": namespace,
        "workload": workload,
        "workload_kind": kind,
        "team": team,
        "cpu_request": _f(a.get("cpuCoreRequestAverage")),
        "cpu_usage": _f(a.get("cpuCoreUsageAverage")),
        "ram_request_gb": _f(a.get("ramByteRequestAverage"), GB),
        "ram_usage_gb": _f(a.get("ramByteUsageAverage"), GB),
        "cpu_cost": cpu_cost,
        "ram_cost": ram_cost,
        "pv_cost": pv_cost,
        "network_cost": net_cost,
        "other_cost": other,
        "total_cost": total,
        # OpenCost reports efficiency as a fraction; we store percent.
        "total_efficiency": round(float(eff) * 100, 4) if eff is not None else None,
    }


def _f(v, div: float = 1.0):
    return None if v is None else float(v) / div


def fetch_live(window: str = "10m", base_url: str | None = None, timeout: float = 5.0) -> list[dict]:
    """Current state of every running workload (not stored). Used by the dashboard's
    Live panel: deploy a new pod and it appears here within ~1-2 minutes."""
    import requests

    url = f"{(base_url or config.OPENCOST_URL).rstrip('/')}/allocation/compute"
    params = {"window": window, "aggregate": "namespace,controller", "accumulate": "true"}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise OpenCostUnavailable(str(exc)) from exc
    rows, _ = normalise(payload, config.load_team_map())
    out = []
    for r in rows:
        if r["namespace"] == "__idle__":
            continue
        req, use = r.get("cpu_request") or 0.0, r.get("cpu_usage") or 0.0
        eff = r.get("total_efficiency")
        if eff is None and req:
            eff = use / req * 100
        status = "IDLE" if (eff or 0) < config.IDLE_EFFICIENCY_PCT else (
            "OVER-PROVISIONED" if (eff or 0) < config.RIGHTSIZE_EFFICIENCY_PCT else "OK")
        out.append({**r, "efficiency_pct": round(eff, 2) if eff is not None else None, "status": status})
    return sorted(out, key=lambda r: r["total_cost"], reverse=True)
