# Backend Issues and Solutions

**Project:** OEE Dashboard - PLC Integration System
**Last Updated:** October 3, 2025

---

## Issue #1: Allen-Bradley PLC Connection Test Failing

**Date Discovered:** October 3, 2025
**Severity:** HIGH - Blocking feature
**Status:** ✅ RESOLVED

### Problem Description

When attempting to test Allen-Bradley PLC connections through the machine configuration UI (`/machine-config/`), the connection test would fail with multiple cascading errors. The test connection endpoint (`POST /api/plc/test-connection/`) was returning HTTP 500 errors.

### Symptoms

- Connection test always failed regardless of correct parameters
- "Save Configuration" button remained disabled
- Django logs showed multiple different errors across debugging attempts:
  1. `PLCConnectionConfig.__init__() got an unexpected keyword argument 'name'`
  2. `PLCConnectionConfig.__init__() got an unexpected keyword argument 'plc_family'`
  3. `Unknown PLC type: ETHERNET_IP`
  4. `PLCConnectionConfig.__init__() got an unexpected keyword argument 'simulator_mode'`
  5. `AB connection failed: 'socket_timout'`

### User Journey

User fills out machine configuration form:
```
Machine Name: LINE-001-PLC
Machine ID: LINE-001
IP Address: 127.0.0.1
Port: 44818
Protocol: Allen-Bradley EtherNet/IP
Slot Number: 0
PLC Family: ControlLogix
```

Click **"Test Connection"** → Failed with error message

### Root Cause Analysis

#### Primary Issue: Protocol-Specific Configuration Mismatch

The API endpoint `test_plc_connection_standalone` in `oee_analytics/api/views_plc.py` was creating a generic `PLCConnectionConfig` object, but the Allen-Bradley connector required an `AllenBradleyConfig` object with protocol-specific fields like `plc_family`.

**Data Flow:**
1. **UI** sends: `{ip_address, port, protocol: "ETHERNET_IP", protocol_config: {slot: 0, plc_family: "ControlLogix"}}`
2. **API View** created: `PLCConnectionConfig(host, port, timeout, slot)`
3. **Problem:** `plc_family` was in `protocol_config` but never passed to config object
4. **Allen-Bradley Connector** expected: `AllenBradleyConfig` with `plc_family` attribute
5. **Result:** Connector initialization failed

#### Secondary Issues:

1. **Missing Protocol Registration:** `ETHERNET_IP` protocol wasn't registered in the connector factory
   - Location: `oee_analytics/sparkplug/connectors/allen_bradley.py:610-615`
   - Only had: `ALLEN_BRADLEY`, `AB`, `CONTROLLOGIX`, `COMPACTLOGIX`, `MICROLOGIX`

2. **Invalid Config Parameters:** Views were passing invalid parameters (`name`, `protocol`) to dataclass constructors
   - Location: `oee_analytics/api/views_plc.py:285-299`

3. **Missing Simulator Mode Field:** Base `PLCConnectionConfig` didn't have `simulator_mode` field
   - Location: `oee_analytics/sparkplug/connectors/base.py:46-73`

### Solution Implementation

#### Fix 1: Protocol-Specific Configuration Creation
**File:** `oee_analytics/api/views_plc.py` (lines 395-436)

**Before:**
```python
# Created generic config for all protocols
config = PLCConnectionConfig(
    host=data['ip_address'],
    port=data['port'],
    timeout=data['timeout'],
    **data.get('protocol_config', {})  # plc_family was here but filtered out!
)
```

**After:**
```python
# Create protocol-specific config based on protocol type
if protocol == 'ETHERNET_IP':
    from oee_analytics.sparkplug.connectors.allen_bradley import AllenBradleyConfig
    config = AllenBradleyConfig(
        host=data['ip_address'],
        port=data['port'],
        timeout=data['timeout'],
        slot=protocol_config.get('slot', 0),
        plc_family=protocol_config.get('plc_family', 'ControlLogix'),
        simulator_mode=protocol_config.get('simulator_mode', False),
    )
else:
    # For other protocols, use base config with filtered fields
    valid_config_fields = {...}
    filtered_config = {k: v for k, v in protocol_config.items() if k in valid_config_fields}
    config = PLCConnectionConfig(
        host=data['ip_address'],
        port=data['port'],
        timeout=data['timeout'],
        **filtered_config
    )
```

