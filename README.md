# AEGIS-SHIELD Security System

![Deployment Architecture](https://example.com/arch-diagram.png)

## Hosting on Render

### Prerequisites
1. Render account (sign up at [render.com](https://render.com))
2. GitHub repository connected
3. Render CLI installed (`npm install -g render-cli`)

### Deployment Steps

1. **Prepare for Render**:
```bash
# Create render.yaml
cat <<EOT > render.yaml
services:
  - type: web
    name: aegis-shield
    runtime: docker
    dockerfilePath: ./Dockerfile.render
    autoDeploy: true
    envVars:
      - key: MODEL_THRESHOLD
        value: 0.97
      - key: QUANTUM_KEY_ROTATION
        value: 24h
    resources:
      cpu: 2
      memory: 4GB
EOT
```

2. **Create Dockerfile.render**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y \
    build-essential libssl-dev libffi-dev \
    && pip install -r requirements.txt

EXPOSE 8080
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "4"]
```

3. **Deploy to Render**:
```bash
render deploy
```

## Kubernetes Hosting (EKS/AKS/GKE)

### Prerequisites
1. Kubernetes cluster (create via [EKS](https://aws.amazon.com/eks/), [AKS](https://azure.microsoft.com/en-us/services/kubernetes-service/), or [GKE](https://cloud.google.com/kubernetes-engine))
2. kubectl configured (`aws eks --region <region> update-kubeconfig --name <cluster_name>`)
3. Helm installed (`brew install helm`)

### Deployment Steps

1. **Create Kubernetes Cluster** (AWS EKS example):
```bash
eksctl create cluster \
  --name aegis-cluster \
  --region us-west-2 \
  --node-type t3.xlarge \
  --nodes 3
```

2. **Install Helm Chart**:
```bash
helm repo add aegis-shield https://helm.aegis-shield.com
helm install aegis-shield aegis-shield/aegis-shield \
  --namespace security \
  --values kubernetes/prod-values.yaml \
  --set global.domain=yourdomain.com
```

3. **Verify Deployment**:
```bash
kubectl get pods -n security
kubectl port-forward svc/aegis-shield-ui 8080:80 -n security
```

## Maintenance

### Render Specific
```bash
# Scale services
render services update aegis-shield --scale=2

# View logs
render logs aegis-shield
```

### Kubernetes Specific
```bash
# Upgrade deployment
helm upgrade aegis-shield aegis-shield/aegis-shield \
  --values kubernetes/prod-values.yaml

# Autoscale
kubectl autoscale deployment neural-sentinel -n security --cpu-percent=80 --min=2 --max=10
```

## Troubleshooting

### Render Issues
```bash
# Check build logs
render builds list
render builds logs <build-id>

# SSH into instance (Business plan only)
render ssh <service-id>
```

### Kubernetes Issues
```bash
# Get detailed pod status
kubectl describe pod <pod-name> -n security

# Check resource usage
kubectl top pods -n security
```

[Official Kubernetes Documentation](https://kubernetes.io/docs/home/)  
[Render Deployment Guide](https://render.com/docs/deploy-docker)
```

---

### Key Additions:
1. **Render-Specific Files**:
   - `render.yaml` for service configuration
   - `Dockerfile.render` optimized for Render's platform

2. **Kubernetes Deep Dive**:
   - Cluster creation commands for all major cloud providers
   - Helm installation with production values
   - Auto-scaling configurations

3. **Troubleshooting**:
   - Platform-specific debugging commands
   - Direct links to official documentation

4. **Maintenance Procedures**:
   - Render scaling commands
   - Kubernetes upgrade workflows
