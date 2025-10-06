# Peripheral Data Integration - Revised Implementation Plan

**Project:** OEE Analytics Platform - Northbound & Peripheral Data Integration
**Duration:** 7-9 weeks
**Owner:** Backend Data Integration Team
**Branch:** peripheral-data-integration
**Status:** Ready to implement

---

## Overview

This plan focuses **ONLY on unimplemented components** identified in the gap analysis. Existing infrastructure (PLC connectivity, TimescaleDB, stream processing, APIs, security) will be leveraged and extended.

**Key Deliverables:**
1. MES/ERP integration layer
2. Historian (OSIsoft PI, Wonderware) connectors
3. Generic IoT sensor ingestion (MQTT, HTTP)
4. CSV/Excel import utilities
5. Context enrichment processors
6. Data quality validation
7. Export APIs (CSV, Parquet)

---

## Phase 1: MES/ERP Integration Layer (Weeks 1-3)

**Objective:** Connect to MES/ERP systems for production schedules, work orders, recipes, and material data.

### 1.1 MES Connector Framework

**Files to Create:**
```
oee_analytics/connectors/mes/
├── __init__.py
├── base_mes_connector.py       # Abstract base class
├── rest_mes_connector.py       # REST API client
├── soap_mes_connector.py       # SOAP/XML client
└── schedule_sync_service.py    # Bidirectional sync
```

**Implementation:**
```python
# base_mes_connector.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class BaseMESConnector(ABC):
    """Abstract base for MES system connectors"""

    @abstractmethod
    async def get_production_schedules(
        self,
        line_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch production schedules from MES"""
        pass

    @abstractmethod
    async def get_work_order(self, work_order_id: str) -> Dict[str, Any]:
        """Fetch work order details"""
        pass

    @abstractmethod
    async def download_recipe(self, recipe_id: str) -> Dict[str, Any]:
        """Download recipe/procedure from MES"""
        pass

    @abstractmethod
    async def update_order_status(
        self,
        work_order_id: str,
        status: str,
        actual_quantity: int
    ) -> bool:
        """Update work order status (bidirectional sync)"""
        pass

    @abstractmethod
    async def get_material_consumption(
        self,
        line_id: str,
        work_order_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch material/BOM consumption data"""
        pass
```

**API Endpoints:**
```python
# oee_analytics/api/views_mes.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
async def sync_schedules(request):
    """
    POST /api/mes/schedules/sync/
    Sync production schedules from MES to OEE platform

    Request:
    {
        "line_id": "LINE-001",
        "start_date": "2025-10-05T00:00:00Z",
        "end_date": "2025-10-12T00:00:00Z"
    }
    """
    # Fetch from MES
    # Create/update ProductionSchedule models
    # Return sync status
    pass

@api_view(['POST'])
async def download_recipe(request):
    """
    POST /api/mes/recipes/download/
    Download recipe from MES and store locally
    """
    pass

@api_view(['POST'])
async def update_order_status(request):
    """
    POST /api/mes/orders/update/
    Push order completion status back to MES
    """
    pass
```

**Data Models (extend existing):**
```python
# oee_analytics/models/mes_sync.py
from django.db import models

class MESScheduleSync(models.Model):
    """Track MES schedule synchronization"""
    sync_id = models.AutoField(primary_key=True)
    mes_system = models.CharField(max_length=50)  # SAP, Oracle, etc.
    line = models.ForeignKey('ProductionLine', on_delete=models.CASCADE)
    sync_timestamp = models.DateTimeField(auto_now_add=True)
    schedules_fetched = models.IntegerField()
    schedules_created = models.IntegerField()
    schedules_updated = models.IntegerField()
    sync_status = models.CharField(max_length=20)  # SUCCESS, PARTIAL, FAILED
    error_message = models.TextField(blank=True, null=True)

class RecipeDownload(models.Model):
    """Track recipe downloads from MES"""
    download_id = models.AutoField(primary_key=True)
    mes_recipe_id = models.CharField(max_length=100)
    local_recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    download_timestamp = models.DateTimeField(auto_now_add=True)
    recipe_version = models.CharField(max_length=20)
    downloaded_by = models.CharField(max_length=100)
```

**Configuration:**
```yaml
# config/mes_config.yml
mes:
  enabled: true
  system_type: 'sap_me'  # or 'oracle_mes', 'custom_rest'

  connection:
    base_url: 'https://mes.example.com/api/v1'
    auth_type: 'oauth2'  # or 'basic', 'api_key'
    client_id: '${MES_CLIENT_ID}'
    client_secret: '${MES_CLIENT_SECRET}'
    timeout_seconds: 30

  sync:
    schedule_sync_interval_minutes: 15
    auto_sync_enabled: true
    bidirectional_updates: true

  field_mappings:
    work_order_number: 'OrderNumber'
    planned_quantity: 'TargetQuantity'
    product_id: 'MaterialNumber'
```

