"""Live monitor: minute-level spike detection and short-term forecast.

The daily pipeline (anomaly.py / forecast.py) needs weeks of history. For a live
demo we also watch the last hour at 2-minute resolution, so a container that
suddenly costs more is flagged within a few minutes:

  cost rate (per hour) = max(cpu request, cpu usage) x CPU price
                       + max(ram request, ram usage) x RAM price      (OpenCost's own formula)

  SPIKE    latest rate > 1.5 x its own baseline AND z-score > 3
           (baseline = the previous 8 points, i.e. ~16 minutes)
  GROWING  steady rise: linear-fit slope > 30 % of the mean per hour, R^2 > 0.6
  forecast linear trend on the last 10 points, projected 30 minutes ahead
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from . import config, opencost

GB = 1024 ** 3
STEP_MIN = 2
BASELINE_POINTS = 8
MIN_BASELINE = 4
SPIKE_RATIO = 1.5
SPIKE_Z = 3.0
GROWTH_PCT_PER_HOUR = 30.0
GROWTH_R2 = 0.6
FORECAST_POINTS = 15  # 15 x 2 min = 30 minutes
MIN_ALERT_RATE = 0.002  # USD/hour (~0.06 CPU): below this, changes are noise


def _floor(dt: datetime, minutes: int) -> datetime:
    return dt.replace(second=0, microsecond=0, minute=dt.minute - dt.minute % minutes)


def fetch_timeline(minutes: int = 60, base_url: str | None = None, timeout: float = 8.0) -> dict:
    import requests

    end = _floor(datetime.now(timezone.utc), STEP_MIN)
    start = end - timedelta(minutes=minutes)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    url = f"{(base_url or config.OPENCOST_URL).rstrip('/')}/allocation/compute"
    params = {"window": f"{start.strftime(fmt)},{end.strftime(fmt)}", "aggregate": "namespace,controller",
              "step": f"{STEP_MIN}m", "accumulate": "false"}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        sets = resp.json().get("data") or []
    except Exception as exc:  # noqa: BLE001
        raise opencost.OpenCostUnavailable(str(exc)) from exc

    team_map = config.load_team_map()
    series: dict[tuple[str, str], dict] = {}
    for s in sets:
        if not isinstance(s, dict):
            continue
        for name, a in s.items():
            if name.startswith("__") or not isinstance(a, dict) or float(a.get("minutes") or 0) < 0.5:
                continue
            props = a.get("properties") or {}
            ns, wl = props.get("namespace"), props.get("controller")
            if not ns or not wl:
                continue
            cpu_req, cpu_use = float(a.get("cpuCoreRequestAverage") or 0), float(a.get("cpuCoreUsageAverage") or 0)
            ram_req, ram_use = float(a.get("ramByteRequestAverage") or 0) / GB, float(a.get("ramByteUsageAverage") or 0) / GB
            rate = max(cpu_req, cpu_use) * config.CPU_PRICE_PER_CORE_HOUR + max(ram_req, ram_use) * config.RAM_PRICE_PER_GB_HOUR
            labels = props.get("labels") or {}
            key = (ns, wl)
            entry = series.setdefault(key, {
                "namespace": ns, "workload": wl,
                "team": labels.get("team") or team_map.get(ns) or labels.get("app_kubernetes_io_part_of") or "unassigned",
                "points": []})
            entry["points"].append({"t": a["window"]["start"], "rate": rate, "cpu_request": cpu_req, "cpu_usage": cpu_use})
    for e in series.values():
        e["points"].sort(key=lambda p: p["t"])
    return {"start": start.isoformat(), "end": end.isoformat(), "step_minutes": STEP_MIN, "series": list(series.values())}


def _spikes(rates: np.ndarray) -> list[tuple[int, float, float, float]]:
    """Baseline = the last BASELINE_POINTS *normal* points, so a spike that lasts
    (e.g. replicas scaled up and left there) keeps being reported as a spike."""
    out, normal = [], []
    for i, r in enumerate(rates):
        if len(normal) >= MIN_BASELINE:
            base = np.array(normal[-BASELINE_POINTS:])
            mu = float(base.mean())
            sd = max(float(base.std()), 0.05 * mu, 1e-12)
            z = (r - mu) / sd
            if mu > 0 and r >= SPIKE_RATIO * mu and z >= SPIKE_Z:
                out.append((i, float(z), float(r / mu), mu))
                continue
        normal.append(float(r))
    return out


def analyse(tl: dict) -> dict:
    workloads, events = [], []
    step_h = STEP_MIN / 60
    for e in tl["series"]:
        pts = e["points"]
        if not pts:
            continue
        rates = np.array([p["rate"] for p in pts])
        spikes = _spikes(rates)
        spike_idx = {i for i, *_ in spikes}
        for i, p in enumerate(pts):
            p["anomaly"] = i in spike_idx

        # baseline = average of the most recent normal (non-spike) points
        latest = float(rates[-1])
        normal = [float(r) for i, r in enumerate(rates) if i not in spike_idx]
        baseline = float(np.mean(normal[-BASELINE_POINTS:])) if normal else latest

        # growth: slope over the last 10 points, as % of the mean per hour
        # trend + forecast ignore spike points (replaced by the normal level), so one incident
        # neither looks like "growth" nor bends the forecast after it has been fixed
        clean = rates.copy()
        for i in spike_idx:
            clean[i] = baseline
        tail = clean[-10:]
        growth, r2 = 0.0, 0.0
        if len(tail) >= 5 and tail.mean() > 0:
            x = np.arange(len(tail), dtype=float)
            a, b = np.polyfit(x, tail, 1)
            fit = a * x + b
            ss_tot = float(((tail - tail.mean()) ** 2).sum())
            r2 = 1 - float(((tail - fit) ** 2).sum()) / ss_tot if ss_tot > 0 else 0.0
            growth = a / step_h / tail.mean() * 100
        else:
            a, b = 0.0, latest

        # forecast next 30 min: linear trend (flat if too little data); never below 0
        fc_start = datetime.fromisoformat(pts[-1]["t"].replace("Z", "+00:00"))
        n = len(tail)
        forecast = [{"t": (fc_start + timedelta(minutes=STEP_MIN * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "rate": max(float(a * (n - 1 + k) + b), 0.0) if n >= 5 else latest}
                    for k in range(1, FORECAST_POINTS + 1)]

        # active only while the newest point is still abnormal; otherwise it is resolved
        recent_spike = (len(rates) - 1) in spike_idx
        if recent_spike:
            # a fresh jump: a straight line through pre-spike points would wrongly predict a drop,
            # so assume the new level continues until someone fixes it
            forecast = [{**f, "rate": latest} for f in forecast]
        # the most recent run of consecutive spike points = the current / last incident
        ep_start = ep_end = None
        if spike_idx:
            ep_end = max(spike_idx)
            ep_start = ep_end
            while ep_start - 1 in spike_idx:
                ep_start -= 1
        peak_ratio = (max(float(rates[i]) for i in range(ep_start, ep_end + 1)) / baseline
                      if ep_end is not None and baseline > 0 else None)

        status = None
        quiet = e["namespace"] in config.SYSTEM_NAMESPACES  # never alert on Kubernetes' own pods
        if quiet:
            pass
        elif recent_spike and latest >= MIN_ALERT_RATE:
            status = "SPIKE"
        elif ep_end is not None and max(float(rates[ep_end]), baseline) >= MIN_ALERT_RATE:
            status = "RESOLVED"  # spiked earlier in the window, back to normal now
        elif growth >= GROWTH_PCT_PER_HOUR and r2 >= GROWTH_R2 and latest >= MIN_ALERT_RATE:
            status = "GROWING"
        w = {**{k: e[k] for k in ("namespace", "workload", "team")},
             "status": status, "latest_rate": latest, "baseline_rate": baseline,
             "ratio": latest / baseline if baseline > 0 else None,
             "growth_pct_per_hour": round(float(growth), 1), "trend_r2": round(float(r2), 2),
             "next_30min_cost": float(sum(f["rate"] for f in forecast) * step_h),
             "projected_day_cost": latest * 24,
             "series": pts, "forecast": forecast}
        workloads.append(w)
        base_ev = {"namespace": e["namespace"], "workload": e["workload"]}
        if status == "SPIKE":
            events.append({"type": "SPIKE", **base_ev, "ratio": w["ratio"], "peak_ratio": peak_ratio,
                           "since": pts[ep_start]["t"]})
        elif status == "RESOLVED":
            events.append({"type": "RESOLVED", **base_ev, "peak_ratio": peak_ratio, "since": pts[ep_start]["t"],
                           "resolved_at": pts[min(ep_end + 1, len(pts) - 1)]["t"]})
        elif status == "GROWING":
            events.append({"type": "GROWING", **base_ev, "growth_pct_per_hour": w["growth_pct_per_hour"]})
    order = {"SPIKE": 0, "GROWING": 1, "RESOLVED": 2}
    events.sort(key=lambda ev: order[ev["type"]])
    workloads.sort(key=lambda w: (order.get(w["status"], 3), -w["latest_rate"]))
    return {**{k: tl[k] for k in ("start", "end", "step_minutes")}, "events": events, "workloads": workloads}
