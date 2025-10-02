# Ansible Quick Start Guide

**5-Minute Setup** | Deploy your first OEE Edge Gateway

---

## Prerequisites

- [ ] Ansible 2.14+ installed
- [ ] SSH access to edge gateway hosts
- [ ] MQTT broker and TimescaleDB running
- [ ] Certificates generated (see below)

---

## Step 1: Install Ansible (if needed)

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ansible -y

# macOS
brew install ansible

# Verify
ansible --version  # Should be >= 2.14
```

---

## Step 2: Install Required Collections

```bash
cd ansible
ansible-galaxy collection install community.general ansible.posix
```

---

## Step 3: Setup SSH Access

```bash
# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/oee_deploy_key -C "oee-deployment"

# Copy to edge gateway (repeat for each host)
ssh-copy-id -i ~/.ssh/oee_deploy_key oeeadmin@10.10.1.10

# Test connection
ssh -i ~/.ssh/oee_deploy_key oeeadmin@10.10.1.10
```

---

## Step 4: Generate Certificates

```bash
# Navigate to cert directory
cd ../docker/compose/certs

# Generate CA and certificates
./generate_certs.sh

# Generate client cert for each edge gateway
source generate_certs.sh
generate_client_cert edge_SITE01-LINE01
generate_client_cert edge_SITE01-LINE02
```

**Verify certificates created**:
```bash
ls -la
# Should see:
# - ca.crt, ca.key (Certificate Authority)
# - client_edge_SITE01-LINE01.crt, client_edge_SITE01-LINE01.key
```

---

## Step 5: Update Inventory

Edit `ansible/inventory/production.yml`:

```yaml
edge-site01-line01:
  ansible_host: 10.10.1.10  # Your edge gateway IP
  edge_node_id: edge_SITE01-LINE01
  site_id: SITE01
  line_id: LINE01
  opcua_servers:
    - endpoint: opc.tcp://192.168.10.10:4840  # Your PLC OPC-UA endpoint
      description: Line 1 PLC
      vendor: Rockwell
      tags:
        - node_id: ns=2;s=ProductionCount
          name: production_count
          type: counter.total
```

**Update MQTT/DB hosts**:
```yaml
all:
  vars:
    mqtt_broker_host: mqtt.production.local  # Your MQTT broker
    timescaledb_host: timescaledb.local      # Your TimescaleDB
```

---

## Step 6: Test Connectivity

```bash
cd ansible

# Ping all edge gateways
ansible edge_gateways -m ping

# Expected output:
# edge-site01-line01 | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```

**If ping fails**:
- Check SSH key: `ssh -i ~/.ssh/oee_deploy_key oeeadmin@10.10.1.10`
- Verify IP address in inventory
- Check firewall rules: `telnet 10.10.1.10 22`

---

## Step 7: Deploy Edge Gateway

### Test in Staging First

```bash
# Deploy to staging
ansible-playbook -i inventory/staging.yml playbooks/deploy_edge_gateway.yml --check

# If check passes, deploy for real
ansible-playbook -i inventory/staging.yml playbooks/deploy_edge_gateway.yml
```

### Deploy to Production

```bash
# Deploy to all production gateways
ansible-playbook playbooks/deploy_edge_gateway.yml

# Or deploy to specific gateway
ansible-playbook playbooks/deploy_edge_gateway.yml --limit edge-site01-line01

# Or deploy to specific site
ansible-playbook playbooks/deploy_edge_gateway.yml --limit site01_gateways
```

**Deployment will**:
1. Install Python 3.11 and dependencies
2. Create OEE user and directories
3. Deploy certificates
4. Copy application code
5. Create systemd service
6. Start edge gateway

**Expected output**:
```
PLAY RECAP
edge-site01-line01    : ok=42   changed=18   unreachable=0    failed=0    skipped=2
```

---

## Step 8: Verify Deployment

```bash
# Check service status
ansible edge_gateways -a "systemctl status oee-edge-gateway"

# Check logs
ansible edge_gateways -a "journalctl -u oee-edge-gateway -n 50"

# Check health endpoint
ansible edge_gateways -m uri -a "url=http://localhost:9100/health"
```

