# Sparkplug B MQTT Integration for OEE Dashboard

A production-ready Sparkplug B MQTT integration layer that connects industrial PLCs to the OEE Dashboard for real-time manufacturing analytics and Overall Equipment Effectiveness (OEE) calculations.

## Features

### 🏭 Comprehensive PLC Support
- **Siemens PLCs**: S7-300, S7-400, S7-1200, S7-1500, LOGO!, ET200SP
- **Allen-Bradley PLCs**: ControlLogix, CompactLogix, MicroLogix, PLC-5, SLC-500, Micro800
- **Protocol Support**: S7 communication, EtherNet/IP, CIP protocol
- **Auto-discovery**: Automatic tag discovery and configuration
- **Connection pooling**: Optimized connection management with retry logic

### 🚀 Sparkplug B Protocol
- **Complete Implementation**: NBIRTH/NDEATH/DBIRTH/DDEATH/NDATA/DDATA/NCMD/DCMD
- **Sequence Management**: Proper sequence number tracking and validation
- **Birth Certificates**: Full birth/death certificate flow management
- **Quality Tracking**: Message quality scoring and validation
- **Command Support**: Optional command write-back with security controls

### 📊 Real-time OEE Processing
- **Live Data Ingestion**: Real-time telemetry processing to SQL Server
- **Production Cycles**: Automatic cycle detection and timing
- **Quality Events**: Real-time quality tracking and defect recording
- **Downtime Events**: Automated downtime detection and categorization
- **Performance Metrics**: Availability, Performance, Quality calculations

### 🛡️ Production-Grade Features
- **Resilience**: Store-and-forward, automatic reconnection, circuit breakers
- **Security**: mTLS/TLS support, RBAC, audit trails, command validation
- **Monitoring**: Prometheus metrics, health checks, structured logging
- **Scalability**: Support for 100+ simultaneous PLC connections
- **Configuration**: Hot-reload, environment-based config, validation

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for development)
- SQL Server (included in Docker setup)
- MQTT Broker (Eclipse Mosquitto included)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd oee_dashboard

# Copy environment template
cd docker/compose
cp .env.example .env

# Edit configuration
nano .env
```

### 2. Deploy with Docker
```bash
# Deploy complete system
./deploy.sh

# Check status
./deploy.sh status

# View logs
./deploy.sh logs sparkplug-agent
```

### 3. Access Interfaces
- **OEE Dashboard**: http://localhost
- **Grafana Monitoring**: http://localhost/grafana (admin/admin123)
- **Prometheus Metrics**: http://localhost:9090
- **Health Checks**: http://localhost:8002/health

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Siemens PLCs  │    │Allen-Bradley PLCs│   │   Other PLCs    │
│   S7-1500       │    │   ControlLogix   │    │                │
│   S7-1200       │    │   CompactLogix   │    │                │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │     Sparkplug B Agent       │
                    │   ┌─────────────────────┐   │
                    │   │  PLC Connectors     │   │
                    │   │  - S7 Protocol      │   │
                    │   │  - EtherNet/IP      │   │
                    │   │  - Tag Discovery    │   │
                    │   └─────────────────────┘   │
                    │   ┌─────────────────────┐   │
                    │   │  Sparkplug B MQTT   │   │
                    │   │  - Protocol Engine  │   │
                    │   │  - Birth/Death      │   │
                    │   │  - Sequence Mgmt    │   │
                    │   └─────────────────────┘   │
                    │   ┌─────────────────────┐   │
                    │   │  Data Processor     │   │
                    │   │  - OEE Mapping      │   │
                    │   │  - Cycle Detection  │   │
                    │   │  - Quality Scoring  │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                      ┌───────────▼───────────┐
                      │    MQTT Broker        │
                      │  (Eclipse Mosquitto)  │
                      └───────────┬───────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │      SQL Server Database    │
                    │   ┌─────────────────────┐   │
                    │   │  Raw Events         │   │
                    │   │  Metric History     │   │
                    │   │  Production Cycles  │   │
                    │   │  Quality Events     │   │
                    │   │  Downtime Events    │   │
                    │   │  OEE Rollups        │   │
                    │   └─────────────────────┘   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │     OEE Dashboard           │
                    │  - Real-time Dashboards     │
                    │  - Production Analytics     │
                    │  - Performance Monitoring   │
                    │  - Alert Management         │
                    └─────────────────────────────┘
```

