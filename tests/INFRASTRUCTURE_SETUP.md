# Integration Test Infrastructure Setup Guide

**Date**: 2025-10-01
**Status**: Tests Created ✓ | Infrastructure Pending

## Quick Summary

- **49 tests** created and validated
- **8 framework tests** passing
- **41 integration/load tests** require infrastructure
- All test code syntax validated

## Test Status

### ✅ Working Tests (No Infrastructure Required)

```bash
py -m pytest tests/test_framework_validation.py -v
# 8/8 tests PASSED
```

### ⏳ Integration Tests (Require Infrastructure)

- **6 E2E Sparkplug tests** → Requires MQTT + TimescaleDB
- **5 Store-Forward tests** → Requires MQTT + Redis
- **6 Backpressure tests** → Requires MQTT + Redis + OPC-UA
- **9 OPC-UA tests** → Requires OPC-UA + MQTT + TimescaleDB
- **5 Load tests** → Requires all services
- **10 TimescaleDB tests** → Requires TimescaleDB

---

## Infrastructure Requirements

### Required Services

| Service | Purpose | Port | Status |
|---------|---------|------|--------|
| **MQTT Broker** | Message routing | 1883, 8883 | ❌ Not running |
| **TimescaleDB** | Time-series data | 5432 | ❌ Not running |
| **Redis** | Store-and-forward queue | 6379 | ❌ Not running |
| **OPC-UA Simulator** | PLC simulation | 4840 | ❌ Not running |

### Current Environment Issues

1. **Docker Desktop**: Unable to start
2. **WSL**: No Linux distributions installed
3. **Windows Services**: No native PostgreSQL/Redis/MQTT running

---

## Setup Options

### Option 1: Docker Compose (Recommended)

**Prerequisites**:
- Docker Desktop installed and running
- OR Docker in WSL2

**Steps**:

```bash
# 1. Start MQTT cluster
cd docker/compose
./certs/generate_certs.sh
docker-compose -f docker-compose.mqtt-cluster.yml up -d

# 2. Start TimescaleDB
docker-compose -f docker-compose.timescaledb.yml up -d

# 3. Start Redis (if not in compose files)
docker run -d --name oee-redis -p 6379:6379 redis:7-alpine

# 4. Verify services
docker ps
curl http://localhost:18083  # EMQX dashboard
redis-cli ping
psql -h localhost -U oeeuser -d oee_analytics_test
```

**Initialize TimescaleDB Schema**:

```bash
# Connect to TimescaleDB
psql -h localhost -U oeeuser -d oee_analytics_test

# Run initialization script
\i docker/compose/timescaledb/init/01_init_timescaledb.sql
```

### Option 2: WSL2 + Docker

**Install WSL2 Ubuntu**:

```powershell
# List available distributions
wsl --list --online

# Install Ubuntu
wsl --install Ubuntu

# Set as default
wsl --set-default Ubuntu
```

**Install Docker in WSL2**:

```bash
# In WSL Ubuntu terminal
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo usermod -aG docker $USER

# Test
docker ps
```

**Then follow Option 1 steps in WSL**.

### Option 3: Windows Native Services

**Install Individual Services**:

1. **PostgreSQL with TimescaleDB**:
   ```powershell
   # Download PostgreSQL 15
   # https://www.postgresql.org/download/windows/

   # Install TimescaleDB extension
   # https://docs.timescale.com/install/latest/self-hosted/installation-windows/
   ```

2. **Redis**:
   ```powershell
   # Option A: Memurai (Redis-compatible for Windows)
   winget install Memurai.Memurai-Developer

   # Option B: Redis in WSL
   wsl
   sudo apt install redis-server
   sudo service redis-server start
   ```

3. **MQTT Broker**:
   ```powershell
   # Option A: Mosquitto
   winget install EclipseFoundation.Mosquitto

   # Option B: EMQX (recommended)
   # Download from https://www.emqx.io/downloads
   ```

4. **OPC-UA Simulator**:
   ```bash
   # Python-based simulator (included in tests)
   py -m pip install asyncua
   ```

### Option 4: Cloud Test Environment

**Use managed services** (for CI/CD):

- AWS RDS PostgreSQL with TimescaleDB
- AWS ElastiCache Redis
- AWS IoT Core MQTT
- Self-hosted OPC-UA simulator on EC2

---

## Running Tests

### 1. Framework Validation (No Infrastructure)

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard

# Run framework tests
py -m pytest tests/test_framework_validation.py -v

# Expected: 8/8 PASSED
```

### 2. Integration Tests (Requires Infrastructure)

**Prerequisites**: All services running (see setup options above)

**Environment Variables**:

```powershell
# Set test environment
$env:TEST_MQTT_BROKER="localhost"
$env:TEST_MQTT_PORT=1883
$env:TEST_MQTT_PORT_SSL=8883
$env:TEST_TIMESCALE_HOST="localhost"
$env:TEST_TIMESCALE_PORT=5432
$env:TEST_TIMESCALE_DB="oee_analytics_test"
$env:TEST_TIMESCALE_USER="oeeuser"
$env:TEST_TIMESCALE_PASSWORD="OEE_Analytics2024!"
$env:TEST_REDIS_HOST="localhost"
$env:TEST_REDIS_PORT=6379
```

**Run All Tests**:

```bash
# All integration tests
py -m pytest tests/ -v

