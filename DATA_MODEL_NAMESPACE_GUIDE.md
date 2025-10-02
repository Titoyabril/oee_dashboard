##Data Model & Namespace Guide

**Complete guide for OEE Analytics data model and canonical namespace**

---

## Table of Contents

1. [Overview](#overview)
2. [Asset Hierarchy Model](#asset-hierarchy-model)
3. [Canonical Namespace](#canonical-namespace)
4. [Sparkplug B Integration](#sparkplug-b-integration)
5. [Signal Types](#signal-types)
6. [Tag Mapping](#tag-mapping)
7. [Usage Examples](#usage-examples)
8. [Best Practices](#best-practices)

---

## Overview

### Data Model Architecture

The OEE Analytics system uses a **hierarchical asset model** with a **canonical namespace** for consistent data representation across different protocols and systems.

```
Site (Plant/Factory)
 └── Area (Production Area)
      └── Production Line
           └── Cell (Manufacturing Cell)
                └── Machine (Individual Equipment)
                     └── Tags (Canonical Signals)
```

### Key Concepts

- **Asset Hierarchy**: Physical organization of manufacturing assets
- **Canonical Tags**: Standardized signal definitions
- **Namespace**: Hierarchical naming convention
- **Sparkplug Integration**: MQTT-based protocol mapping
- **Tag Mapping**: Bridge between PLC addresses and canonical tags

---

## Asset Hierarchy Model

### Site (Plant/Factory)

Top-level organizational unit representing a manufacturing facility.

**Model**: `oee_analytics.models.asset_hierarchy.Site`

**Fields**:
```python
class Site(models.Model):
    site_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Location
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')

    # Contact
    site_manager = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    # Status
    active = models.BooleanField(default=True)
    commission_date = models.DateField(blank=True)
```

**Canonical Path**: `site.{site_id}`

**Example**:
```python
site = Site.objects.create(
    site_id="PLANT_A",
    name="Plant A - Detroit",
    country="USA",
    timezone="America/Detroit"
)

# Canonical path: site.PLANT_A
```

### Area (Production Area)

Logical grouping within a site (floor, department, zone).

**Model**: `oee_analytics.models.asset_hierarchy.Area`

**Area Types**:
- PRODUCTION
- ASSEMBLY
- PACKAGING
- QUALITY
- MAINTENANCE
- WAREHOUSE
- UTILITIES
- OTHER

**Canonical Path**: `site.{site_id}.area.{area_id}`

**Example**:
```python
area = Area.objects.create(
    area_id="FLOOR_1",
    site=site,
    name="Production Floor 1",
    area_type="PRODUCTION",
    floor_area_sqm=5000
)

# Canonical path: site.PLANT_A.area.FLOOR_1
```

### Production Line

Assembly or production line within an area.

**Model**: `oee_analytics.models.asset_hierarchy.ProductionLine`

**Statuses**:
- RUNNING
- IDLE
- DOWN
- MAINTENANCE
- CHANGEOVER

**Canonical Path**: `site.{site_id}.area.{area_id}.line.{line_id}`

**Example**:
```python
line = ProductionLine.objects.create(
    line_id="LINE_01",
    area=area,
    name="Assembly Line 1",
    design_capacity_per_hour=120,
    standard_cycle_time_seconds=30,
    scheduled_uptime_hours_per_day=22,
    shifts_per_day=3
)

# Canonical path: site.PLANT_A.area.FLOOR_1.line.LINE_01
```

### Cell (Manufacturing Cell)

Individual workstation or process step within a line.

**Model**: `oee_analytics.models.asset_hierarchy.Cell`

**Cell Types**:
- PROCESSING
- ASSEMBLY
- TESTING
- INSPECTION
- PACKAGING
- MATERIAL_HANDLING
- BUFFER
- OTHER

**Canonical Path**: `site.{site_id}.area.{area_id}.line.{line_id}.cell.{cell_id}`

**Example**:
```python
cell = Cell.objects.create(
    cell_id="STATION_01",
    line=line,
    name="Welding Station 1",
    cell_type="PROCESSING",
    sequence_order=1,
    cycle_time_seconds=25
)

# Canonical path: site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01
```

### Machine (Equipment)

Individual piece of equipment within a cell.

**Model**: `oee_analytics.models.asset_hierarchy.Machine`

**Machine Types**:
- CNC
- ROBOT
- CONVEYOR
- PRESS
- FURNACE
- PUMP
- MOTOR
- SENSOR
- PLC
- HMI
- OTHER

**Statuses**:
- RUNNING
- IDLE
- DOWN
- ALARM
- WARNING
- MAINTENANCE
- OFFLINE

**Canonical Path**: `site.{site_id}.area.{area_id}.line.{line_id}.cell.{cell_id}.machine.{machine_id}`

**Example**:
```python
machine = Machine.objects.create(
    machine_id="ROBOT_01",
    cell=cell,
    name="ABB IRB 6700",
    machine_type="ROBOT",
    manufacturer="ABB",
    model="IRB 6700",
    serial_number="SN123456",

    # OEE Targets
    design_oee_percent=85.0,
    target_availability_percent=90.0,
    target_performance_percent=95.0,
    target_quality_percent=99.0,

    # Connectivity
    ip_address="192.168.1.100",
    port=4840,
    protocol="OPCUA"
)

# Canonical path: site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01.machine.ROBOT_01
```

---

## Canonical Namespace

### Namespace Structure

All tags follow a hierarchical namespace pattern:

```
site.{site_id}.area.{area_id}.line.{line_id}.cell.{cell_id}.machine.{machine_id}.{tag_name}
```

### Example Paths

```
# Good parts counter for Robot 01
site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01.machine.ROBOT_01.counter.good

# Running state for CNC machine
site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_02.machine.CNC_01.state.run

# Temperature sensor
site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01.machine.ROBOT_01.temperature
```

### Path Generation

```python
# Get full canonical path for a machine
machine = Machine.objects.get(machine_id="ROBOT_01")
canonical_path = machine.get_canonical_path()
# Returns: site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01.machine.ROBOT_01

# Get hierarchy dictionary
hierarchy = machine.get_full_hierarchy()
# Returns:
# {
#     'site_id': 'PLANT_A',
#     'site_name': 'Plant A - Detroit',
#     'area_id': 'FLOOR_1',
#     'area_name': 'Production Floor 1',
#     'line_id': 'LINE_01',
#     'line_name': 'Assembly Line 1',
#     'cell_id': 'STATION_01',
#     'cell_name': 'Welding Station 1',
#     'machine_id': 'ROBOT_01',
#     'machine_name': 'ABB IRB 6700',
#     'canonical_path': 'site.PLANT_A.area.FLOOR_1.line.LINE_01.cell.STATION_01.machine.ROBOT_01'
# }
```

---

## Sparkplug B Integration

### Sparkplug Node

Edge gateway or node publishing data.

**Model**: `oee_analytics.sparkplug.models.SparkplugNode`

**Topic Namespace**: `spBv1.0/{group_id}/N{node_id}`

**Example**:
```python
node = SparkplugNode.objects.create(
    node_id="EDGE_GATEWAY_01",
    group_id="PLANT_A",
    mqtt_broker_host="mqtt.example.com",
    mqtt_broker_port=8883,
    mqtt_use_tls=True
)

# Topic namespace: spBv1.0/PLANT_A/NEDGE_GATEWAY_01
```

### Sparkplug Device

Device connected to a Sparkplug node.

**Model**: `oee_analytics.sparkplug.models.SparkplugDevice`

**Topic Namespace**: `spBv1.0/{group_id}/D{node_id}/{device_id}`

**Example**:
```python
device = SparkplugDevice.objects.create(
    device_id="PLC_01",
    node=node,
    device_type="PLC",
    manufacturer="Siemens",
    model="S7-1200",
    machine=machine  # Link to asset hierarchy
)

# Topic namespace: spBv1.0/PLANT_A/DEDGE_GATEWAY_01/PLC_01
```

### Sparkplug Message Types

- **NBIRTH**: Node birth certificate
- **NDEATH**: Node death certificate
- **DBIRTH**: Device birth certificate
- **DDEATH**: Device death certificate
- **NDATA**: Node data
- **DDATA**: Device data
- **NCMD**: Node command
- **DCMD**: Device command

### Sequence Number Tracking

```python
# Validate sequence number
node = SparkplugNode.objects.get(node_id="EDGE_GATEWAY_01")

# Valid sequence
is_valid = node.update_sequence_number(1)  # True
is_valid = node.update_sequence_number(2)  # True

# Sequence gap (error)
is_valid = node.update_sequence_number(5)  # False (expects 3)

# Birth resets sequence
is_valid = node.update_sequence_number(0)  # True (birth)
```

---

## Signal Types

### Canonical Tag Types

**Model**: `oee_analytics.models.asset_hierarchy.CanonicalTag`

#### State Signals (Boolean)

```python
# Running state
CanonicalTag.objects.create(
    tag_name="state.run",
    tag_type="state.run",
    data_type="BOOL"
)

# Other states
state.idle        # Idle state
state.down        # Down/fault state
state.blocked     # Blocked by downstream
```

#### Counter Signals (Integer)

```python
# Good parts counter
CanonicalTag.objects.create(
    tag_name="counter.good",
    tag_type="counter.good",
    data_type="INT",
    unit="parts",
    min_value=0
)

# Other counters
counter.total     # Total parts produced
counter.reject    # Rejected/scrap parts
```

#### Rate Signals (Real/Float)

```python
# Instantaneous rate
CanonicalTag.objects.create(
    tag_name="rate.instant",
    tag_type="rate.instant",
    data_type="REAL",
    unit="parts/min"
)

rate.average      # Average rate over period
```

#### Cycle Time Signals

```python
cycle.time_actual  # Actual cycle time
cycle.time_ideal   # Ideal/target cycle time
```

#### Fault Signals

```python
fault.code         # Fault code (INT)
fault.active       # Active fault flag (BOOL)
fault.severity     # Fault severity (INT)
```

#### Utilization Signals

```python
utilization.planned_time  # Planned production time
utilization.runtime       # Actual runtime
```

#### Process Variables

```python
temperature       # Temperature (°C, °F)
pressure          # Pressure (bar, psi)
vibration         # Vibration (mm/s)
speed             # Speed (rpm, m/s)
power             # Power (kW)
energy            # Energy (kWh)
```

### Signal Type Reference Table

| Tag Type | Data Type | Unit | Description |
|----------|-----------|------|-------------|
| state.run | BOOL | - | Running state |
| state.idle | BOOL | - | Idle state |
| state.down | BOOL | - | Down state |
| counter.good | INT | parts | Good parts count |
| counter.total | INT | parts | Total parts count |
| counter.reject | INT | parts | Reject parts count |
| rate.instant | REAL | parts/min | Instantaneous rate |
| rate.average | REAL | parts/min | Average rate |
| cycle.time_actual | REAL | seconds | Actual cycle time |
| cycle.time_ideal | REAL | seconds | Ideal cycle time |
| fault.code | INT | - | Fault code |
| fault.active | BOOL | - | Active fault |
| fault.severity | INT | - | Fault severity (1-5) |
| temperature | REAL | °C | Temperature |
| pressure | REAL | bar | Pressure |
| speed | REAL | rpm | Speed |
| power | REAL | kW | Power |

---

## Tag Mapping

### AssetTagMapping Model

Maps physical PLC tags to canonical tags with transformation.

**Model**: `oee_analytics.models.asset_hierarchy.AssetTagMapping`

**Example**:
```python
# Map OPC-UA tag to canonical tag
mapping = AssetTagMapping.objects.create(
    machine=machine,
    canonical_tag=CanonicalTag.objects.get(tag_name="counter.good"),
    source_address="ns=2;i=1001",
    source_name="GoodPartsCount",
    scale_factor=1.0,
    offset=0.0,
    sampling_interval_ms=1000,
    deadband_type=1,  # Absolute
    deadband_value=0.5
)

# Generated Sparkplug metric name
metric_name = mapping.get_sparkplug_metric_name()
# Returns: PLANT_A.FLOOR_1.LINE_01.STATION_01.ROBOT_01.counter.good
```

### Value Transformation

```python
# Transform raw PLC value to canonical value
raw_value = 1500  # Raw PLC value
transformed = mapping.apply_transformation(raw_value)
# Result = (raw_value * scale_factor) + offset

# Example with temperature conversion (°F to °C)
mapping.scale_factor = 0.5556  # (F-32) * 5/9 approximation
mapping.offset = -17.78        # Adjustment for Fahrenheit
celsius = mapping.apply_transformation(100)  # 100°F → ~37.8°C
```

### Quality Code Mapping

```python
# OPC-UA quality to Sparkplug quality
# 0 (Good) → 192 (GOOD)
# Bad_* → 0 (BAD)
# Uncertain_* → 64 (UNCERTAIN)

tag = CanonicalTag.objects.create(
    tag_name="temperature",
    tag_type="temperature",
    data_type="REAL",
    quality_threshold=192  # Minimum quality for good data
)
```

---

## Usage Examples

### Creating Complete Hierarchy

```python
from oee_analytics.models.asset_hierarchy import (
    Site, Area, ProductionLine, Cell, Machine
)

# Create hierarchy
site = Site.objects.create(
    site_id="DETROIT_PLANT",
    name="Detroit Manufacturing Plant",
    timezone="America/Detroit"
)

area = Area.objects.create(
    area_id="ASSEMBLY_FLOOR",
    site=site,
    name="Assembly Floor",
    area_type="ASSEMBLY"
)

line = ProductionLine.objects.create(
    line_id="LINE_A",
    area=area,
    name="Assembly Line A",
    design_capacity_per_hour=100,
    standard_cycle_time_seconds=36
)

cell = Cell.objects.create(
    cell_id="STATION_1",
    line=line,
    name="Welding Station 1",
    cell_type="PROCESSING",
    sequence_order=1
)

machine = Machine.objects.create(
    machine_id="WELDER_01",
    cell=cell,
    name="Spot Welder #1",
    machine_type="OTHER",
    ip_address="192.168.1.50",
    protocol="OPCUA"
)
```

### Creating Canonical Tags and Mappings

```python
from oee_analytics.models.asset_hierarchy import CanonicalTag, AssetTagMapping

# Define canonical tags
good_count_tag = CanonicalTag.objects.create(
    tag_name="counter.good",
    description="Good parts counter",
    tag_type="counter.good",
    data_type="INT",
    unit="parts",
    min_value=0
)

temperature_tag = CanonicalTag.objects.create(
    tag_name="temperature",
    description="Weld temperature",
    tag_type="temperature",
    data_type="REAL",
    unit="°C",
    min_value=0,
    max_value=500,
    deadband_absolute=0.5
)

# Map to machine
AssetTagMapping.objects.create(
    machine=machine,
    canonical_tag=good_count_tag,
    source_address="ns=2;i=1001",
    source_name="WeldCount",
    sampling_interval_ms=500
)

AssetTagMapping.objects.create(
    machine=machine,
    canonical_tag=temperature_tag,
    source_address="ns=2;i=1002",
    source_name="WeldTemp",
    scale_factor=1.0,
    offset=0.0,
    deadband_value=0.5
)
```

### Querying Hierarchy

```python
# Get all machines for a line
line = ProductionLine.objects.get(line_id="LINE_A")
machines = Machine.objects.filter(cell__line=line)

# Get all active machines for a site
site = Site.objects.get(site_id="DETROIT_PLANT")
machines = Machine.objects.filter(
    cell__line__area__site=site,
    active=True
)

# Get machine with full hierarchy
machine = Machine.objects.select_related(
    'cell__line__area__site'
).get(machine_id="WELDER_01")

hierarchy = machine.get_full_hierarchy()
```

### Sparkplug Integration

```python
from oee_analytics.sparkplug.models import SparkplugNode, SparkplugDevice

# Create Sparkplug node
node = SparkplugNode.objects.create(
    node_id="EDGE_01",
    group_id="DETROIT_PLANT",
    mqtt_broker_host="mqtt.detroit-plant.com",
    mqtt_use_tls=True
)

# Create device linked to machine
device = SparkplugDevice.objects.create(
    device_id="PLC_WELDER_01",
    node=node,
    device_type="PLC",
    machine=machine
)

# Get Sparkplug topic
topic = f"{node.topic_namespace}/{device.device_id}"
# Returns: spBv1.0/DETROIT_PLANT/NEDGE_01/PLC_WELDER_01
```

---

## Best Practices

### Naming Conventions

1. **IDs should be alphanumeric with underscores**
   ```python
   site_id="PLANT_A"          # Good
   site_id="Plant A"          # Bad (spaces)
   ```

2. **Use descriptive display names**
   ```python
   name="Detroit Manufacturing Plant - Assembly Floor 1"
   ```

3. **Consistent canonical tag names**
   ```python
   "counter.good"    # Standard
   "GoodCount"       # Non-standard
   ```

### Performance Optimization

1. **Use select_related for hierarchy queries**
   ```python
   machine = Machine.objects.select_related(
       'cell__line__area__site'
   ).get(machine_id="M001")
   ```

2. **Index critical fields**
   - All canonical paths use indexed fields
   - Status fields are indexed
   - Foreign keys are automatically indexed

3. **Batch create tag mappings**
   ```python
   mappings = [
       AssetTagMapping(machine=m, canonical_tag=tag, ...)
       for m in machines
   ]
   AssetTagMapping.objects.bulk_create(mappings)
   ```

### Data Integrity

1. **Always validate before creating mappings**
   ```python
   if machine.protocol == "OPCUA":
       source_address = "ns=2;i=1001"
   elif machine.protocol == "MODBUS":
       source_address = "40001"
   ```

2. **Use transactions for hierarchy changes**
   ```python
   from django.db import transaction

   with transaction.atomic():
       site = Site.objects.create(...)
       area = Area.objects.create(site=site, ...)
       line = ProductionLine.objects.create(area=area, ...)
   ```

3. **Check for duplicates**
   ```python
   machine, created = Machine.objects.get_or_create(
       cell=cell,
       machine_id="M001",
       defaults={'name': 'New Machine'}
   )
   ```

### Sparkplug Integration

1. **Always handle sequence numbers**
   ```python
   if not node.update_sequence_number(seq_num):
       logger.warning(f"Sequence gap detected for {node.node_id}")
   ```

2. **Track birth/death certificates**
   ```python
   node.status = "BIRTH"
   node.last_birth_timestamp = timezone.now()
   node.save()
   ```

3. **Link devices to machines**
   ```python
   device.machine = Machine.objects.get(machine_id="M001")
   device.save()
   ```

---

## Appendix: Complete Data Model Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      ASSET HIERARCHY                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Site (PLANT_A)                                         │
│   │                                                      │
│   ├─ Area (FLOOR_1)                                    │
│   │   │                                                 │
│   │   ├─ ProductionLine (LINE_01)                      │
│   │   │   │                                             │
│   │   │   ├─ Cell (STATION_01)                         │
│   │   │   │   │                                         │
│   │   │   │   ├─ Machine (ROBOT_01)                    │
│   │   │   │   │   │                                     │
│   │   │   │   │   ├─ AssetTagMapping                   │
│   │   │   │   │   │   ├─ CanonicalTag (counter.good)   │
│   │   │   │   │   │   ├─ source_address: ns=2;i=1001   │
│   │   │   │   │   │   └─ Sparkplug metric name         │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                   SPARKPLUG INTEGRATION                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  SparkplugNode (EDGE_01)                                │
│   │  Topic: spBv1.0/PLANT_A/NEDGE_01                   │
│   │                                                      │
│   ├─ SparkplugDevice (PLC_01)                          │
│   │   Topic: spBv1.0/PLANT_A/DEDGE_01/PLC_01           │
│   │   Machine: → Machine (ROBOT_01)                    │
│   │                                                      │
│   └─ SparkplugMetric                                    │
│       Name: PLANT_A.FLOOR_1.LINE_01.STATION_01.ROBOT_01.counter.good
│       Value: 1500                                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-02
**Status**: Production-Ready