**Celery Tasks:**
```python
# oee_analytics/tasks.py (add to existing)
from celery import shared_task
from .connectors.mes import MESConnectorFactory

@shared_task
def sync_mes_schedules_periodic():
    """Periodic task to sync MES schedules"""
    connector = MESConnectorFactory.get_connector()
    lines = ProductionLine.objects.filter(is_active=True)

    for line in lines:
        # Sync schedules for next 7 days
        schedules = await connector.get_production_schedules(
            line.line_id,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7)
        )

        # Update local database
        for schedule in schedules:
            ProductionSchedule.objects.update_or_create(
                work_order_number=schedule['work_order_number'],
                defaults={
                    'line': line,
                    'planned_start_utc': schedule['planned_start'],
                    'planned_end_utc': schedule['planned_end'],
                    'planned_quantity': schedule['planned_quantity'],
                    # ... other fields
                }
            )
```

**Testing:**
- Unit tests for MES connector methods
- Integration test with mock MES API
- Schedule sync accuracy validation
- Bidirectional update test (OEE → MES)

---

### 1.2 ERP Connector (SAP/Oracle)

**Files to Create:**
```
oee_analytics/connectors/erp/
├── __init__.py
├── base_erp_connector.py
├── sap_connector.py         # SAP OData/BAPI client
├── oracle_connector.py      # Oracle EBS REST
└── material_sync.py         # Material master sync
```

**Implementation Focus:**
- Material master data sync
- Labor/cost center data
- Inventory consumption tracking
- Production variance reporting

**API Endpoints:**
```python
@api_view(['POST'])
async def sync_material_master(request):
    """POST /api/erp/materials/sync/"""
    pass

@api_view(['GET'])
async def get_labor_costs(request):
    """GET /api/erp/labor/?line_id=LINE-001&date=2025-10-05"""
    pass
```

---

## Phase 2: Historian Data Integration (Weeks 3-5)

**Objective:** Import historical time-series data from OSIsoft PI and Wonderware Historian.

### 2.1 OSIsoft PI Connector

**Files to Create:**
```
oee_analytics/connectors/historian/
├── __init__.py
├── base_historian_connector.py
├── osisoft_pi_connector.py     # PI Web API client
├── wonderware_connector.py     # InSQL REST client
└── historian_backfill.py       # Bulk import manager
```

**Implementation:**
```python
# osisoft_pi_connector.py
import aiohttp
from typing import List, Dict, Any
from datetime import datetime

class OSIsoftPIConnector:
    """Connector for OSIsoft PI Historian via PI Web API"""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.auth = aiohttp.BasicAuth(username, password)

    async def get_tag_data(
        self,
        tag_name: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1s'
    ) -> List[Dict[str, Any]]:
        """
        Fetch tag data from PI Historian

        Returns:
        [
            {'timestamp': '2025-10-05T12:00:00Z', 'value': 75.5, 'quality': 'Good'},
            {'timestamp': '2025-10-05T12:00:01Z', 'value': 75.6, 'quality': 'Good'},
        ]
        """
        url = f"{self.base_url}/streams/{tag_name}/recorded"
        params = {
            'startTime': start_time.isoformat(),
            'endTime': end_time.isoformat(),
            'maxCount': 100000
        }

        async with aiohttp.ClientSession(auth=self.auth) as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return self._parse_pi_response(data)

    def _parse_pi_response(self, data: Dict) -> List[Dict]:
        """Parse PI Web API response to normalized format"""
        points = []
        for item in data.get('Items', []):
            points.append({
                'timestamp': item['Timestamp'],
                'value': item['Value'],
                'quality': self._map_quality_code(item.get('Good', True))
            })
        return points

    @staticmethod
    def _map_quality_code(pi_good: bool) -> int:
        """Map PI quality to OEE quality score (0-100)"""
        return 100 if pi_good else 0
```

**Backfill Manager:**
```python
# historian_backfill.py
class HistorianBackfillManager:
    """Manage bulk historical data import"""

    async def backfill_tag(
        self,
        tag_name: str,
        machine_id: str,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 10000
    ):
        """
        Backfill historical data in batches

        Process:
        1. Fetch data in chunks (10K points)
        2. Map to OEE data model
        3. Bulk insert to TimescaleDB
        4. Track progress in BackfillJob model
        """
        connector = OSIsoftPIConnector(...)

        current_time = start_date
        while current_time < end_date:
            batch_end = min(current_time + timedelta(hours=1), end_date)

            # Fetch batch
            data = await connector.get_tag_data(tag_name, current_time, batch_end)

            # Transform to OEE format
            events = [
                SQLMachineEvent(
                    machine_id=machine_id,
                    timestamp_utc=point['timestamp'],
                    event_type='SENSOR_DATA',
                    event_value=point['value'],
                    source_system='PI_HISTORIAN',
                    quality_score=point['quality']
                )
                for point in data
            ]

            # Bulk insert
            SQLMachineEvent.objects.bulk_create(events, batch_size=1000)

            current_time = batch_end
```

