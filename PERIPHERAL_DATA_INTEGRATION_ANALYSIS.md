# Peripheral Data Integration - Existing vs. Required Analysis

**Date:** October 5, 2025
**Branch:** peripheral-data-integration
**Objective:** Identify gaps between current implementation and required peripheral data integration features

---

## Executive Summary

**Analysis Result:** The OEE platform already has **~60% of the required infrastructure** for peripheral data integration. Key gaps are in MES/ERP connectivity, IoT sensor integration, and historical data import capabilities.

**Existing Strengths:**
- ✅ Robust PLC connectivity (OPC-UA, Sparkplug B, direct drivers)
- ✅ Stream processing pipeline with normalization
- ✅ TimescaleDB for time-series storage
- ✅ SQL Server integration for legacy data
- ✅ REST/GraphQL/WebSocket APIs
- ✅ Comprehensive data models (Plant, Area, Line, Machine, Product, Recipe, Shift, Schedule)

**Key Gaps to Address:**
- ❌ No MES/ERP connector infrastructure
- ❌ Limited IoT sensor protocol support (no MQTT generic, no HTTP polling)
- ❌ No CSV/Excel import for historical data
- ❌ No Historian (OSIsoft PI, Wonderware) connectors
- ❌ Missing context enrichment for production schedules
- ❌ No recipe/changeover sync from MES

---

## Detailed Component Analysis

### 1. **MES/ERP Integration** ❌ NOT IMPLEMENTED

#### Required Features (from plan):
- MES API connector for production schedules, work orders
- SAP/Oracle ERP integration for material/labor data
- Recipe download and changeover sync
- Order/schedule status updates (bidirectional)

#### Existing Infrastructure:
**Data Models (sql_server_models.py):**
- ✅ `ProductionSchedule` model exists (lines 624-661)
  - Fields: schedule_id, line, recipe, planned_start/end, actual_start/end, work_order_number
  - Status tracking: PLANNED, ACTIVE, COMPLETED, CANCELLED
  - Priority levels 1-10
- ✅ `Recipe` model exists (lines 163-195)
  - Fields: recipe_id, product, line, version, target_cycle_time, setup_time, teardown_time
- ✅ `Product` model exists (lines 134-160)
  - Fields: product_id, product_name, product_family, sku, standard_cycle_time
- ✅ `OperatorShift` model exists (lines 664-685)
  - Fields: operator_id, line, shift_date, shift_number, role

**Stream Processing:**
- ✅ Normalizer exists (`stream_processing/normalizer.py`)
- ✅ Tag mapping and metadata enrichment capability
- ❌ No MES/ERP connector modules

**APIs:**
- ✅ REST endpoints exist (`/api/machines/`, `/api/lines/`)
- ❌ No MES-specific endpoints for schedule sync
- ❌ No ERP material/labor endpoints

**Gap Analysis:**
```
MISSING:
├── MES/ERP connector modules
│   ├── mes_connector.py (REST/SOAP client)
│   ├── erp_connector.py (SAP/Oracle integration)
│   └── schedule_sync.py (bidirectional sync)
├── API endpoints
│   ├── /api/mes/schedules/sync/
│   ├── /api/mes/recipes/download/
│   └── /api/mes/orders/update/
└── Data processors
    ├── Schedule enrichment processor
    └── Recipe changeover handler
```

**Recommendation:** Implement MES/ERP connector layer using existing data models.

---

### 2. **IoT Sensor Integration** ⚠️ PARTIAL

#### Required Features (from plan):
- Generic MQTT sensor ingestion (temp, vibration, pressure)
- HTTP REST polling for environmental sensors
- IoT-specific data routing and normalization
- Sensor metadata management

#### Existing Infrastructure:
**PLC Connectivity (sparkplug/connectors/):**
- ✅ OPC-UA client (`opcua_client.py`)
- ✅ Allen-Bradley CIP (`allen_bradley.py`)
- ✅ Siemens S7 (`siemens.py`)
- ✅ Modbus TCP (`modbus_tcp.py`)
- ✅ Base connector abstraction (`base.py`)

**MQTT Infrastructure:**
- ✅ Sparkplug B decoder (`stream_processing/sparkplug_decoder.py`)
- ✅ MQTT client with mTLS (`sparkplug/mqtt_client.py`)
- ❌ No generic MQTT (non-Sparkplug) support
- ❌ No HTTP REST polling client

**Data Models:**
- ✅ `SQLMachineEvent` supports flexible payload_json (line 296)
- ✅ Quality score field for data quality (line 299)
- ❌ No dedicated IoT sensor metadata model

