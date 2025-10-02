# OEE Analytics - Ansible Automation

Production-grade automation for deploying and managing OEE edge gateways across manufacturing sites.

## Overview

This Ansible project automates:
- ✅ Edge gateway deployment to plant floor devices
- ✅ Certificate distribution and rotation (1-year lifecycle)
- ✅ MQTT user and ACL management
- ✅ OPC-UA client configuration
- ✅ System monitoring and health checks

## Project Structure

```
ansible/
├── ansible.cfg                    # Ansible configuration
├── inventory/
│   ├── production.yml             # Production sites inventory
│   └── staging.yml                # Staging/lab inventory
├── playbooks/
│   ├── deploy_edge_gateway.yml    # Deploy edge gateway
│   ├── rotate_certificates.yml    # Certificate rotation
│   └── manage_mqtt_users.yml      # MQTT user management
├── roles/
│   ├── common/                    # Base system configuration
│   ├── python/                    # Python environment setup
│   ├── certificates/              # Certificate distribution
│   ├── edge_gateway/              # Edge gateway application
│   ├── opcua_client/              # OPC-UA configuration
│   └── monitoring/                # Prometheus exporter
└── README.md                      # This file
```

## Prerequisites

### On Ansible Controller (your laptop/jumphost)

1. **Install Ansible**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ansible python3-pip

# macOS
brew install ansible

# Verify
ansible --version  # Should be >= 2.14
```

2. **Install Required Collections**:
```bash
ansible-galaxy collection install community.general
ansible-galaxy collection install ansible.posix
```

3. **SSH Key Setup**:
```bash
# Generate SSH key for OEE deployments
ssh-keygen -t ed25519 -f ~/.ssh/oee_deploy_key -C "oee-deployment"

# Copy public key to edge gateways (repeat for each)
ssh-copy-id -i ~/.ssh/oee_deploy_key oeeadmin@10.10.1.10
```

### On Edge Gateway Hosts

1. **Operating System**: Ubuntu 20.04+ or RHEL 8+
2. **User**: `oeeadmin` with sudo privileges
3. **Network Access**: SSH port 22, MQTT broker reachable
4. **Minimum Resources**: 2 CPU, 4 GB RAM, 20 GB disk

## Quick Start

### 1. Update Inventory

Edit `inventory/production.yml` with your sites:

```yaml
edge-site01-line01:
  ansible_host: 10.10.1.10
  edge_node_id: edge_SITE01-LINE01
  site_id: SITE01
  line_id: LINE01
  opcua_servers:
    - endpoint: opc.tcp://192.168.10.10:4840
      description: Line 1 PLC
      vendor: Rockwell
```

### 2. Generate Certificates

```bash
cd ../docker/compose/certs
./generate_certs.sh

# Generate certificates for each edge gateway
source generate_certs.sh
generate_client_cert edge_SITE01-LINE01
generate_client_cert edge_SITE01-LINE02
```

### 3. Test Connectivity

```bash
cd ansible
ansible edge_gateways -m ping
```

Expected output:
```
edge-site01-line01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### 4. Deploy Edge Gateway

```bash
# Deploy to staging first
ansible-playbook -i inventory/staging.yml playbooks/deploy_edge_gateway.yml

# Deploy to production
ansible-playbook -i inventory/production.yml playbooks/deploy_edge_gateway.yml

# Deploy to specific host
ansible-playbook -i inventory/production.yml playbooks/deploy_edge_gateway.yml \
    --limit edge-site01-line01
```

## Usage Examples

### Deploy New Edge Gateway

```bash
# Full deployment (all roles)
ansible-playbook playbooks/deploy_edge_gateway.yml

# Deploy only application code (skip system setup)
ansible-playbook playbooks/deploy_edge_gateway.yml --tags edge_gateway

# Dry run (check what would change)
ansible-playbook playbooks/deploy_edge_gateway.yml --check --diff
```

### Certificate Rotation

Certificates expire after 1 year. Rotate them automatically:

```bash
# Check all gateways and rotate if needed
ansible-playbook playbooks/rotate_certificates.yml

# Force rotation for specific gateway
ansible-playbook playbooks/rotate_certificates.yml \
    --limit edge-site01-line01 \
    --extra-vars "force_rotation=true"

# Dry run
ansible-playbook playbooks/rotate_certificates.yml --check
```

The playbook will:
1. Check certificate expiration (< 30 days remaining)
2. Generate new key pair on edge gateway
3. Sign CSR with CA on controller
4. Deploy new certificate
5. Rolling restart (one at a time)
6. Verify MQTT connection

### MQTT User Management

