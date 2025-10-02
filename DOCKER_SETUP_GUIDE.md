# Docker Desktop Installation & Infrastructure Setup Guide

**Target**: Deploy OEE Analytics infrastructure and run integration tests

## Step 1: Install Docker Desktop

### Download Docker Desktop

1. **Open Browser** and navigate to:
   ```
   https://www.docker.com/products/docker-desktop/
   ```

2. **Download for Windows**
   - Click "Download for Windows"
   - File: `Docker Desktop Installer.exe` (~500 MB)

### Installation Steps

1. **Run Installer** (requires Administrator privileges)
   - Double-click `Docker Desktop Installer.exe`
   - Accept the license agreement
   - Keep default settings:
     - ✓ Use WSL 2 instead of Hyper-V (recommended)
     - ✓ Add shortcut to desktop

2. **Wait for Installation** (~5-10 minutes)
   - Installer will download required components
   - Windows may prompt for permissions

3. **Restart Computer** (required)
   - Docker requires a restart to complete installation

### Post-Installation Verification

After restart, verify Docker is running:

1. **Start Docker Desktop**
   - Docker should start automatically
   - Look for Docker icon in system tray (bottom-right)
   - Icon should show "Docker Desktop is running"

2. **Open PowerShell or Command Prompt**
   ```powershell
   # Check Docker version
   docker --version
   # Expected: Docker version 24.0.x, build xxxxx

   # Check Docker Compose version
   docker-compose --version
   # Expected: Docker Compose version v2.x.x

   # Verify Docker is running
   docker ps
   # Expected: Empty table (no containers running yet)
   ```

3. **If Docker Daemon Not Running**
   - Open Docker Desktop from Start Menu
   - Wait for "Docker Desktop starting..." to complete
   - Green icon in tray = ready

### Troubleshooting

**Issue: "WSL 2 installation is incomplete"**
```powershell
# Enable WSL 2
wsl --install
# Restart computer
```

**Issue: "Docker daemon not running"**
- Start Docker Desktop application manually
- Wait 30-60 seconds for startup

**Issue: "Hyper-V is not enabled"**
- Go to Control Panel → Programs → Turn Windows features on or off
- Enable: Hyper-V, Containers, Virtual Machine Platform
- Restart computer

---

## Step 2: Deploy OEE Analytics Infrastructure

Once Docker is installed and running, deploy the infrastructure stack.

### Navigate to Project Directory

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard
```

### Generate Certificates (One-Time Setup)

```bash
cd docker/compose/certs

# On Windows with Git Bash or WSL
bash generate_certs.sh

# If bash not available, you'll need to manually create certificates
# See: README in certs directory
```

**Manual Certificate Generation (if bash not available)**:
```bash
# Install OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html
# Then run the commands from generate_certs.sh manually
```

### Start MQTT Cluster (EMQX)

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard\docker\compose

# Start 3-node EMQX cluster with HAProxy
docker-compose -f docker-compose.mqtt-cluster.yml up -d
```

**Expected Output**:
```
Creating network "compose_mqtt_cluster_network" ... done
Creating emqx1      ... done
Creating emqx2      ... done
Creating emqx3      ... done
Creating haproxy    ... done
Creating prometheus ... done
Creating grafana    ... done
```

**Verify MQTT Cluster**:
```bash
# Check containers are running
docker ps

# Expected: 6 containers (emqx1, emqx2, emqx3, haproxy, prometheus, grafana)

# Check EMQX dashboard
# Open browser: http://localhost:18083
# Default credentials: admin / public
```

### Start TimescaleDB

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard\docker\compose

# Start TimescaleDB + PgAdmin
docker-compose -f docker-compose.timescaledb.yml up -d
```

**Expected Output**:
```
Creating network "compose_timescaledb_network" ... done
Creating timescaledb        ... done
Creating pgadmin            ... done
Creating postgres-exporter  ... done
```

**Verify TimescaleDB**:
```bash
# Check container is running
docker ps | findstr timescaledb

# Connect to database (password: OEE_Analytics2024!)
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test

