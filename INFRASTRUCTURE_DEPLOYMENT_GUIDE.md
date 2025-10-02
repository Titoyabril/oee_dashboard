# OEE Analytics - Infrastructure Deployment Guide

**Date**: 2025-10-01
**Status**: Integration Tests Ready | Infrastructure Setup Required

---

## Current Status

### ✅ Completed
- **Integration test suite**: 49 tests created and validated
- **Framework tests**: 8/8 passing
- **Test infrastructure code**: All syntax validated
- **Docker compose files**: MQTT cluster, TimescaleDB, Redis configurations ready
- **Terraform IaC**: AWS deployment templates prepared

### ⏳ Pending
- **Docker environment**: Docker Desktop unable to start
- **WSL2**: Ubuntu 24.04 installation in progress (may require system restart)
- **Service deployment**: MQTT, TimescaleDB, Redis not running

---

## Deployment Options

### Option 1: WSL2 + Docker (Recommended for Development)

**Current Status**: Ubuntu 24.04 installation in progress

**Next Steps After WSL Installation Completes**:

1. **Verify WSL Installation**:
   ```powershell
   wsl --list --verbose
   wsl --set-default Ubuntu-24.04
   ```

2. **Access WSL Ubuntu**:
   ```powershell
   wsl
   ```

3. **Update and Install Docker in WSL** (run in WSL terminal):
   ```bash
   # Update packages
   sudo apt update && sudo apt upgrade -y

   # Install Docker
   sudo apt install -y docker.io docker-compose

   # Start Docker
   sudo systemctl start docker
   sudo systemctl enable docker

   # Add user to docker group
   sudo usermod -aG docker $USER

   # Restart WSL to apply group changes
   exit
   ```

4. **Restart WSL from PowerShell**:
   ```powershell
   wsl --shutdown
   wsl
   ```

5. **Verify Docker Works**:
   ```bash
   docker --version
   docker ps
   ```

6. **Navigate to Project in WSL**:
   ```bash
   cd /mnt/c/dev/projects/oee_dashboard/oee_dashboard
   ```

7. **Deploy Services**:
   ```bash
   # Generate certificates for MQTT
   cd docker/compose/certs
   chmod +x generate_certs.sh
   ./generate_certs.sh
   cd ..

   # Start MQTT cluster
   docker-compose -f docker-compose.mqtt-cluster.yml up -d

   # Start TimescaleDB
   docker-compose -f docker-compose.timescaledb.yml up -d

   # Verify services
   docker ps
   ```

8. **Initialize TimescaleDB**:
   ```bash
   # Wait for TimescaleDB to be ready
   sleep 10

   # Run init script
   docker exec -i oee-timescaledb psql -U oeeuser -d oee_analytics_test < timescaledb/init/01_init_timescaledb.sql
   ```

9. **Access Services**:
   - MQTT Dashboard: http://localhost:18083 (admin/public)
   - PgAdmin: http://localhost:5050 (admin@oee.local / admin)
   - Grafana: http://localhost:3000 (admin/admin)
   - HAProxy Stats: http://localhost:8404/stats (admin/admin)

---

### Option 2: Docker Desktop (When Fixed)

**Current Issue**: Docker Desktop won't start

**Troubleshooting Steps**:

1. **Check Windows Features**:
   ```powershell
   # Run as Administrator
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```

2. **Restart Computer** (required after enabling features)

3. **Update WSL Kernel**:
   ```powershell
   wsl --update
   wsl --set-default-version 2
   ```

4. **Reinstall/Update Docker Desktop**:
   - Download latest: https://www.docker.com/products/docker-desktop/
   - Uninstall current version
   - Install new version
   - Enable WSL2 integration during setup

5. **Start Docker Desktop and Enable WSL Integration**:
   - Settings → Resources → WSL Integration
   - Enable integration with Ubuntu-24.04

6. **Then Follow Same Deployment Steps as Option 1**