**Gap Analysis:**
```
MISSING:
├── IoT connectors
│   ├── generic_mqtt_connector.py (non-Sparkplug MQTT)
│   ├── http_polling_connector.py (REST sensors)
│   └── iot_sensor_mapper.py (metadata mapping)
├── Data models
│   ├── IoTSensor (sensor metadata)
│   └── IoTSensorReading (time-series)
└── Stream routing
    └── IoT-specific normalization rules
```

**Recommendation:** Extend connector framework for generic MQTT and HTTP polling.

---

### 3. **Historian Data Integration** ❌ NOT IMPLEMENTED

#### Required Features (from plan):
- OSIsoft PI connector (REST API)
- Wonderware Historian connector
- Time-series backfill capability
- Data quality mapping from historian to OEE

#### Existing Infrastructure:
**Data Storage:**
- ✅ TimescaleDB with hypertables (partitioned time-series)
- ✅ Compression (11.1:1 ratio documented)
- ✅ Continuous aggregates (1min, 5min, 1hr)
- ❌ No historian-specific connectors

**Data Import:**
- ❌ No bulk import utilities
- ❌ No data reconciliation logic
- ❌ No quality code translation tables

**Gap Analysis:**
```
MISSING:
├── Historian connectors
│   ├── osisoft_pi_connector.py (PI Web API client)
│   ├── wonderware_connector.py (InSQL REST)
│   └── historian_backfill.py (bulk import)
├── Data reconciliation
│   ├── quality_code_mapper.py (OPC → OEE quality)
│   └── timestamp_aligner.py (clock drift correction)
└── Import utilities
    └── bulk_import_manager.py (batch processing)
```

**Recommendation:** Create historian connector layer with backfill capabilities.

---

### 4. **CSV/Excel Import** ❌ NOT IMPLEMENTED

#### Required Features (from plan):
- CSV upload for manual sensor logs
- Excel import for historical downtime records
- Validation and error reporting
- Template downloads for users

#### Existing Infrastructure:
**Web Framework:**
- ✅ Django views and templates
- ✅ File upload support (Django FileField)
- ❌ No CSV/Excel parsers configured

**Data Validation:**
- ✅ Model validators (MinValueValidator, MaxValueValidator)
- ❌ No CSV-specific validation pipeline

**Gap Analysis:**
```
MISSING:
├── Import views
│   ├── csv_import_view.py (upload + parse)
│   ├── excel_import_view.py (pandas integration)
│   └── import_validator.py (data validation)
├── Templates
│   ├── csv_import_template.csv (download)
│   ├── downtime_import_template.xlsx
│   └── sensor_log_template.csv
└── API endpoints
    ├── /api/import/csv/
    ├── /api/import/excel/
    └── /api/import/validate/
```

**Recommendation:** Build CSV/Excel import wizard with validation.

---

### 5. **Context Enrichment** ⚠️ PARTIAL

#### Required Features (from plan):
- Join PLC tags with production schedules
- Enrich sensor data with shift/operator context
- Product/recipe metadata tagging
- Real-time context lookup during normalization

#### Existing Infrastructure:
**Normalizer (`stream_processing/normalizer.py`):**
- ✅ Tag mapping and metadata enrichment
- ✅ Quality code propagation
- ✅ Machine/line/site hierarchy tagging
- ⚠️ Limited to PLC-centric context

**Data Models:**
- ✅ Full asset hierarchy (Plant → Area → Line → Machine)
- ✅ ProductionSchedule with work_order_number
- ✅ OperatorShift assignments
- ❌ No automatic schedule-to-telemetry joining

**API Context:**
- ✅ GraphQL for flexible queries
- ❌ No real-time schedule lookup in normalizer

**Gap Analysis:**
```
MISSING:
├── Enrichment processors
│   ├── schedule_enricher.py (join telemetry → schedule)
│   ├── shift_enricher.py (add operator context)
│   └── recipe_enricher.py (add product metadata)
├── Normalizer enhancements
│   ├── Real-time schedule cache
│   ├── Operator lookup by timestamp
│   └── Recipe version tagging
└── Data flow
    └── PLC tags → (enrich) → OEE calculations
```

**Recommendation:** Extend normalizer with schedule/shift/recipe enrichment.

---

### 6. **Data Quality & Validation** ⚠️ PARTIAL

#### Required Features (from plan):
- Quality code validation (OPC UA Good/Bad/Uncertain)
- Out-of-range detection for sensors
- Duplicate detection and filtering
- Data completeness checks

#### Existing Infrastructure:
**Quality Tracking:**
- ✅ Quality score in `SQLMachineEvent` (0-100)
- ✅ Sparkplug quality code propagation
- ✅ Dead letter queue handling (stream processor)
- ❌ No out-of-range validation rules

