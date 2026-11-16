#!/usr/bin/env bash
# One-time setup of the local Kubernetes sandbox: kind + Prometheus + OpenCost + metrics-server
# + the three test workloads. Safe to re-run (skips what already exists).
#   bash scripts/setup_cluster.sh                        # local kind cluster
#   bash scripts/setup_cluster.sh --use-current-context  # an existing EKS/AKS/GKE cluster
#
# Needs: Docker Desktop running, kind, kubectl, helm  (brew install kind kubectl helm)
set -euo pipefail
CLUSTER=finops
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }

if [ "${1:-}" = "--use-current-context" ]; then
  say "Using current kubectl context: $(kubectl config current-context)  (EKS / AKS / GKE)"
else
docker info >/dev/null 2>&1 || { echo "Docker is not running. Open Docker Desktop first."; exit 1; }

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  say "Creating kind cluster '$CLUSTER'"
  kind create cluster --name "$CLUSTER"
else
  say "kind cluster '$CLUSTER' already exists"
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null
fi

say "Installing Prometheus (OpenCost needs it)"
helm upgrade --install prometheus prometheus \
  --repo https://prometheus-community.github.io/helm-charts \
  --namespace prometheus-system --create-namespace \
  --set prometheus-pushgateway.enabled=false \
  --set alertmanager.enabled=false \
  -f https://raw.githubusercontent.com/opencost/opencost/develop/kubernetes/prometheus/extraScrapeConfigs.yaml \
  --wait --timeout 10m

say "Installing OpenCost"
helm upgrade --install opencost opencost \
  --repo https://opencost.github.io/opencost-helm-chart \
  --namespace opencost --create-namespace --wait --timeout 10m

say "Installing metrics-server (kind needs --kubelet-insecure-tls)"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' 2>/dev/null || true

say "Deploying test workloads"
kubectl apply -f "$ROOT/k8s/workloads.yaml"

say "Done. Pods:"
kubectl get pods -A | grep -Ev "Completed" || true
echo
echo "Next: ./start.sh live"
