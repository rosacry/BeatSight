# BeatSight Production Infrastructure
# ====================================
# Google Kubernetes Engine (GKE) Autopilot
# Domain: beatsight.io

## Why GKE Autopilot?
- **Pay per pod** - only pay for actual CPU/RAM usage
- **Zero node management** - Google handles everything
- **Auto-scaling** - scales to zero when idle
- **$300 free credit** - ~3-6 months free to start
- **Enterprise-grade** - Google's infrastructure

## Quick Start

### 1. Set Up Google Cloud

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Create new project (or use existing)
gcloud projects create beatsight --name="BeatSight Production"
gcloud config set project beatsight

# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Enable billing (required - use your $300 credit)
# Do this in console: https://console.cloud.google.com/billing
```

### 2. Create GKE Autopilot Cluster

```bash
# Create Autopilot cluster (this takes ~5 minutes)
gcloud container clusters create-auto beatsight \
  --region=us-central1 \
  --release-channel=stable

# Get credentials for kubectl
gcloud container clusters get-credentials beatsight --region=us-central1

# Verify connection
kubectl get nodes
```

### 3. Install Ingress & Cert-Manager

```bash
# Install nginx-ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/cloud/deploy.yaml

# Wait for ingress controller to get external IP
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Get the external IP (save this for DNS)
kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Install cert-manager for automatic TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml

# Wait for cert-manager
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=120s
```

### 4. Configure DNS for beatsight.io

After getting the Load Balancer IP, add these DNS records:

| Type | Name | Value |
|------|------|-------|
| A | @ | <LOAD_BALANCER_IP> |
| A | api | <LOAD_BALANCER_IP> |
| A | docs | <LOAD_BALANCER_IP> |
| CNAME | www | beatsight.io |

### 5. Set Up Secrets with Google Secret Manager

```bash
# Create secrets in Secret Manager (more secure than K8s secrets)
echo -n "your-database-url" | gcloud secrets create DATABASE_URL --data-file=-
echo -n "your-jwt-secret" | gcloud secrets create JWT_SECRET --data-file=-
echo -n "your-sentry-dsn" | gcloud secrets create SENTRY_DSN --data-file=-

# Or use K8s secrets (simpler for starting out)
kubectl create namespace beatsight

# Copy and edit the template
cp k8s/secrets.template.yaml k8s/secrets.yaml
# Edit k8s/secrets.yaml with your values
kubectl apply -f k8s/secrets.yaml
```

### 6. Deploy BeatSight

```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Deploy everything
kubectl apply -k k8s/base/

# Check deployment status
kubectl get pods -n beatsight -w

# Check ingress
kubectl get ingress -n beatsight

# View logs
kubectl logs -n beatsight -l app=beatsight-backend -f
```

### 7. Set Up Cloud SQL (Managed PostgreSQL)

```bash
# Create Cloud SQL instance
gcloud sql instances create beatsight-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=<SECURE_PASSWORD>

# Create database
gcloud sql databases create beatsight --instance=beatsight-db

# Create user
gcloud sql users create beatsight \
  --instance=beatsight-db \
  --password=<USER_PASSWORD>

# Get connection name for your app
gcloud sql instances describe beatsight-db --format='value(connectionName)'
# Output: beatsight:us-central1:beatsight-db
```

## Cost Breakdown (Estimated)

### Autopilot Pricing (pay per pod)
| Resource | Price |
|----------|-------|
| vCPU | $0.0445/hr per vCPU |
| Memory | $0.0049/hr per GB |
| Ephemeral Storage | $0.00011/hr per GB |

### Typical Monthly Costs

| Scenario | Est. Monthly Cost |
|----------|-------------------|
| **Idle/Dev** (minimal pods) | $5-15 |
| **Light Production** (1-2 replicas) | $30-50 |
| **Medium Traffic** (auto-scaled) | $80-150 |
| **High Traffic** | $200+ (but you'd have revenue) |

### Other GCP Costs
| Service | Cost |
|---------|------|
| Cloud SQL (db-f1-micro) | ~$10/mo |
| Load Balancer | ~$18/mo |
| Cloud Storage (audio files) | ~$0.02/GB/mo |
| **Total Minimum** | **~$30-40/mo** |

With $300 credit, you get **~6-10 months free!**

## CI/CD Integration

Add these secrets to GitHub Actions:

| Secret | How to Get |
|--------|------------|
| `GCP_PROJECT_ID` | `beatsight` |
| `GCP_SA_KEY` | Service account JSON (see below) |
| `GKE_CLUSTER` | `beatsight` |
| `GKE_ZONE` | `us-central1` |

### Create Service Account for CI/CD

```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# Grant permissions
gcloud projects add-iam-policy-binding beatsight \
  --member="serviceAccount:github-actions@beatsight.iam.gserviceaccount.com" \
  --role="roles/container.developer"

gcloud projects add-iam-policy-binding beatsight \
  --member="serviceAccount:github-actions@beatsight.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@beatsight.iam.gserviceaccount.com

# Base64 encode for GitHub secret
cat github-actions-key.json | base64 -w 0
# Add this output as GCP_SA_KEY secret in GitHub

# Delete local key file (security)
rm github-actions-key.json
```

## Useful Commands

```bash
# Scale deployment
kubectl scale deployment beatsight-backend -n beatsight --replicas=3

# View resource usage
kubectl top pods -n beatsight

# View Autopilot costs
gcloud billing accounts list
# Check costs in: https://console.cloud.google.com/billing

# Force rollout restart
kubectl rollout restart deployment/beatsight-backend -n beatsight

# View HPA status
kubectl get hpa -n beatsight

# Debug pod issues
kubectl describe pod <pod-name> -n beatsight
kubectl logs <pod-name> -n beatsight --previous
```

## Monitoring

GKE Autopilot includes built-in monitoring:
- **Cloud Monitoring**: https://console.cloud.google.com/monitoring
- **Cloud Logging**: https://console.cloud.google.com/logs
- **Error Reporting**: https://console.cloud.google.com/errors

Your Sentry + Grafana Cloud setup will also work alongside these.