**Data Models:**
```python
# oee_analytics/models/historian_sync.py
class HistorianBackfillJob(models.Model):
    """Track historian backfill jobs"""
    job_id = models.AutoField(primary_key=True)
    historian_system = models.CharField(max_length=50)  # PI, Wonderware
    tag_name = models.CharField(max_length=200)
    machine = models.ForeignKey('Machine', on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    job_status = models.CharField(max_length=20)  # PENDING, RUNNING, COMPLETED, FAILED
    points_fetched = models.BigIntegerField(default=0)
    points_imported = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

class HistorianTagMapping(models.Model):
    """Map historian tags to OEE machine/signals"""
    mapping_id = models.AutoField(primary_key=True)
    historian_system = models.CharField(max_length=50)
    historian_tag = models.CharField(max_length=200)
    machine = models.ForeignKey('Machine', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=50)  # temperature, pressure, speed, etc.
    unit = models.CharField(max_length=20)
    scale_factor = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    offset = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
```

**API Endpoints:**
```python
@api_view(['POST'])
async def start_backfill_job(request):
    """
    POST /api/historian/backfill/start/

    Request:
    {
        "historian_system": "PI",
        "tag_name": "LINE01.TEMP_01",
        "machine_id": "MACHINE-001",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-10-01T00:00:00Z"
    }
    """
    # Create BackfillJob
    # Start async backfill task
    # Return job_id
    pass

@api_view(['GET'])
async def get_backfill_status(request):
    """GET /api/historian/backfill/status/{job_id}/"""
    pass
```

**Testing:**
- Mock PI Web API responses
- Backfill accuracy validation
- Performance test (1M points import)
- Quality code mapping verification

---

## Phase 3: IoT Sensor Integration (Weeks 5-6)

**Objective:** Ingest generic MQTT sensors and HTTP-polled environmental sensors.

### 3.1 Generic MQTT Connector (Non-Sparkplug)

**Files to Create:**
```
oee_analytics/connectors/iot/
├── __init__.py
├── generic_mqtt_connector.py
├── http_polling_connector.py
├── iot_sensor_mapper.py
└── iot_normalizer.py
```

**Implementation:**
```python
# generic_mqtt_connector.py
import paho.mqtt.client as mqtt
import json
from typing import Dict, Any

class GenericMQTTConnector:
    """Generic MQTT connector for IoT sensors (non-Sparkplug)"""

    def __init__(self, broker: str, port: int = 1883):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.message_handlers = {}

    def subscribe_topic(self, topic: str, handler_func):
        """Subscribe to MQTT topic with custom handler"""
        self.message_handlers[topic] = handler_func
        self.client.subscribe(topic, qos=1)

    def _on_message(self, client, userdata, msg):
        """Route message to appropriate handler"""
        handler = self.message_handlers.get(msg.topic)
        if handler:
            try:
                payload = json.loads(msg.payload.decode())
                handler(msg.topic, payload)
            except Exception as e:
                logger.error(f"Error processing MQTT message: {e}")

    async def connect(self):
        """Connect to MQTT broker"""
        self.client.on_message = self._on_message
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

# Example handler for temperature sensor
async def handle_temperature_sensor(topic: str, payload: Dict[str, Any]):
    """
    Expected payload:
    {
        "sensor_id": "TEMP_ZONE_A",
        "temperature": 72.5,
        "humidity": 45.2,
        "timestamp": "2025-10-05T12:00:00Z"
    }
    """
    # Map to machine
    mapping = IoTSensorMapping.objects.get(sensor_id=payload['sensor_id'])

    # Create event
    SQLMachineEvent.objects.create(
        machine=mapping.machine,
        timestamp_utc=payload['timestamp'],
        event_type='IOT_SENSOR',
        event_value=payload['temperature'],
        payload_json=json.dumps(payload),
        source_system='MQTT_IOT',
        quality_score=100
    )
```

### 3.2 HTTP Polling Connector

**Implementation:**
```python
# http_polling_connector.py
import aiohttp
import asyncio

class HTTPPollingConnector:
    """Poll REST APIs for sensor data"""

    def __init__(self, endpoints: List[Dict]):
        """
        endpoints = [
            {
                'url': 'http://sensor.local/api/data',
                'interval_seconds': 60,
                'sensor_id': 'ENV_SENSOR_01',
                'machine_id': 'MACHINE-001'
            }
        ]
        """
        self.endpoints = endpoints
        self.running = False

    async def start_polling(self):
        """Start polling all endpoints"""
        self.running = True
        tasks = [self._poll_endpoint(ep) for ep in self.endpoints]
        await asyncio.gather(*tasks)

    async def _poll_endpoint(self, endpoint: Dict):
        """Poll single endpoint periodically"""
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(endpoint['url']) as response:
                        data = await response.json()
                        await self._process_sensor_data(endpoint, data)
            except Exception as e:
                logger.error(f"Polling error for {endpoint['url']}: {e}")

            await asyncio.sleep(endpoint['interval_seconds'])

    async def _process_sensor_data(self, endpoint: Dict, data: Dict):
        """Process polled sensor data"""
        SQLMachineEvent.objects.create(
            machine_id=endpoint['machine_id'],
            timestamp_utc=datetime.now(timezone.utc),
            event_type='HTTP_SENSOR',
            payload_json=json.dumps(data),
            source_system='HTTP_POLLING',
            quality_score=100
        )
```

