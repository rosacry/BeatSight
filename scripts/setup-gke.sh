#!/bin/bash
# BeatSight GKE Autopilot Setup Script
# Run this after purchasing beatsight.io domain

set -e

echo "🚀 BeatSight GKE Autopilot Setup"
echo "================================"

# Configuration - Using your existing project
PROJECT_ID="beatsight"
REGION="us-central1"
CLUSTER_NAME="beatsight"
DOMAIN="beatsight.io"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v gcloud &> /dev/null; then
        echo -e "${RED}❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install${NC}"
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found. Install from: https://kubernetes.io/docs/tasks/tools/${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Prerequisites OK${NC}"
}

# Step 1: Select existing GCP Project
setup_project() {
    echo -e "\n${YELLOW}Step 1: Using existing GCP project...${NC}"
    
    # Use existing beatsight project
    gcloud config set project $PROJECT_ID
    
    echo -e "${GREEN}✅ Project '$PROJECT_ID' selected${NC}"
}

# Step 2: Enable APIs
enable_apis() {
    echo -e "\n${YELLOW}Step 2: Enabling required APIs...${NC}"
    
    APIS=(
        "container.googleapis.com"
        "compute.googleapis.com"
        "cloudbuild.googleapis.com"
        "secretmanager.googleapis.com"
        "sqladmin.googleapis.com"
        "servicenetworking.googleapis.com"
    )
    
    for api in "${APIS[@]}"; do
        echo "Enabling $api..."
        gcloud services enable $api --quiet
    done
    
    echo -e "${GREEN}✅ APIs enabled${NC}"
}

# Step 3: Create GKE Autopilot Cluster
create_cluster() {
    echo -e "\n${YELLOW}Step 3: Creating GKE Autopilot cluster...${NC}"
    
    if gcloud container clusters describe $CLUSTER_NAME --region=$REGION &> /dev/null; then
        echo "Cluster $CLUSTER_NAME already exists"
    else
        echo "Creating Autopilot cluster (this takes ~5 minutes)..."
        gcloud container clusters create-auto $CLUSTER_NAME \
            --region=$REGION \
            --release-channel=stable
    fi
    
    # Get credentials
    gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION
    
    echo -e "${GREEN}✅ Cluster ready${NC}"
}

# Step 4: Reserve Static IP
reserve_ip() {
    echo -e "\n${YELLOW}Step 4: Reserving static IP...${NC}"
    
    if gcloud compute addresses describe beatsight-ip --global &> /dev/null; then
        echo "Static IP already reserved"
    else
        gcloud compute addresses create beatsight-ip --global
    fi
    
    IP=$(gcloud compute addresses describe beatsight-ip --global --format='value(address)')
    echo -e "${GREEN}✅ Static IP: $IP${NC}"
    echo ""
    echo -e "${YELLOW}📝 Add these DNS records for $DOMAIN:${NC}"
    echo "   A    @      $IP"
    echo "   A    api    $IP"
    echo "   A    docs   $IP"
    echo "   A    www    $IP"
}

# Step 5: Create Cloud SQL Instance
create_database() {
    echo -e "\n${YELLOW}Step 5: Creating Cloud SQL PostgreSQL...${NC}"
    
    read -p "Enter database root password: " -s DB_ROOT_PASSWORD
    echo ""
    
    if gcloud sql instances describe beatsight-db &> /dev/null; then
        echo "Database instance already exists"
    else
        echo "Creating Cloud SQL instance (this takes ~5 minutes)..."
        gcloud sql instances create beatsight-db \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region=$REGION \
            --root-password=$DB_ROOT_PASSWORD \
            --storage-auto-increase \
            --backup-start-time=04:00
        
        # Create database
        gcloud sql databases create beatsight --instance=beatsight-db
        
        # Create user
        read -p "Enter app database password: " -s DB_APP_PASSWORD
        echo ""
        gcloud sql users create beatsight \
            --instance=beatsight-db \
            --password=$DB_APP_PASSWORD
    fi
    
    CONNECTION_NAME=$(gcloud sql instances describe beatsight-db --format='value(connectionName)')
    echo -e "${GREEN}✅ Database ready${NC}"
    echo "   Connection name: $CONNECTION_NAME"
}

