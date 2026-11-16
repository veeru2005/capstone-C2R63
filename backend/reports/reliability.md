# CLOUD-04 — Reliability baseline (KPI-4, KPI-5, KPI-6)

- KPI-4 recovery rate: **100.0 %**
- KPI-5 error rate: **0.0 %**
- KPI-6 worst p95 latency: **4.58 ms** (in-process, 60-day dataset)

| Fault | Description | Recovered | Note | Time (ms) |
|---|---|---|---|---|
| F1 | OpenCost unreachable (connection refused) | yes | failed run recorded, data intact | 2054.3 |
| F2 | OpenCost timeout (non-routable host) | yes | timeout handled, data intact | 510.2 |
| F3 | Malformed payload (garbage JSON structure) | yes | all rows rejected with reasons | 3.0 |
| F4 | Duplicate replay of a full payload | yes | idempotent upsert, no double-count | 15.2 |
| F5 | Corrupt record (negative cost) inside valid payload | yes | bad row quarantined, rest accepted | 14.2 |
| F6 | 6-day gap in cost history (collector outage) | yes | gaps zero-filled, forecast + recommendations still produced | 14.3 |
| F7 | Recovery: replay after gap | yes | state reconciled to the original totals | 22.0 |

| Endpoint | p50 ms | p95 ms | p99 ms | errors % |
|---|---|---|---|---|
| /health | 1.18 | 1.28 | 1.39 | 0.0 |
| /costs | 2.95 | 3.3 | 21.83 | 0.0 |
| /costs/summary | 1.63 | 1.72 | 1.8 | 0.0 |
| /attribution?by=team | 1.45 | 1.52 | 1.74 | 0.0 |
| /trends?by=team | 4.0 | 4.58 | 7.27 | 0.0 |
| /anomalies | 1.24 | 1.33 | 1.54 | 0.0 |
| /forecast | 1.48 | 1.6 | 1.7 | 0.0 |
| /recommendations | 1.25 | 1.31 | 1.49 | 0.0 |