**Data Models:**
- ✅ `QualityDefect` model (lines 258-281 in sql_server_models.py)
- ✅ `SQLQualityEvent` model (lines 427-463)
- ❌ No sensor range configuration model

**Gap Analysis:**
```
MISSING:
├── Validation rules
│   ├── sensor_range_validator.py (min/max checks)
│   ├── duplicate_detector.py (time window dedup)
│   └── completeness_checker.py (gap detection)
├── Data models
│   ├── SensorRangeConfig (expected min/max)
│   └── DataQualityRule (validation rules)
└── Stream processing
    └── Validation stage before normalization
```

**Recommendation:** Add validation stage in stream processing pipeline.

---

### 7. **API Enhancements** ⚠️ PARTIAL

#### Required Features (from plan):
- Northbound APIs for BI/analytics tools
- Data export endpoints (CSV, JSON, Parquet)
- Real-time WebSocket for IoT sensor streams
- Batch query endpoints for historical data

#### Existing Infrastructure:
**APIs (`oee_analytics/api/`):**
- ✅ REST endpoints (`/api/kpi/current/`, `/api/trend/`, `/api/machines/status/`)
- ✅ GraphQL (`/api/graphql/`)
- ✅ WebSocket support (Django Channels configured)
- ✅ Pagination and filtering
- ❌ No data export endpoints
- ❌ No bulk historical query optimization

**Serializers:**
- ✅ DRF serializers for existing models
- ✅ Audit trail serializers (`serializers_audit.py`)
- ❌ No export-specific serializers (CSV/Parquet)

**Gap Analysis:**
```
MISSING:
├── Export endpoints
│   ├── /api/export/csv/ (CSV download)
│   ├── /api/export/parquet/ (columnar format)
│   └── /api/export/json/ (bulk JSON)
├── Batch query
│   ├── /api/batch/telemetry/ (large time ranges)
│   ├── /api/batch/oee/ (aggregated rollups)
│   └── Query optimization for 10M+ rows
└── WebSocket enhancements
    ├── /ws/iot/sensors/ (IoT sensor stream)
    └── Subscription filtering by sensor type
```

**Recommendation:** Add export endpoints and optimize batch queries.

---

### 8. **Stream Processing Enhancements** ✅ STRONG FOUNDATION

#### Required Features (from plan):
- Multi-source ingestion (PLC + MES + IoT + Historian)
- Unified normalization pipeline
- Routing to appropriate storage (time-series vs. events)
- Performance: 100K messages/sec throughput

#### Existing Infrastructure:
**Stream Processor (`stream_processing/stream_processor.py`):**
- ✅ Sparkplug decoder → Normalizer → OEE Calculator pipeline
- ✅ Fault state machine for event detection
- ✅ Async processing with asyncio
- ✅ Prometheus metrics export
- ✅ Separate queues for telemetry vs. events
- ✅ Quality code propagation
- ⚠️ Currently PLC-centric (Sparkplug B only)

**Performance:**
- ✅ 100K MQTT messages/sec validated (test_300_point_phase4_performance.py)
- ✅ 100K TimescaleDB inserts/sec validated
- ✅ Sub-1s end-to-end latency

**Gap Analysis:**
```
MINOR ENHANCEMENTS NEEDED:
├── Decoder layer
│   ├── Add MES JSON decoder
│   ├── Add generic MQTT decoder
│   └── Add CSV row decoder
├── Normalizer
│   ├── Support non-PLC data sources
│   └── Add IoT sensor normalization rules
└── Routing
    └── Dynamic routing by data source type
```

**Recommendation:** Extend decoder layer for multi-source support.

---

### 9. **Security & Compliance** ✅ MOSTLY COMPLETE

#### Required Features (from plan):
- mTLS for all external connections
- Data encryption at rest
- Audit logging for data access
- RBAC for API access

#### Existing Infrastructure:
**Security:**
- ✅ mTLS configured (MQTT broker cluster)
- ✅ PKI certificate management
- ✅ Certificate auto-rotation
- ✅ OT/IT network segmentation
- ✅ JWT authentication for APIs

**Audit Logging:**
- ✅ `AuditLog` model (`models/audit_log.py`)
- ✅ Audit serializers (`api/serializers_audit.py`)
- ✅ Audit API endpoints (`api/views_audit.py`)
- ✅ `ConfigurationAudit` in SQL Server models (lines 714-742)

**RBAC:**
- ✅ Django permissions framework
- ✅ User/Group models
- ❌ No granular data access controls (row-level security)

**Gap Analysis:**
```
MINOR GAPS:
├── Row-level security
│   └── Filter data by user's assigned sites/lines
├── Data encryption
│   └── TimescaleDB encryption at rest (infrastructure)
└── Audit enhancements
    └── Log all MES/ERP data sync operations
```