# Inside psql:
\dt  # List tables
\q   # Quit
```

### Start Redis

```bash
# Start Redis container
docker run -d ^
  --name oee-redis ^
  -p 6379:6379 ^
  redis:7-alpine ^
  redis-server --appendonly yes

# Verify Redis
docker exec -it oee-redis redis-cli ping
# Expected: PONG
```

### Initialize TimescaleDB Schema

```bash
# Copy SQL init script into container
docker cp docker/compose/timescaledb/init/01_init_timescaledb.sql timescaledb:/tmp/

# Execute initialization script
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test -f /tmp/01_init_timescaledb.sql
```

**Expected Output**:
```
CREATE TABLE
CREATE INDEX
SELECT create_hypertable
SELECT add_dimension
ALTER TABLE
SELECT add_compression_policy
...
```

### Verify All Services Running

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected Output**:
```
NAMES                 STATUS              PORTS
emqx1                 Up 2 minutes        0.0.0.0:1883->1883/tcp, ...
emqx2                 Up 2 minutes        1883/tcp, ...
emqx3                 Up 2 minutes        1883/tcp, ...
haproxy               Up 2 minutes        0.0.0.0:1883->1883/tcp, ...
prometheus            Up 2 minutes        0.0.0.0:9090->9090/tcp
grafana               Up 2 minutes        0.0.0.0:3000->3000/tcp
timescaledb           Up 1 minute         0.0.0.0:5432->5432/tcp
pgadmin               Up 1 minute         0.0.0.0:5050->80/tcp
postgres-exporter     Up 1 minute         0.0.0.0:9187->9187/tcp
oee-redis             Up 30 seconds       0.0.0.0:6379->6379/tcp
```

### Access Web Interfaces

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **EMQX Dashboard** | http://localhost:18083 | admin / public |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | (no auth) |
| **PgAdmin** | http://localhost:5050 | admin@admin.com / admin |

---

## Step 3: Run Integration Tests

### Install Missing Python Dependencies

```bash
# Install eclipse-tahu alternative (if needed)
# Since eclipse-tahu not on PyPI, we use simplified builder in tests

# Install PostgreSQL adapter
py -m pip install psycopg2-binary

# Install any other missing packages
py -m pip install asyncpg redis aiofiles
```

### Run Framework Validation Tests

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard

# Run framework validation
py -m pytest tests/test_framework_validation.py -v -s
```

**Expected**: 8/8 tests pass

### Run Integration Tests

#### Test 1: End-to-End Sparkplug B

```bash
py -m pytest tests/integration/test_e2e_sparkplug.py -v -s
```

**Expected Results**:
- NBIRTH → Database flow: ✓
- NDATA telemetry with <1s latency: ✓
- DBIRTH/DDATA device messages: ✓
- Sequence number validation: ✓
- Message ordering under load: ✓
- Continuous aggregate updates: ✓

#### Test 2: Store-and-Forward Resilience

```bash
py -m pytest tests/integration/test_store_forward.py -v -s
```

**Expected Results**:
- Broker outage queue management: ✓
- Queue persistence across restarts: ✓
- Max queue watermark (500 MB): ✓
- **Zero data loss validation**: ✓
- Long outage simulation: ✓

#### Test 3: Backpressure & Adaptive Sampling

```bash
py -m pytest tests/integration/test_backpressure.py -v -s
```

**Expected Results**:
- Backpressure detection: ✓
- Backpressure clearing: ✓
- Adaptive sampling (250ms → 2000ms): ✓
- No message loss during sampling changes: ✓
- Transition delay anti-thrashing: ✓
- Memory stability under load: ✓

#### Test 4: OPC-UA Integration

```bash
py -m pytest tests/integration/test_opcua_integration.py -v -s
```

**Note**: Requires OPC-UA simulator. Skip if not available:
```bash
py -m pytest tests/integration/test_opcua_integration.py -v -s -m "not requires_opcua"
```

#### Test 5: TimescaleDB Performance

```bash
py -m pytest tests/integration/test_timescaledb_performance.py -v -s
```