```bash
# Add new edge gateway user
ansible-playbook playbooks/manage_mqtt_users.yml

# You'll be prompted for:
# Action: add
# Client ID: edge_SITE02-LINE03
# Role: edge
# Password: <secure password>
```

This will:
- Create MQTT user
- Generate client certificate
- Configure ACL permissions
- Display certificate location

```bash
# List existing users
ansible-playbook playbooks/manage_mqtt_users.yml
# Action: list

# Remove user
ansible-playbook playbooks/manage_mqtt_users.yml
# Action: remove
# Client ID: edge_OLD-GATEWAY
```

### Update Application Code

```bash
# Push code changes without reconfiguring system
ansible-playbook playbooks/deploy_edge_gateway.yml --tags edge_gateway

# Restart all edge gateways
ansible edge_gateways -a "systemctl restart oee-edge-gateway"
```

### Check Service Status

```bash
# Check if all gateways are running
ansible edge_gateways -a "systemctl status oee-edge-gateway"

# View logs
ansible edge_gateways -a "journalctl -u oee-edge-gateway -n 50"

# Check health endpoints
ansible edge_gateways -m uri -a "url=http://localhost:9100/health"
```

## Inventory Management

### Production Inventory Structure

```yaml
all:
  vars:
    mqtt_broker_host: mqtt.oee.prod.local
    mqtt_broker_port: 8883
    timescaledb_host: timescaledb.oee.prod.local

  children:
    edge_gateways:
      children:
        site01_gateways:
          hosts:
            edge-site01-line01:
              ansible_host: 10.10.1.10
              edge_node_id: edge_SITE01-LINE01
              opcua_servers:
                - endpoint: opc.tcp://192.168.10.10:4840
                  tags:
                    - node_id: ns=2;s=ProductionCount
                      name: production_count
                      type: counter.total
```

### Environment-Specific Variables

Create `inventory/group_vars/` and `inventory/host_vars/` for site-specific overrides:

```bash
inventory/
├── group_vars/
│   ├── all.yml                   # Global variables
│   ├── site01_gateways.yml       # Site 01 specific
│   └── production.yml            # Production environment
└── host_vars/
    └── edge-site01-line01.yml    # Host-specific config
```

## Roles

### common
Base system configuration for all hosts.

**Tasks**:
- Install system packages
- Create OEE user and directories
- Configure NTP for time sync
- Set system limits and sysctl tunables

### python
Python environment setup.

**Tasks**:
- Install Python 3.11
- Create virtual environment
- Install OEE dependencies (paho-mqtt, asyncua, etc.)

### certificates
Certificate distribution and verification.

**Tasks**:
- Copy CA certificate
- Deploy client certificate and private key
- Set correct permissions (600 for keys)
- Add certificate expiry monitoring cron job

### edge_gateway
Main edge gateway application.

**Tasks**:
- Copy Python source code
- Generate configuration file from template
- Create systemd service
- Configure log rotation
- Start and enable service

### monitoring
Prometheus metrics exporter.

**Tasks**:
- Install node_exporter
- Configure application metrics endpoint
- Create health check endpoint

## Configuration Templates

### Edge Gateway Config (`edge_gateway.yml.j2`)

Generated from inventory variables:

```yaml
mqtt:
  broker_host: {{ mqtt_broker_host }}
  broker_port: {{ mqtt_broker_port }}
  tls:
    ca_cert: /etc/oee/certs/ca.crt
    client_cert: /etc/oee/certs/client.crt

opcua:
  endpoints:
{% for server in opcua_servers %}
    - url: {{ server.endpoint }}
      tags:
{% for tag in server.tags %}
        - node_id: {{ tag.node_id }}
          name: {{ tag.name }}
{% endfor %}
{% endfor %}
```

## Troubleshooting

### Playbook Fails on SSH Connection

```bash
# Test SSH manually
ssh -i ~/.ssh/oee_deploy_key oeeadmin@10.10.1.10

# Check SSH config in ansible.cfg
grep private_key_file ansible.cfg

# Add -vvv for verbose output
ansible-playbook playbooks/deploy_edge_gateway.yml -vvv
```

### Certificate Not Found

```bash
# Check if certificate exists
ls -la ../docker/compose/certs/client_edge_SITE01-LINE01.*

# Generate if missing
cd ../docker/compose/certs
source generate_certs.sh
generate_client_cert edge_SITE01-LINE01
```

### Service Won't Start

