# OEE Analytics - Integration Test Suite Status

**Date**: 2025-10-01
**Status**: Test Framework Validated ✓

## Test Suite Overview

Created comprehensive integration and load tests for the OEE Analytics platform covering:

- **End-to-End Sparkplug B Integration** (6 tests)
- **Store-and-Forward Resilience** (5 tests)
- **Backpressure & Adaptive Sampling** (6 tests)
- **OPC-UA Integration** (9 tests)
- **Fault Storm Load Testing** (5 tests)
- **TimescaleDB Performance** (10 tests)

**Total**: 41 integration/load tests + 8 framework validation tests

## Test Framework Status

### ✓ Validated Components

- [x] **pytest** - Version 8.4.2 installed and working
- [x] **pytest-asyncio** - Async test support validated
- [x] **Test Configuration** - Environment fixtures loading correctly
- [x] **Test Fixtures** - All custom fixtures operational:
  - `test_config` - Test environment configuration
  - `sparkplug_message_builder` - Simplified Sparkplug B message builder
  - `test_node_id` / `test_device_id` - Unique ID generators
  - `generate_telemetry_data` - Telemetry data generator
  - `measure_latency` - Performance measurement utility

### Framework Validation Results

```
test_framework_validation.py::test_pytest_working PASSED
test_framework_validation.py::test_async_working PASSED
test_framework_validation.py::test_fixtures_config PASSED
test_framework_validation.py::test_sparkplug_message_builder PASSED
test_framework_validation.py::test_node_id_generator PASSED
test_framework_validation.py::test_device_id_generator PASSED
test_framework_validation.py::test_telemetry_generator PASSED
test_framework_validation.py::test_latency_measurement PASSED

======================== 8 passed, 1 warning in 0.24s ========================
```

## Test Collection Status

All 41 integration/load tests successfully collected:

```bash
$ py -m pytest tests/ --collect-only
========================= 41 tests collected in 0.02s =========================
```

## Infrastructure Requirements

### Required Services (Not Currently Running)

The integration tests require the following services to be running:

1. **MQTT Broker** (Port 1883)
   - Mosquitto or EMQX
   - TLS/mTLS configuration for secure tests
   - ACL configuration for permission tests

2. **TimescaleDB** (Port 5432)
   - PostgreSQL with TimescaleDB extension
   - Database: `oee_analytics_test`
   - User: `oeeuser`
   - Hypertables and continuous aggregates configured

3. **Redis** (Port 6379)
   - Used for store-and-forward queue
   - Separate DB (15) for test isolation

4. **OPC-UA Simulator** (Port 4840)
   - asyncua server with test namespace
   - Test variables for production/temperature/state

### Starting Infrastructure

**Option 1: Docker Compose (Recommended)**

```bash
cd docker/compose

# Start MQTT cluster with monitoring
docker-compose -f docker-compose.mqtt-cluster.yml up -d

# Start TimescaleDB
docker-compose -f docker-compose.timescaledb.yml up -d

# Start Redis (if not in other compose files)
docker run -d --name oee-redis -p 6379:6379 redis:7-alpine
```

**Option 2: Development Environment**

See `ansible/README.md` for setting up development environment with required services.

## Test Limitations

### Known Constraints

1. **Sparkplug B Protocol**
   - Using simplified JSON-based message builder for testing
   - Full Eclipse Tahu library not available via PyPI
   - Tests validate message structure, not binary protobuf encoding
   - **Impact**: Tests verify application logic but not wire protocol compatibility

2. **No Live Infrastructure**
   - Docker not available in current test environment
   - Tests cannot connect to MQTT/TimescaleDB/Redis
   - **Impact**: Tests validated for syntax/structure only, not runtime behavior

3. **Mock Data Only**
   - Tests use fixtures and generators, not real PLC data
   - OPC-UA simulator not running
   - **Impact**: Cannot validate end-to-end data flow with real equipment

### Workarounds Implemented

1. **Sparkplug Message Builder**
   - Created `SimpleSparkplugBuilder` in `conftest.py`
   - Generates JSON payloads for testing
   - Compatible with test assertions
   - Does NOT generate Sparkplug B protobuf format