**Expected Results**:
- Hypertable validation: ✓
- Compression policies: ✓
- Continuous aggregates: ✓
- Write performance >10k inserts/sec: ✓
- Read performance <100ms: ✓
- Concurrent write handling: ✓

#### Test 6: Fault Storm Load Tests

```bash
py -m pytest tests/load/test_fault_storm.py -v -s
```

**Expected Results**:
- 1000 msg/sec sustained: ✓
- Burst pattern handling: ✓
- Concurrent nodes (10 @ 100 msg/sec): ✓
- Memory stability: ✓
- Latency p95 < 2000ms, p99 < 5000ms: ✓

### Run All Tests

```bash
# Run complete test suite
py -m pytest tests/ -v -s --maxfail=5

# OR run by category
py -m pytest -m integration -v -s
py -m pytest -m load -v -s

# With coverage report
py -m pip install pytest-cov
py -m pytest tests/ --cov=oee_analytics --cov-report=html
```

### Monitor During Tests

**In separate terminal windows**:

```bash
# Monitor Docker container stats
docker stats

# Monitor MQTT messages
docker exec -it emqx1 emqx_ctl broker stats

# Monitor TimescaleDB connections
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test -c "SELECT * FROM pg_stat_activity;"

# Monitor Redis queue
docker exec -it oee-redis redis-cli monitor
```

---

## Step 4: Verify Results

### Check Test Logs

```bash
# Tests create logs in tests/logs/
dir tests\logs\pytest.log

# View recent test output
type tests\logs\pytest.log | findstr /C:"PASSED" /C:"FAILED"
```

### Verify Database Data

```bash
# Connect to TimescaleDB
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test

# Check telemetry data
SELECT COUNT(*) FROM telemetry;
SELECT machine_id, COUNT(*) FROM telemetry GROUP BY machine_id;

# Check continuous aggregates
SELECT * FROM telemetry_1min ORDER BY bucket DESC LIMIT 10;

# Check compression status
SELECT * FROM timescaledb_information.chunks;
```

### Check MQTT Broker

Open browser: http://localhost:18083

**Dashboard → Clients**:
- View connected test clients
- Check message rates

**Dashboard → Topics**:
- View Sparkplug topics
- Check message counts

**Dashboard → Metrics**:
- Messages/sec received
- Messages/sec sent
- Connection counts

### Performance Metrics

**From Test Output**:
```
End-to-End Latency: XX ms (Target: <1000ms)
Write Throughput: XXXX inserts/sec (Target: >10000)
Message Rate: XXX msg/sec (Target: 1000)
p95 Latency: XXX ms (Target: <2000ms)
p99 Latency: XXX ms (Target: <5000ms)
```

---

## Step 5: Cleanup (When Done)

### Stop All Services

```bash
cd C:\dev\projects\oee_dashboard\oee_dashboard\docker\compose

# Stop MQTT cluster
docker-compose -f docker-compose.mqtt-cluster.yml down

# Stop TimescaleDB
docker-compose -f docker-compose.timescaledb.yml down

# Stop Redis
docker stop oee-redis
docker rm oee-redis

# Verify all stopped
docker ps -a
```

### Remove All Containers and Volumes (Clean Reset)

```bash
# WARNING: This deletes all data!

# Remove all OEE containers
docker-compose -f docker-compose.mqtt-cluster.yml down -v
docker-compose -f docker-compose.timescaledb.yml down -v
docker rm -f oee-redis

# Remove networks
docker network prune -f

# Remove volumes (WARNING: Deletes all data!)
docker volume prune -f
```

### Preserve Data (Backup Before Cleanup)

```bash
# Backup TimescaleDB
docker exec timescaledb pg_dump -U oeeuser oee_analytics_test > backup_$(date +%Y%m%d).sql

# Backup Redis
docker exec oee-redis redis-cli BGSAVE
docker cp oee-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

---

## Troubleshooting

### Issue: Container Won't Start

```bash
# Check logs
docker logs <container_name>