# Specific test suites
py -m pytest tests/integration/test_e2e_sparkplug.py -v
py -m pytest tests/integration/test_store_forward.py -v
py -m pytest tests/integration/test_backpressure.py -v
py -m pytest tests/integration/test_opcua_integration.py -v
py -m pytest tests/integration/test_timescaledb_performance.py -v
py -m pytest tests/load/test_fault_storm.py -v

# By marker
py -m pytest -m integration -v
py -m pytest -m load -v
py -m pytest -m "requires_mqtt" -v
py -m pytest -m "not requires_opcua" -v  # Skip OPC-UA tests
```

**Run with Coverage**:

```bash
# Install coverage plugin
py -m pip install pytest-cov

# Run with coverage report
py -m pytest tests/ --cov=oee_analytics --cov-report=html

# View report
start htmlcov/index.html
```

---

## Troubleshooting

### Issue 1: Docker Desktop Won't Start

**Symptoms**: `Error response from daemon: Docker Desktop is unable to start`

**Solutions**:
1. Restart Windows
2. Update Docker Desktop to latest version
3. Enable WSL2 integration
4. Check Windows Hyper-V/WSL features enabled
5. Use WSL2 Docker instead (Option 2 above)

### Issue 2: No WSL Distributions

**Symptoms**: `Windows Subsystem for Linux has no installed distributions`

**Solution**:
```powershell
wsl --install Ubuntu
wsl --set-default Ubuntu
```

### Issue 3: Connection Refused (MQTT/Redis/PostgreSQL)

**Check Services Running**:
```bash
# Windows
tasklist | findstr mosquitto
tasklist | findstr postgres
tasklist | findstr redis

# Docker
docker ps

# WSL
sudo systemctl status mosquitto
sudo systemctl status postgresql
sudo systemctl status redis
```

**Check Firewall**:
```powershell
# Allow ports
New-NetFirewallRule -DisplayName "MQTT" -Direction Inbound -LocalPort 1883 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "PostgreSQL" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Redis" -Direction Inbound -LocalPort 6379 -Protocol TCP -Action Allow
```

### Issue 4: TimescaleDB Extension Not Found

**Solution**:
```sql
-- Connect to database
psql -h localhost -U postgres

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Verify
\dx timescaledb
```

### Issue 5: Test Timeouts

**Increase Timeout**:
```bash
# Edit tests/pytest.ini
timeout = 600  # Increase from 300 to 600 seconds
```

**Or skip slow tests**:
```bash
py -m pytest -m "not slow" -v
```

---

## Test Performance Targets

| Metric | Target | Test |
|--------|--------|------|
| E2E Latency (MQTT → DB) | <1s | test_e2e_sparkplug_ndata_telemetry |
| Write Performance | >10k inserts/sec | test_timescaledb_write_performance |
| Query Performance | <100ms | test_timescaledb_read_performance |
| Load Test Throughput | 1000 msg/sec | test_fault_storm_1000_msg_per_sec |
| Load Test Latency p95 | <2s | test_fault_storm_latency_under_load |
| Load Test Latency p99 | <5s | test_fault_storm_latency_under_load |
| OPC-UA Update Rate | 100 Hz | test_opcua_high_frequency_updates |

---

## CI/CD Integration

### GitHub Actions Workflow

Create `.github/workflows/integration-tests.yml`:

```yaml
name: Integration Tests

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mosquitto:
        image: eclipse-mosquitto:2
        ports:
          - 1883:1883

      timescaledb:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_USER: oeeuser
          POSTGRES_PASSWORD: OEE_Analytics2024!
          POSTGRES_DB: oee_analytics_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Initialize TimescaleDB
        run: |
          psql -h localhost -U oeeuser -d oee_analytics_test -f docker/compose/timescaledb/init/01_init_timescaledb.sql
        env:
          PGPASSWORD: OEE_Analytics2024!

      - name: Run framework tests
        run: pytest tests/test_framework_validation.py -v

      - name: Run integration tests
        run: pytest tests/ --cov=oee_analytics --cov-report=xml -v
        env:
          TEST_MQTT_BROKER: localhost
          TEST_TIMESCALE_HOST: localhost
          TEST_REDIS_HOST: localhost

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## Next Steps

### Immediate (Fix Environment)

1. ✅ **Fix Docker Desktop** OR install WSL2 Ubuntu
2. ✅ **Start required services** using Option 1, 2, or 3
3. ✅ **Initialize TimescaleDB schema**
4. ✅ **Verify connectivity** to all services
5. ✅ **Run integration tests**

### Short-term (Test Execution)

1. Run each test suite individually to isolate issues
2. Fix any test failures or connection issues
3. Document actual vs target performance metrics
4. Create test execution report

### Long-term (CI/CD)

1. Set up GitHub Actions workflow
2. Add automated test runs on PR
3. Configure test reporting and coverage badges
4. Set up nightly load test runs

---

## Test Suite Statistics

- **Total Tests**: 49
- **Framework Tests**: 8 ✅ PASSING
- **Integration Tests**: 41 ⏳ PENDING (infrastructure)
- **Coverage Target**: >80% for production code
- **Performance Tests**: 5 load tests with latency/throughput targets

---

## Contact

For questions or issues with test infrastructure:
- See main project documentation
- Check `TEST_STATUS.md` for detailed test descriptions
- Open GitHub issue for test failures

---

**Last Updated**: 2025-10-01
**Test Framework Version**: pytest 8.4.2
**Python Version**: 3.13.6
