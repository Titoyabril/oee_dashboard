#!/bin/bash
# Deployment script for Sparkplug B OEE System
# Handles production deployment with proper startup sequencing

set -e

# Configuration
COMPOSE_FILE="docker-compose.sparkplug.yml"
ENV_FILE=".env"
PROJECT_NAME="oee-sparkplug"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check if required tools are installed
check_prerequisites() {
    log "Checking prerequisites..."
    
    local tools=("docker" "docker-compose" "curl")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "$tool is required but not installed"
            exit 1
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    success "All prerequisites met"
}

# Function to validate environment file
validate_environment() {
    log "Validating environment configuration..."
    
    if [[ ! -f "$ENV_FILE" ]]; then
        warn "Environment file $ENV_FILE not found"
        log "Creating from template..."
        cp .env.example "$ENV_FILE"
        warn "Please edit $ENV_FILE with your configuration before continuing"
        exit 1
    fi
    
    # Check required variables
    local required_vars=(
        "SQL_SA_PASSWORD"
        "SPARKPLUG_GROUP_ID"
        "SPARKPLUG_NODE_ID"
    )
    
    source "$ENV_FILE"
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            error "Required environment variable $var is not set in $ENV_FILE"
            exit 1
        fi
    done
    
    success "Environment configuration validated"
}

# Function to create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    local dirs=(
        "config"
        "logs"
        "certs"
        "mosquitto/config"
        "mosquitto/data"
        "mosquitto/log"
        "prometheus"
        "grafana/provisioning"
        "grafana/dashboards"
        "nginx/conf.d"
        "sql"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
    done
    
    success "Directories created"
}