---

### Option 3: Windows Native Services (No Docker)

**For Development Without Docker**:

#### 1. PostgreSQL with TimescaleDB

```powershell
# Download PostgreSQL 15
# https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

# Install PostgreSQL
# During install: Set password for postgres user

# Download TimescaleDB
# https://docs.timescale.com/install/latest/self-hosted/installation-windows/

# Install TimescaleDB extension
# Follow installer wizard

# Create test database
psql -U postgres -c "CREATE DATABASE oee_analytics_test;"
psql -U postgres -c "CREATE USER oeeuser WITH PASSWORD 'OEE_Analytics2024!';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE oee_analytics_test TO oeeuser;"

# Enable TimescaleDB extension
psql -U postgres -d oee_analytics_test -c "CREATE EXTENSION timescaledb CASCADE;"

# Run initialization script
psql -U oeeuser -d oee_analytics_test -f C:\dev\projects\oee_dashboard\oee_dashboard\docker\compose\timescaledb\init\01_init_timescaledb.sql
```

#### 2. Redis (Memurai for Windows)

```powershell
# Option A: Install Memurai (Redis-compatible)
winget install Memurai.Memurai-Developer

# Verify
redis-cli ping
# Expected: PONG

# Option B: Use WSL Redis
wsl
sudo apt install redis-server
sudo service redis-server start
redis-cli ping
```

#### 3. MQTT Broker (Mosquitto or EMQX)

**Mosquitto**:
```powershell
# Install
winget install EclipseFoundation.Mosquitto

# Configure
# Edit C:\Program Files\mosquitto\mosquitto.conf
# Add:
#   listener 1883
#   allow_anonymous true

# Start service
net start mosquitto

# Test
# Open another terminal
mosquitto_sub -h localhost -t test
# In another terminal:
mosquitto_pub -h localhost -t test -m "hello"
```

**EMQX** (Recommended):
```powershell
# Download from https://www.emqx.io/downloads
# Choose "Windows (zip)"
# Extract to C:\Program Files\EMQX

# Start
cd "C:\Program Files\EMQX\bin"
.\emqx.cmd start

# Access dashboard
# http://localhost:18083
# Login: admin / public
```

#### 4. Configure Test Environment Variables

```powershell
# Set environment variables for tests
$env:TEST_MQTT_BROKER="localhost"
$env:TEST_MQTT_PORT=1883
$env:TEST_TIMESCALE_HOST="localhost"
$env:TEST_TIMESCALE_PORT=5432
$env:TEST_TIMESCALE_DB="oee_analytics_test"
$env:TEST_TIMESCALE_USER="oeeuser"
$env:TEST_TIMESCALE_PASSWORD="OEE_Analytics2024!"
$env:TEST_REDIS_HOST="localhost"
$env:TEST_REDIS_PORT=6379
```

---

### Option 4: Cloud Deployment (Production)

**Use Terraform for AWS Deployment**:

```bash
cd terraform

# Initialize Terraform
terraform init

# Review plan
terraform plan \
  -var="environment=production" \
  -var="alert_email=ops@company.com" \
  -var="timescale_password=SecurePassword123!"

# Deploy infrastructure
terraform apply

# Get outputs
terraform output mqtt_broker_endpoint
terraform output application_url
terraform output timescaledb_endpoint
```

**Services Created**:
- **MQTT Cluster**: 3× EC2 instances running EMQX
- **TimescaleDB**: RDS PostgreSQL with TimescaleDB
- **Redis**: ElastiCache cluster
- **Application**: ECS Fargate for Django app
- **Load Balancer**: ALB with SSL termination
- **Monitoring**: CloudWatch + SNS alerts

---

## Service Verification

### Check All Services Running