## Configuration

### PLC Configuration
```yaml
plc_connections:
  - id: "production_line_1"
    type: "SIEMENS_S7"
    host: "192.168.1.100"
    port: 102
    rack: 0
    slot: 1
    timeout: 10.0
    enabled: true
    
    tags:
      - name: "cycle_start"
        address: "DB1,0.0"
        data_type: "BOOL"
        oee_metric_type: "CYCLE_START"
```

### Metric Mapping
```yaml
metric_mappings:
  - machine_id: "MACHINE_001"
    sparkplug_metric_name: "cycle_start"
    oee_metric_type: "CYCLE_START"
    quality_threshold: 192
```

### MQTT Configuration
```yaml
mqtt:
  broker_host: "mqtt-broker"
  broker_port: 1883
  use_tls: true
  ca_cert_path: "/app/certs/ca.crt"
  qos: 1
  keep_alive: 60
```

## Management Commands

### Run Sparkplug Agent
```bash
# Basic usage
python manage.py sparkplug_agent

# With configuration file
python manage.py sparkplug_agent --config-file config.yaml

# Development mode
python manage.py sparkplug_agent --log-level DEBUG --dry-run

# Production mode
python manage.py sparkplug_agent \
  --config-file /app/config/production.yaml \
  --log-level INFO \
  --broker-host mqtt.company.com \
  --group-id Production_Line_A
```

### Available Options
- `--config-file`: Path to YAML configuration file
- `--log-level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `--dry-run`: Run without database writes (testing)
- `--broker-host`: MQTT broker hostname
- `--broker-port`: MQTT broker port
- `--group-id`: Sparkplug group ID
- `--node-id`: Sparkplug node ID
- `--metrics-port`: Prometheus metrics port
- `--disable-plc`: Disable PLC connections
- `--disable-processing`: Disable data processing

## Testing and Simulation

### PLC Simulators
```python
from oee_analytics.sparkplug.testing import SiemensS7Simulator, AllenBradleySimulator

# Create simulators
s7_sim = SiemensS7Simulator(host="localhost", port=10102)
ab_sim = AllenBradleySimulator(host="localhost", port=10818)

# Start simulation
await s7_sim.start()
await ab_sim.start()
```

### Load Testing
```python
from oee_analytics.sparkplug.testing import SparkplugLoadTester, LoadTestConfig

# Configure load test
config = LoadTestConfig(
    broker_host="localhost",
    num_nodes=50,
    num_devices_per_node=10,
    test_duration=300.0,
    data_interval=1.0
)

# Run load test
tester = SparkplugLoadTester(config)
results = await tester.run_load_test()

print(f"Success rate: {results.success_rate:.1f}%")
print(f"Average latency: {results.avg_latency_ms:.1f} ms")
print(f"Throughput: {results.avg_throughput_msg_sec:.1f} msg/sec")
```

## Monitoring and Observability

### Prometheus Metrics
- `sparkplug_messages_received_total`: Total messages received
- `sparkplug_message_processing_seconds`: Message processing time
- `sparkplug_active_nodes`: Number of active nodes
- `sparkplug_sequence_errors_total`: Sequence number errors
- `sparkplug_mqtt_connected`: MQTT connection status
- `sparkplug_oee_cycles_created_total`: Production cycles created

### Health Checks
```bash
# Check overall health
curl http://localhost:8002/health

# Check readiness
curl http://localhost:8002/ready

# Check metrics
curl http://localhost:8001/metrics
```

### Logging
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "sparkplug.mqtt_client",
  "message": "Message processed",
  "group_id": "Production",
  "node_id": "Line_01",
  "message_type": "NDATA",
  "processing_time_ms": 15.2,
  "sequence_number": 123
}
```

## Performance Targets

- **P99 Ingestion Lag**: ≤60 seconds
- **P95 End-to-End Latency**: <3 seconds
- **Message Throughput**: 1000+ messages/second
- **PLC Connections**: 100+ simultaneous connections
- **Data Retention**: 90+ days of raw data
- **Uptime**: 99.9% availability target

## Security Features

### Authentication & Authorization
- mTLS client certificates for MQTT
- RBAC with sparkplug_ingest and sparkplug_command roles
- ACLs for command write-back
- API key authentication for REST endpoints

### Data Protection
- TLS encryption for all communications
- Certificate pinning and validation
- Audit trails for all write operations
- Payload validation and sanitization