**Data Models:**
```python
# oee_analytics/models/iot_sensors.py
class IoTSensor(models.Model):
    """IoT sensor metadata"""
    sensor_id = models.CharField(max_length=100, primary_key=True)
    sensor_type = models.CharField(max_length=50)  # temperature, vibration, pressure, etc.
    machine = models.ForeignKey('Machine', on_delete=models.CASCADE)
    protocol = models.CharField(max_length=20)  # MQTT, HTTP, Modbus
    mqtt_topic = models.CharField(max_length=200, blank=True, null=True)
    http_endpoint = models.URLField(blank=True, null=True)
    polling_interval_seconds = models.IntegerField(blank=True, null=True)
    unit = models.CharField(max_length=20)
    min_expected_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_expected_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)

class IoTSensorReading(models.Model):
    """Time-series IoT sensor data"""
    reading_id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey(IoTSensor, on_delete=models.CASCADE)
    timestamp_utc = models.DateTimeField(db_index=True)
    value = models.DecimalField(max_digits=18, decimal_places=6)
    quality_score = models.SmallIntegerField(default=100)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = 'IoTSensorReadings'
        indexes = [
            models.Index(fields=['sensor', 'timestamp_utc']),
        ]
```

**Configuration:**
```yaml
# config/iot_config.yml
iot:
  mqtt:
    enabled: true
    broker: 'iot-broker.local'
    port: 1883
    topics:
      - pattern: 'factory/+/temperature'
        sensor_type: 'temperature'
      - pattern: 'factory/+/vibration'
        sensor_type: 'vibration'

  http_polling:
    enabled: true
    endpoints:
      - url: 'http://env-sensor.local/api/data'
        interval_seconds: 60
        sensor_id: 'ENV_01'
        machine_id: 'MACHINE-001'
```

---

## Phase 4: CSV/Excel Import (Week 6)

**Objective:** Allow manual import of historical sensor logs and downtime records.

### 4.1 Import Wizard

**Files to Create:**
```
oee_analytics/import/
├── __init__.py
├── csv_importer.py
├── excel_importer.py
├── validators.py
└── templates/
    ├── sensor_log_template.csv
    ├── downtime_import_template.xlsx
    └── schedule_import_template.csv
```

**Implementation:**
```python
# csv_importer.py
import pandas as pd
from typing import List, Dict, Any

class CSVImporter:
    """Import sensor logs from CSV"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.errors = []

    def validate(self) -> bool:
        """Validate CSV structure and data"""
        try:
            df = pd.read_csv(self.file_path)

            # Check required columns
            required_columns = ['timestamp', 'machine_id', 'sensor_type', 'value']
            missing = set(required_columns) - set(df.columns)
            if missing:
                self.errors.append(f"Missing columns: {missing}")
                return False

            # Validate data types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['value'] = pd.to_numeric(df['value'])

            # Check for duplicates
            duplicates = df.duplicated(subset=['timestamp', 'machine_id', 'sensor_type'])
            if duplicates.any():
                self.errors.append(f"Found {duplicates.sum()} duplicate records")

            # Validate machine_id exists
            invalid_machines = set(df['machine_id']) - set(
                Machine.objects.values_list('machine_id', flat=True)
            )
            if invalid_machines:
                self.errors.append(f"Invalid machine IDs: {invalid_machines}")
                return False

            return True

        except Exception as e:
            self.errors.append(str(e))
            return False

    def import_data(self) -> Dict[str, Any]:
        """Import validated CSV data"""
        if not self.validate():
            return {'success': False, 'errors': self.errors}

        df = pd.read_csv(self.file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Batch create events
        events = [
            SQLMachineEvent(
                machine_id=row['machine_id'],
                timestamp_utc=row['timestamp'],
                event_type='CSV_IMPORT',
                event_value=row['value'],
                payload_json=row.to_json(),
                source_system='CSV_IMPORT',
                quality_score=100
            )
            for _, row in df.iterrows()
        ]

        SQLMachineEvent.objects.bulk_create(events, batch_size=1000)

        return {
            'success': True,
            'records_imported': len(events),
            'errors': []
        }
```

**Django Views:**
```python
# oee_analytics/views_import.py
from django.shortcuts import render
from django.http import JsonResponse

def csv_import_wizard(request):
    """Render CSV import wizard"""
    return render(request, 'import/csv_wizard.html')

@csrf_exempt
def upload_csv(request):
    """
    POST /api/import/csv/upload/
    """
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']

        # Save temporarily
        temp_path = f'/tmp/{csv_file.name}'
        with open(temp_path, 'wb+') as f:
            for chunk in csv_file.chunks():
                f.write(chunk)

        # Validate
        importer = CSVImporter(temp_path)
        if not importer.validate():
            return JsonResponse({
                'success': False,
                'errors': importer.errors
            }, status=400)

        # Import
        result = importer.import_data()
        return JsonResponse(result)
```

