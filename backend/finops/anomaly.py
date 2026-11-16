"""Spend-anomaly detection.

  * reference_threshold  (O2 reference): the alert a plain dashboard would raise —
        flag a day if cost > 1.5 x the trailing 7-day average.
  * zscore               (O3 contribution, from Review-2): trailing-window z-score,
        window = 14 days, threshold = 2.5. Uses only *past* days (no leakage), and a
        robust std floor so perfectly flat series don't divide by zero.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import config
from .trends import daily_series

STD_FLOOR_FRAC = 0.02  # std is never treated as smaller than 2 % of the mean


def zscore_flags(y: np.ndarray, window: int, threshold: float) -> list[tuple[int, float, float, float]]:
    out = []
    for i in range(window, len(y)):
        past = y[i - window:i]
        mu = float(past.mean())
        sd = max(float(past.std(ddof=0)), STD_FLOOR_FRAC * abs(mu), 1e-9)
        z = (y[i] - mu) / sd
        if z > threshold:
            out.append((i, z, mu, sd))
    return out


def threshold_flags(y: np.ndarray, ratio: float, window: int = 7) -> list[tuple[int, float, float, float]]:
    out = []
    for i in range(window, len(y)):
        mu = float(y[i - window:i].mean())
        if mu > 0 and y[i] > ratio * mu:
            out.append((i, y[i] / mu, mu, 0.0))
    return out


def detect(conn: sqlite3.Connection, method: str = "zscore", window: int | None = None,
           threshold: float | None = None, store: bool = True) -> list[dict]:
    wide = daily_series(conn, "workload")
    if wide.empty:
        return []
    results = []
    for g in wide.columns:
        y = wide[g].to_numpy()
        if method == "zscore":
            flags = zscore_flags(y, window or config.ANOMALY_WINDOW_DAYS, threshold or config.ANOMALY_Z_THRESHOLD)
        elif method == "reference-threshold":
            flags = threshold_flags(y, threshold or config.REFERENCE_SPIKE_RATIO)
        else:
            raise ValueError(method)
        ns, wl = g.split("/", 1)
        for i, score, mu, sd in flags:
            results.append({"date": wide.index[i], "namespace": ns, "workload": wl, "method": method,
                            "total_cost": round(float(y[i]), 6), "baseline_mean": round(mu, 6),
                            "baseline_std": round(sd, 6), "score": round(float(score), 3)})
    if store:
        conn.execute("DELETE FROM anomalies WHERE method = ?", (method,))
        conn.executemany(
            "INSERT INTO anomalies (date, namespace, workload, method, total_cost, baseline_mean, baseline_std, score) "
            "VALUES (:date,:namespace,:workload,:method,:total_cost,:baseline_mean,:baseline_std,:score)",
            results,
        )
    return results


def evaluate(flags: list[dict], truth: set[tuple[str, str, str]], eval_from: str | None = None) -> dict:
    """Precision / recall / F1 against the planted ground truth (independent oracle)."""
    pred = {(f["date"], f["namespace"], f["workload"]) for f in flags if not eval_from or f["date"] >= eval_from}
    gt = {t for t in truth if not eval_from or t[0] >= eval_from}
    tp = len(pred & gt)
    fp = len(pred - gt)
    fn = len(gt - pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4),
            "false_positives": sorted(pred - gt), "missed": sorted(gt - pred)}


def as_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)