```bash
# Check service status
ansible edge-site01-line01 -a "systemctl status oee-edge-gateway"

# View logs
ansible edge-site01-line01 -a "journalctl -u oee-edge-gateway -n 100"

# Check configuration
ansible edge-site01-line01 -a "cat /etc/oee/edge_gateway.yml"

# Test Python execution manually
ansible edge-site01-line01 -a \
    "su - oee -c 'cd /opt/oee/edge && source venv/bin/activate && python --version'"
```

### MQTT Connection Fails

```bash
# Test MQTT connection with mosquitto_pub
ansible edge-site01-line01 -a \
    "mosquitto_pub \
        --cafile /etc/oee/certs/ca.crt \
        --cert /etc/oee/certs/client.crt \
        --key /etc/oee/certs/client.key \
        -h mqtt.oee.prod.local \
        -p 8883 \
        -t test \
        -m 'test'"

# Check MQTT broker logs
ssh mqtt-broker-01 "docker logs emqx1 --tail 100"
```

## Best Practices

### 1. Use Staging Environment First

Always test in staging before production:

```bash
# Test in staging
ansible-playbook -i inventory/staging.yml playbooks/deploy_edge_gateway.yml

# If successful, deploy to production
ansible-playbook -i inventory/production.yml playbooks/deploy_edge_gateway.yml
```

### 2. Serial Deployment for Production

Deploy to one site at a time to minimize risk:

```bash
ansible-playbook playbooks/deploy_edge_gateway.yml --limit site01_gateways
ansible-playbook playbooks/deploy_edge_gateway.yml --limit site02_gateways
```

### 3. Use Tags for Partial Updates

```bash
# Update only application code
ansible-playbook playbooks/deploy_edge_gateway.yml --tags edge_gateway

# Update only certificates
ansible-playbook playbooks/deploy_edge_gateway.yml --tags certificates

# Skip monitoring setup
ansible-playbook playbooks/deploy_edge_gateway.yml --skip-tags monitoring
```

### 4. Backup Before Changes

```bash
# Create backup playbook
ansible-playbook playbooks/backup_edge_gateway.yml

# Or manually
ansible edge_gateways -a "tar -czf /tmp/oee-backup-$(date +%Y%m%d).tar.gz /etc/oee /opt/oee"
```

### 5. Version Control for Inventory

```bash
# Commit inventory changes
git add inventory/production.yml
git commit -m "Add SITE02-LINE03 edge gateway"
git push
```

## Security Considerations

### SSH Keys
- Use dedicated SSH key for OEE deployments
- Rotate SSH keys annually
- Limit key access (chmod 600)

### Certificate Management
- Client certificates expire after 1 year
- Monitor expiration with cron job
- Use automated rotation playbook

### Secrets
- **Never commit passwords to Git**
- Use Ansible Vault for sensitive data:

```bash
# Create encrypted variables file
ansible-vault create inventory/group_vars/production/vault.yml

# Add sensitive data
---
mqtt_broker_password: SecurePassword123!
timescaledb_password: AnotherSecurePassword!

# Edit vault
ansible-vault edit inventory/group_vars/production/vault.yml

# Use in playbook
ansible-playbook playbooks/deploy_edge_gateway.yml --ask-vault-pass
```

### Least Privilege
- `oeeadmin` user has sudo only for required commands
- `oee` service user runs with minimal permissions
- Systemd service uses security hardening (NoNewPrivileges, PrivateTmp)

## Monitoring

### Health Checks

```bash
# Check all gateways
ansible edge_gateways -m uri -a "url=http://localhost:9100/health return_content=yes"

# Expected response
{
    "status": "healthy",
    "mqtt_connected": true,
    "opcua_connected": true,
    "uptime_seconds": 12345
}
```

### Prometheus Metrics

```bash
# Scrape metrics from gateway
curl http://10.10.1.10:9100/metrics

# Key metrics:
# sparkplug_messages_received_total
# sparkplug_mqtt_connected
# opcua_session_up
# edge_cache_queue_size
```

### Logs

```bash
# Centralized log collection
ansible edge_gateways -a "journalctl -u oee-edge-gateway --since '1 hour ago' -o json" \
    | jq -r .MESSAGE
```

## References

- [Ansible Documentation](https://docs.ansible.com/)
- [OEE Analytics Architecture](../IMPLEMENTATION_SUMMARY.md)
- [MQTT Cluster Setup](../docker/compose/README_MQTT_CLUSTER.md)
- [Certificate Generation](../docker/compose/certs/generate_certs.sh)

## Support

For issues or questions:
1. Check playbook logs: `ansible/logs/ansible.log`
2. Review service logs: `journalctl -u oee-edge-gateway`
3. Open GitHub issue with `[ansible]` tag

---

**Last Updated**: 2025-10-01
**Maintained By**: Manufacturing IT Team