**Templates:**
```csv
# templates/sensor_log_template.csv
timestamp,machine_id,sensor_type,value,unit,quality
2025-10-05T12:00:00Z,MACHINE-001,temperature,75.5,degC,100
2025-10-05T12:00:01Z,MACHINE-001,temperature,75.6,degC,100
2025-10-05T12:00:02Z,MACHINE-001,pressure,45.2,psi,100
```

```excel
# downtime_import_template.xlsx (structure)
Columns:
- start_timestamp (datetime)
- end_timestamp (datetime)
- machine_id (text)
- line_id (text)
- reason_code (text)
- description (text)
- operator_id (text)
```

**API Endpoints:**
```python
@api_view(['POST'])
def import_csv(request):
    """POST /api/import/csv/"""
    pass

@api_view(['POST'])
def import_excel(request):
    """POST /api/import/excel/"""
    pass

@api_view(['GET'])
def download_template(request):
    """GET /api/import/template/?type=sensor_log"""
    pass
```

---

## Phase 5: Context Enrichment (Week 7)

**Objective:** Enrich telemetry data with production schedule, shift, operator, and recipe context.

### 5.1 Schedule Enrichment Processor

**Files to Create:**
```
oee_analytics/stream_processing/enrichers/
├── __init__.py
├── schedule_enricher.py
├── shift_enricher.py
└── recipe_enricher.py
```

**Implementation:**
```python
# schedule_enricher.py
from typing import Optional, Dict, Any
from datetime import datetime
from ..normalizer import NormalizedMetric

class ScheduleEnricher:
    """Enrich telemetry with production schedule context"""

    def __init__(self):
        self.schedule_cache = {}  # In-memory cache
        self.cache_ttl_seconds = 300  # 5 minutes

    async def enrich(self, metric: NormalizedMetric) -> NormalizedMetric:
        """
        Add schedule context to metric

        Adds to metric.metadata:
        - work_order_number
        - product_id
        - recipe_id
        - planned_quantity
        """
        schedule = await self._get_active_schedule(
            metric.line_id,
            metric.timestamp_utc
        )

        if schedule:
            metric.metadata['work_order_number'] = schedule.work_order_number
            metric.metadata['product_id'] = schedule.recipe.product_id
            metric.metadata['recipe_id'] = schedule.recipe.recipe_id
            metric.metadata['planned_quantity'] = schedule.planned_quantity
            metric.metadata['schedule_status'] = schedule.schedule_status

        return metric

    async def _get_active_schedule(
        self,
        line_id: str,
        timestamp: datetime
    ) -> Optional['ProductionSchedule']:
        """Get active schedule for line at timestamp (with caching)"""
        cache_key = f"{line_id}:{timestamp.date()}"

        if cache_key in self.schedule_cache:
            cached_time, schedule = self.schedule_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl_seconds:
                return schedule

        # Fetch from database
        schedule = ProductionSchedule.objects.filter(
            line_id=line_id,
            planned_start_utc__lte=timestamp,
            planned_end_utc__gte=timestamp,
            schedule_status='ACTIVE'
        ).first()

        # Cache result
        self.schedule_cache[cache_key] = (datetime.now(), schedule)

        return schedule
```

**Integration with Stream Processor:**
```python
# Modify stream_processing/stream_processor.py

from .enrichers.schedule_enricher import ScheduleEnricher
from .enrichers.shift_enricher import ShiftEnricher
from .enrichers.recipe_enricher import RecipeEnricher

class StreamProcessor:
    def __init__(self, config: StreamProcessorConfig, logger=None):
        # ... existing init ...

        # Add enrichers
        self.schedule_enricher = ScheduleEnricher()
        self.shift_enricher = ShiftEnricher()
        self.recipe_enricher = RecipeEnricher()

    async def _process_normalized_metric(self, metric: NormalizedMetric):
        """Process a normalized metric through enrichers and calculators"""
        try:
            # Stage 1: Context enrichment
            metric = await self.schedule_enricher.enrich(metric)
            metric = await self.shift_enricher.enrich(metric)
            metric = await self.recipe_enricher.enrich(metric)

            # Stage 2: Send to telemetry queue (with enriched context)
            await self.telemetry_queue.put({
                'type': 'telemetry',
                'data': {
                    'machine_id': metric.machine_id,
                    'line_id': metric.line_id,
                    'site_id': metric.site_id,
                    'name': metric.name,
                    'value': metric.value,
                    'timestamp_utc': metric.timestamp_utc.isoformat(),
                    'quality': metric.quality,
                    'metadata': metric.metadata  # Now includes schedule/shift/recipe context
                }
            })

            # Stage 3: OEE calculator and fault detection
            # ... existing code ...
```

**Shift Enricher:**
```python
# shift_enricher.py
class ShiftEnricher:
    """Add shift and operator context"""

    async def enrich(self, metric: NormalizedMetric) -> NormalizedMetric:
        """Add shift context to metric"""
        shift = await self._get_active_shift(metric.line_id, metric.timestamp_utc)

        if shift:
            metric.metadata['shift_number'] = shift.shift_number
            metric.metadata['shift_date'] = shift.shift_date.isoformat()
            metric.metadata['operator_id'] = shift.operator_id
            metric.metadata['operator_role'] = shift.role

        return metric

    async def _get_active_shift(self, line_id: str, timestamp: datetime):
        """Find active shift for line at timestamp"""
        return OperatorShift.objects.filter(
            line_id=line_id,
            start_time_utc__lte=timestamp,
            end_time_utc__gte=timestamp
        ).first()
```

