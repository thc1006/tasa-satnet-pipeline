# Kubernetes Deployment Guide

## Prerequisites

- Local Kubernetes cluster (Docker Desktop, minikube, or k3s)
- kubectl configured and connected to your cluster
- Docker daemon running
- Image built: `docker build -t tasa-satnet-pipeline:latest .`

## Quick Start

### 1. Build Docker Image

```bash
# Build the image
docker build -t tasa-satnet-pipeline:latest .

# Verify the image
docker images | grep tasa-satnet-pipeline
```

### 2. Load Image into Kubernetes (if using local cluster)

```bash
# For Docker Desktop - no action needed
# For minikube
minikube image load tasa-satnet-pipeline:latest

# For k3s
docker save tasa-satnet-pipeline:latest | sudo k3s ctr images import -
```

### 3. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create ConfigMap
kubectl apply -f k8s/configmap.yaml

# Verify
kubectl get all -n tasa-satnet
```

> **Note**: this pipeline is batch (Jobs), not a long-running service. The
> previously-shipped `deployment.yaml` / `service.yaml` were removed because
> the container's `CMD` is a one-shot healthcheck that exits 0, which under
> `restartPolicy: Always` looped forever (CrashLoopBackOff). Run as Jobs.

### 4. Run Parser Job

```bash
# Run the parser as a Job
kubectl apply -f k8s/job-parser.yaml

# Check job status
kubectl get jobs -n tasa-satnet

# View logs
kubectl logs -n tasa-satnet job/tasa-parser-job
```

### 5. Run Full Pipeline Smoke Test

```bash
# End-to-end test (parse → scenario → metrics → scheduler)
kubectl apply -f k8s/job-test-real.yaml

# Watch
kubectl logs -n tasa-satnet job/tasa-test-pipeline -f
```

## Resource Access

### Access Pod Shell

```bash
# Get pod name
kubectl get pods -n tasa-satnet

# Open shell in pod
kubectl exec -it -n tasa-satnet <pod-name> -- /bin/bash
```

### Copy Files from Pod

```bash
# Copy output files
kubectl cp tasa-satnet/<pod-name>:/app/data/oasis_windows.json ./oasis_windows.json
kubectl cp tasa-satnet/<pod-name>:/app/reports ./reports
```

### View Logs

```bash
# Follow logs in real-time
kubectl logs -f -n tasa-satnet deployment/tasa-pipeline

# View logs for specific container
kubectl logs -n tasa-satnet <pod-name> -c parser
```

## Persistent Storage

Data persists across pod restarts using PersistentVolumeClaims:

- `tasa-data-pvc`: Input data and parsed outputs
- `tasa-reports-pvc`: Generated reports and metrics

### Check PVC Status

```bash
kubectl get pvc -n tasa-satnet
kubectl describe pvc tasa-data-pvc -n tasa-satnet
```

## Scaling

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment tasa-pipeline -n tasa-satnet --replicas=3

# Verify scaling
kubectl get pods -n tasa-satnet -w
```

### Horizontal Pod Autoscaler (HPA)

```bash
# Create HPA
kubectl autoscale deployment tasa-pipeline \
  -n tasa-satnet \
  --cpu-percent=80 \
  --min=1 \
  --max=5

# Check HPA status
kubectl get hpa -n tasa-satnet
```

## Monitoring

### Resource Usage

```bash
# Check resource usage
kubectl top pods -n tasa-satnet
kubectl top nodes
```

### Events

```bash
# View cluster events
kubectl get events -n tasa-satnet --sort-by='.lastTimestamp'
```

## Cleanup

```bash
# Delete all resources in namespace
kubectl delete namespace tasa-satnet

# Or delete individually
kubectl delete -f k8s/job-test-real.yaml --ignore-not-found
kubectl delete -f k8s/job-integrated-pipeline.yaml --ignore-not-found
kubectl delete -f k8s/job-parser.yaml --ignore-not-found
kubectl delete -f k8s/configmap.yaml
kubectl delete -f k8s/namespace.yaml
```

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod for events
kubectl describe pod -n tasa-satnet <pod-name>

# Check for image pull issues
kubectl get events -n tasa-satnet | grep "Failed"
```

### Job Not Completing

```bash
# Check job status
kubectl describe job -n tasa-satnet tasa-parser-job

# View job logs
kubectl logs -n tasa-satnet job/tasa-parser-job
```

### PVC Issues

```bash
# Check PVC status
kubectl get pvc -n tasa-satnet
kubectl describe pvc -n tasa-satnet tasa-data-pvc

# Check StorageClass
kubectl get storageclass
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to K8s

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t tasa-satnet-pipeline:${{ github.sha }} .
      
      - name: Configure kubectl
        uses: azure/k8s-set-context@v3
        with:
          method: kubeconfig
          kubeconfig: ${{ secrets.KUBE_CONFIG }}
      
      - name: Deploy to K8s
        run: |
          kubectl apply -f k8s/
          kubectl set image deployment/tasa-pipeline \
            parser=tasa-satnet-pipeline:${{ github.sha }} \
            -n tasa-satnet
```

## Production Considerations

1. **Image Registry**: Push images to a registry (DockerHub, GCR, ECR)
2. **Resource Limits**: Adjust CPU/memory based on actual workload
3. **Health Checks**: Add liveness and readiness probes
4. **Secrets**: Use Kubernetes Secrets for sensitive data
5. **Network Policies**: Restrict pod-to-pod communication
6. **Monitoring**: Integrate with Prometheus/Grafana
7. **Logging**: Set up centralized logging (ELK, Loki)
8. **Backup**: Implement PV backup strategy

## Advanced Configuration

### Custom StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: tasa-fast-storage
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
```

### Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tasa-pipeline-netpol
  namespace: tasa-satnet
spec:
  podSelector:
    matchLabels:
      app: tasa-pipeline
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: tasa-satnet
  egress:
  - to:
    - namespaceSelector: {}
```

## Support

For issues or questions, check:
- Project README: `../README.md`
- CLAUDE.md for development guidelines
- GitHub Issues: [link to repo]