**Healthy response**:
```json
{
    "status": "healthy",
    "mqtt_connected": true,
    "opcua_connected": true,
    "uptime_seconds": 123
}
```

---

## Common Tasks

### View Logs

```bash
ansible edge_gateways -a "journalctl -u oee-edge-gateway -f"
```

### Restart Service

```bash
ansible edge_gateways -a "systemctl restart oee-edge-gateway"
```

### Update Application Code

```bash
# Push code changes
ansible-playbook playbooks/deploy_edge_gateway.yml --tags edge_gateway

# Restart services
ansible edge_gateways -a "systemctl restart oee-edge-gateway"
```

### Check Health

```bash
ansible-playbook playbooks/health_check.yml
# Generates HTML report in ansible/reports/
```

### Backup Configuration

```bash
ansible-playbook playbooks/backup_restore.yml
# Saves backup to ansible/backups/
```

### Rotate Certificates

```bash
# Check which certs need rotation
ansible-playbook playbooks/rotate_certificates.yml --check

# Rotate expiring certificates
ansible-playbook playbooks/rotate_certificates.yml
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service logs
ansible edge-site01-line01 -a "journalctl -u oee-edge-gateway -n 100 --no-pager"

# Check configuration
ansible edge-site01-line01 -a "cat /etc/oee/edge_gateway.yml"

# Verify Python environment
ansible edge-site01-line01 -a "ls -la /opt/oee/edge/venv/bin/python"
```

### MQTT Connection Fails

```bash
# Test MQTT connection manually
ansible edge-site01-line01 -a "mosquitto_pub \
    --cafile /etc/oee/certs/ca.crt \
    --cert /etc/oee/certs/client.crt \
    --key /etc/oee/certs/client.key \
    -h mqtt.production.local \
    -p 8883 \
    -t test \
    -m 'test'"

# Check certificate permissions
ansible edge-site01-line01 -a "ls -la /etc/oee/certs/"
```

### OPC-UA Connection Fails

```bash
# Test OPC-UA connectivity
ansible edge-site01-line01 -a "nc -zv 192.168.10.10 4840"

# Check OPC-UA server is running
# Check firewall rules on PLC
```

### High Memory Usage

```bash
# Check memory usage
ansible edge_gateways -a "free -h"

# Check process memory
ansible edge_gateways -a "ps aux | grep edge_gateway | head -1"

# Restart if needed
ansible edge_gateways -a "systemctl restart oee-edge-gateway"
```

---

## Next Steps

1. ✅ **Deployed**: Edge gateway running
2. ⏭️ **Monitor**: Set up Grafana dashboards
3. ⏭️ **Scale**: Deploy to more sites
4. ⏭️ **Automate**: Schedule certificate rotation
5. ⏭️ **Backup**: Set up automated backups

---

## Useful Commands Cheat Sheet

| Task | Command |
|------|---------|
| **Ping all** | `ansible edge_gateways -m ping` |
| **Status** | `ansible edge_gateways -a "systemctl status oee-edge-gateway"` |
| **Restart** | `ansible edge_gateways -a "systemctl restart oee-edge-gateway"` |
| **Logs** | `ansible edge_gateways -a "journalctl -u oee-edge-gateway -n 50"` |
| **Health** | `ansible-playbook playbooks/health_check.yml` |
| **Deploy** | `ansible-playbook playbooks/deploy_edge_gateway.yml` |
| **Backup** | `ansible-playbook playbooks/backup_restore.yml` |
| **Certificates** | `ansible-playbook playbooks/rotate_certificates.yml` |
| **Update code** | `ansible-playbook playbooks/deploy_edge_gateway.yml --tags edge_gateway` |
| **Single host** | `ansible-playbook playbooks/deploy_edge_gateway.yml --limit edge-site01-line01` |
| **Dry run** | `ansible-playbook playbooks/deploy_edge_gateway.yml --check` |

---

## Getting Help

- **Ansible Docs**: https://docs.ansible.com/
- **Full README**: `ansible/README.md`
- **Architecture**: `../IMPLEMENTATION_SUMMARY.md`
- **Deployment Guide**: `../INFRASTRUCTURE_DEPLOYMENT_GUIDE.md`

---

**Last Updated**: 2025-10-01
**Version**: 1.0.0