**Recipe Enricher:**
```python
# recipe_enricher.py
class RecipeEnricher:
    """Add recipe/product metadata"""

    async def enrich(self, metric: NormalizedMetric) -> NormalizedMetric:
        """Add recipe context (if available from schedule)"""
        if 'recipe_id' in metric.metadata:
            recipe = await self._get_recipe(metric.metadata['recipe_id'])
            if recipe:
                metric.metadata['product_name'] = recipe.product.product_name
                metric.metadata['product_family'] = recipe.product.product_family
                metric.metadata['target_cycle_time'] = float(recipe.target_cycle_time_seconds)
                metric.metadata['recipe_version'] = recipe.version

        return metric

    async def _get_recipe(self, recipe_id: str):
        """Get recipe details"""
        return Recipe.objects.select_related('product').get(recipe_id=recipe_id)
```

---

## Phase 6: Data Quality Validation (Week 7)

**Objective:** Add validation layer to detect out-of-range sensors, duplicates, and data completeness issues.

### 6.1 Validation Pipeline

**Files to Create:**
```
oee_analytics/stream_processing/validators/
├── __init__.py
├── range_validator.py
├── duplicate_detector.py
└── completeness_checker.py
```

**Implementation:**
```python
# range_validator.py
class SensorRangeValidator:
    """Validate sensor values are within expected range"""

    async def validate(self, metric: NormalizedMetric) -> bool:
        """
        Check if metric value is within expected range
        Returns: True if valid, False if out-of-range
        """
        # Get expected range for this sensor
        range_config = await self._get_range_config(
            metric.machine_id,
            metric.signal_type
        )

        if not range_config:
            return True  # No range configured = assume valid

        if metric.value < range_config.min_value or metric.value > range_config.max_value:
            # Log violation
            logger.warning(
                f"Out-of-range: {metric.machine_id}.{metric.name} = {metric.value} "
                f"(expected: {range_config.min_value} - {range_config.max_value})"
            )

            # Update quality score
            metric.quality = 50  # Degraded quality

            # Create alert event
            await self._create_quality_alert(metric, range_config)

            return False

        return True

    async def _get_range_config(self, machine_id: str, signal_type: str):
        """Fetch sensor range configuration"""
        return SensorRangeConfig.objects.filter(
            machine_id=machine_id,
            signal_type=signal_type,
            is_active=True
        ).first()

# duplicate_detector.py
class DuplicateDetector:
    """Detect and filter duplicate sensor readings"""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.recent_readings = {}  # {machine_id: [(timestamp, value), ...]}

    async def is_duplicate(self, metric: NormalizedMetric) -> bool:
        """Check if metric is duplicate within time window"""
        key = f"{metric.machine_id}:{metric.name}"

        # Clean old readings
        self._cleanup_old_readings(key, metric.timestamp_utc)

        # Check for exact match
        if key in self.recent_readings:
            for ts, value in self.recent_readings[key]:
                if abs((metric.timestamp_utc - ts).total_seconds()) < 1 and metric.value == value:
                    logger.debug(f"Duplicate detected: {key} at {metric.timestamp_utc}")
                    return True

        # Add to recent readings
        if key not in self.recent_readings:
            self.recent_readings[key] = []
        self.recent_readings[key].append((metric.timestamp_utc, metric.value))

        return False
```

**Data Models:**
```python
# oee_analytics/models/data_quality.py
class SensorRangeConfig(models.Model):
    """Expected value ranges for sensors"""
    config_id = models.AutoField(primary_key=True)
    machine = models.ForeignKey('Machine', on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=50)  # temperature, pressure, speed
    min_value = models.DecimalField(max_digits=18, decimal_places=6)
    max_value = models.DecimalField(max_digits=18, decimal_places=6)
    unit = models.CharField(max_length=20)
    violation_action = models.CharField(max_length=20, default='ALERT')  # ALERT, REJECT, DEGRADE
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DataQualityAlert(models.Model):
    """Track data quality violations"""
    alert_id = models.BigAutoField(primary_key=True)
    machine = models.ForeignKey('Machine', on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=50)  # OUT_OF_RANGE, DUPLICATE, GAP
    timestamp_utc = models.DateTimeField()
    metric_name = models.CharField(max_length=100)
    metric_value = models.DecimalField(max_digits=18, decimal_places=6)
    expected_min = models.DecimalField(max_digits=18, decimal_places=6, blank=True, null=True)
    expected_max = models.DecimalField(max_digits=18, decimal_places=6, blank=True, null=True)
    severity = models.CharField(max_length=20, default='WARNING')
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Integration:**
```python
# Modify stream_processor.py to add validation stage