2. **Database Fixtures**
   - Async fixtures prepared for asyncpg (TimescaleDB)
   - Clean fixtures with truncate/reset for test isolation
   - **Status**: Not tested against live database

3. **MQTT Fixtures**
   - Both sync (paho) and async (asyncio-mqtt) clients configured
   - **Status**: Not tested against live broker

## Running Tests

### Syntax Validation (Working)

All test files validated for Python syntax:

```bash
py -m py_compile tests/conftest.py                              # OK
py -m py_compile tests/integration/test_e2e_sparkplug.py         # OK
py -m py_compile tests/integration/test_store_forward.py         # OK
py -m py_compile tests/integration/test_backpressure.py          # OK
py -m py_compile tests/integration/test_opcua_integration.py     # OK
py -m py_compile tests/load/test_fault_storm.py                  # OK
py -m py_compile tests/integration/test_timescaledb_performance.py # OK
```

### Framework Validation (Working)

```bash
cd tests
py -m pytest test_framework_validation.py -v -s
```

### Integration Tests (Requires Infrastructure)

**Run all tests:**
```bash
py -m pytest tests/ -v -s
```

**Run specific test categories:**
```bash
# E2E Sparkplug tests
py -m pytest tests/integration/test_e2e_sparkplug.py -v -s

# Store-and-forward resilience
py -m pytest tests/integration/test_store_forward.py -v -s

# Backpressure handling
py -m pytest tests/integration/test_backpressure.py -v -s

# OPC-UA integration
py -m pytest tests/integration/test_opcua_integration.py -v -s

# TimescaleDB performance
py -m pytest tests/integration/test_timescaledb_performance.py -v -s

# Load tests
py -m pytest tests/load/ -v -s
```

**Run with markers:**
```bash
# Only integration tests
py -m pytest -m integration -v

# Only load/performance tests
py -m pytest -m load -v

# Only slow tests
py -m pytest -m slow -v

# Exclude MQTT tests
py -m pytest -m "not requires_mqtt" -v
```

## Test Coverage by Component

### 1. Sparkplug B MQTT Client ✓

**Files Tested:**
- `oee_analytics/sparkplug/mqtt_client.py`
- `oee_analytics/sparkplug/edge_gateway.py`

**Tests Created:**
- E2E message flow (NBIRTH/NDATA/DBIRTH/DDATA)
- Store-and-forward during outages
- Backpressure detection and adaptive sampling
- Sequence number validation
- Message ordering under load
- Statistics tracking

### 2. Edge Cache (Store-and-Forward) ✓

**Files Tested:**
- `oee_analytics/edge/cache.py`

**Tests Created:**
- Redis queue persistence
- Queue watermark enforcement (500 MB limit)
- Zero data loss during broker outages
- Queue persistence across gateway restarts
- Long outage simulation (1 hour)

### 3. OPC-UA Connectors ✓

**Files Tested:**
- `oee_analytics/sparkplug/connectors/opcua_client.py`

**Tests Created:**
- Connection and namespace discovery
- Value read/write operations
- Subscription monitoring with callbacks
- OPC-UA → Sparkplug → TimescaleDB pipeline
- Connection resilience
- High-frequency updates (100 Hz)
- Tag configuration

### 4. TimescaleDB Backend ✓

**Files Tested:**
- `oee_analytics/db/timescale_backend.py`
- TimescaleDB schema and configuration

**Tests Created:**
- Hypertable configuration validation
- Continuous aggregates (1min/5min/1hour)
- Write performance (>10k inserts/sec target)
- Read performance (<100ms query target)
- Compression and retention policies
- Space partitioning benefits
- Concurrent writes

### 5. Load Testing ✓

**Performance Targets:**
- 1000 msg/sec sustained throughput
- <2s p95 latency under load
- <5s p99 latency under load
- Zero data loss during fault storms
- Memory stability under sustained load

**Tests Created:**
- Fault storm (1000 msg/sec for 30s)
- Burst pattern (2000 msg/sec bursts)
- Concurrent nodes (10 @ 100 msg/sec)
- Memory stability monitoring
- Latency percentile measurements

## Next Steps

### Phase 1: Infrastructure Setup