# Function to generate certificates
generate_certificates() {
    log "Checking SSL certificates..."
    
    if [[ ! -f "certs/ca.crt" ]] || [[ ! -f "certs/server.crt" ]] || [[ ! -f "certs/server.key" ]]; then
        log "Generating self-signed certificates..."
        
        # Create CA key and certificate
        openssl genrsa -out certs/ca.key 4096
        openssl req -new -x509 -days 365 -key certs/ca.key -out certs/ca.crt \
            -subj "/C=US/ST=State/L=City/O=OEE/CN=OEE-CA"
        
        # Create server key and certificate
        openssl genrsa -out certs/server.key 4096
        openssl req -new -key certs/server.key -out certs/server.csr \
            -subj "/C=US/ST=State/L=City/O=OEE/CN=oee-dashboard"
        openssl x509 -req -days 365 -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key \
            -CAcreateserial -out certs/server.crt
        
        # Create client certificate
        openssl genrsa -out certs/client.key 4096
        openssl req -new -key certs/client.key -out certs/client.csr \
            -subj "/C=US/ST=State/L=City/O=OEE/CN=sparkplug-client"
        openssl x509 -req -days 365 -in certs/client.csr -CA certs/ca.crt -CAkey certs/ca.key \
            -CAcreateserial -out certs/client.crt
        
        # Set permissions
        chmod 600 certs/*.key
        chmod 644 certs/*.crt
        
        success "Certificates generated"
    else
        success "Certificates already exist"
    fi
}

# Function to create configuration files
create_config_files() {
    log "Creating configuration files..."
    
    # Mosquitto configuration
    cat > mosquitto/config/mosquitto.conf << EOF
# Mosquitto MQTT Broker Configuration
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information

# Port configuration
listener 1883
listener 9001
protocol websockets

# Authentication (uncomment to enable)
# allow_anonymous false
# password_file /mosquitto/config/passwd

# TLS configuration (uncomment to enable)
# listener 8883
# cafile /mosquitto/certs/ca.crt
# certfile /mosquitto/certs/server.crt
# keyfile /mosquitto/certs/server.key
# require_certificate true
EOF

    # Prometheus configuration
    cat > prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'sparkplug-agent'
    static_configs:
      - targets: ['sparkplug-agent:8001']
    scrape_interval: 5s
    metrics_path: /metrics

  - job_name: 'oee-dashboard'
    static_configs:
      - targets: ['oee-dashboard:8000']
    scrape_interval: 30s
    metrics_path: /metrics

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF

    # Nginx configuration
    cat > nginx/conf.d/default.conf << EOF
upstream oee_dashboard {
    server oee-dashboard:8000;
}

upstream grafana {
    server grafana:3000;
}

server {
    listen 80;
    server_name _;
    
    # Redirect to HTTPS (uncomment for production)
    # return 301 https://\$server_name\$request_uri;
    
    location / {
        proxy_pass http://oee_dashboard;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /grafana/ {
        proxy_pass http://grafana/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias /var/www/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# HTTPS server (uncomment for production)
# server {
#     listen 443 ssl http2;
#     server_name _;
#     
#     ssl_certificate /etc/nginx/certs/server.crt;
#     ssl_certificate_key /etc/nginx/certs/server.key;
#     ssl_trusted_certificate /etc/nginx/certs/ca.crt;
#     
#     location / {
#         proxy_pass http://oee_dashboard;
#         proxy_set_header Host \$host;
#         proxy_set_header X-Real-IP \$remote_addr;
#         proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto \$scheme;
#     }
# }
EOF

    success "Configuration files created"
}

# Function to build images
build_images() {
    log "Building Docker images..."
    
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build --no-cache
    
    success "Docker images built"
}

# Function to start core services
start_core_services() {
    log "Starting core services..."
    
    # Start database first
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d sqlserver
    log "Waiting for SQL Server to be ready..."
    sleep 30
    
    # Wait for database to be healthy
    local retries=30
    while [ $retries -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T sqlserver /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "${SQL_SA_PASSWORD}" -Q "SELECT 1" &>/dev/null; then
            break
        fi
        sleep 10
        ((retries--))
    done
    
    if [ $retries -eq 0 ]; then
        error "SQL Server failed to start"
        exit 1
    fi
    
    # Start Redis and MQTT broker
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d redis mqtt-broker
    log "Waiting for Redis and MQTT broker..."
    sleep 10
    
    success "Core services started"
}

# Function to start application services
start_application_services() {
    log "Starting application services..."
    
    # Start main application
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d oee-dashboard
    log "Waiting for Django application..."
    sleep 20
    
    # Start Celery workers
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d celery-worker celery-beat
    
    # Start Sparkplug agent
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d sparkplug-agent
    log "Waiting for Sparkplug agent..."
    sleep 15
    
    success "Application services started"
}

# Function to start monitoring services
start_monitoring_services() {
    log "Starting monitoring services..."
    
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d prometheus grafana
    log "Waiting for monitoring services..."
    sleep 10
    
    success "Monitoring services started"
}

# Function to start simulators and proxy
start_remaining_services() {
    log "Starting PLC simulators and reverse proxy..."
    
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d plc-simulator-s7 plc-simulator-ab nginx
    
    success "All services started"
}

# Function to check service health
check_service_health() {
    log "Checking service health..."
    
    local services=(
        "sqlserver:1433"
        "redis:6379"
        "mqtt-broker:1883"
        "oee-dashboard:8000"
        "sparkplug-agent:8002"
        "prometheus:9090"
        "grafana:3000"
    )
    
    for service in "${services[@]}"; do
        local name="${service%:*}"
        local port="${service#*:}"
        
        log "Checking $name..."
        if timeout 10 bash -c "</dev/tcp/$name/$port"; then
            success "$name is responding"
        else
            warn "$name is not responding on port $port"
        fi
    done
}

# Function to show deployment summary
show_deployment_summary() {
    log "Deployment Summary"
    echo "===================="
    echo ""
    echo "Services URLs:"
    echo "  OEE Dashboard:    http://localhost"
    echo "  Grafana:          http://localhost/grafana (admin/${GRAFANA_PASSWORD:-admin123})"
    echo "  Prometheus:       http://localhost:9090"
    echo "  Sparkplug Metrics: http://localhost:8001/metrics"
    echo "  Health Check:     http://localhost:8002/health"
    echo ""
    echo "MQTT Broker:"
    echo "  Host: localhost"
    echo "  Port: 1883 (MQTT), 9001 (WebSocket)"
    echo ""
    echo "Database:"
    echo "  Host: localhost"
    echo "  Port: 1433"
    echo "  Username: sa"
    echo "  Password: ${SQL_SA_PASSWORD}"
    echo ""
    echo "PLC Simulators:"
    echo "  Siemens S7:       localhost:10102"
    echo "  Allen-Bradley:    localhost:10818"
    echo ""
    echo "Management Commands:"
    echo "  View logs:        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f [service]"
    echo "  Stop services:    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down"
    echo "  Restart service:  docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart [service]"
    echo ""
}

# Function to cleanup on failure
cleanup_on_failure() {
    error "Deployment failed. Cleaning up..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --remove-orphans
}

# Main deployment function
deploy() {
    local start_time=$(date +%s)
    
    log "Starting Sparkplug B OEE System deployment..."
    
    # Set up error handling
    trap cleanup_on_failure ERR
    
    # Run deployment steps
    check_prerequisites
    validate_environment
    create_directories
    generate_certificates
    create_config_files
    build_images
    start_core_services
    start_application_services
    start_monitoring_services
    start_remaining_services
    
    log "Waiting for all services to stabilize..."
    sleep 30
    
    check_service_health
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    success "Deployment completed successfully in ${duration} seconds!"
    show_deployment_summary
}

# Command line argument handling
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "stop")
        log "Stopping services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" restart
        success "Services restarted"
        ;;
    "logs")
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f "${2:-}"
        ;;
    "status")
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
        ;;
    "clean")
        log "Cleaning up deployment..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --volumes --remove-orphans
        docker system prune -f
        success "Cleanup completed"
        ;;
    "help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy    Deploy the complete system (default)"
        echo "  stop      Stop all services"
        echo "  restart   Restart all services"
        echo "  logs      View logs (optional service name)"
        echo "  status    Show service status"
        echo "  clean     Clean up deployment and volumes"
        echo "  help      Show this help message"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac