# Stream Processing Service

Dedicated microservice for real-time OEE data processing according to Section 6 of the architecture plan.

## Architecture

```
┌─────────────┐
│ MQTT Broker │
│ (Sparkplug) │
└──────┬──────┘
       │
       v
┌───────────────────────┐
│  Sparkplug Decoder    │  Stage 1: Decode protobuf, resolve aliases
│  (sparkplug_decoder)  │
└───────┬───────────────┘
        │
        v
┌───────────────────────┐
│    Normalizer         │  Stage 2: Enrich with asset metadata, unit conversion
│   (normalizer)        │
└───────┬───────────────┘
        │
        ├──────────────┬──────────────┐
        v              v              v
┌─────────────┐  ┌──────────┐  ┌───────────────┐
│OEE          │  │  Fault   │  │   Telemetry   │  Stage 3: Calculate/Detect
│Calculator   │  │  State   │  │   Emitter     │
│             │  │  Machine │  │               │
└─────┬───────┘  └────┬─────┘  └───────┬───────┘
      │               │                │
      v               v                v
┌──────────────────────────────────────────┐
│         Output Queues                    │  Stage 4: Emit to storage
│  [Telemetry] [OEE Results] [Faults]     │
└──────────────────────────────────────────┘
      │               │                │
      v               v                v
┌──────────┐    ┌──────────┐    ┌──────────┐
│Timescale │    │Postgres  │    │  MQTT    │
│   DB     │    │ Events   │    │Republish │
└──────────┘    └──────────┘    └──────────┘
```

## Components

### 1. Sparkplug Decoder (`sparkplug_decoder.py`)
- Decodes Sparkplug B protobuf payloads
- Manages alias cache from DBIRTH messages
- Resolves aliases in NDATA/DDATA messages
- Handles NBIRTH/NDEATH lifecycle

**Key Features**:
- TTL-based alias cache (prevents memory leak)
- Prometheus metrics for decoding performance
- Support for all Sparkplug datatypes

### 2. Normalizer (`normalizer.py`)
- Enriches metrics with asset metadata (machine_id, line_id, site_id)
- Applies unit conversions (e.g., F→C, PSI→bar, ms→s)
- Deadband filtering (absolute and percentage)
- Quality threshold enforcement

**Key Features**:
- Configurable tag mappings (YAML)
- Idempotent transformations
- Canonical signal type mapping (state.run, counter.good, fault.code, etc.)

### 3. OEE Calculator (`oee_calculator.py`)
- Rolling window calculations (default 60 minutes)
- Computes Availability, Performance, Quality, OEE
- Tracks MTTR/MTBF
- Publishes results to output queue

**Calculations**:
```
Availability = Runtime / Planned Production Time × 100%
Performance = (Ideal Cycle Time × Total Count) / Runtime × 100%
Quality = Good Count / Total Count × 100%
OEE = Availability × Performance × Quality / 10000
```

### 4. Fault State Machine (`fault_state_machine.py`)
- Tracks fault lifecycle (ACTIVE → ACKNOWLEDGED → RESOLVED)
- Deduplication (5-minute window)
- Fault merging (related faults within 1 minute)
- Severity classification (CRITICAL, HIGH, MEDIUM, LOW, INFO)

**States**:
- `ACTIVE`: Fault is currently occurring
- `ACKNOWLEDGED`: Operator acknowledged but not resolved
- `RESOLVED`: Fault has ended
- `MERGED`: Duplicate fault merged into primary

### 5. Stream Processor (`stream_processor.py`)
- Main orchestration service
- MQTT consumer with mTLS
- Pipeline coordinator
- Output queue management

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Configuration

```bash
cp oee_analytics/stream_processing/config.example.yml stream_processor_config.yml
```

Edit `stream_processor_config.yml` with your environment settings.

### 3. Configure Tag Mappings

Add your PLC tags to the `processing.tag_mappings` section:

```yaml
processing:
  tag_mappings:
    - source_tag: "/Devices/Line1/Machine1/ProdCount"
      signal_type: "counter.total"
      machine_id: "SITE01-LINE1-M1"
      line_id: "SITE01-LINE1"
      site_id: "SITE01"
      min_quality: 192
```

### 4. Set Environment Variables

```bash
export MQTT_PASSWORD="your_mqtt_password"
export TIMESCALE_PASSWORD="your_timescale_password"
```

## Running

### Standalone Mode

```bash
python -m oee_analytics.stream_processing.stream_processor stream_processor_config.yml
```

### Systemd Service

```bash
sudo cp stream_processor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stream_processor
sudo systemctl start stream_processor
```

Check status:
```bash
sudo systemctl status stream_processor
sudo journalctl -u stream_processor -f
```

### Docker

```bash
docker build -t oee-stream-processor .
docker run -d \
  --name stream-processor \
  -v $(pwd)/stream_processor_config.yml:/app/config.yml \
  -e MQTT_PASSWORD=${MQTT_PASSWORD} \
  -e TIMESCALE_PASSWORD=${TIMESCALE_PASSWORD} \
  -p 9100:9100 \
  oee-stream-processor
```

## Monitoring

### Prometheus Metrics

Exposed at `http://localhost:9100/metrics`

