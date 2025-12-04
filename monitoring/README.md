# BeatSight Monitoring

This directory contains monitoring configuration for BeatSight's AI pipeline and infrastructure.

## Overview

- **Grafana Dashboards**: Pre-built dashboards for visualizing system health
- **Prometheus Rules**: Alerting rules for proactive incident detection

## Components

### Grafana Dashboards

#### Modal GPU Workers Dashboard (`grafana/dashboards/modal-workers.json`)

Comprehensive dashboard for monitoring Modal GPU worker performance:

- **Overview Panel**: Quick stats for jobs queued, processing, completed (24h), failed (24h)
- **Queue Depth**: Time series showing job queue depth over time
- **Processing Performance**: 
  - Processing time percentiles (p50, p95, p99)
  - Job completion rate per hour
- **GPU Utilization**: 
  - GPU utilization by worker
  - GPU memory usage by worker
- **Error Rates**:
  - Rolling error rate (5m window)
  - Failures by error type (pie chart)

**Import Instructions:**
1. Open Grafana → Dashboards → Import
2. Upload `modal-workers.json` or paste JSON
3. Select your Prometheus data source
4. Click Import

### Prometheus Alert Rules

#### BeatSight Alerts (`prometheus/rules/beatsight-alerts.yml`)

| Alert | Severity | Trigger |
|-------|----------|---------|
| `AIJobQueueBackup` | Warning | >20 jobs queued for 10min |
| `AIJobQueueCritical` | Critical | >50 jobs queued for 5min |
| `AIJobSlowProcessing` | Warning | p95 latency >5min for 15min |
| `AIJobHighErrorRate` | Warning | >10% error rate for 10min |
| `AIJobCriticalErrorRate` | Critical | >30% error rate for 5min |
| `NoActiveWorkers` | Critical | 0 workers for 2min |
| `WorkerStale` | Warning | No heartbeat in 2min |
| `LowGPUUtilization` | Info | <20% GPU with queued jobs |
| `GPUMemoryHigh` | Warning | >95% GPU memory for 5min |
| `NoJobsCompleted` | Warning | 0 completions in 1h with queued jobs |

**Installation:**
```bash
# Copy to Prometheus rules directory
cp prometheus/rules/beatsight-alerts.yml /etc/prometheus/rules/

# Reload Prometheus
curl -X POST http://localhost:9090/-/reload
```

## Required Metrics

The dashboards and alerts expect these metrics from your application:

### Job Metrics
```
beatsight_ai_jobs_queued          # Gauge: Current jobs in queue
beatsight_ai_jobs_processing      # Gauge: Jobs currently processing
beatsight_ai_jobs_completed_total # Counter: Total completed jobs
beatsight_ai_jobs_failed_total    # Counter: Total failed jobs (with error_type label)
beatsight_ai_job_duration_seconds # Histogram: Job processing duration
```

### Worker Metrics
```
beatsight_modal_worker_active           # Gauge: 1 if worker is active
beatsight_modal_worker_last_heartbeat_seconds # Gauge: Unix timestamp of last heartbeat
beatsight_modal_gpu_utilization_percent # Gauge: GPU utilization 0-100 (with worker label)
beatsight_modal_gpu_memory_bytes        # Gauge: GPU memory used (with worker label)
beatsight_modal_gpu_memory_total_bytes  # Gauge: Total GPU memory (with worker label)
```

## Adding Metrics to Your Application

### Backend (FastAPI)

```python
from prometheus_client import Counter, Gauge, Histogram

# Job metrics
jobs_queued = Gauge('beatsight_ai_jobs_queued', 'Jobs in queue')
jobs_processing = Gauge('beatsight_ai_jobs_processing', 'Jobs processing')
jobs_completed = Counter('beatsight_ai_jobs_completed_total', 'Jobs completed')
jobs_failed = Counter('beatsight_ai_jobs_failed_total', 'Jobs failed', ['error_type'])
job_duration = Histogram(
    'beatsight_ai_job_duration_seconds',
    'Job duration',
    buckets=[30, 60, 120, 180, 300, 600, 900, 1800]
)
```

### Modal Worker (Python)

```python
import pynvml

def report_gpu_metrics():
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    
    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
    
    return {
        'gpu_utilization': util.gpu,
        'gpu_memory_used': memory.used,
        'gpu_memory_total': memory.total
    }
```

## Grafana Cloud Setup

For Grafana Cloud users:

1. Create a free account at [grafana.com](https://grafana.com)
2. Create a Prometheus data source pointing to your metrics endpoint
3. Import the dashboard JSON
4. Set up alert notification channels (Slack, PagerDuty, etc.)

## Local Development

For local testing with Docker:

```bash
# Start Prometheus and Grafana
docker-compose -f monitoring/docker-compose.yml up -d

# Access Grafana at http://localhost:3000 (admin/admin)
# Access Prometheus at http://localhost:9090
```

## Runbook Links

All alerts include `runbook_url` annotations pointing to:
- `https://docs.beatsight.io/ops/runbooks/<runbook-name>`

Create corresponding runbook documentation for each alert type.