**Docker (WSL/Desktop)**:
```bash
docker ps

# Expected output:
# - emqx-node1, emqx-node2, emqx-node3 (MQTT cluster)
# - oee-timescaledb (PostgreSQL)
# - oee-pgadmin (PgAdmin)
# - redis (if using Docker)
# - prometheus, grafana (monitoring)
# - haproxy (load balancer)
```

**Windows Native**:
```powershell
# Check PostgreSQL
Get-Service | Where-Object {$_.Name -like '*postgres*'}

# Check Redis/Memurai
Get-Service | Where-Object {$_.Name -like '*redis*' -or $_.Name -like '*memurai*'}

# Check Mosquitto/EMQX
Get-Service | Where-Object {$_.Name -like '*mosquitto*' -or $_.Name -like '*emqx*'}

# Test connectivity
Test-NetConnection -ComputerName localhost -Port 5432  # PostgreSQL
Test-NetConnection -ComputerName localhost -Port 6379  # Redis
Test-NetConnection -ComputerName localhost -Port 1883  # MQTT
```

### Test Connectivity

**PostgreSQL/TimescaleDB**:
```bash
psql -h localhost -U oeeuser -d oee_analytics_test -c "SELECT version();"
psql -h localhost -U oeeuser -d oee_analytics_test -c "SELECT extname FROM pg_extension WHERE extname='timescaledb';"
```

**Redis**:
```bash
redis-cli ping
# Expected: PONG

redis-cli set test "hello"
redis-cli get test
# Expected: "hello"
```

**MQTT**:
```bash
# Terminal 1 - Subscribe
mosquitto_sub -h localhost -p 1883 -t test/topic

# Terminal 2 - Publish
mosquitto_pub -h localhost -p 1883 -t test/topic -m "Hello MQTT"

# Expected: "Hello MQTT" appears in Terminal 1
```

---

## Running Integration Tests

### Prerequisites Checklist

- [ ] All services running (MQTT, TimescaleDB, Redis)
- [ ] TimescaleDB schema initialized
- [ ] Environment variables set
- [ ] Test dependencies installed (`py -m pip install pytest pytest-asyncio asyncpg asyncio-mqtt`)

### Execute Tests

```powershell
cd C:\dev\projects\oee_dashboard\oee_dashboard

# Set environment (if not already set)
$env:TEST_MQTT_BROKER="localhost"
$env:TEST_MQTT_PORT=1883
$env:TEST_TIMESCALE_HOST="localhost"
$env:TEST_TIMESCALE_PORT=5432
$env:TEST_TIMESCALE_DB="oee_analytics_test"
$env:TEST_TIMESCALE_USER="oeeuser"
$env:TEST_TIMESCALE_PASSWORD="OEE_Analytics2024!"
$env:TEST_REDIS_HOST="localhost"
$env:TEST_REDIS_PORT=6379

# Run framework tests (no infrastructure needed)
py -m pytest tests/test_framework_validation.py -v

# Run all integration tests
py -m pytest tests/ -v -s

# Run specific test suites
py -m pytest tests/integration/test_e2e_sparkplug.py -v
py -m pytest tests/integration/test_store_forward.py -v
py -m pytest tests/integration/test_timescaledb_performance.py -v
py -m pytest tests/load/test_fault_storm.py -v

# Generate coverage report
py -m pip install pytest-cov
py -m pytest tests/ --cov=oee_analytics --cov-report=html --cov-report=term
start htmlcov/index.html
```

---

## Monitoring and Dashboards

### EMQX Dashboard
- **URL**: http://localhost:18083
- **Login**: admin / public
- **Features**:
  - Client connections
  - Topic subscriptions
  - Message throughput
  - Rule engine

### Grafana (MQTT Metrics)
- **URL**: http://localhost:3000
- **Login**: admin / admin
- **Dashboards**:
  - EMQX cluster metrics
  - Message rates and latencies
  - Connection counts

### PgAdmin (TimescaleDB)
- **URL**: http://localhost:5050
- **Login**: admin@oee.local / admin
- **Features**:
  - Query editor
  - Schema browser
  - Performance insights

