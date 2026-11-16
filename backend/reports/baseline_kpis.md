# CLOUD-04 — KPI baseline (O2 reference vs O3/O4 candidate)

Measured: 2026-11-16T07:25:17+00:00

| KPI | O2 reference | O3/O4 candidate | Target |
|---|---|---|---|
| KPI-2 cost-forecast accuracy | 90.608 % (R1-moving-average) | 94.609 % (O3-seasonal-trend) | O3 >= O2 + 3 pp |
| KPI-3 anomaly-detection precision | 38.1 % (cost > 1.5 x 7-day avg) | 72.73 % (z-score, window 14d, threshold 2.5) | O3 >= O2 + 3 pp |
| KPI-1 estimated savings (monthly) | 122.2586 USD/month (naive unused-request waste (upper bound, not actionable)) | 81.3955 USD/month (O4 safe recommendations (p95 x 1.3 headroom, no system deletes)) | — |

Attribution reconciliation: max difference between groupings = 0.0 USD -> PASS

## Forecast backtest (rolling origin, 7-day horizon, last 28 days)

| Model | MAPE % | Accuracy % |
|---|---|---|
| R1-moving-average | 9.392 | 90.608 |
| R2-linear-trend | 10.128 | 89.872 |
| O3-seasonal-trend | 5.391 | 94.609 |

### O2 reference: TP 8 / FP 13 / FN 1 — precision 0.381, recall 0.8889, F1 0.5333
Missed: [('2026-10-21', 'analytics', 'batch-reporter')]

### O3 z-score: TP 8 / FP 3 / FN 1 — precision 0.7273, recall 0.8889, F1 0.8
Missed: [('2026-10-21', 'analytics', 'batch-reporter')]
