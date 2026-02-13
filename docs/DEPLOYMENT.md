# BeatSight Production Deployment Guide

*Last Updated: November 2025*

This guide covers deploying BeatSight's web backend to production. For desktop development setup, see `docs/SETUP.md`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer (HTTPS)                        │
│                    (Azure App Gateway / Cloudflare)             │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   API Server    │ │   API Server    │ │   API Server    │
│   (Container)   │ │   (Container)   │ │   (Container)   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │    Redis      │    │  Blob Storage │
│   (Primary)   │    │   (Cache)     │    │   (Audio)     │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## Prerequisites

### Required Services
- PostgreSQL 15+ (Azure Database for PostgreSQL recommended)
- Redis 7+ (Azure Cache for Redis recommended)
- Blob storage for audio files (Azure Blob Storage)
- Container registry (Azure Container Registry)
- SSL certificate (Let's Encrypt / Azure managed)

### Local Tools
- Docker & Docker Compose
- Azure CLI (`az`) or equivalent cloud CLI
- Poetry (for local testing)

---

## Environment Variables

Create a `.env.production` file (never commit to version control):

```bash
# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
LOGGING_JSON=true

# Database
DATABASE_DSN=postgresql+asyncpg://user:password@host:5432/beatsight_prod

# Redis
REDIS_URL=redis://:password@host:6380/0?ssl=true

# Authentication (CRITICAL: generate secure keys!)
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_ALGORITHM=HS256

# CORS (adjust for your domain)
CORS_ORIGINS=["https://beatsight.io","https://www.beatsight.io"]

# Blob Storage
AZURE_STORAGE_CONNECTION_STRING=<connection_string>
AZURE_STORAGE_CONTAINER_NAME=audio-files
```

### Generating Secure Keys

```bash
# JWT secret (minimum 32 bytes)
openssl rand -hex 32

# Database password
openssl rand -base64 24
```

---

## Docker Build

### Dockerfile

Create `backend/Dockerfile`:

```dockerfile
# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Export requirements (no dev dependencies)
RUN poetry export -f requirements.txt --without-hashes --without dev > requirements.txt

# Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with uvicorn
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Build & Push

```bash
cd backend

# Build image
docker build -t beatsight-api:latest .

# Tag for registry
docker tag beatsight-api:latest <registry>/beatsight-api:v1.0.0

# Push to registry
docker push <registry>/beatsight-api:v1.0.0
```

---

## Database Setup

### Initial Schema Migration

```bash
# From local machine with database access
cd backend
poetry install

# Run Alembic migrations
DATABASE_DSN="postgresql+asyncpg://..." poetry run alembic upgrade head
```

### Create Migration (when schema changes)

```bash
poetry run alembic revision --autogenerate -m "description of changes"
poetry run alembic upgrade head
```

### Backup & Restore

```bash
# Backup
pg_dump -h $DB_HOST -U $DB_USER -d beatsight_prod > backup_$(date +%Y%m%d).sql

# Restore
psql -h $DB_HOST -U $DB_USER -d beatsight_prod < backup_20251124.sql
```

---

## Azure Deployment (Recommended)

### Container Apps

```bash
# Login
az login

# Create resource group
az group create --name beatsight-prod --location eastus

# Create Container Apps environment
az containerapp env create \
    --name beatsight-env \
    --resource-group beatsight-prod \
    --location eastus

# Deploy API
az containerapp create \
    --name beatsight-api \
    --resource-group beatsight-prod \
    --environment beatsight-env \
    --image <registry>/beatsight-api:v1.0.0 \
    --target-port 8000 \
    --ingress external \
    --cpu 0.5 \
    --memory 1Gi \
    --min-replicas 2 \
    --max-replicas 10 \
    --env-vars \
        ENVIRONMENT=production \
        DATABASE_DSN=secretref:database-dsn \
        REDIS_URL=secretref:redis-url \
        JWT_SECRET_KEY=secretref:jwt-secret
```

### App Service (Alternative)

```bash
# Create App Service Plan
az appservice plan create \
    --name beatsight-plan \
    --resource-group beatsight-prod \
    --sku B2 \
    --is-linux

# Create Web App
az webapp create \
    --name beatsight-api \
    --resource-group beatsight-prod \
    --plan beatsight-plan \
    --deployment-container-image-name <registry>/beatsight-api:v1.0.0

# Configure
az webapp config appsettings set \
    --name beatsight-api \
    --resource-group beatsight-prod \
    --settings ENVIRONMENT=production DATABASE_DSN="@Microsoft.KeyVault(SecretUri=...)"
```

---

## Docker Compose (Self-Hosted)

For self-hosted deployments, use `docker-compose.production.yml`:

```yaml
version: '3.8'

services:
  api:
    image: beatsight-api:latest
    restart: always
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_DSN=${DATABASE_DSN}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - LOGGING_JSON=true
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15-alpine
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=beatsight_prod

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

---

## SSL/TLS Configuration

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.beatsight.io;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.beatsight.io;

    ssl_certificate /etc/letsencrypt/live/api.beatsight.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.beatsight.io/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoring & Logging

### Structured Logs

With `LOGGING_JSON=true`, logs are JSON-formatted for ingestion:

```json
{
  "timestamp": "2025-11-24T12:00:00.000Z",
  "level": "info",
  "event": "request_completed",
  "method": "POST",
  "path": "/api/auth/login",
  "status_code": 200,
  "duration_ms": 45.2
}
```

### Health Checks

```bash
# Liveness
curl https://api.beatsight.io/health
# {"status": "ok", "timestamp": "..."}

# Readiness (checks DB/Redis)
curl https://api.beatsight.io/health/ready
```

### Recommended Monitoring Stack
- **Logs**: Azure Log Analytics / Datadog / ELK
- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry → Jaeger
- **Alerts**: PagerDuty / Opsgenie

---

## Security Checklist

- [ ] JWT_SECRET_KEY is unique, generated securely, not committed
- [ ] Database credentials rotated from defaults
- [ ] Redis protected with password and/or VNet
- [ ] CORS origins restricted to production domains
- [ ] HTTPS enforced, HTTP redirects to HTTPS
- [ ] Rate limiting enabled
- [ ] SQL injection protection (SQLAlchemy parameterized queries ✓)
- [ ] Input validation via Pydantic ✓
- [ ] Non-root container user ✓
- [ ] Dependency vulnerabilities scanned (`pip-audit`)

---

## Rollback Procedure

```bash
# 1. Identify last working version
docker images | grep beatsight-api

# 2. Update deployment
az containerapp update \
    --name beatsight-api \
    --resource-group beatsight-prod \
    --image <registry>/beatsight-api:v0.9.0

# 3. Verify health
curl https://api.beatsight.io/health

# 4. If database migration caused issue, restore backup
psql -h $DB_HOST -U $DB_USER -d beatsight_prod < backup_before_deploy.sql
```

---

## Scaling Guidelines

| Load | API Replicas | DB Tier | Redis Size |
|------|-------------|---------|------------|
| < 100 DAU | 2 | Basic | Basic C0 |
| 100-1K DAU | 3-5 | Standard | Standard C1 |
| 1K-10K DAU | 5-10 | GP_Gen5_4 | Premium P1 |
| 10K+ DAU | 10+ | GP_Gen5_8+ | Premium P3 |

---

## CI/CD Pipeline

See `.github/workflows/deploy.yml` (to be created) for:
- Build and push Docker image on tag
- Run migrations
- Deploy to staging → smoke test → deploy to production
- Automatic rollback on health check failure

---

## Support

- **Issues**: https://github.com/rosacry/BeatSight/issues
- **Security vulnerabilities**: security@beatsight.io (private disclosure)