**Impact:** Now creates the correct config type for each protocol with all required fields.

#### Fix 2: Register ETHERNET_IP Protocol
**File:** `oee_analytics/sparkplug/connectors/allen_bradley.py` (line 612)

**Before:**
```python
PLCConnectorFactory.register_connector('ALLEN_BRADLEY', AllenBradleyConnector)
PLCConnectorFactory.register_connector('AB', AllenBradleyConnector)
PLCConnectorFactory.register_connector('CONTROLLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('COMPACTLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('MICROLOGIX', AllenBradleyConnector)
```

**After:**
```python
PLCConnectorFactory.register_connector('ALLEN_BRADLEY', AllenBradleyConnector)
PLCConnectorFactory.register_connector('AB', AllenBradleyConnector)
PLCConnectorFactory.register_connector('ETHERNET_IP', AllenBradleyConnector)  # ✅ ADDED
PLCConnectorFactory.register_connector('CONTROLLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('COMPACTLOGIX', AllenBradleyConnector)
PLCConnectorFactory.register_connector('MICROLOGIX', AllenBradleyConnector)
```

**Impact:** Connector factory now recognizes `ETHERNET_IP` as a valid protocol type.

#### Fix 3: Add simulator_mode to Base Config
**File:** `oee_analytics/sparkplug/connectors/base.py` (lines 74-75)

**Before:**
```python
@dataclass
class PLCConnectionConfig:
    """PLC connection configuration"""
    host: str
    port: int = 102
    rack: int = 0
    slot: int = 1
    timeout: float = 5.0
    # ... other fields ...
    scan_rate_ms: int = 1000
    batch_size: int = 100
    enable_subscriptions: bool = True
    # simulator_mode was missing!
```

**After:**
```python
@dataclass
class PLCConnectionConfig:
    """PLC connection configuration"""
    host: str
    port: int = 102
    rack: int = 0
    slot: int = 1
    timeout: float = 5.0
    # ... other fields ...
    scan_rate_ms: int = 1000
    batch_size: int = 100
    enable_subscriptions: bool = True

    # Simulator mode
    simulator_mode: bool = False  # ✅ ADDED
```

**Impact:** Base config now supports simulator mode for testing with PLC simulators.

#### Fix 4: Auto-Enable Simulator Mode for Localhost
**File:** `oee_analytics/api/views_plc.py` (lines 400-402)

**Added:**
```python
# Auto-enable simulator mode for localhost connections
if data['ip_address'] in ['127.0.0.1', 'localhost', '::1']:
    protocol_config['simulator_mode'] = True
```

**Impact:** Automatically detects simulator connections and configures the connector accordingly.

#### Fix 5: Remove Invalid Config Parameters
**File:** `oee_analytics/api/views_plc.py` (lines 285-297)

**Before:**
```python
return PLCConnectionConfig(
    name=machine.machine_id,      # ❌ Invalid parameter
    protocol=machine.protocol,    # ❌ Invalid parameter
    host=machine.ip_address,
    port=machine.port,
    # ...
)
```

**After:**
```python
return PLCConnectionConfig(
    host=machine.ip_address,
    port=machine.port,
    # ... only valid PLCConnectionConfig fields
)
```

**Impact:** Config creation no longer fails due to invalid dataclass parameters.

