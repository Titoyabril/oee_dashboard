# Production MQTT Cluster with mTLS

This directory contains the production-ready MQTT broker cluster configuration for the OEE Analytics system using EMQX with mutual TLS authentication.

## Architecture

- **3-Node EMQX Cluster**: High-availability MQTT broker cluster with automatic failover
- **HAProxy Load Balancer**: Distributes MQTT connections across cluster nodes
- **Mutual TLS (mTLS)**: Certificate-based authentication for all edge devices
- **Role-Based Access Control (RBAC)**: Fine-grained permissions per client role
- **Prometheus + Grafana**: Comprehensive monitoring and alerting
- **Persistent Storage**: Message retention and session persistence

## Quick Start

### 1. Generate Certificates

```bash
cd certs
chmod +x generate_certs.sh
./generate_certs.sh
```

This creates:
- **CA certificate** (`ca.crt`, `ca.key`)
- **Server certificate** (`server.crt`, `server.key`, `server.pem`)
- **Sample client certificates** (`client_*.crt`, `client_*.key`)

### 2. Start the Cluster

```bash
docker-compose -f docker-compose.mqtt-cluster.yml up -d
```

### 3. Verify Cluster Status

Check EMQX dashboard (node 1): http://localhost:18083
- Default credentials: `admin` / `public`
- Navigate to **Cluster** → **Nodes** to verify all 3 nodes are joined

Check HAProxy stats: http://localhost:8404/stats
- Credentials: `admin` / `admin`
- Verify all backend servers are green (UP)

Check Prometheus: http://localhost:9090
Check Grafana: http://localhost:3000 (admin/admin)

## Client Connection

### Python Client Example (with mTLS)

```python
import paho.mqtt.client as mqtt
import ssl

# Configure TLS
client = mqtt.Client("edge_SITE01-LINE01")
client.tls_set(
    ca_certs="certs/ca.crt",
    certfile="certs/client_edge_SITE01-LINE01.crt",
    keyfile="certs/client_edge_SITE01-LINE01.key",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

# Connect to load balancer
client.connect("localhost", 8883, 60)

# Publish Sparkplug message
client.publish("spBv1.0/GROUP01/NBIRTH/edge_SITE01-LINE01", payload, qos=1)
```

### Connection Endpoints

- **Production (mTLS)**: `mqtt.oee.local:8883` or `localhost:8883`
- **Development (TCP)**: `localhost:1883` (no TLS, for testing only)
- **Load Balancer Stats**: `http://localhost:8404/stats`

## Role-Based Access Control (RBAC)

### Edge Role (`edge_*`)
- **Allowed**: Publish to `spBv1.0/+/{N|D}BIRTH/edge_<node_id>`, `/NDATA/`, `/DDATA/`
- **Denied**: All subscribe operations

Example client ID: `edge_SITE01-LINE01`

### Analytics Role (`analytics_*`)
- **Allowed**: Subscribe to `spBv1.0/#` (all Sparkplug topics)
- **Denied**: All publish operations

Example client ID: `analytics_OEE-PROCESSOR`

### SCADA Host Role (`scada_*`)
- **Allowed**: Subscribe to data topics; Publish commands (`/NCMD/`, `/DCMD/`)
- Example client ID: `scada_PRIMARY-HOST`

### Dashboard Role (`dashboard_*`)
- **Allowed**: Subscribe to data and birth topics (read-only)
- **Denied**: All publish operations

Example client ID: `dashboard_OEE-PRODUCTION`

### Admin Role (`admin_*`)
- **Allowed**: Full pub/sub access for management
- Example client ID: `admin_USERNAME`

## Certificate Management

### Generate New Edge Client Certificate

```bash
cd certs
source generate_certs.sh
generate_client_cert edge_SITE02-LINE03
```

This creates:
- `client_edge_SITE02-LINE03.crt` (public certificate)
- `client_edge_SITE02-LINE03.key` (private key - **KEEP SECRET!**)

### Distribute Certificates to Edge Devices

1. Copy to edge device securely (SCP/Ansible):
   ```bash
   scp certs/ca.crt edge-device:/etc/oee/certs/
   scp certs/client_edge_*.crt edge-device:/etc/oee/certs/
   scp certs/client_edge_*.key edge-device:/etc/oee/certs/
   ```

2. Set permissions on edge device:
   ```bash
   chmod 600 /etc/oee/certs/client_*.key
   chmod 644 /etc/oee/certs/ca.crt /etc/oee/certs/client_*.crt
   ```

### Certificate Rotation

Certificates expire after 1 year. To rotate:

1. Generate new certificates (keep same client ID)
2. Distribute to edge devices
3. Update edge gateway configuration
4. Restart edge gateway services

**Best Practice**: Automate with Ansible playbook (see `../ansible/` directory)

## Cluster Operations

### Scale Up (Add Node 4)

