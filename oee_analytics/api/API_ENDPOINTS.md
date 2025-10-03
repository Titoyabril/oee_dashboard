# OEE Analytics REST API Endpoints

## Base URL
All endpoints are prefixed with `/api/`

## Authentication
Most endpoints require authentication. Use token authentication:
```
Authorization: Token <your-token>
```

Get token: `POST /api/auth/token/`

---

## KPI & Metrics Endpoints

### GET `/api/kpi/current/`
**Get current OEE metrics for all production lines**

**Query Parameters:**
- `site_id` (optional): Filter by site ID

**Response:**
```json
[
  {
    "line_id": "LINE-001",
    "current_oee": 85.5,
    "current_availability": 92.3,
    "current_performance": 95.1,
    "current_quality": 97.5,
    "shift_production_count": 1250,
    "shift_target_count": 1500,
    "active_downtime_events": 2,
    "last_update": "2025-10-03T12:30:00Z"
  }
]
```

**Also available at:** `/api/dashboard/summary/`

---

### GET `/api/trend/`
**Get historical trend data for metrics**

**Query Parameters:**
- `line_id` (required): Production line ID
- `metric` (required): One of `oee`, `availability`, `performance`, `quality`
- `hours` (optional, default=24): Time range in hours

**Response:**
```json
{
  "line_id": "LINE-001",
  "metric_name": "oee",
  "data_points": [
    {
      "timestamp": "2025-10-03T10:00:00Z",
      "value": 85.5
    },
    {
      "timestamp": "2025-10-03T11:00:00Z",
      "value": 87.2
    }
  ],
  "unit": "%",
  "aggregation": "raw"
}
```

**Also available at:** `/api/dashboard/trend/`

---

### GET `/api/machines/status/`
**Get current status overview of all machines**

**Query Parameters:**
- `site_id` (optional): Filter by site ID
- `line_id` (optional): Filter by production line ID

**Response:**
```json
{
  "count": 5,
  "machines": [
    {
      "machine_id": "LINE-001",
      "status": "running",
      "oee": 85.5,
      "availability": 92.3,
      "performance": 95.1,
      "quality": 97.5,
      "current_production": 1250,
      "target_production": 1500,
      "active_faults": 0,
      "last_update": "2025-10-03T12:30:00Z"
    }
  ]
}
```

**Status Values:**
- `running`: OEE >= 85%
- `degraded`: OEE >= 60% and < 85%
- `stopped`: OEE < 60%
- `fault`: Active downtime events present

---

## Fault/Downtime Endpoints

### GET `/api/downtime/active/`
**Get currently active downtime events**

Returns all downtime events from the last hour.

**Response:**
```json
[
  {
    "id": 123,
    "line_id": "LINE-001",
    "station_id": "STATION-05",
    "severity": "high",
    "ts": "2025-10-03T12:15:00Z",
    "detail": "Machine jam detected"
  }
]
```

**Alias:** Can be accessed as `/api/faults/active/` via routing

---

### GET `/api/downtime/`
**Get downtime event history with filtering**

**Query Parameters:**
- `line_id` (optional): Filter by production line
- `station_id` (optional): Filter by station
- `severity` (optional): Filter by severity
- `from_time` (optional): Start time (ISO 8601 format)
- `to_time` (optional): End time (ISO 8601 format)
- `page` (optional): Page number
- `page_size` (optional, default=50): Results per page

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/downtime/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "line_id": "LINE-001",
      "station_id": "STATION-05",
      "severity": "high",
      "ts": "2025-10-03T12:15:00Z",
      "detail": "Machine jam detected"
    }
  ]
}
```

**Alias:** Can be accessed as `/api/faults/history/` via routing

---

### POST `/api/downtime/{id}/acknowledge/`
**Acknowledge a downtime event**

**Request Body:**
```json
{
  "acknowledged_by": "operator_123",
  "notes": "Cleared jam and restarted machine"
}
```

**Response:**
```json
{
  "status": "acknowledged",
  "event_id": 123,
  "acknowledged_by": "operator_123"
}
```

---

## Asset Management Endpoints

### GET `/api/machines/`
**List all machines** (requires SQL Server models)

### GET `/api/lines/`
**List all production lines** (requires SQL Server models)

### GET `/api/sites/`
**List all sites** (requires SQL Server models)

### GET `/api/areas/`
**List all areas** (requires SQL Server models)

---

## Sparkplug B Endpoints

### GET `/api/sparkplug/nodes/`
**List all Sparkplug B nodes**

### GET `/api/sparkplug/devices/`
**List all Sparkplug B devices**

### GET `/api/sparkplug/metrics/`
**List Sparkplug B metrics**

---

## ML Endpoints

### GET `/api/ml/models/`
**List ML model registry**

### GET `/api/ml/predictions/`
**List ML predictions/inferences**

---

## GraphQL Endpoint

### POST `/api/graphql/`
**GraphQL API for flexible queries**

GraphiQL interface available at: `http://localhost:8000/api/graphql/`

---

## Example Usage

### Get Current OEE for All Lines
```bash
curl -H "Authorization: Token your-token-here" \
     http://localhost:8000/api/kpi/current/
```

### Get OEE Trend for Last 12 Hours
```bash
curl -H "Authorization: Token your-token-here" \
     "http://localhost:8000/api/trend/?line_id=LINE-001&metric=oee&hours=12"
```

### Get Machine Status
```bash
curl -H "Authorization: Token your-token-here" \
     http://localhost:8000/api/machines/status/
```

### Get Active Faults
```bash
curl -H "Authorization: Token your-token-here" \
     http://localhost:8000/api/downtime/active/
```

### Get Fault History for a Line
```bash
curl -H "Authorization: Token your-token-here" \
     "http://localhost:8000/api/downtime/?line_id=LINE-001&from_time=2025-10-01T00:00:00Z"
```

---

## Notes

- All timestamps are in ISO 8601 format (UTC)
- Pagination is available on list endpoints (50 items per page by default)
- Filtering is available via query parameters
- Most endpoints support both JSON and browsable API formats
- Token authentication is required for write operations
- ReadOnly endpoints allow unauthenticated access for GET requests