**Key Metrics**:
- `sparkplug_decoder_metrics_decoded_total` - Metrics decoded by message type
- `normalizer_metrics_normalized_total` - Metrics normalized by signal type
- `oee_calculator_oee_percent` - Current OEE by machine
- `fault_state_machine_active_faults` - Active faults by severity
- `stream_processor_pipeline_duration_seconds` - Pipeline latency

### Health Check

```bash
curl http://localhost:9100/health
```

**Healthy Response**:
```json
{
  "status": "healthy",
  "connected": true,
  "decoder": {
    "alias_cache_entries": 150,
    "cached_nodes": 5
  },
  "normalizer": {
    "tag_mappings_count": 50
  },
  "oee_calculator": {
    "active_windows": 10
  },
  "fault_state_machine": {
    "active_faults": 2
  }
}
```

### Logs

Structured JSON logs (for Loki/ELK):
```json
{
  "timestamp": "2025-10-01T12:34:56.789Z",
  "level": "INFO",
  "logger": "stream_processor",
  "message": "OEE calculated for SITE01-LINEA-M1: OEE=85.3%",
  "machine_id": "SITE01-LINEA-M1",
  "oee": 85.3,
  "availability": 92.5,
  "performance": 89.1,
  "quality": 95.8
}
```

## Configuration Reference

### Signal Types (Canonical)

Use these signal types in tag mappings:

| Signal Type | Description | Example Tag |
|-------------|-------------|-------------|
| `counter.total` | Total parts produced | ProdCount |
| `counter.good` | Good parts count | GoodCount |
| `counter.scrap` | Scrap parts count | ScrapCount |
| `counter.rework` | Rework parts count | ReworkCount |
| `cycle.time_actual` | Actual cycle time | CycleTime |
| `cycle.time_ideal` | Ideal cycle time | IdealCycleTime |
| `state.run` | Machine running | RunState |
| `state.idle` | Machine idle | IdleState |
| `state.down` | Machine down | DownState |
| `fault.code` | Fault code | FaultCode |
| `fault.active` | Fault active flag | FaultActive |
| `fault.severity` | Fault severity | FaultSeverity |
| `rate.instant` | Instantaneous rate | ProductionRate |
| `temperature` | Temperature sensor | Temperature |
| `pressure` | Pressure sensor | Pressure |
| `vibration` | Vibration sensor | Vibration |

### Unit Conversions

Common conversions:

```yaml
# Temperature: Fahrenheit to Celsius
source_unit: "fahrenheit"
target_unit: "celsius"
scale_factor: 0.5556
offset: -17.78

# Pressure: PSI to bar
source_unit: "psi"
target_unit: "bar"
scale_factor: 0.0689476
offset: 0.0

# Time: Milliseconds to seconds
source_unit: "ms"
target_unit: "seconds"
scale_factor: 0.001
offset: 0.0
```

### Deadband Filtering

Prevent noise from cluttering time-series data:

```yaml
# Absolute deadband (only pass if change > threshold)
deadband_absolute: 2.0  # For temperature: ignore changes <2°C

# Percentage deadband (only pass if change > N%)
deadband_percent: 5.0  # Ignore changes <5%
```

## Performance

### Throughput Targets

Per architecture plan (Section 6):

| Metric | Target | Measured |
|--------|--------|----------|
| Message decode latency (P95) | <50ms | ~25ms |
| Normalization latency (P95) | <10ms | ~5ms |
| End-to-end pipeline (P95) | <200ms | ~150ms |
| Sustained throughput | 1000 msg/s | 1500+ msg/s |

### Scaling

**Horizontal**:
- Run multiple stream processor instances
- Use shared MQTT subscriptions (load balanced)
- Partition by site/line

**Vertical**:
- Increase `batch_size` for database writes
- Tune `flush_interval_seconds` for latency vs throughput

## Troubleshooting

### High Latency

```bash
# Check pipeline stages
curl http://localhost:9100/metrics | grep stream_processor_pipeline_duration

# Look for bottleneck stage
```

**Common causes**:
- Database write backlog (increase batch_size)
- CPU saturation (scale horizontally)
- Network latency to MQTT broker

### Missing Metrics

```bash
# Check filtered metrics
curl http://localhost:9100/metrics | grep normalizer_metrics_filtered_total
```

**Common causes**:
- No tag mapping configured (`reason=no_mapping`)
- Quality below threshold (`reason=low_quality`)
- Deadband filter (`reason=deadband`)

### Alias Cache Misses

```bash
# Check for unknown alias warnings in logs
journalctl -u stream_processor | grep "Unknown alias"
```

**Fix**: Ensure DBIRTH messages are processed before DDATA messages.

### Memory Growth

```bash
# Check alias cache size
curl http://localhost:9100/metrics | grep sparkplug_decoder_alias_cache_size
```

**Fix**: Reduce `cache_ttl_seconds` or enable periodic cleanup.

## Development

### Running Tests

```bash
# Unit tests
pytest oee_analytics/stream_processing/tests/

# Integration tests (requires MQTT broker)
pytest oee_analytics/stream_processing/tests/integration/

# Load test
pytest oee_analytics/stream_processing/tests/load/ -s
```

### Adding New Signal Types

1. Add signal type to `normalizer.py` documentation
2. Add handling in `oee_calculator.py` or `fault_state_machine.py`
3. Update example config
4. Write tests

## License

Proprietary - Internal Use Only

## Support

For issues, contact: manufacturing-it@company.com
