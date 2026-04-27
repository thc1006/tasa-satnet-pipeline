#!/bin/bash
# Local K8s deployment script

set -e

echo "=== TASA SatNet Pipeline - K8s Deployment ==="
echo ""

# Check prerequisites
echo "Step 1: Checking prerequisites..."
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not found"
    exit 1
fi

echo "[OK] Prerequisites found"
echo ""

# Build Docker image
echo "Step 2: Building Docker image..."
docker build -t tasa-satnet-pipeline:latest . || {
    echo "ERROR: Docker build failed"
    exit 1
}
echo "[OK] Docker image built"
echo ""

# Load image to K8s (for local clusters)
echo "Step 3: Loading image to K8s..."
if command -v minikube &> /dev/null; then
    echo "Detected minikube, loading image..."
    minikube image load tasa-satnet-pipeline:latest
elif command -v kind &> /dev/null; then
    echo "Detected kind, loading image..."
    kind load docker-image tasa-satnet-pipeline:latest
else
    echo "Using Docker Desktop, image already available"
fi
echo "[OK] Image loaded"
echo ""

# Deploy to K8s. Note: this pipeline is batch (Jobs), not a long-running
# service. There is no Deployment / Service to apply — those manifests were
# deleted because the container's CMD is a oneshot healthcheck that exits
# on success, which made restartPolicy: Always loop forever (CrashLoopBackOff).
echo "Step 4: Deploying to K8s..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
echo "[OK] Base deployment complete"
echo ""

echo "=== Deployment Complete ==="
echo ""
echo -e "\033[36mAvailable Jobs:\033[0m"
echo "  kubectl apply -f k8s/job-parser.yaml             # Parser-only batch run"
echo "  kubectl apply -f k8s/job-test-real.yaml          # Full pipeline smoke test"
echo "  kubectl apply -f k8s/job-integrated-pipeline.yaml # Phase 3C integrated test (TLE, Multi-constellation, Viz)"
echo ""
echo -e "\033[36mManagement Commands:\033[0m"
echo "  kubectl get all -n tasa-satnet                   # Check status"
echo "  kubectl logs -f -n tasa-satnet job/<job-name>    # Follow job logs"
echo "  kubectl describe configmap tasa-pipeline-config -n tasa-satnet  # View config"
echo ""
echo -e "\033[33mPhase 3C Features Enabled:\033[0m"
echo "  ✓ TLE-OASIS Integration (union merge strategy)"
echo "  ✓ Multi-Constellation Support (GPS, Starlink, OneWeb, Iridium)"
echo "  ✓ Visualization Generation (4 types)"
echo "  ✓ Constellation Conflict Detection"
echo "  ✓ Priority-based Scheduling"