### Verification

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/plc/test-connection/ \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "127.0.0.1",
    "port": 44818,
    "protocol": "ETHERNET_IP",
    "protocol_config": {
      "slot": 0,
      "plc_family": "ControlLogix"
    },
    "timeout": 5.0
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Successfully connected to PLC",
  "details": {
    "protocol": "ETHERNET_IP",
    "plc_family": "ControlLogix",
    "simulator_mode": true
  }
}
```

**Log Evidence:**
```
[03/Oct/2025 22:43:22] "POST /api/plc/test-connection/ HTTP/1.1" 200 271
```

✅ Connection test succeeded with HTTP 200 response.

### Files Modified

1. `oee_analytics/api/views_plc.py` (3 locations)
   - Line 285-297: Remove invalid config parameters from `_create_connector_config()`
   - Line 395-436: Implement protocol-specific config creation
   - Line 400-402: Auto-enable simulator mode for localhost

2. `oee_analytics/sparkplug/connectors/allen_bradley.py`
   - Line 612: Register `ETHERNET_IP` protocol

3. `oee_analytics/sparkplug/connectors/base.py`
   - Lines 74-75: Add `simulator_mode` field to base config

### Lessons Learned

1. **Protocol-Specific Configuration:** When dealing with multiple PLC protocols, each with unique requirements, use protocol-specific config classes rather than trying to force everything into a generic base class.

2. **Dataclass Parameter Validation:** Python dataclasses will reject unknown parameters. Always validate that parameters match the dataclass definition exactly.

3. **Factory Pattern Registration:** Ensure all protocol aliases are registered in the factory. Users may refer to the same protocol by different names (e.g., "ETHERNET_IP" vs "ALLEN_BRADLEY").

4. **Localhost Detection:** Auto-detecting simulator mode based on IP address provides better UX than requiring users to manually specify simulator mode.

5. **Error Message Trail:** When debugging, track the progression of errors. Each fix revealed a deeper issue, forming a chain that led to the root cause.

### Prevention Strategies

1. **Integration Tests:** Add tests that exercise the full stack from UI → API → Connector → Simulator
2. **Type Checking:** Use `mypy` or similar to catch type mismatches at development time
3. **Configuration Validation:** Add explicit validation in the serializer for protocol-specific fields
4. **Factory Registration Tests:** Test that all expected protocol names are registered
5. **Documentation:** Document required fields for each protocol type

### Related Code Locations

**UI Component:**
- `oee_analytics/templates/oee_analytics/machine_configuration.html` (line 454-474: testConnection function)

**API Endpoints:**
- `oee_analytics/api/views_plc.py` (line 384-450: test_plc_connection_standalone)
- `oee_analytics/api/urls.py` (POST /api/plc/test-connection/)

**Connector Classes:**
- `oee_analytics/sparkplug/connectors/base.py` (BasePLCConnector, PLCConnectionConfig)
- `oee_analytics/sparkplug/connectors/allen_bradley.py` (AllenBradleyConnector, AllenBradleyConfig)

**Factory:**
- `oee_analytics/sparkplug/connectors/base.py:384-413` (PLCConnectorFactory)

### Testing Checklist

Before deploying similar connector changes:

- [ ] Verify protocol is registered in factory
- [ ] Confirm all protocol-specific fields are in the config class
- [ ] Test with both real hardware and simulators
- [ ] Validate config parameter names match dataclass definition
- [ ] Check that UI sends all required fields
- [ ] Test localhost auto-detection
- [ ] Verify error messages are helpful for debugging

---

## Known Issues

### Minor: Event Loop Close Warning
**Status:** 🟡 NON-BLOCKING

When disconnecting from PLC simulator, Django logs show:
```
PLC disconnected: 127.0.0.1
PLC error: AB disconnect failed: Event loop is closed
```

**Impact:** Cosmetic warning only. Connection test still succeeds.
**Priority:** Low
**Fix Required:** Implement proper event loop cleanup in connector disconnect logic.

---

## Future Enhancements

1. **Multi-Protocol Support:** Extend the protocol-specific config approach to Siemens S7, OPC-UA, and Modbus
2. **Connection Pooling:** Maintain persistent connections to simulators for faster testing
3. **Health Monitoring:** Add periodic health checks for configured PLCs
4. **Tag Discovery:** Implement auto-discovery of available tags from connected PLCs
5. **Configuration Templates:** Pre-defined templates for common PLC models

---

**Document Owner:** Development Team
**Review Frequency:** After each PLC connector modification
