# 500-Point Test Runner Dashboard - User Guide

## Overview

The Test Runner Dashboard provides a web-based interface for executing and monitoring the complete 500-point test plan with real-time results, logs, and phase-by-phase controls.

---

## Features

### ✨ Key Capabilities

1. **Phase-by-Phase Execution**
   - Run individual test phases (1-5)
   - View detailed results for each phase
   - Monitor execution time and test counts

2. **Complete Test Suite Execution**
   - Run all 500 tests with a single click
   - Track overall pass/fail rates
   - Monitor total execution time

3. **Real-Time Results**
   - Live test output display
   - Pass/fail/warning counts
   - Execution time tracking

4. **Log Management**
   - Automatic log file generation
   - Timestamped log files for each run
   - Full test output preservation

---

## Accessing the Dashboard

### Starting the Server

1. **Navigate to project directory:**
   ```bash
   cd C:\dev\projects\oee_dashboard\oee_dashboard
   ```

2. **Start Django development server:**
   ```bash
   py manage.py runserver 8000 --skip-checks
   ```

3. **Access the dashboard:**
   - Open your browser
   - Navigate to: `http://localhost:8000/test-runner/`

---

## Dashboard Interface

### Header Section

**Summary Statistics:**
- **Total Tests:** 500
- **Critical Tests:** 71
- **Test Phases:** 5
- **Execution Time:** ~2 seconds

### Test Phases

Each phase card displays:
- **Phase Name** (e.g., "Phase 1: Edge Layer")
- **Test Count** (100 tests per phase)
- **Critical Test Count** (varies by phase)
- **Description** (what the phase tests)
- **Run Phase Button** (execute that specific phase)

#### Phase Breakdown:

**Phase 1: Edge Layer** (100 tests, 15 critical)
- OPC-UA Client
- MQTT Sparkplug B Publisher
- Direct Drivers (CIP/S7)
- Protocol Selection
- Data Model & Namespace

**Phase 2: Processing & Storage** (100 tests, 13 critical)
- Sparkplug Lifecycle
- MQTT Broker Cluster
- Stream Processing
- TimescaleDB

**Phase 3: APIs & Security** (100 tests, 15 critical)
- REST/GraphQL APIs
- WebSocket Push
- Network Security
- Certificate Management
- Access Control

**Phase 4: Performance & Resilience** (100 tests, 10 critical)
- Throughput & Scale
- Resource Utilization
- Edge/Broker/Backend Resilience

**Phase 5: Observability & Quality** (100 tests, 8 critical)
- Metrics (Prometheus)
- Logging (ELK)
- Tracing (OpenTelemetry)
- Quality Codes
- Data Validation
- Clock Synchronization

### Run All Button

- **Orange "Run All 500 Tests" button**
- Executes complete test suite
- Shows combined results from all phases

---

## Using the Dashboard

### Running a Single Phase

1. **Locate the phase card** you want to test
2. **Click "Run Phase" button**
3. **Watch the execution:**
   - Button shows spinner and "Running..." text
   - Loading overlay appears
   - Phase card highlights with orange border
4. **View results:**
   - Results section appears at bottom
   - Shows pass/fail/warning counts
   - Displays execution time
   - Shows complete test output in log viewer

### Running All Tests

1. **Click "Run All 500 Tests" button** at the top
2. **Wait for execution** (typically 1-2 seconds)
3. **Review comprehensive results:**
   - Total passed: 500 (if all pass)
   - Total failed: 0 (target)
   - Warnings: 3 (external library warnings)
   - Execution time: ~1.5 seconds

### Reading Results

**Results Header:**
- Test name/phase
- Success/Failure badge (green checkmark or red X)

**Statistics Grid:**
- **Passed:** Green count of passing tests
- **Failed:** Red count of failed tests
- **Warnings:** Yellow count of warnings
- **Time:** Blue execution time in seconds

**Log Viewer:**
- Dark-themed terminal output
- Scrollable test output
- Shows pytest verbose results
- Color-coded test status

---

## API Endpoints

The dashboard uses the following API endpoints (can also be called directly):

### Run Single Phase
```bash
POST /api/test-runner/run-phase/
Content-Type: application/json
Body: {"phase_id": 1}
```

### Run All Tests
```bash
POST /api/test-runner/run-all/
Content-Type: application/json
```

### Get Test Status
```bash
GET /api/test-runner/status/
```

### List Log Files
```bash
GET /api/test-runner/logs/
```

### Get Log File
```bash
GET /api/test-runner/log/?file=phase1_20251005_123456.log
```

---

## Log Files

### Location
All test logs are saved to:
```
C:\dev\projects\oee_dashboard\oee_dashboard\tests\logs\
```

### Naming Convention

**Phase Logs:**
```
phase{N}_{timestamp}.log
Example: phase1_20251005_123456.log
```

**All Tests Log:**
```
all_500_tests_{timestamp}.log
Example: all_500_tests_20251005_123456.log
```

