## OEE Analytics API Documentation

Comprehensive REST and GraphQL API for the OEE Analytics system.

---

## Table of Contents

1. [Authentication](#authentication)
2. [REST API](#rest-api)
3. [GraphQL API](#graphql-api)
4. [Examples](#examples)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)

---

## Authentication

### Token Authentication

All API requests require authentication via token.

#### Get Token

```http
POST /api/auth/token/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response**:
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

#### Use Token

Include token in `Authorization` header:

```http
GET /api/machines/
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

---

## REST API

Base URL: `/api/`

### Configuration Endpoints

#### Plants

```http
GET    /api/plants/              # List all plants
GET    /api/plants/{id}/         # Get specific plant
POST   /api/plants/              # Create plant
PUT    /api/plants/{id}/         # Update plant
DELETE /api/plants/{id}/         # Delete plant
```

#### Sites

```http
GET    /api/sites/               # List all sites
GET    /api/sites/{id}/          # Get specific site
POST   /api/sites/               # Create site
PUT    /api/sites/{id}/          # Update site
DELETE /api/sites/{id}/          # Delete site
```

**Query Parameters**:
- `plant={plant_id}` - Filter by plant

#### Production Lines

```http
GET    /api/lines/               # List all lines
GET    /api/lines/{id}/          # Get specific line
GET    /api/lines/{id}/machines/ # Get machines on line
POST   /api/lines/               # Create line
PUT    /api/lines/{id}/          # Update line
DELETE /api/lines/{id}/          # Delete line
```

**Query Parameters**:
- `area={area_id}` - Filter by area
- `area__site={site_id}` - Filter by site

#### Machines

```http
GET    /api/machines/                    # List all machines
GET    /api/machines/{id}/               # Get specific machine
GET    /api/machines/{id}/current_status/ # Get current status
GET    /api/machines/{id}/metrics/       # Get metrics history
POST   /api/machines/                    # Create machine
PUT    /api/machines/{id}/               # Update machine
DELETE /api/machines/{id}/               # Delete machine
```

**Query Parameters**:
- `line={line_id}` - Filter by line
- `line__area__site={site_id}` - Filter by site
- `machine_type={type}` - Filter by type

**Example Machine Response**:
```json
{
  "machine_id": "SITE01-LINE1-M1",
  "machine_name": "CNC Mill #1",
  "machine_type": "CNC",
  "line": 1,
  "line_name": "Assembly Line 1",
  "site_name": "Plant A",
  "is_active": true,
  "ideal_cycle_time_seconds": 12.5,
  "target_availability": 90.0,
  "target_performance": 85.0,
  "target_quality": 95.0
}
```

---

### Metrics Endpoints

#### OEE Metrics

```http
GET /api/metrics/                # List OEE metrics
GET /api/metrics/{id}/           # Get specific metric
```

**Query Parameters**:
- `line_id={line_id}` - Filter by line
- `shift_start={datetime}` - Filter by shift
- `from_time={datetime}` - Start time
- `to_time={datetime}` - End time
- `page={number}` - Pagination
- `page_size={number}` - Results per page (max 1000)

**Example Response**:
```json
{
  "count": 150,
  "next": "http://api.example.com/api/metrics/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "timestamp": "2025-10-01T14:30:00Z",
      "shift_start": "2025-10-01T06:00:00Z",
      "line_id": "SITE01-LINE1",
      "availability": 92.5,
      "performance": 89.1,
      "quality": 95.8,
      "oee": 85.3,
      "target_count": 3000,
      "actual_count": 2847,
      "good_count": 2730,
      "reject_count": 117,
      "total_downtime_minutes": 45.2,
      "planned_downtime_minutes": 30.0
    }
  ]
}
```

#### Downtime Events

```http
GET  /api/downtime/              # List downtime events
GET  /api/downtime/active/       # Get active events only
GET  /api/downtime/{id}/         # Get specific event
POST /api/downtime/              # Log downtime event
POST /api/downtime/{id}/acknowledge/ # Acknowledge fault
```

**Query Parameters**:
- `line_id={line_id}` - Filter by line
- `station_id={machine_id}` - Filter by machine
- `severity={level}` - Filter by severity
- `from_time={datetime}` - Start time
- `to_time={datetime}` - End time

**Create Downtime Event**:
```http
POST /api/downtime/
Content-Type: application/json

{
  "ts": "2025-10-01T14:35:00Z",
  "line_id": "SITE01-LINE1",
  "station_id": "M1",
  "reason": "Material Jam",
  "duration_s": 300,
  "severity": 2,
  "detail": "Jam at infeed conveyor"
}
```

**Acknowledge Fault**:
```http
POST /api/downtime/123/acknowledge/
Content-Type: application/json

{
  "acknowledged_by": "john.doe",
  "notes": "Cleared jam, restarted line"
}
```

---

### Sparkplug Endpoints

#### Nodes

```http
GET /api/sparkplug/nodes/           # List Sparkplug nodes
GET /api/sparkplug/nodes/{id}/      # Get specific node
GET /api/sparkplug/nodes/{id}/devices/ # Get node's devices
```

**Query Parameters**:
- `group_id={group}` - Filter by group
- `status={status}` - Filter by status (ONLINE, OFFLINE, BIRTH, DEATH)
- `is_active={true|false}` - Filter by active status

#### Devices

```http
GET /api/sparkplug/devices/          # List Sparkplug devices
GET /api/sparkplug/devices/{id}/     # Get specific device
GET /api/sparkplug/devices/{id}/metrics/ # Get device's metrics
```

**Query Parameters**:
- `node={node_id}` - Filter by node
- `device_name={name}` - Filter by device name

#### Metrics

```http
GET /api/sparkplug/metrics/          # List Sparkplug metrics
GET /api/sparkplug/metrics/{id}/     # Get specific metric
```

**Query Parameters**:
- `device={device_id}` - Filter by device
- `name={metric_name}` - Filter by metric name
- `sparkplug_type={type}` - Filter by Sparkplug type

---

### ML Endpoints

#### Models

```http
GET  /api/ml/models/              # List ML models
GET  /api/ml/models/{id}/         # Get specific model
POST /api/ml/models/              # Register new model
PUT  /api/ml/models/{id}/         # Update model
POST /api/ml/models/{id}/activate/ # Activate model
```

**Query Parameters**:
- `model_type={type}` - Filter by type (downtime_prediction, quality_risk, oee_forecast)
- `is_active={true|false}` - Filter by active status

**Example Model**:
```json
{
  "model_name": "downtime_predictor_v2",
  "model_version": "2.1.0",
  "model_path": "/models/downtime_v2.pkl",
  "model_type": "downtime_prediction",
  "performance_metrics": {
    "accuracy": 0.92,
    "precision": 0.89,
    "recall": 0.94,
    "f1_score": 0.91
  },
  "is_active": true,
  "created_at": "2025-10-01T10:00:00Z"
}
```

#### Predictions

```http
GET /api/ml/predictions/         # List predictions
GET /api/ml/predictions/{id}/    # Get specific prediction
```

**Query Parameters**:
- `line_id={line_id}` (required)
- `model_name={name}` - Filter by model
- `prediction_type={type}` - Filter by type
- `from_time={datetime}` - Start time
- `to_time={datetime}` - End time

---

### Dashboard Endpoints

#### Dashboard Summary

```http
GET /api/dashboard/summary/
```

Get current OEE summary for all lines.

**Query Parameters**:
- `site_id={site_id}` - Filter by site

**Response**:
```json
[
  {
    "line_id": "SITE01-LINE1",
    "current_oee": 85.3,
    "current_availability": 92.5,
    "current_performance": 89.1,
    "current_quality": 95.8,
    "shift_production_count": 2847,
    "shift_target_count": 3000,
    "active_downtime_events": 2,
    "last_update": "2025-10-01T14:30:00Z"
  }
]
```

#### Trend Data

```http
GET /api/dashboard/trend/
```

Get time-series trend data for charting.

**Query Parameters** (required):
- `line_id={line_id}` - Line ID
- `metric={metric}` - Metric name (oee, availability, performance, quality)

**Optional Parameters**:
- `hours={hours}` - Hours of history (default: 24)
- `aggregation={level}` - Aggregation level (raw, 1min, 5min, 1hour)

**Response**:
```json
{
  "metric_name": "oee",
  "unit": "%",
  "aggregation": "raw",
  "data_points": [
    {
      "timestamp": "2025-10-01T14:00:00Z",
      "value": 85.3
    },
    {
      "timestamp": "2025-10-01T15:00:00Z",
      "value": 87.1
    }
  ]
}
```

---

## GraphQL API

Endpoint: `/api/graphql/`

GraphQL provides a flexible query language for the OEE system.

### Interactive Explorer

Visit `/api/graphql/` in your browser for GraphiQL interface.

### Example Queries

#### Get Current OEE

```graphql
query {
  oee_current(line_id: "SITE01-LINE1") {
    line_id
    timestamp
    oee
    availability
    performance
    quality
    good_count
    total_count
    downtime_minutes
  }
}
```

#### Get OEE Trend

```graphql
query {
  oee_trend(
    line_id: "SITE01-LINE1",
    from_time: "2025-10-01T00:00:00Z",
    to_time: "2025-10-01T23:59:59Z",
    limit: 100
  ) {
    timestamp
    oee
    availability
    performance
    quality
  }
}
```

#### Get Active Faults

```graphql
query {
  active_faults(line_id: "SITE01-LINE1") {
    machine_id
    fault_code
    severity
    duration_seconds
    start_time
  }
}
```

#### Get Sparkplug Nodes

```graphql
query {
  sparkplug_nodes(group_id: "SITE01", status: "ONLINE") {
    node_id
    group_id
    status
    last_data_timestamp
    devices {
      device_name
      status
    }
  }
}
```

#### Get ML Predictions

```graphql
query {
  ml_predictions(
    line_id: "SITE01-LINE1",
    prediction_type: "downtime_probability"
  ) {
    timestamp
    model_name
    prediction_value
    confidence_score
    explanation_data
  }
}
```

### Example Mutations

#### Activate ML Model

```graphql
mutation {
  update_ml_model(
    model_name: "downtime_predictor_v2",
    is_active: true
  ) {
    success
    model {
      model_name
      is_active
    }
  }
}
```

#### Acknowledge Fault

```graphql
mutation {
  acknowledge_fault(
    event_id: 123,
    acknowledged_by: "john.doe"
  ) {
    success
    event {
      id
      reason
      detail
    }
  }
}
```

---

## Examples

### Python with `requests`

```python
import requests

BASE_URL = "http://localhost:8000/api"

# Get token
response = requests.post(f"{BASE_URL}/auth/token/", json={
    "username": "user",
    "password": "pass"
})
token = response.json()["token"]

headers = {
    "Authorization": f"Token {token}"
}

# Get machines
machines = requests.get(f"{BASE_URL}/machines/", headers=headers)
print(machines.json())

# Get OEE metrics
metrics = requests.get(
    f"{BASE_URL}/metrics/",
    headers=headers,
    params={"line_id": "SITE01-LINE1", "page_size": 100}
)
print(metrics.json())
```

### JavaScript with `fetch`

```javascript
const BASE_URL = "http://localhost:8000/api";

// Get token
const response = await fetch(`${BASE_URL}/auth/token/`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "user",
    password: "pass"
  })
});

const { token } = await response.json();

// Get dashboard summary
const summary = await fetch(`${BASE_URL}/dashboard/summary/`, {
  headers: { "Authorization": `Token ${token}` }
});

const data = await summary.json();
console.log(data);
```

### GraphQL with `fetch`

```javascript
const GRAPHQL_URL = "http://localhost:8000/api/graphql/";

const query = `
  query {
    oee_current(line_id: "SITE01-LINE1") {
      oee
      availability
      performance
      quality
    }
  }
`;

const response = await fetch(GRAPHQL_URL, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Token ${token}`
  },
  body: JSON.stringify({ query })
});

const { data } = await response.json();
console.log(data.oee_current);
```

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "error": "Error message",
  "detail": "Detailed explanation",
  "field_errors": {
    "field_name": ["Error for this field"]
  }
}
```

---

## Rate Limiting

**Limits** (per user):
- 1000 requests per hour for authenticated users
- 100 requests per hour for anonymous users

**Headers**:
- `X-RateLimit-Limit` - Request limit
- `X-RateLimit-Remaining` - Remaining requests
- `X-RateLimit-Reset` - Reset time (Unix timestamp)

**429 Response**:
```json
{
  "error": "Rate limit exceeded",
  "detail": "Try again in 3600 seconds"
}
```

---

## Permissions

### Roles

- **Admin**: Full access (read + write all)
- **Site Manager**: Read all, write site data
- **Engineer**: Read all, write ML models
- **Operator**: Read all, acknowledge faults
- **Viewer**: Read-only access

### Endpoint Permissions

| Endpoint | Read | Write |
|----------|------|-------|
| Configuration (plants, sites, lines, machines) | All authenticated | Admin, Site Manager |
| Metrics | All authenticated | - (read-only) |
| Downtime events | All authenticated | Operator+ |
| Sparkplug | All authenticated | - (read-only) |
| ML models | All authenticated | Engineer, Admin |
| ML predictions | All authenticated | - (read-only) |

---

## Versioning

Current API version: **v1**

Future versions will be available at `/api/v2/`

---

## Support

For API issues or questions, contact: manufacturing-it@company.com