# Common issues:
# - Port already in use
# - Insufficient memory
# - Configuration error
```

**Fix Port Conflicts**:
```bash
# Find process using port
netstat -ano | findstr :1883

# Kill process (replace PID)
taskkill /PID <pid> /F
```

### Issue: EMQX Cluster Not Forming

```bash
# Check cluster status
docker exec emqx1 emqx_ctl cluster status

# If nodes not connected, restart in order
docker restart emqx1
docker restart emqx2
docker restart emqx3
```

### Issue: TimescaleDB Connection Refused

```bash
# Check if TimescaleDB is ready
docker exec timescaledb pg_isready -U oeeuser

# Check logs
docker logs timescaledb

# Verify password
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test
```

### Issue: Tests Timing Out

```bash
# Increase pytest timeout in pytest.ini
timeout = 600  # 10 minutes

# Or run specific test with longer timeout
py -m pytest tests/integration/test_e2e_sparkplug.py -v -s --timeout=600
```

### Issue: Out of Memory

```bash
# Check Docker memory allocation
# Docker Desktop → Settings → Resources → Advanced
# Increase Memory to at least 8 GB

# Check container memory usage
docker stats
```

### Issue: Certificate Errors (MQTT)

```bash
# Regenerate certificates
cd docker/compose/certs
bash generate_certs.sh

# Restart MQTT cluster
docker-compose -f docker-compose.mqtt-cluster.yml restart
```

---

## Performance Tuning

### For Load Tests

Before running load tests, ensure Docker has adequate resources:

**Docker Desktop Settings** → **Resources**:
- **CPUs**: 4+ cores
- **Memory**: 8+ GB
- **Swap**: 2 GB
- **Disk**: 50+ GB

### For TimescaleDB

```bash
# Connect to TimescaleDB
docker exec -it timescaledb psql -U oeeuser -d oee_analytics_test

# Check current settings
SHOW shared_buffers;
SHOW effective_cache_size;
SHOW work_mem;

# Adjust if needed (already configured in docker-compose)
# See: docker/compose/timescaledb/config/postgresql.conf
```

---

## Next Steps After Successful Testing

1. **Review Test Results**
   - Check all tests passed
   - Review performance metrics
   - Identify any bottlenecks

2. **Fix Any Issues**
   - Address test failures
   - Optimize slow queries
   - Tune configuration

3. **Production Deployment**
   - Use Ansible playbooks for edge gateways
   - Use Terraform for cloud infrastructure
   - See: `ansible/README.md` and `terraform/README.md`

4. **CI/CD Integration**
   - Set up GitHub Actions
   - Automate test runs on PR
   - Deploy to staging automatically

5. **Monitoring Setup**
   - Configure Grafana dashboards
   - Set up alerting rules
   - Enable log aggregation

---

## Quick Reference

### Common Commands

```bash
# Start all services
cd docker/compose
docker-compose -f docker-compose.mqtt-cluster.yml up -d
docker-compose -f docker-compose.timescaledb.yml up -d
docker run -d --name oee-redis -p 6379:6379 redis:7-alpine

# Run all tests
py -m pytest tests/ -v -s

# Stop all services
docker-compose -f docker-compose.mqtt-cluster.yml down
docker-compose -f docker-compose.timescaledb.yml down
docker stop oee-redis && docker rm oee-redis

# Check logs
docker logs emqx1
docker logs timescaledb
docker logs oee-redis
```

### Service URLs

- EMQX Dashboard: http://localhost:18083 (admin/public)
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- PgAdmin: http://localhost:5050 (admin@admin.com/admin)

### Test Commands

```bash
# Framework validation
py -m pytest tests/test_framework_validation.py -v -s

# All integration tests
py -m pytest tests/integration/ -v -s

# All load tests
py -m pytest tests/load/ -v -s

# Specific test
py -m pytest tests/integration/test_e2e_sparkplug.py::test_e2e_sparkplug_ndata_telemetry -v -s
```

---

**For support or issues, refer to `DEPLOYMENT_STATUS.md` or open a GitHub issue.**
