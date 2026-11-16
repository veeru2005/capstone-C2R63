"""Cost forecasting + backtest harness.

Models:
  R1-moving-average, R2-linear-trend   -> O2 reference (from trends.py)
  O3-seasonal-trend                    -> O3 candidate: linear trend on de-seasonalised,
                                          spike-cleaned history x weekly profile.
                                          Pure numpy, so it runs everywhere (Prophet does not
                                          install on Python 3.14). Prophet is used automatically
                                          when importable, as 'O3-prophet'.

Accuracy = 100 - MAPE (%), measured by rolling-origin backtest on the last N days,
so every model is evaluated on exactly the same evidence (AC-4).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import numpy as np

from .anomaly import zscore_flags
from .trends import REFERENCE_METHODS, daily_series


def _clean_spikes(y: np.ndarray, window: int = 14, z: float = 2.5) -> np.ndarray:
    """Replace detected spikes by their trailing mean so one incident doesn't bend the forecast."""
    y = y.astype(float).copy()
    for i, _, mu, _ in zscore_flags(y, window, z):
        y[i] = mu
    return y


def project_seasonal_trend(history: np.ndarray, horizon: int, start_weekday: int = 0,
                           window: int = 56) -> np.ndarray:
    h = _clean_spikes(history[-window:])
    n = len(h)
    if n < 14:
        return REFERENCE_METHODS["R1-moving-average"](history, horizon)
    wd = (start_weekday + np.arange(n)) % 7
    overall = h.mean() or 1e-9
    profile = np.array([h[wd == d].mean() / overall if np.any(wd == d) else 1.0 for d in range(7)])
    profile = np.where(profile > 0, profile, 1.0)
    deseason = h / profile[wd]
    x = np.arange(n, dtype=float)
    a, b = np.polyfit(x[-28:], deseason[-28:], 1)
    fut = np.arange(n, n + horizon, dtype=float)
    fut_wd = (start_weekday + n + np.arange(horizon)) % 7
    return np.maximum((a * fut + b) * profile[fut_wd], 0.0)


def _prophet_available() -> bool:
    try:
        import prophet  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def project_prophet(history: np.ndarray, horizon: int, start_date: date) -> np.ndarray:
    import pandas as pd
    from prophet import Prophet

    ds = pd.date_range(start_date, periods=len(history), freq="D")
    m = Prophet(weekly_seasonality=True, daily_seasonality=False, yearly_seasonality=False)
    m.fit(pd.DataFrame({"ds": ds, "y": history}))
    fut = m.make_future_dataframe(periods=horizon)
    return np.maximum(m.predict(fut)["yhat"].to_numpy()[-horizon:], 0.0)


def models() -> dict:
    ms = {
        "R1-moving-average": lambda h, k, d0: REFERENCE_METHODS["R1-moving-average"](h, k),
        "R2-linear-trend": lambda h, k, d0: REFERENCE_METHODS["R2-linear-trend"](h, k),
        "O3-seasonal-trend": lambda h, k, d0: project_seasonal_trend(h, k, d0.weekday()),
    }
    if _prophet_available():
        ms["O3-prophet"] = lambda h, k, d0: project_prophet(h, k, d0)
    return ms


def mape(actual: np.ndarray, pred: np.ndarray) -> float:
    mask = actual > 1e-9
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs(actual[mask] - pred[mask]) / actual[mask]) * 100)


def backtest(conn: sqlite3.Connection, by: str = "workload", horizon: int = 7,
             test_days: int = 28, min_train: int = 28) -> dict:
    """Rolling-origin backtest. For each group and each origin in the last `test_days`
    days (step = horizon), train on everything before the origin and forecast `horizon`
    days. Returns per-model MAPE and accuracy (= 100 - MAPE, floored at 0)."""
    wide = daily_series(conn, by)
    if wide.empty:
        return {}
    d0 = date.fromisoformat(wide.index[0])
    n = len(wide)
    origins = [o for o in range(max(min_train, n - test_days), n - horizon + 1, horizon)]
    if not origins:  # not enough history yet (e.g. a fresh live cluster) -> no KPI-2
        return {}
    out: dict = {}
    for name, fn in models().items():
        errs, per_group = [], {}
        for g in wide.columns:
            y = wide[g].to_numpy()
            if y.sum() == 0:
                continue
            g_errs = []
            for o in origins:
                pred = fn(y[:o], horizon, d0)
                g_errs.append(mape(y[o:o + horizon], pred))
            per_group[g] = round(float(np.mean(g_errs)), 3)
            errs.extend(g_errs)
        m = float(np.mean(errs)) if errs else float("nan")
        out[name] = {"mape_pct": round(m, 3), "accuracy_pct": round(max(100 - m, 0), 3),
                     "origins": len(origins), "horizon": horizon, "per_group_mape": per_group}
    return out


def forecast_and_store(conn: sqlite3.Connection, horizon: int = 14, model: str = "O3-seasonal-trend") -> int:
    wide = daily_series(conn, "workload")
    if wide.empty:
        return 0
    fn = models()[model]
    d0 = date.fromisoformat(wide.index[0])
    last = date.fromisoformat(wide.index[-1])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("DELETE FROM forecasts WHERE model = ?", (model,))
    rows = []
    for g in wide.columns:
        y = wide[g].to_numpy()
        pred = fn(y, horizon, d0)
        # simple uncertainty band: +/- 1.96 x std of recent residuals around the 7-day mean
        resid_sd = float(np.std(y[-28:] - np.convolve(y[-34:], np.ones(7) / 7, "valid")[-28:])) if len(y) >= 34 else float(np.std(y))
        ns, wl = g.split("/", 1)
        for k, v in enumerate(pred, start=1):
            rows.append((model, ns, wl, (last + timedelta(days=k)).isoformat(), float(v),
                         max(float(v) - 1.96 * resid_sd, 0.0), float(v) + 1.96 * resid_sd, now))
    conn.executemany(
        "INSERT INTO forecasts (model, namespace, workload, target_date, value, lower, upper, generated_at) "
        "VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)
