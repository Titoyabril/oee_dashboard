#!/bin/bash
# Production entrypoint script for Sparkplug B Agent

set -e

# Environment variables with defaults
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-oee_dashboard.settings}
export SPARKPLUG_LOG_LEVEL=${SPARKPLUG_LOG_LEVEL:-INFO}
export SPARKPLUG_CONFIG_FILE=${SPARKPLUG_CONFIG_FILE:-/app/config/sparkplug_config.yaml}

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Function to check if service is ready
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=${4:-60}
    
    log "Waiting for $service_name at $host:$port..."
    
    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            log "$service_name is ready!"
            return 0
        fi
        sleep 1
    done
    
    log "ERROR: $service_name at $host:$port is not ready after ${timeout}s"
    return 1
}

# Function to validate configuration
validate_config() {
    log "Validating configuration..."
    
    # Check required environment variables
    local required_vars=(
        "MQTT_BROKER_HOST"
        "DATABASE_HOST"
        "DATABASE_NAME"
        "DATABASE_USER"
        "DATABASE_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            log "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Check configuration file exists
    if [[ ! -f "$SPARKPLUG_CONFIG_FILE" ]]; then
        log "ERROR: Configuration file not found: $SPARKPLUG_CONFIG_FILE"
        exit 1
    fi
    
    log "Configuration validation passed"
}

# Function to run database migrations
run_migrations() {
    log "Running database migrations..."
    python manage.py migrate --noinput
    log "Database migrations completed"
}

# Function to create default configuration if needed
create_default_config() {
    if [[ ! -f "$SPARKPLUG_CONFIG_FILE" ]]; then
        log "Creating default configuration..."
        python manage.py sparkplug_agent --create-default-config "$SPARKPLUG_CONFIG_FILE"
    fi
}

# Function to start health check server
start_health_check() {
    log "Starting health check server..."
    python -c "
import asyncio
import json
from aiohttp import web
from datetime import datetime

async def health_check(request):
    return web.json_response({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'sparkplug-agent',
        'version': '1.0.0'
    })

async def readiness_check(request):
    # Add readiness checks here
    return web.json_response({
        'status': 'ready',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {
            'database': 'ok',
            'mqtt': 'ok'
        }
    })

app = web.Application()
app.router.add_get('/health', health_check)
app.router.add_get('/ready', readiness_check)

web.run_app(app, host='0.0.0.0', port=8002)
" &
    
    HEALTH_CHECK_PID=$!
    log "Health check server started (PID: $HEALTH_CHECK_PID)"
}

# Function to cleanup on exit
cleanup() {
    log "Cleaning up..."
    
    if [[ -n "$HEALTH_CHECK_PID" ]]; then
        kill "$HEALTH_CHECK_PID" 2>/dev/null || true
    fi
    
    if [[ -n "$SPARKPLUG_PID" ]]; then
        kill "$SPARKPLUG_PID" 2>/dev/null || true
    fi
    
    log "Cleanup completed"
}

# Set up signal handlers
trap cleanup EXIT TERM INT

# Main execution
main() {
    log "Starting Sparkplug B Agent (Production)"
    log "Configuration file: $SPARKPLUG_CONFIG_FILE"
    log "Log level: $SPARKPLUG_LOG_LEVEL"
    
    # Validate configuration
    validate_config
    
    # Wait for dependencies
    if [[ -n "$DATABASE_HOST" ]]; then
        wait_for_service "$DATABASE_HOST" "${DATABASE_PORT:-1433}" "Database"
    fi
    
    if [[ -n "$MQTT_BROKER_HOST" ]]; then
        wait_for_service "$MQTT_BROKER_HOST" "${MQTT_BROKER_PORT:-1883}" "MQTT Broker"
    fi
    
    # Run database migrations
    run_migrations
    
    # Create default configuration if needed
    create_default_config
    
    # Start health check server
    start_health_check
    
    # Start the Sparkplug agent
    log "Starting Sparkplug B Agent..."
    exec python manage.py sparkplug_agent \
        --config-file "$SPARKPLUG_CONFIG_FILE" \
        --log-level "$SPARKPLUG_LOG_LEVEL" \
        "$@"
}

# Run main function
main "$@"