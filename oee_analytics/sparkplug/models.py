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


class OPCUAServerConnection(models.Model):
    """OPC-UA Server connection configuration"""

    SECURITY_MODE_CHOICES = [
        ('None', 'No Security'),
        ('Sign', 'Sign Only'),
        ('SignAndEncrypt', 'Sign and Encrypt'),
    ]

    AUTH_MODE_CHOICES = [
        ('Anonymous', 'Anonymous'),
        ('UsernamePassword', 'Username/Password'),
        ('Certificate', 'Certificate'),
    ]

    STATUS_CHOICES = [
        ('DISCONNECTED', 'Disconnected'),
        ('CONNECTING', 'Connecting'),
        ('CONNECTED', 'Connected'),
        ('ERROR', 'Error'),
        ('DISABLED', 'Disabled'),
    ]

    # Identification
    server_id = models.CharField(max_length=100, unique=True, help_text="Unique server identifier")
    name = models.CharField(max_length=200, help_text="Display name")
    endpoint_url = models.URLField(max_length=500, help_text="OPC-UA endpoint URL")

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISCONNECTED')
    enabled = models.BooleanField(default=True)
    last_connection = models.DateTimeField(blank=True, null=True)
    last_disconnection = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, null=True)

    # Security settings
    security_mode = models.CharField(max_length=20, choices=SECURITY_MODE_CHOICES, default='SignAndEncrypt')
    security_policy = models.CharField(max_length=50, default='Basic256Sha256')
    auth_mode = models.CharField(max_length=20, choices=AUTH_MODE_CHOICES, default='Certificate')

    # Credentials
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)  # Should be encrypted

    # Certificates
    client_cert_path = models.CharField(max_length=500, blank=True, null=True)
    client_key_path = models.CharField(max_length=500, blank=True, null=True)
    server_cert_path = models.CharField(max_length=500, blank=True, null=True)

    # Connection settings
    session_timeout_ms = models.IntegerField(default=30000)
    keep_alive_interval_ms = models.IntegerField(default=10000)
    reconnect_interval_s = models.IntegerField(default=5)
    max_reconnect_attempts = models.IntegerField(default=-1, help_text="-1 for infinite")

    # Subscription settings
    publishing_interval_ms = models.IntegerField(default=250)
    max_notifications_per_publish = models.IntegerField(default=1000)

    # Performance
    max_concurrent_reads = models.IntegerField(default=100)
    batch_read_size = models.IntegerField(default=50)

    # Metrics
    total_subscriptions = models.IntegerField(default=0)
    total_monitored_items = models.IntegerField(default=0)
    total_data_changes = models.BigIntegerField(default=0)
    total_errors = models.BigIntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opcua_server_connection'
        indexes = [
            models.Index(fields=['server_id']),
            models.Index(fields=['status', 'enabled']),
        ]

    def __str__(self):
        return f"{self.name} ({self.endpoint_url})"


class OPCUANodeMapping(models.Model):
    """Mapping between OPC-UA nodes and Sparkplug metrics"""

    DATA_TYPE_CHOICES = [
        ('BOOL', 'Boolean'),
        ('INT', 'Integer'),
        ('DINT', 'Double Integer'),
        ('REAL', 'Real/Float'),
        ('LREAL', 'Long Real/Double'),
        ('STRING', 'String'),
        ('DATETIME', 'DateTime'),
    ]

    OEE_METRIC_CHOICES = [
        ('CYCLE_START', 'Cycle Start'),
        ('CYCLE_END', 'Cycle End'),
        ('CYCLE_TIME', 'Cycle Time'),
        ('PART_COUNT_GOOD', 'Good Parts'),
        ('PART_COUNT_SCRAP', 'Scrap Parts'),
        ('PART_COUNT_REWORK', 'Rework Parts'),
        ('QUALITY_FLAG', 'Quality Flag'),
        ('DOWNTIME_START', 'Downtime Start'),
        ('DOWNTIME_END', 'Downtime End'),
        ('DOWNTIME_REASON', 'Downtime Reason'),
        ('MACHINE_STATUS', 'Machine Status'),
        ('PRODUCTION_RATE', 'Production Rate'),
        ('TEMPERATURE', 'Temperature'),
        ('PRESSURE', 'Pressure'),
        ('VIBRATION', 'Vibration'),
        ('SPEED', 'Speed'),
        ('ALARM_ACTIVE', 'Alarm Active'),
    ]

    # Association
    server = models.ForeignKey(OPCUAServerConnection, on_delete=models.CASCADE)

    # OPC-UA node
    opcua_node_id = models.CharField(max_length=500, help_text="OPC-UA Node ID (e.g., ns=2;i=1001)")
    display_name = models.CharField(max_length=200)
    browse_path = models.CharField(max_length=1000, blank=True, null=True)

    # Sparkplug mapping
    sparkplug_metric_name = models.CharField(max_length=200)
    sparkplug_node = models.ForeignKey(SparkplugNode, on_delete=models.SET_NULL, blank=True, null=True)
    sparkplug_device = models.ForeignKey(SparkplugDevice, on_delete=models.SET_NULL, blank=True, null=True)

    # Data processing
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default='REAL')
    scale_factor = models.FloatField(default=1.0)
    offset = models.FloatField(default=0.0)
    unit = models.CharField(max_length=50, blank=True, null=True)

    # Subscription settings
    sampling_interval_ms = models.IntegerField(default=250)
    deadband_type = models.IntegerField(default=1, help_text="0=None, 1=Absolute, 2=Percent")
    deadband_value = models.FloatField(default=0.0)
    queue_size = models.IntegerField(default=10)
    discard_oldest = models.BooleanField(default=True)

    # OEE mapping
    oee_metric_type = models.CharField(max_length=30, choices=OEE_METRIC_CHOICES, blank=True, null=True)
    machine_id = models.CharField(max_length=100, blank=True, null=True)
    line_id = models.CharField(max_length=100, blank=True, null=True)

    # Status
    enabled = models.BooleanField(default=True)
    last_value = models.TextField(blank=True, null=True)
    last_timestamp = models.DateTimeField(blank=True, null=True)
    last_quality = models.IntegerField(default=100, help_text="0-100 quality score")

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opcua_node_mapping'
        unique_together = ('server', 'opcua_node_id')
        indexes = [
            models.Index(fields=['server', 'enabled']),
            models.Index(fields=['sparkplug_metric_name']),
            models.Index(fields=['oee_metric_type', 'machine_id']),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.opcua_node_id})"

    def apply_scaling(self, value):
        """Apply scale factor and offset to value"""
        if value is None:
            return None
        try:
            return (float(value) * self.scale_factor) + self.offset
        except (ValueError, TypeError):
            return value


class OPCUASubscription(models.Model):
    """OPC-UA subscription tracking"""

    server = models.ForeignKey(OPCUAServerConnection, on_delete=models.CASCADE)
    subscription_id = models.IntegerField()

    # Settings
    publishing_interval_ms = models.IntegerField(default=250)
    keep_alive_count = models.IntegerField(default=10)
    lifetime_count = models.IntegerField(default=3000)
    max_notifications_per_publish = models.IntegerField(default=1000)
    publishing_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)

    # Status
    active = models.BooleanField(default=False)
    monitored_items_count = models.IntegerField(default=0)
    last_sequence_number = models.BigIntegerField(default=0)

    # Metrics
    total_data_changes = models.BigIntegerField(default=0)
    total_events = models.BigIntegerField(default=0)
    total_errors = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opcua_subscription'
        unique_together = ('server', 'subscription_id')

    def __str__(self):
        return f"Subscription {self.subscription_id} on {self.server.name}"