# Step 6: Create Kubernetes Secrets
create_secrets() {
    echo -e "\n${YELLOW}Step 6: Creating Kubernetes namespace and secrets...${NC}"
    
    # Create namespace
    kubectl create namespace beatsight --dry-run=client -o yaml | kubectl apply -f -
    
    # Generate JWT secret
    JWT_SECRET=$(openssl rand -base64 32)
    
    echo ""
    echo "Enter your secrets (or press Enter to skip):"
    read -p "Sentry DSN: " SENTRY_DSN
    read -p "Grafana Cloud Instance ID: " GRAFANA_INSTANCE_ID
    read -p "Grafana Cloud API Key: " -s GRAFANA_API_KEY
    echo ""
    
    # Create secret
    kubectl create secret generic beatsight-secrets \
        --namespace=beatsight \
        --from-literal=JWT_SECRET="$JWT_SECRET" \
        --from-literal=SENTRY_DSN="${SENTRY_DSN:-}" \
        --from-literal=GRAFANA_CLOUD_INSTANCE_ID="${GRAFANA_INSTANCE_ID:-}" \
        --from-literal=GRAFANA_CLOUD_API_KEY="${GRAFANA_API_KEY:-}" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    echo -e "${GREEN}✅ Secrets created${NC}"
}

# Step 7: Create GitHub Actions Service Account
create_service_account() {
    echo -e "\n${YELLOW}Step 7: Creating CI/CD service account...${NC}"
    
    SA_NAME="github-actions"
    SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
    
    # Create service account
    if gcloud iam service-accounts describe $SA_EMAIL &> /dev/null; then
        echo "Service account already exists"
    else
        gcloud iam service-accounts create $SA_NAME \
            --display-name="GitHub Actions CI/CD"
        
        # Grant permissions
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/container.developer" \
            --quiet
        
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/storage.admin" \
            --quiet
    fi
    
    # Create key
    KEY_FILE="/tmp/github-actions-key.json"
    gcloud iam service-accounts keys create $KEY_FILE \
        --iam-account=$SA_EMAIL
    
    echo ""
    echo -e "${GREEN}✅ Service account created${NC}"
    echo ""
    echo -e "${YELLOW}📝 Add these secrets to GitHub (Settings → Secrets → Actions):${NC}"
    echo ""
    echo "GCP_PROJECT_ID:"
    echo "$PROJECT_ID"
    echo ""
    echo "GKE_CLUSTER:"
    echo "$CLUSTER_NAME"
    echo ""
    echo "GKE_ZONE:"
    echo "$REGION"
    echo ""
    echo "GCP_SA_KEY (base64 encoded):"
    cat $KEY_FILE | base64 -w 0
    echo ""
    echo ""
    
    # Cleanup
    rm $KEY_FILE
    echo -e "${YELLOW}⚠️  Key file deleted for security${NC}"
}

# Main
main() {
    check_prerequisites
    
    echo ""
    echo "This script will set up:"
    echo "  1. GCP Project: $PROJECT_ID"
    echo "  2. GKE Autopilot cluster in $REGION"
    echo "  3. Cloud SQL PostgreSQL database"
    echo "  4. Static IP for $DOMAIN"
    echo "  5. CI/CD service account"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    setup_project
    enable_apis
    create_cluster
    reserve_ip
    create_database
    create_secrets
    create_service_account
    
    echo ""
    echo -e "${GREEN}🎉 Setup complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Add DNS records (shown above)"
    echo "  2. Add GitHub secrets (shown above)"
    echo "  3. Push to main branch to trigger deployment"
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n beatsight"
    echo "  kubectl logs -n beatsight -l app=beatsight-backend"
    echo "  gcloud sql connect beatsight-db --user=beatsight"
}

main "$@"
