#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  FinOps Cloud-Cost Optimisation Dashboard (CLOUD-04) — ONE command to run it.
#
#   ./start.sh            Demo mode: 90 days of simulated cluster data. No Docker needed.
#   ./start.sh live       Live mode: real kind cluster + OpenCost, auto-refresh every 2 min.
#   ./start.sh setup      One-time: create kind cluster + Prometheus + OpenCost + test apps.
#   ./start.sh test       Run all tests + regenerate KPI and reliability reports.
#   ./start.sh docker     Run backend + frontend in Docker containers (docker compose).
#
#  Press Ctrl+C to stop everything.  Dashboard: http://localhost:5173   API: http://localhost:8000/docs
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BE="$ROOT/backend"; FE="$ROOT/frontend"; LOGS="$ROOT/logs"
MODE="${1:-demo}"
mkdir -p "$LOGS"
PIDS=()

say()  { printf "\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!!  %s\033[0m\n" "$*"; }

cleanup() {
  echo; say "Stopping..."
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  exit 0
}
trap cleanup INT TERM

ensure_backend() {
  if [ ! -x "$BE/venv/bin/python" ]; then
    say "Creating Python virtual environment (first run only)"
    python3 -m venv "$BE/venv"
  fi
  if ! "$BE/venv/bin/python" -c "import fastapi, uvicorn, pandas, numpy, requests" 2>/dev/null; then
    say "Installing backend packages"
    "$BE/venv/bin/pip" install -q -r "$BE/requirements.txt"
  fi
}

ensure_frontend() {
  if [ ! -d "$FE/node_modules" ]; then
    say "Installing frontend packages (first run only)"
    (cd "$FE" && npm install --silent)
  fi
}

free_port() {  # kill whatever is still listening from a previous run
  local pid; pid=$(lsof -ti tcp:"$1" 2>/dev/null || true)
  [ -n "$pid" ] && { warn "Port $1 busy (pid $pid) — stopping old process"; kill $pid 2>/dev/null || true; sleep 1; }
  return 0
}

start_backend() {
  free_port 8000
  say "Starting backend  -> http://localhost:8000/docs   (log: logs/backend.log)"
  (cd "$BE" && exec env "$@" venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000) >"$LOGS/backend.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 30); do curl -sf localhost:8000/health >/dev/null && break; sleep 0.5; done
}

start_frontend() {
  free_port 5173
  say "Starting frontend -> http://localhost:5173        (log: logs/frontend.log)"
  (cd "$FE" && exec npm run dev -- --host 0.0.0.0 --port 5173 --strictPort) >"$LOGS/frontend.log" 2>&1 &
  PIDS+=($!)
  sleep 3
  command -v open >/dev/null && open "http://localhost:5173" || true
}

case "$MODE" in
  demo)
    ensure_backend; ensure_frontend
    export FINOPS_DB_PATH="$BE/finops.db"
    if ! "$BE/venv/bin/python" - <<'PY' 2>/dev/null
import os, sqlite3, sys
c = sqlite3.connect(os.environ["FINOPS_DB_PATH"])
sys.exit(0 if c.execute("select count(*) from cost_allocations").fetchone()[0] else 1)
PY
    then
      say "No data yet — generating 90-day sandbox dataset + KPI report"
      (cd "$BE" && venv/bin/python -m finops.pipeline --source simulator --fresh)
    fi
    start_backend FINOPS_DB_PATH="$FINOPS_DB_PATH"
    start_frontend
    say "DEMO MODE running. Ctrl+C to stop."
    ;;

  live)
    ensure_backend; ensure_frontend
    docker info >/dev/null 2>&1 || { warn "Docker Desktop is not running. Start it, then re-run."; exit 1; }
    kubectl get --raw /healthz >/dev/null 2>&1 || { warn "No Kubernetes cluster. Run: ./start.sh setup"; exit 1; }
    free_port 9003
    say "Port-forwarding OpenCost API -> localhost:9003 (UI -> localhost:9090)"
    kubectl port-forward -n opencost service/opencost 9003:9003 9090:9090 >"$LOGS/port-forward.log" 2>&1 &
    PIDS+=($!)
    sleep 3
    export FINOPS_DB_PATH="$BE/finops_live.db"
    say "First pull from OpenCost"
    (cd "$BE" && venv/bin/python -m finops.pipeline --source opencost --window 7d) || warn "First pull failed — OpenCost may still be warming up; auto-sync will retry."
    start_backend FINOPS_DB_PATH="$FINOPS_DB_PATH" AUTO_SYNC_MINUTES=2
    start_frontend
    say "LIVE MODE running. Try: kubectl apply -f k8s/demo-new-app.yaml  (appears in ~2 min). Ctrl+C to stop."
    ;;

  setup)
    bash "$ROOT/scripts/setup_cluster.sh"; exit 0 ;;

  test)
    ensure_backend
    (cd "$BE" && venv/bin/pip install -q pytest httpx && venv/bin/python -m pytest -q -p no:warnings \
      && venv/bin/python -m finops.pipeline --source simulator --fresh >/dev/null \
      && venv/bin/python scripts/evaluate_reliability.py 2>/dev/null | head -8)
    say "Reports: backend/reports/baseline_kpis.md  backend/reports/reliability.md"
    exit 0 ;;

  docker)
    docker info >/dev/null 2>&1 || { warn "Docker Desktop is not running."; exit 1; }
    (cd "$ROOT" && docker compose up --build); exit 0 ;;

  *) sed -n '3,12p' "$0"; exit 1 ;;
esac

wait
