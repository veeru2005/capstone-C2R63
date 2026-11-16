"""FinOps Cloud-Cost Optimisation Dashboard (CLOUD-04) — core package.

Layers (one-directional data flow):
    opencost / simulator  ->  validation  ->  db (SQLite)
    db  ->  attribution (O1)  ->  trends (O2 reference)
    db  ->  anomaly + forecast (O3)  ->  recommend (O4)
    db  ->  FastAPI (main.py)  ->  React dashboard
"""

__version__ = "0.4.0"
