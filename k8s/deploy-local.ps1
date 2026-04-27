# PowerShell deployment script for Windows

Write-Host "=== TASA SatNet Pipeline - K8s Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Step 1: Checking prerequisites..." -ForegroundColor Yellow
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: kubectl not found" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: docker not found" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Prerequisites found" -ForegroundColor Green
Write-Host ""

# Check Docker daemon
Write-Host "Step 2: Checking Docker daemon..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "[OK] Docker daemon running" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker daemon not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Build Docker image
Write-Host "Step 3: Building Docker image..." -ForegroundColor Yellow
docker build -t tasa-satnet-pipeline:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker image built" -ForegroundColor Green
Write-Host ""

# Check if using Docker Desktop
Write-Host "Step 4: Checking K8s context..." -ForegroundColor Yellow
$context = kubectl config current-context
Write-Host "Current context: $context"

if ($context -match "docker-desktop") {
    Write-Host "[OK] Using Docker Desktop K8s" -ForegroundColor Green
} else {
    Write-Host "Note: Using context: $context" -ForegroundColor Yellow
}
Write-Host ""

# Deploy to K8s. Note: this pipeline is batch (Jobs), not a long-running
# service. There is no Deployment / Service to apply.
Write-Host "Step 5: Deploying to K8s..." -ForegroundColor Yellow
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
Write-Host "[OK] Base deployment complete" -ForegroundColor Green
Write-Host ""

Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Available Jobs:" -ForegroundColor Cyan
Write-Host "  kubectl apply -f k8s/job-test-real.yaml          # Basic pipeline test"
Write-Host "  kubectl apply -f k8s/job-integrated-pipeline.yaml # Phase 3C integrated test (TLE, Multi-constellation, Viz)"
Write-Host ""
Write-Host "Management Commands:" -ForegroundColor Cyan
Write-Host "  kubectl get all -n tasa-satnet                   # Check status"
Write-Host "  kubectl logs -f -n tasa-satnet job/<job-name>    # Follow job logs"
Write-Host "  kubectl describe configmap tasa-pipeline-config -n tasa-satnet  # View config"
Write-Host ""
Write-Host "Phase 3C Features Enabled:" -ForegroundColor Yellow
Write-Host "  ✓ TLE-OASIS Integration (union merge strategy)"
Write-Host "  ✓ Multi-Constellation Support (GPS, Starlink, OneWeb, Iridium)"
Write-Host "  ✓ Visualization Generation (4 types)"
Write-Host "  ✓ Constellation Conflict Detection"
Write-Host "  ✓ Priority-based Scheduling"