### Network Security
- Network segmentation support
- Firewall-friendly communication patterns
- VPN/site-to-site connectivity
- DMZ deployment options

## Troubleshooting

### Common Issues

#### MQTT Connection Failures
```bash
# Check broker connectivity
curl -v telnet://mqtt-broker:1883

# Check certificates
openssl verify -CAfile ca.crt client.crt

# View MQTT logs
docker logs oee-sparkplug_mqtt-broker_1
```

#### PLC Communication Issues
```bash
# Test PLC connectivity
telnet 192.168.1.100 102

# Check firewall rules
sudo ufw status

# View PLC connector logs
docker logs oee-sparkplug_sparkplug-agent_1 | grep PLC
```

#### Database Performance
```bash
# Check SQL Server performance
docker exec -it oee-sparkplug_sqlserver_1 /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P password \
  -Q "SELECT * FROM sys.dm_exec_requests WHERE status = 'running'"

# Monitor query performance
curl http://localhost:8001/metrics | grep database_query
```

#### Sequence Number Errors
```bash
# Check for gaps in sequence numbers
curl http://localhost:8001/metrics | grep sequence_errors

# View detailed sequence tracking
docker logs oee-sparkplug_sparkplug-agent_1 | grep "Sequence"
```

### Performance Tuning

#### MQTT Optimization
```yaml
mqtt:
  keep_alive: 30          # Reduce for faster detection
  qos: 1                  # Use QoS 1 for reliability
  max_queue_size: 50000   # Increase for high throughput
  batch_size: 500         # Increase for efficiency
```

#### Database Optimization
```yaml
processing:
  batch_size: 1000        # Increase for better throughput
  processing_interval: 0.5 # Reduce for lower latency
  quality_threshold: 75   # Adjust based on requirements
```

#### PLC Connection Tuning
```yaml
plc_connections:
  - timeout: 5.0          # Reduce for faster detection
    scan_rate_ms: 500     # Adjust based on requirements
    max_connections: 20   # Pool size per PLC
```

## Development Setup

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver

# Run Sparkplug agent in debug mode
python manage.py sparkplug_agent --log-level DEBUG --dry-run
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test suite
python -m pytest tests/test_sparkplug/

# Run with coverage
python -m pytest tests/ --cov=oee_analytics.sparkplug
```

### Code Quality
```bash
# Format code
black oee_analytics/

# Lint code
flake8 oee_analytics/

# Type checking
mypy oee_analytics/
```

## Deployment Strategies

### Single Server Deployment
- All services on one server
- Suitable for small to medium installations
- Use Docker Compose for orchestration

### Multi-Server Deployment
- Separate database server
- Dedicated MQTT broker
- Load-balanced application servers
- Use Kubernetes or Docker Swarm

### Edge Deployment
- Local data collection and processing
- Store-and-forward to central system
- Reduced network dependencies
- Edge computing optimization

### Cloud Deployment
- Container orchestration (Kubernetes/EKS/AKS)
- Managed databases and message queues
- Auto-scaling and load balancing
- High availability and disaster recovery

## File Structure

```
oee_analytics/sparkplug/
├── __init__.py
├── models.py                    # Django models for Sparkplug data
├── mqtt_client.py              # MQTT client and protocol handler
├── data_processor.py           # Data processing and OEE mapping
├── config.py                   # Configuration management
├── monitoring.py               # Health checks and metrics
├── connectors/
│   ├── __init__.py
│   ├── base.py                 # Base PLC connector class
│   ├── siemens.py              # Siemens S7 connector
│   └── allen_bradley.py        # Allen-Bradley connector
├── testing/
│   ├── __init__.py
│   ├── plc_simulators.py       # PLC simulators
│   ├── load_testing.py         # Load testing utilities
│   └── validators.py           # Protocol validators
└── management/
    └── commands/
        └── sparkplug_agent.py  # Django management command

docker/
├── production/
│   ├── sparkplug_config.yaml   # Production configuration
│   └── entrypoint.sh           # Production entrypoint
├── development/
│   └── sparkplug_config.yaml   # Development configuration
└── compose/
    ├── docker-compose.sparkplug.yml  # Complete deployment
    ├── .env.example            # Environment template
    └── deploy.sh               # Deployment script
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting guide above
- Review the logs for error details
- Contact the development team

---

**Built with ❤️ for the manufacturing industry**