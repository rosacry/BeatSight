#!/usr/bin/env bash
# BeatSight Monitoring Setup Script
# This script helps set up Prometheus and Grafana for BeatSight monitoring.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITORING_DIR="$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           BeatSight Monitoring Setup                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    local missing=()
    
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ Missing prerequisites: ${missing[*]}"
        echo "   Please install them and try again."
        exit 1
    fi
    
    echo "✅ Prerequisites OK"
}

# Create docker-compose file if it doesn't exist
create_docker_compose() {
    local compose_file="$MONITORING_DIR/docker-compose.yml"
    
    if [ -f "$compose_file" ]; then
        echo "📄 docker-compose.yml already exists"
        return
    fi
    
    echo "📝 Creating docker-compose.yml..."
    
    cat > "$compose_file" << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: beatsight-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/rules:/etc/prometheus/rules:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    restart: unless-stopped
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:10.2.2
    container_name: beatsight-grafana
    ports:
      - "3001:3000"
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=beatsight
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3001
    restart: unless-stopped
    networks:
      - monitoring
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
EOF

    echo "✅ docker-compose.yml created"
}

# Create Prometheus config
create_prometheus_config() {
    local prometheus_dir="$MONITORING_DIR/prometheus"
    local config_file="$prometheus_dir/prometheus.yml"
    
    mkdir -p "$prometheus_dir"
    
    if [ -f "$config_file" ]; then
        echo "📄 prometheus.yml already exists"
        return
    fi
    
    echo "📝 Creating prometheus.yml..."
    
    cat > "$config_file" << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: []
          # Add your Alertmanager endpoint here
          # - targets: ['alertmanager:9093']

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # BeatSight Backend API
  - job_name: 'beatsight-backend'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['host.docker.internal:8000']
        labels:
          service: 'backend'
    # Uncomment for production
    # - targets: ['api.beatsight.io:443']
    #   scheme: https

  # Modal GPU Workers (if exposing metrics)
  # - job_name: 'modal-workers'
  #   static_configs:
  #     - targets: ['modal-worker-1:9091', 'modal-worker-2:9091']
EOF

    echo "✅ prometheus.yml created"
}

# Create Grafana provisioning
create_grafana_provisioning() {
    local grafana_dir="$MONITORING_DIR/grafana"
    local provisioning_dir="$grafana_dir/provisioning"
    
    mkdir -p "$provisioning_dir/datasources"
    mkdir -p "$provisioning_dir/dashboards"
    
    # Datasource provisioning
    cat > "$provisioning_dir/datasources/prometheus.yml" << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
EOF

    # Dashboard provisioning
    cat > "$provisioning_dir/dashboards/default.yml" << 'EOF'
apiVersion: 1

providers:
  - name: 'BeatSight Dashboards'
    orgId: 1
    folder: 'BeatSight'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    echo "✅ Grafana provisioning created"
}

# Start services
start_services() {
    echo ""
    echo "🚀 Starting monitoring services..."
    
    cd "$MONITORING_DIR"
    
    if docker compose version &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi
    
    echo ""
    echo "⏳ Waiting for services to start..."
    sleep 5
    
    # Check if services are running
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "✅ Prometheus is running at http://localhost:9090"
    else
        echo "⚠️  Prometheus may still be starting..."
    fi
    
    if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
        echo "✅ Grafana is running at http://localhost:3001"
    else
        echo "⚠️  Grafana may still be starting..."
    fi
}

# Stop services
stop_services() {
    echo "🛑 Stopping monitoring services..."
    
    cd "$MONITORING_DIR"
    
    if docker compose version &> /dev/null; then
        docker compose down
    else
        docker-compose down
    fi
    
    echo "✅ Services stopped"
}

# Show status
show_status() {
    echo ""
    echo "📊 Service Status:"
    echo ""
    
    cd "$MONITORING_DIR"
    
    if docker compose version &> /dev/null; then
        docker compose ps
    else
        docker-compose ps
    fi
}

# Print help
print_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     Create configuration files and start services"
    echo "  start     Start monitoring services"
    echo "  stop      Stop monitoring services"
    echo "  status    Show service status"
    echo "  logs      Show service logs"
    echo "  help      Show this help message"
    echo ""
    echo "Access Points (after setup):"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3001 (admin/beatsight)"
}

# Main
main() {
    local command="${1:-setup}"
    
    case "$command" in
        setup)
            check_prerequisites
            create_docker_compose
            create_prometheus_config
            create_grafana_provisioning
            start_services
            echo ""
            echo "╔══════════════════════════════════════════════════════════════╗"
            echo "║  ✅ Monitoring setup complete!                               ║"
            echo "║                                                              ║"
            echo "║  Prometheus: http://localhost:9090                           ║"
            echo "║  Grafana:    http://localhost:3001                           ║"
            echo "║              Login: admin / beatsight                        ║"
            echo "║                                                              ║"
            echo "║  The Modal Workers dashboard is pre-loaded.                  ║"
            echo "║  Add your backend URL to prometheus.yml for metrics.         ║"
            echo "╚══════════════════════════════════════════════════════════════╝"
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        logs)
            cd "$MONITORING_DIR"
            if docker compose version &> /dev/null; then
                docker compose logs -f
            else
                docker-compose logs -f
            fi
            ;;
        help|--help|-h)
            print_help
            ;;
        *)
            echo "Unknown command: $command"
            print_help
            exit 1
            ;;
    esac
}

main "$@"