1. Edit `docker-compose.mqtt-cluster.yml`:
   ```yaml
   emqx4:
     image: emqx/emqx:5.4.0
     environment:
       - EMQX_NODE__NAME=emqx@emqx4.local
       - EMQX_CLUSTER__STATIC__SEEDS=emqx@emqx1.local,emqx@emqx2.local,emqx@emqx3.local,emqx@emqx4.local
     # ... rest of config
   ```

2. Update HAProxy backend:
   ```cfg
   server emqx4 emqx4.local:8883 check
   ```

3. Restart cluster:
   ```bash
   docker-compose -f docker-compose.mqtt-cluster.yml up -d
   ```

### Rolling Restart (Zero Downtime)

```bash
# Restart nodes one at a time
docker-compose -f docker-compose.mqtt-cluster.yml restart emqx1
sleep 30  # Wait for cluster sync
docker-compose -f docker-compose.mqtt-cluster.yml restart emqx2
sleep 30
docker-compose -f docker-compose.mqtt-cluster.yml restart emqx3
```

### Backup & Restore

```bash
# Backup EMQX data
docker cp emqx1:/opt/emqx/data ./backup/emqx1_data_$(date +%Y%m%d)

# Restore
docker cp ./backup/emqx1_data_20250101 emqx1:/opt/emqx/data
docker-compose -f docker-compose.mqtt-cluster.yml restart emqx1
```

## Monitoring & Alerting

### Key Metrics (Prometheus)

- `emqx_sessions_count` - Active MQTT sessions
- `emqx_messages_received` - Messages received/sec
- `emqx_messages_sent` - Messages sent/sec
- `emqx_messages_dropped` - Dropped messages (alert on > 0)
- `haproxy_backend_status` - Backend health (alert on DOWN)

### Recommended Alerts

1. **Broker Down**: `emqx_sessions_count == 0`
2. **High Message Drop Rate**: `rate(emqx_messages_dropped[5m]) > 10`
3. **Backend Unhealthy**: `haproxy_backend_status < 1`
4. **High Connection Rate**: `rate(emqx_sessions_count[1m]) > 100`

## Troubleshooting

### Clients Cannot Connect

1. **Check certificates**:
   ```bash
   openssl s_client -connect localhost:8883 \
       -CAfile certs/ca.crt \
       -cert certs/client_edge_TEST.crt \
       -key certs/client_edge_TEST.key
   ```

2. **Check EMQX logs**:
   ```bash
   docker logs emqx1 --tail 100 -f
   ```

3. **Verify ACL rules**:
   - Check client ID matches role prefix (`edge_*`, `analytics_*`, etc.)
   - Review `emqx_config/acl.conf`

### Cluster Split-Brain

If nodes show as separate clusters:

1. Check network connectivity between containers
2. Verify `EMQX_CLUSTER__STATIC__SEEDS` matches on all nodes
3. Restart nodes sequentially

### High Latency

1. Check HAProxy stats for backend response times
2. Review EMQX resource usage (`docker stats`)
3. Scale cluster horizontally (add more nodes)

## Security Hardening

### Production Checklist

- [ ] Disable TCP port 1883 (only use TLS 8883)
- [ ] Change default admin password in EMQX dashboard
- [ ] Restrict HAProxy stats access (change credentials)
- [ ] Enable firewall rules (only allow specific IPs to ports 1883/8883)
- [ ] Set up certificate expiry monitoring
- [ ] Configure log aggregation (ELK/Loki)
- [ ] Enable audit logging in EMQX
- [ ] Implement network segmentation (OT/IT VLANs)

### Network Segmentation

Recommended firewall rules:

```bash
# Allow edge devices (OT VLAN) to MQTT broker
iptables -A INPUT -s 10.10.0.0/16 -p tcp --dport 8883 -j ACCEPT

# Allow analytics services (IT VLAN) to MQTT broker
iptables -A INPUT -s 192.168.1.0/24 -p tcp --dport 8883 -j ACCEPT

# Deny all other access
iptables -A INPUT -p tcp --dport 8883 -j DROP
```

## Performance Tuning

### EMQX Settings

For high-throughput scenarios (>10,000 msg/sec):

```bash
# Increase max connections
EMQX_LISTENERS__SSL__DEFAULT__MAX_CONNECTIONS=50000

# Increase inflight window
EMQX_MQTT__MAX_INFLIGHT=5000

# Enable batch processing
EMQX_MQTT__BATCH_DELIVER=true
```

### HAProxy Settings

For handling 100,000+ concurrent connections:

```cfg
global
    maxconn 100000
    tune.ssl.cachesize 100000
```

## References

- [EMQX Documentation](https://www.emqx.io/docs/en/v5.0/)
- [Sparkplug B Specification](https://sparkplug.eclipse.org/)
- [HAProxy Configuration Manual](http://www.haproxy.org/)
- [Prometheus EMQX Exporter](https://github.com/emqx/emqx-prometheus)
