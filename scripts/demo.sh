#!/usr/bin/env bash
# Demo lab controller — run from the project folder while ./start.sh live is running.
#
#   ./scripts/demo.sh up       deploy the 5 demo containers (do this 20+ min before the demo)
#   ./scripts/demo.sh spike    runaway scale-out: spike-service 1 -> 6 replicas  (SPIKE in ~6 min)
#   ./scripts/demo.sh calm     back to 1 replica
#   ./scripts/demo.sh grow     restart growing-job so its 30-minute climb starts again
#   ./scripts/demo.sh status   show demo pods and their live CPU use
#   ./scripts/demo.sh down     delete all demo containers
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
say() { printf "\033[1;36m==> %s\033[0m\n" "$*"; }

# Always talk to OUR cluster, even if Docker Desktop switched kubectl to another one
kind get clusters 2>/dev/null | grep -qx finops && kubectl config use-context kind-finops >/dev/null 2>&1
kubectl get --raw /healthz >/dev/null 2>&1 || { echo "No Kubernetes cluster. Start Docker Desktop, then ./start.sh setup"; exit 1; }

case "${1:-}" in
  up)
    say "Deploying demo lab (idle, oversized, steady, growing, spike)"
    kubectl apply -f "$ROOT/k8s/demo-new-app.yaml" -f "$ROOT/k8s/demo-lab.yaml"
    kubectl -n demo rollout status deploy --timeout=180s
    say "Done. Open http://localhost:5173/#live — give it ~15 min to learn each app's normal cost before 'spike'."
    ;;
  spike)
    say "Simulating a runaway scale-out: spike-service 1 -> 6 replicas"
    kubectl -n demo scale deployment spike-service --replicas=6
    say "Watch the Live page: SPIKE appears in about 6 minutes (OpenCost data arrives ~4 min late)."
    ;;
  calm)
    kubectl -n demo scale deployment spike-service --replicas=1
    say "spike-service back to 1 replica. The Live page shows SPIKE RESOLVED in about 6 minutes."
    ;;
  grow)
    kubectl -n demo rollout restart deployment growing-job
    say "growing-job restarted; its CPU use climbs again for 30 minutes."
    ;;
  status)
    kubectl -n demo get deploy,pods
    echo; kubectl top pods -n demo 2>/dev/null || echo "(metrics not ready yet)"
    ;;
  down)
    kubectl delete -f "$ROOT/k8s/demo-lab.yaml" -f "$ROOT/k8s/demo-new-app.yaml" --ignore-not-found
    say "Demo lab removed."
    ;;
  *)
    sed -n '2,9p' "$0"; exit 1 ;;
esac