### HAProxy Stats
- **URL**: http://localhost:8404/stats
- **Login**: admin / admin
- **Features**:
  - Backend server health
  - Request rates
  - Connection pools

---

## Troubleshooting

### Docker Won't Start

**Symptoms**: `Error response from daemon: Docker Desktop is unable to start`

**Solutions**:
1. Enable Windows features (Hyper-V, WSL)
2. Update WSL kernel: `wsl --update`
3. Restart computer
4. Reinstall Docker Desktop
5. Use WSL2 Docker instead (Option 1)

### WSL Installation Stuck

**Current Status**: Ubuntu-24.04 installation may take 5-15 minutes

**If Stuck >15 minutes**:
```powershell
# Cancel installation
Ctrl+C

# Try simpler Ubuntu
wsl --install Ubuntu

# Or check WSL status
wsl --status
```

### Services Won't Connect

**Check Firewall**:
```powershell
# Allow ports
New-NetFirewallRule -DisplayName "PostgreSQL" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Redis" -Direction Inbound -LocalPort 6379 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "MQTT" -Direction Inbound -LocalPort 1883,8883 -Protocol TCP -Action Allow
```

**Check Services Running**:
```bash
# Docker
docker ps
docker logs <container-name>

# Windows services
Get-Service | Where-Object {$_.Status -eq 'Running'}
```

### Tests Fail with Connection Errors

**Verify Environment Variables**:
```powershell
# Check variables are set
$env:TEST_MQTT_BROKER
$env:TEST_TIMESCALE_HOST
$env:TEST_REDIS_HOST

# Re-export if needed
$env:TEST_MQTT_BROKER="localhost"
# ... etc
```

**Test Individual Connections**:
```bash
# MQTT
mosquitto_pub -h localhost -t test -m "hello"

# Redis
redis-cli ping

# PostgreSQL
psql -h localhost -U oeeuser -d oee_analytics_test -c "SELECT 1;"
```

---

## Next Steps After Infrastructure Setup

1. **Run Integration Tests**: Verify all 49 tests pass
2. **Performance Benchmarking**: Measure actual vs target metrics
3. **Load Testing**: Run fault storm tests (1000 msg/sec)
4. **CI/CD Setup**: Configure GitHub Actions workflow
5. **Production Deployment**: Use Terraform to deploy to AWS
6. **Monitoring Setup**: Configure alerts and dashboards
7. **Documentation**: Update runbooks and operational procedures

---

## Production Deployment Checklist

Before going to production:

- [ ] All integration tests passing (49/49)
- [ ] Load tests meet performance targets
- [ ] Security audit completed (mTLS, ACLs, network segmentation)
- [ ] Backup and recovery procedures tested
- [ ] Monitoring and alerting configured
- [ ] Runbooks created for common operations
- [ ] Disaster recovery plan documented
- [ ] Penetration testing completed
- [ ] Compliance requirements met (if applicable)
- [ ] Change management approval obtained

---

## Reference Documentation

- **Implementation Summary**: `IMPLEMENTATION_SUMMARY.md`
- **Test Status**: `tests/TEST_STATUS.md`
- **Test Infrastructure**: `tests/INFRASTRUCTURE_SETUP.md`
- **MQTT Cluster Guide**: `docker/compose/README_MQTT_CLUSTER.md`
- **Terraform Deployment**: `terraform/README.md` (to be created)
- **Ansible Playbooks**: `ansible/README.md` (to be created)

---

## Support

For issues with infrastructure deployment:
- Review this guide and referenced documentation
- Check service logs: `docker logs <container>`
- Verify network connectivity and firewall rules
- Test each service individually before running integration tests

---

**Last Updated**: 2025-10-01
**Deployment Status**: Pending Infrastructure Setup
**Test Readiness**: 100% (49/49 tests created and validated)