1. **Start Docker Services**
   ```bash
   cd docker/compose
   ./deploy.sh  # If script exists
   # OR manually:
   docker-compose -f docker-compose.mqtt-cluster.yml up -d
   docker-compose -f docker-compose.timescaledb.yml up -d
   ```

2. **Verify Services**
   ```bash
   docker ps  # Check all containers running
   curl http://localhost:18083  # EMQX dashboard
   psql -h localhost -U oeeuser -d oee_analytics_test  # TimescaleDB
   redis-cli ping  # Redis
   ```

3. **Initialize TimescaleDB Schema**
   ```bash
   psql -h localhost -U oeeuser -d oee_analytics_test -f docker/compose/timescaledb/init/01_init_timescaledb.sql
   ```

### Phase 2: Run Integration Tests

1. **Start with Simple Tests**
   ```bash
   py -m pytest tests/integration/test_e2e_sparkplug.py::test_e2e_sparkplug_nbirth_to_database -v -s
   ```

2. **Progress Through Test Suite**
   - Fix any connection issues
   - Verify database writes
   - Check MQTT connectivity
   - Monitor logs for errors

3. **Run Full Suite**
   ```bash
   py -m pytest tests/ -v -s --maxfail=1
   ```

### Phase 3: CI/CD Integration

1. **GitHub Actions Workflow**
   - Add `.github/workflows/integration-tests.yml`
   - Use docker-compose for service dependencies
   - Run tests on PR and merge to main

2. **Test Reporting**
   - Add pytest-html for HTML reports
   - Add pytest-cov for coverage reports
   - Upload to CI artifacts

## Issues and Resolutions

### Issue 1: Eclipse Tahu Not on PyPI ✓ RESOLVED

**Problem**: `eclipse-tahu==1.1.4` in requirements.txt not available via pip

**Resolution**: Created simplified `SimpleSparkplugBuilder` in conftest.py that generates JSON payloads for testing

**Impact**: Tests validate application logic but not binary protobuf wire format

### Issue 2: Emoji Characters in Windows Console ✓ RESOLVED

**Problem**: UnicodeEncodeError when printing ✓ emoji in test output

**Resolution**: Replaced emoji with `[OK]` text markers

### Issue 3: datetime.utcnow() Deprecation ✓ RESOLVED

**Problem**: Warning about deprecated datetime.utcnow()

**Resolution**: Changed to `datetime.now(timezone.utc)`

## Test Quality Metrics

### Code Quality

- **Syntax**: ✓ All files compile without errors
- **Type Hints**: Partial (could be improved)
- **Docstrings**: ✓ All tests documented
- **Comments**: ✓ Clear scenario descriptions

### Test Quality

- **Isolation**: ✓ Clean fixtures for database/redis
- **Repeatability**: ✓ Unique IDs per test run
- **Assertions**: ✓ Clear expected vs actual
- **Error Messages**: ✓ Descriptive failure messages
- **Performance**: ✓ Latency measurements included

### Coverage Readiness

Ready for coverage reporting once infrastructure is available:
- Install: `py -m pip install pytest-cov`
- Run: `py -m pytest --cov=oee_analytics --cov-report=html`

## References

- **Pytest Documentation**: https://docs.pytest.org/
- **pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
- **Sparkplug B Specification**: https://sparkplug.eclipse.org/
- **TimescaleDB Documentation**: https://docs.timescale.com/
- **OEE Architecture Plan**: See original architecture document

## Maintainer Notes

**Test Suite Created By**: Claude Code
**Date**: 2025-10-01
**Environment**: Windows, Python 3.13.6, pytest 8.4.2
**Status**: Ready for infrastructure deployment and execution

### Key Decisions

1. **Simplified Sparkplug Builder**: Chose JSON over protobuf for testing to avoid external dependency
2. **Async Tests**: Used pytest-asyncio for async/await support throughout
3. **Fixture Scopes**: Session-scoped for connections, function-scoped for data cleanup
4. **Test Markers**: Categorized tests for selective execution
5. **No Mocking**: Tests designed to run against real infrastructure for true integration testing

---

**For questions or issues, refer to the main project documentation or open a GitHub issue.**