async def _process_normalized_metric(self, metric: NormalizedMetric):
    """Process normalized metric with validation"""
    try:
        # Stage 0: Validation
        is_valid_range = await self.range_validator.validate(metric)
        is_duplicate = await self.duplicate_detector.is_duplicate(metric)

        if is_duplicate:
            logger.debug(f"Skipping duplicate metric: {metric.machine_id}.{metric.name}")
            return  # Skip processing

        # Stage 1: Context enrichment
        # ... existing enrichment code ...
```

---

## Phase 7: API Enhancements (Week 8-9)

**Objective:** Add export endpoints and batch query optimization.

### 7.1 Export Endpoints

**Files to Create:**
```
oee_analytics/api/
├── views_export.py
├── serializers_export.py
└── exporters/
    ├── csv_exporter.py
    ├── parquet_exporter.py
    └── json_exporter.py
```

**Implementation:**
```python
# views_export.py
from rest_framework.decorators import api_view
from django.http import StreamingHttpResponse
import csv
import io

@api_view(['GET'])
def export_telemetry_csv(request):
    """
    GET /api/export/telemetry/csv/

    Query params:
    - machine_id (required)
    - start_date (required)
    - end_date (required)
    - metrics (optional, comma-separated)
    """
    machine_id = request.query_params.get('machine_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    # Query data
    events = SQLMachineEvent.objects.filter(
        machine_id=machine_id,
        timestamp_utc__gte=start_date,
        timestamp_utc__lte=end_date
    ).order_by('timestamp_utc')

    # Stream CSV response
    def csv_generator():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Header
        writer.writerow(['timestamp', 'machine_id', 'event_type', 'value', 'quality'])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        # Data rows
        for event in events.iterator(chunk_size=1000):
            writer.writerow([
                event.timestamp_utc.isoformat(),
                event.machine_id,
                event.event_type,
                event.event_value,
                event.quality_score
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    response = StreamingHttpResponse(csv_generator(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="telemetry_{machine_id}.csv"'
    return response

@api_view(['GET'])
def export_parquet(request):
    """
    GET /api/export/telemetry/parquet/

    Export to columnar Parquet format for analytics tools
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Query data
    events = SQLMachineEvent.objects.filter(...).values(
        'timestamp_utc', 'machine_id', 'event_type', 'event_value', 'quality_score'
    )

    # Convert to DataFrame
    df = pd.DataFrame(events)

    # Write to Parquet
    buffer = io.BytesIO()
    table = pa.Table.from_pandas(df)
    pq.write_table(table, buffer, compression='snappy')

    response = StreamingHttpResponse(buffer.getvalue(), content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="telemetry.parquet"'
    return response
```

### 7.2 Batch Query Optimization

**Implementation:**
```python
@api_view(['POST'])
def batch_telemetry_query(request):
    """
    POST /api/batch/telemetry/

    Optimized for large time ranges (10M+ rows)

    Request:
    {
        "machine_ids": ["MACHINE-001", "MACHINE-002"],
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-10-01T00:00:00Z",
        "aggregation": "1h",  # 1min, 5min, 1h, 1d
        "metrics": ["temperature", "pressure"]
    }
    """
    # Use TimescaleDB continuous aggregates for fast queries
    query = """
    SELECT
        time_bucket('1 hour', timestamp_utc) AS bucket,
        machine_id,
        event_type,
        AVG(event_value) as avg_value,
        MAX(event_value) as max_value,
        MIN(event_value) as min_value,
        COUNT(*) as count
    FROM MachineEvents
    WHERE machine_id = ANY(%s)
      AND timestamp_utc >= %s
      AND timestamp_utc <= %s
      AND event_type = ANY(%s)
    GROUP BY bucket, machine_id, event_type
    ORDER BY bucket
    """

    # Execute and return
    # ...
```

### 7.3 WebSocket IoT Stream

**Implementation:**
```python
# oee_analytics/consumers.py (extend existing)

class IoTSensorConsumer(AsyncWebsocketConsumer):
    """WebSocket for real-time IoT sensor data"""

    async def connect(self):
        self.sensor_types = self.scope['url_route']['kwargs'].get('sensor_types', 'all')
        await self.channel_layer.group_add('iot_sensors', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('iot_sensors', self.channel_name)

    async def iot_sensor_update(self, event):
        """Send IoT sensor update to WebSocket"""
        # Filter by sensor type if specified
        if self.sensor_types != 'all':
            requested_types = self.sensor_types.split(',')
            if event['sensor_type'] not in requested_types:
                return

        await self.send(text_data=json.dumps({
            'type': 'iot_sensor',
            'sensor_id': event['sensor_id'],
            'sensor_type': event['sensor_type'],
            'value': event['value'],
            'timestamp': event['timestamp'],
            'machine_id': event['machine_id']
        }))

# Routing
websocket_urlpatterns = [
    # ... existing patterns ...
    re_path(r'ws/iot/sensors/(?P<sensor_types>\w+)/$', IoTSensorConsumer.as_asgi()),
]
```

---

## Testing Strategy

### Unit Tests
- MES connector methods (mock MES API)
- Historian connector data fetching
- IoT MQTT message parsing
- CSV/Excel validation logic
- Enrichment processor accuracy
- Validation rule enforcement

### Integration Tests
- End-to-end MES schedule sync
- Historian backfill (1M points)
- IoT sensor data flow (MQTT → DB)
- CSV import with 100K rows
- Context enrichment pipeline
- Export endpoint performance

### Performance Tests
- 100K IoT messages/sec ingestion
- Historian backfill: 10M points in < 5 min
- CSV import: 1M rows in < 2 min
- Batch query: 50M rows in < 10s (aggregated)
- WebSocket: 10K concurrent IoT subscriptions

---

## Deployment Checklist

### Configuration
- [ ] MES/ERP connection credentials
- [ ] Historian (PI/Wonderware) API keys
- [ ] IoT MQTT broker endpoints
- [ ] HTTP polling sensor URLs
- [ ] Tag mapping configurations

### Database Migrations
- [ ] Run new model migrations (IoTSensor, HistorianBackfillJob, etc.)
- [ ] Create TimescaleDB hypertables for IoTSensorReading
- [ ] Set up continuous aggregates for IoT data

### Services
- [ ] Deploy MES schedule sync Celery task
- [ ] Start IoT MQTT connector service
- [ ] Start HTTP polling connector service
- [ ] Enable historian backfill worker

### Monitoring
- [ ] Add Prometheus metrics for new connectors
- [ ] Configure alerts for MES sync failures
- [ ] Set up dashboards for IoT sensor health
- [ ] Monitor historian backfill job progress

---

## Success Criteria

### Functionality
- ✅ MES schedules sync every 15 minutes
- ✅ Historian backfill imports 1M+ points/minute
- ✅ IoT sensors publish to MQTT and appear in OEE platform
- ✅ CSV import handles 1M rows with validation
- ✅ Context enrichment adds schedule/shift/recipe to 100% of telemetry
- ✅ Data quality validation catches 99% of out-of-range sensors
- ✅ Export APIs deliver CSV/Parquet in < 30 seconds for 1M rows

### Performance
- ✅ 100K IoT messages/sec ingestion rate
- ✅ MES API response < 2s P95
- ✅ Historian backfill: 10M points in < 5 min
- ✅ Batch query: 50M rows aggregated in < 10s

### Reliability
- ✅ 99.9% uptime for MES sync service
- ✅ Zero data loss for IoT sensor streams
- ✅ Automatic retry on MES/Historian API failures
- ✅ Audit trail for all data imports and syncs

---

## Files to Create Summary

### Connectors (19 files)
```
oee_analytics/connectors/
├── mes/
│   ├── __init__.py
│   ├── base_mes_connector.py
│   ├── rest_mes_connector.py
│   ├── soap_mes_connector.py
│   └── schedule_sync_service.py
├── erp/
│   ├── __init__.py
│   ├── base_erp_connector.py
│   ├── sap_connector.py
│   ├── oracle_connector.py
│   └── material_sync.py
├── historian/
│   ├── __init__.py
│   ├── base_historian_connector.py
│   ├── osisoft_pi_connector.py
│   ├── wonderware_connector.py
│   └── historian_backfill.py
└── iot/
    ├── __init__.py
    ├── generic_mqtt_connector.py
    ├── http_polling_connector.py
    └── iot_sensor_mapper.py
```

### Import (6 files)
```
oee_analytics/import/
├── __init__.py
├── csv_importer.py
├── excel_importer.py
├── validators.py
└── templates/
    ├── sensor_log_template.csv
    ├── downtime_import_template.xlsx
    └── schedule_import_template.csv
```

### Stream Processing (10 files)
```
oee_analytics/stream_processing/
├── enrichers/
│   ├── __init__.py
│   ├── schedule_enricher.py
│   ├── shift_enricher.py
│   └── recipe_enricher.py
└── validators/
    ├── __init__.py
    ├── range_validator.py
    ├── duplicate_detector.py
    └── completeness_checker.py
```

### APIs (10 files)
```
oee_analytics/api/
├── views_mes.py
├── views_historian.py
├── views_iot.py
├── views_export.py
├── views_import.py
├── serializers_export.py
├── urls_peripheral.py
└── exporters/
    ├── csv_exporter.py
    ├── parquet_exporter.py
    └── json_exporter.py
```

### Models (4 files)
```
oee_analytics/models/
├── mes_sync.py (MESScheduleSync, RecipeDownload)
├── historian_sync.py (HistorianBackfillJob, HistorianTagMapping)
├── iot_sensors.py (IoTSensor, IoTSensorReading)
└── data_quality.py (SensorRangeConfig, DataQualityAlert)
```

### Configuration (4 files)
```
config/
├── mes_config.yml
├── erp_config.yml
├── historian_config.yml
└── iot_config.yml
```

### Total: ~53 new files

---

**Plan Status:** ✅ Ready for Implementation
**Estimated Effort:** 7-9 weeks
**Next Step:** Begin Phase 1 - MES/ERP Integration Layer