### Log Contents

Each log file contains:
1. Test execution metadata (phase, timestamp, command)
2. Complete stdout from pytest
3. Complete stderr from pytest
4. Test results summary

---

## Understanding Results

### Success Indicators

✅ **100% Pass Rate:**
- All tests passed
- Green success badge
- Phase card turns green

❌ **Failed Tests:**
- Some tests failed
- Red error badge
- Phase card turns red
- Failed test details in log

⚠️ **Warnings:**
- Tests passed but with warnings
- Yellow warning count
- Usually from external libraries (acceptable)

### Expected Results

**Target Metrics:**
- **Total Tests:** 500/500 PASSED
- **Pass Rate:** 100%
- **Execution Time:** < 2 seconds
- **Test Warnings:** 0-3 (external library warnings acceptable)
- **Critical Tests:** 71/71 PASSED

---

## Troubleshooting

### Dashboard Won't Load

1. **Check server is running:**
   ```bash
   curl http://localhost:8000/test-runner/
   ```
   Should return 200 status

2. **Restart server:**
   ```bash
   py manage.py runserver 8000 --skip-checks
   ```

### Tests Fail to Execute

1. **Check test files exist:**
   ```bash
   dir C:\dev\projects\oee_dashboard\oee_dashboard\tests\integration\test_300_point_*.py
   ```

2. **Verify pytest is installed:**
   ```bash
   py -m pytest --version
   ```

3. **Check logs for errors:**
   - Look in `tests/logs/` directory
   - Review most recent log file

### Test Failures

1. **Review specific test output** in log viewer
2. **Check phase documentation:**
   - `PHASE1_COMPLETE_100_PERCENT.md`
   - `PHASE2_COMPLETE_100_PERCENT.md`
   - etc.
3. **Verify dependencies** are installed
4. **Re-run specific phase** to isolate issue

---

## Best Practices

### Regular Testing

- **Run all 500 tests** before major deployments
- **Run specific phases** after changes to related code
- **Monitor execution time** to catch performance regressions
- **Review logs** for any new warnings

### Performance Monitoring

- **Baseline execution time:** ~1.5-2 seconds
- **Alert on slowdown:** >5 seconds indicates issue
- **Track pass rate:** Should maintain 100%

### CI/CD Integration

The test runner can be integrated into CI/CD pipelines:

```bash
# Run all tests via API
curl -X POST http://localhost:8000/api/test-runner/run-all/ \
     -H "Content-Type: application/json" | python -m json.tool

# Check success
if [ "$?" -eq 0 ]; then
  echo "Tests passed"
else
  echo "Tests failed"
  exit 1
fi
```

---

## Advanced Usage

### Custom Test Execution

Use pytest directly for advanced scenarios:

```bash
# Run specific test
py -m pytest tests/integration/test_300_point_phase1_edge_layer.py::TestA1_OPCUAClient::test_001_opcua_session_basic256sha256 -v

# Run with markers
py -m pytest tests/integration/ -m critical -v

# Run with coverage
py -m pytest tests/integration/ --cov=oee_analytics --cov-report=html
```

### Log Analysis

```bash
# View latest log
type tests\logs\all_500_tests_*.log | more

# Search for failures
findstr /C:"FAILED" tests\logs\*.log

# Count test results
findstr /C:"PASSED" tests\logs\all_500_tests_latest.log | find /c "PASSED"
```

---

## Production Deployment

### Security Considerations

1. **Disable in production** or restrict access:
   ```python
   # In settings.py
   if not DEBUG:
       # Disable test runner or require authentication
   ```

2. **Use authentication** for test runner access
3. **Restrict to internal network** only
4. **Monitor log file growth** and implement rotation

### Performance

- Test execution is synchronous (blocks request)
- For production, consider:
  - Background task queue (Celery)
  - WebSocket for real-time updates
  - Result caching

---

## Reference Files

### Documentation
- `500_TESTS_COMPLETE_FINAL_REPORT.md` - Final test results
- `ZERO_WARNING_VALIDATION_REPORT.md` - Warning resolution
- `PHASE{N}_COMPLETE_100_PERCENT.md` - Phase-specific results

### Code Files
- `oee_analytics/views_test_runner.py` - Backend logic
- `oee_analytics/templates/test_runner/dashboard.html` - Frontend UI
- `oee_analytics/urls.py` - URL routing

### Test Files
- `tests/integration/test_300_point_phase1_edge_layer.py`
- `tests/integration/test_300_point_phase2_processing.py`
- `tests/integration/test_300_point_phase3_apis_security.py`
- `tests/integration/test_300_point_phase4_performance.py`
- `tests/integration/test_300_point_phase5_observability.py`

---

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files in `tests/logs/`
3. Consult phase documentation files
4. Review test file source code

---

**Dashboard Version:** 1.0
**Last Updated:** October 5, 2025
**Compatible With:** Django 5.0.7, Python 3.13.6, pytest 8.4.2
