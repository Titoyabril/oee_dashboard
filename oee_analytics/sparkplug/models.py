"""
Sparkplug B MQTT Integration Models
Models for managing Sparkplug B nodes, devices, and telemetry data
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json
from typing import Dict, Any, Optional


class SparkplugNode(models.Model):
    """Sparkplug B Edge Node (EoN) Definition"""
    
    STATUS_CHOICES = [
        ('OFFLINE', 'Offline'),
        ('ONLINE', 'Online'),
        ('BIRTH', 'Birth Received'),
        ('DEATH', 'Death Received'),
        ('STALE', 'Stale Data'),
    ]
    
    node_id = models.CharField(max_length=100, primary_key=True, help_text="Sparkplug Node ID")
    group_id = models.CharField(max_length=100, help_text="Sparkplug Group ID") 
    description = models.TextField(max_length=500, blank=True, null=True)
    
    # Node status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE')
    last_birth_timestamp = models.DateTimeField(blank=True, null=True)
    last_death_timestamp = models.DateTimeField(blank=True, null=True)
    last_data_timestamp = models.DateTimeField(blank=True, null=True)
    
    # Sequence number tracking for message ordering
    birth_sequence_number = models.BigIntegerField(default=0)
    last_sequence_number = models.BigIntegerField(default=0)
    
    # Connection details
    mqtt_broker_host = models.CharField(max_length=255)
    mqtt_broker_port = models.IntegerField(default=1883)
    mqtt_username = models.CharField(max_length=100, blank=True, null=True)
    mqtt_password = models.CharField(max_length=255, blank=True, null=True)
    mqtt_use_tls = models.BooleanField(default=False)
    
    # Quality and reliability metrics
    message_count = models.BigIntegerField(default=0)
    error_count = models.BigIntegerField(default=0)
    last_error_message = models.TextField(blank=True, null=True)
    data_quality_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    # Management
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sp_nodes'
        indexes = [
            models.Index(fields=['group_id', 'status']),
            models.Index(fields=['status', 'last_data_timestamp']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['group_id', 'node_id'], name='unique_group_node'),
        ]
    
    def __str__(self):
        return f"{self.group_id}/{self.node_id}"
    
    @property
    def topic_namespace(self):
        """Get the Sparkplug topic namespace for this node"""
        return f"spBv1.0/{self.group_id}/N{self.node_id}"
    
    def is_online(self) -> bool:
        """Check if node is currently online"""
        return self.status in ['ONLINE', 'BIRTH']
    
    def update_sequence_number(self, seq_num: int) -> bool:
        """Update sequence number with validation"""
        if seq_num == 0:  # Birth certificate resets sequence
            self.last_sequence_number = 0
            return True
        elif seq_num == self.last_sequence_number + 1:
            self.last_sequence_number = seq_num
            return True
        else:
            # Sequence number gap detected
            self.error_count += 1
            self.last_error_message = f"Sequence gap: expected {self.last_sequence_number + 1}, got {seq_num}"
            return False


class SparkplugDevice(models.Model):
    """Sparkplug B Device Definition"""
    
    STATUS_CHOICES = [
        ('OFFLINE', 'Offline'),
        ('ONLINE', 'Online'),
        ('BIRTH', 'Birth Received'),
        ('DEATH', 'Death Received'),
        ('COMMISSIONING', 'Commissioning'),
        ('MAINTENANCE', 'Maintenance'),
    ]
    
    device_id = models.CharField(max_length=100, help_text="Sparkplug Device ID")
    node = models.ForeignKey(SparkplugNode, on_delete=models.CASCADE, related_name='devices')
    description = models.TextField(max_length=500, blank=True, null=True)
    
    # Device type and metadata
    device_type = models.CharField(max_length=50, help_text="PLC, HMI, Sensor, etc.")
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE')
    last_birth_timestamp = models.DateTimeField(blank=True, null=True)
    last_death_timestamp = models.DateTimeField(blank=True, null=True)
    last_data_timestamp = models.DateTimeField(blank=True, null=True)
    
    # Mapping to OEE entities
    machine = models.ForeignKey(
        'oee_analytics.Machine', 
        on_delete=models.SET_NULL, 
        blank=True, null=True,
        help_text="Associated OEE machine"
    )
    
    # Quality metrics
    message_count = models.BigIntegerField(default=0)
    error_count = models.BigIntegerField(default=0)
    data_quality_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    # Management
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sp_devices'
        indexes = [
            models.Index(fields=['node', 'status']),
            models.Index(fields=['device_type']),
            models.Index(fields=['machine']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['node', 'device_id'], name='unique_node_device'),
        ]
    
    def __str__(self):
        return f"{self.node}/{self.device_id}"
    
    @property
    def topic_namespace(self):
        """Get the Sparkplug topic namespace for this device"""
        return f"spBv1.0/{self.node.group_id}/D{self.device_id}"
    
    def is_online(self) -> bool:
        """Check if device is currently online"""
        return self.status in ['ONLINE', 'BIRTH']


class SparkplugMetric(models.Model):
    """Sparkplug B Metric Definition"""
    
    DATA_TYPE_CHOICES = [
        ('Int8', 'Int8'),
        ('Int16', 'Int16'), 
        ('Int32', 'Int32'),
        ('Int64', 'Int64'),
        ('UInt8', 'UInt8'),
        ('UInt16', 'UInt16'),
        ('UInt32', 'UInt32'),
        ('UInt64', 'UInt64'),
        ('Float', 'Float'),
        ('Double', 'Double'),
        ('Boolean', 'Boolean'),
        ('String', 'String'),
        ('DateTime', 'DateTime'),
        ('Text', 'Text'),
        ('UUID', 'UUID'),
        ('DataSet', 'DataSet'),
        ('Bytes', 'Bytes'),
        ('File', 'File'),
        ('Template', 'Template'),
    ]
    
    metric_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, help_text="Metric name from Sparkplug payload")
    alias = models.BigIntegerField(blank=True, null=True, help_text="Sparkplug metric alias")
    
    # Parent relationships
    node = models.ForeignKey(SparkplugNode, on_delete=models.CASCADE, blank=True, null=True)
    device = models.ForeignKey(SparkplugDevice, on_delete=models.CASCADE, blank=True, null=True)
    
    # Metric metadata
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    description = models.TextField(max_length=500, blank=True, null=True)
    units = models.CharField(max_length=50, blank=True, null=True)
    
    # Value constraints
    min_value = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    max_value = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    
    # OEE mapping
    oee_metric_type = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="OEE metric type: CYCLE_TIME, PART_COUNT, QUALITY_FLAG, etc."
    )
    
    # Quality and monitoring
    last_value = models.TextField(blank=True, null=True, help_text="Last received value as JSON")
    last_timestamp = models.DateTimeField(blank=True, null=True)
    last_quality = models.IntegerField(
        default=192,  # GOOD quality in Sparkplug
        validators=[MinValueValidator(0), MaxValueValidator(255)]
    )
    
    # Statistics
    message_count = models.BigIntegerField(default=0)
    error_count = models.BigIntegerField(default=0)
    
    # Management
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sp_metrics'
        indexes = [
            models.Index(fields=['node', 'name']),
            models.Index(fields=['device', 'name']),
            models.Index(fields=['alias']),
            models.Index(fields=['oee_metric_type']),
            models.Index(fields=['last_timestamp']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['node', 'name'], 
                name='unique_node_metric',
                condition=models.Q(device__isnull=True)
            ),
            models.UniqueConstraint(
                fields=['device', 'name'], 
                name='unique_device_metric',
                condition=models.Q(device__isnull=False)
            ),
            models.CheckConstraint(
                check=models.Q(node__isnull=False) | models.Q(device__isnull=False),
                name='metric_has_parent'
            ),
        ]
    
    def __str__(self):
        parent = self.device or self.node
        return f"{parent}/{self.name}"
    
    def get_typed_value(self, raw_value: Any) -> Any:
        """Convert raw value to proper Python type based on data_type"""
        if raw_value is None:
            return None
            
        try:
            if self.data_type in ['Int8', 'Int16', 'Int32', 'Int64']:
                return int(raw_value)
            elif self.data_type in ['UInt8', 'UInt16', 'UInt32', 'UInt64']:
                return int(raw_value)
            elif self.data_type == 'Float':
                return float(raw_value)
            elif self.data_type == 'Double':
                return float(raw_value)
            elif self.data_type == 'Boolean':
                return bool(raw_value)
            elif self.data_type in ['String', 'Text']:
                return str(raw_value)
            elif self.data_type == 'DateTime':
                if isinstance(raw_value, int):
                    return timezone.datetime.fromtimestamp(raw_value / 1000, tz=timezone.utc)
                return raw_value
            else:
                return raw_value
        except (ValueError, TypeError):
            return raw_value


class SparkplugEventRaw(models.Model):
    """Raw Sparkplug B message storage for audit and replay"""
    
    MESSAGE_TYPE_CHOICES = [
        ('NBIRTH', 'Node Birth'),
        ('NDEATH', 'Node Death'),
        ('DBIRTH', 'Device Birth'),
        ('DDEATH', 'Device Death'),
        ('NDATA', 'Node Data'),
        ('DDATA', 'Device Data'),
        ('NCMD', 'Node Command'),
        ('DCMD', 'Device Command'),
        ('STATE', 'State Message'),
    ]
    
    event_id = models.BigAutoField(primary_key=True)
    
    # Message identification
    topic = models.CharField(max_length=500, help_text="Full MQTT topic")
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    group_id = models.CharField(max_length=100)
    node_id = models.CharField(max_length=100, blank=True, null=True)
    device_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Message content
    sequence_number = models.BigIntegerField(default=0)
    timestamp_utc = models.DateTimeField()
    payload_protobuf = models.BinaryField(help_text="Raw protobuf payload")
    payload_json = models.TextField(help_text="Parsed payload as JSON")
    
    # Processing status
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(blank=True, null=True)
    processing_error = models.TextField(blank=True, null=True)
    
    # Quality metrics
    payload_size_bytes = models.IntegerField()
    mqtt_qos = models.SmallIntegerField(default=1)
    mqtt_retain = models.BooleanField(default=False)
    
    # Metadata
    received_at = models.DateTimeField(default=timezone.now)
    broker_host = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        db_table = 'sp_event_raw'
        indexes = [
            models.Index(fields=['group_id', 'node_id', 'timestamp_utc']),
            models.Index(fields=['message_type', 'timestamp_utc']),
            models.Index(fields=['processed', 'received_at']),
            models.Index(fields=['topic']),
            # Partition-like index for efficient cleanup
            models.Index(fields=['received_at']),
        ]
    
    def __str__(self):
        return f"{self.message_type} - {self.topic} - {self.timestamp_utc}"


class SparkplugMetricHistory(models.Model):
    """Time-series storage for Sparkplug metric values"""
    
    history_id = models.BigAutoField(primary_key=True)
    metric = models.ForeignKey(SparkplugMetric, on_delete=models.CASCADE, related_name='history')
    
    # Value and timestamp
    timestamp_utc = models.DateTimeField(db_index=True)
    value_json = models.TextField(help_text="Value stored as JSON for flexibility")
    quality = models.IntegerField(
        default=192,  # GOOD quality in Sparkplug
        validators=[MinValueValidator(0), MaxValueValidator(255)]
    )
    
    # Message context
    sequence_number = models.BigIntegerField()
    event_raw = models.ForeignKey(SparkplugEventRaw, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Data lineage
    source_system = models.CharField(max_length=50, default='SPARKPLUG')
    ingested_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'sp_metric_history'
        indexes = [
            models.Index(fields=['metric', 'timestamp_utc']),  # Primary time-series index
            models.Index(fields=['timestamp_utc']),  # Time-based queries
            models.Index(fields=['quality']),
            models.Index(fields=['sequence_number']),
            # Hot data index (last 24 hours) - approximated
            models.Index(fields=['metric', 'timestamp_utc', 'quality']),
        ]
        # Note: Would use table partitioning in production SQL Server
    
    def __str__(self):
        return f"{self.metric} - {self.timestamp_utc}"
    
    def get_typed_value(self) -> Any:
        """Get the value converted to proper Python type"""
        if not self.value_json:
            return None
        try:
            raw_value = json.loads(self.value_json)
            return self.metric.get_typed_value(raw_value)
        except (json.JSONDecodeError, AttributeError):
            return self.value_json


class SparkplugNodeState(models.Model):
    """Current state tracking for Sparkplug nodes"""
    
    node = models.OneToOneField(SparkplugNode, on_delete=models.CASCADE, primary_key=True)
    
    # Current session tracking
    session_number = models.BigIntegerField(default=0)
    birth_timestamp = models.DateTimeField(blank=True, null=True)
    last_will_timestamp = models.DateTimeField(blank=True, null=True)
    
    # Connection state
    is_online = models.BooleanField(default=False)
    last_seen_timestamp = models.DateTimeField(blank=True, null=True)
    consecutive_timeouts = models.IntegerField(default=0)
    
    # Birth certificate validation
    birth_certificate_valid = models.BooleanField(default=False)
    required_metrics_count = models.IntegerField(default=0)
    received_metrics_count = models.IntegerField(default=0)
    
    # Performance metrics
    messages_per_minute = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    average_latency_ms = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    packet_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    
    # Health scoring
    health_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sp_node_state'
    
    def __str__(self):
        return f"State: {self.node}"
    
    def calculate_health_score(self) -> Decimal:
        """Calculate health score based on various metrics"""
        score = Decimal('100.0')
        
        # Deduct for timeouts
        if self.consecutive_timeouts > 0:
            score -= min(Decimal('30.0'), Decimal(str(self.consecutive_timeouts * 5)))
        
        # Deduct for packet loss
        score -= self.packet_loss_percent
        
        # Deduct for incomplete birth certificate
        if not self.birth_certificate_valid:
            score -= Decimal('20.0')
        
        # Deduct for high latency
        if self.average_latency_ms > 1000:
            score -= Decimal('10.0')
        
        return max(Decimal('0.0'), score)


class SparkplugCommandAudit(models.Model):
    """Audit trail for Sparkplug command execution"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('FAILED', 'Failed'),
        ('TIMEOUT', 'Timeout'),
    ]
    
    command_id = models.BigAutoField(primary_key=True)
    
    # Command target
    node = models.ForeignKey(SparkplugNode, on_delete=models.CASCADE, blank=True, null=True)
    device = models.ForeignKey(SparkplugDevice, on_delete=models.CASCADE, blank=True, null=True)
    metric_name = models.CharField(max_length=200)
    
    # Command details
    command_value = models.TextField(help_text="Command value as JSON")
    command_timestamp = models.DateTimeField()
    sequence_number = models.BigIntegerField()
    
    # Execution tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sent_at = models.DateTimeField(blank=True, null=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    response_value = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Security and audit
    initiated_by = models.CharField(max_length=100)
    client_ip = models.GenericIPAddressField(blank=True, null=True)
    reason = models.CharField(max_length=500)
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sp_command_audit'
        indexes = [
            models.Index(fields=['node', 'command_timestamp']),
            models.Index(fields=['device', 'command_timestamp']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['initiated_by', 'created_at']),
        ]
    
    def __str__(self):
        target = self.device or self.node
        return f"CMD {self.command_id}: {target}/{self.metric_name}"