"""Central configuration. Every value can be overridden with an environment variable
so the same code runs on a laptop (kind), in Docker, or against a real cluster."""

import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("FINOPS_DB_PATH", BACKEND_DIR / "finops.db"))
FIXTURE_DIR = BACKEND_DIR / "fixtures"
REPORT_DIR = BACKEND_DIR / "reports"

# OpenCost API (exposed via: kubectl port-forward -n opencost service/opencost 9003:9003)
OPENCOST_URL = os.getenv("OPENCOST_URL", "http://localhost:9003")
OPENCOST_TIMEOUT_S = float(os.getenv("OPENCOST_TIMEOUT_S", "10"))
OPENCOST_RETRIES = int(os.getenv("OPENCOST_RETRIES", "3"))

# OpenCost default on-prem / kind pricing (USD per hour). Used by the simulator so
# simulated costs are on the same scale as a real kind cluster running OpenCost.
CPU_PRICE_PER_CORE_HOUR = float(os.getenv("CPU_PRICE_PER_CORE_HOUR", "0.031611"))
RAM_PRICE_PER_GB_HOUR = float(os.getenv("RAM_PRICE_PER_GB_HOUR", "0.004237"))

BILLING_CURRENCY = "USD"

# Data older than this is considered stale -> API reports "degraded"
STALE_AFTER_HOURS = float(os.getenv("STALE_AFTER_HOURS", "36"))

# Anomaly detector (O3) parameters — frozen here so reference and candidate
# are always compared under the same configuration (AC-4).
ANOMALY_WINDOW_DAYS = int(os.getenv("ANOMALY_WINDOW_DAYS", "14"))
ANOMALY_Z_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.5"))
REFERENCE_SPIKE_RATIO = 1.5  # O2 reference alert rule: cost > 1.5 x 7-day average

# Recommendation thresholds (O4)
IDLE_EFFICIENCY_PCT = 5.0       # below this -> IDLE candidate
RIGHTSIZE_EFFICIENCY_PCT = 50.0  # below this -> RIGHT-SIZE candidate
RIGHTSIZE_HEADROOM = 1.3         # recommended request = p95 usage x headroom
COMMITMENT_MIN_DAYS = 30         # need this many days of stable spend
COMMITMENT_MAX_CV = 0.15         # coefficient of variation for "stable"
COMMITMENT_DISCOUNT = 0.30       # typical 1-year committed-use discount

SYSTEM_NAMESPACES = {"kube-system", "opencost", "monitoring", "prometheus-system", "local-path-storage"}

# namespace -> team mapping, used when a workload has no `team` label.
_TEAM_MAP_FILE = BACKEND_DIR / "config" / "teams.json"


def load_team_map() -> dict:
    if _TEAM_MAP_FILE.exists():
        return json.loads(_TEAM_MAP_FILE.read_text())
    return {}