**Recommendation:** Add row-level security for multi-tenant scenarios.

---

## Summary: Existing vs. Required Infrastructure

| Component | Status | Existing Coverage | Gap Severity |
|-----------|--------|-------------------|--------------|
| **MES/ERP Integration** | ❌ Not Implemented | 40% (models exist) | **HIGH** |
| **IoT Sensor Integration** | ⚠️ Partial | 50% (MQTT infra, no generic) | **MEDIUM** |
| **Historian Connectors** | ❌ Not Implemented | 20% (storage ready) | **HIGH** |
| **CSV/Excel Import** | ❌ Not Implemented | 10% (Django upload ready) | **MEDIUM** |
| **Context Enrichment** | ⚠️ Partial | 60% (normalizer exists) | **MEDIUM** |
| **Data Quality** | ⚠️ Partial | 70% (quality codes done) | **LOW** |
| **API Enhancements** | ⚠️ Partial | 75% (REST/GraphQL/WS exist) | **LOW** |
| **Stream Processing** | ✅ Strong | 90% (PLC pipeline complete) | **LOW** |
| **Security** | ✅ Mostly Complete | 95% (mTLS/audit/RBAC done) | **VERY LOW** |

---

## Recommended Implementation Priority

### Phase 1: Critical Infrastructure (Weeks 1-3)
1. **MES/ERP Connector Layer** (Severity: HIGH)
   - Build REST/SOAP client framework
   - Implement schedule sync API
   - Create recipe download handler

2. **Historian Connectors** (Severity: HIGH)
   - OSIsoft PI Web API client
   - Wonderware REST connector
   - Bulk backfill utility

### Phase 2: Data Ingestion (Weeks 4-5)
3. **IoT Sensor Integration** (Severity: MEDIUM)
   - Generic MQTT connector (non-Sparkplug)
   - HTTP REST polling client
   - IoT sensor metadata model

4. **CSV/Excel Import** (Severity: MEDIUM)
   - Upload wizard with validation
   - Template downloads
   - Error reporting UI

### Phase 3: Enrichment & Quality (Weeks 6-7)
5. **Context Enrichment** (Severity: MEDIUM)
   - Schedule enricher (telemetry → work order)
   - Shift/operator context
   - Recipe version tagging

6. **Data Quality Validation** (Severity: LOW)
   - Sensor range validator
   - Duplicate detector
   - Completeness checker

### Phase 4: API & Polish (Weeks 8-9)
7. **API Enhancements** (Severity: LOW)
   - Export endpoints (CSV/Parquet)
   - Batch query optimization
   - IoT WebSocket subscriptions

8. **Security Enhancements** (Severity: VERY LOW)
   - Row-level security
   - Enhanced audit logging
   - Data encryption at rest (infra)

---

## Files to Create (Summary)

### New Connector Modules
```
oee_analytics/connectors/
├── mes/
│   ├── __init__.py
│   ├── mes_connector.py
│   ├── erp_connector.py
│   └── schedule_sync.py
├── iot/
│   ├── __init__.py
│   ├── generic_mqtt_connector.py
│   ├── http_polling_connector.py
│   └── iot_sensor_mapper.py
└── historian/
    ├── __init__.py
    ├── osisoft_pi_connector.py
    ├── wonderware_connector.py
    └── historian_backfill.py
```

### Data Import Infrastructure
```
oee_analytics/import/
├── __init__.py
├── csv_importer.py
├── excel_importer.py
├── validators.py
└── templates/
    ├── sensor_log.csv
    ├── downtime_import.xlsx
    └── schedule_import.csv
```

### Enrichment Processors
```
oee_analytics/stream_processing/enrichers/
├── __init__.py
├── schedule_enricher.py
├── shift_enricher.py
└── recipe_enricher.py
```

### API Extensions
```
oee_analytics/api/
├── views_export.py
├── views_mes.py
├── views_iot.py
├── serializers_export.py
└── urls_peripheral.py
```

### New Models
```
oee_analytics/models/
├── iot_sensors.py (IoTSensor, IoTSensorReading)
├── data_quality.py (SensorRangeConfig, DataQualityRule)
└── mes_sync.py (MESScheduleSync, RecipeDownload)
```

---

## Next Steps

1. **Review this analysis** with stakeholders
2. **Validate priorities** based on business needs
3. **Create detailed implementation plan** for approved components
4. **Set up development environment** for MES/Historian integration testing
5. **Begin Phase 1 implementation** (MES/ERP + Historian connectors)

---

**Analysis Complete:** October 5, 2025
**Analyst:** Claude Code
**Status:** Ready for revised implementation plan
