"""
Audit Logging Models
Comprehensive audit trail for PLC write operations and system changes
Meets compliance requirements for manufacturing data integrity
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class PLCWriteAudit(models.Model):
    """
    Audit log for all PLC write operations
    Required for compliance and security tracking
    """

    OPERATION_TYPE_CHOICES = [
        ('WRITE_SINGLE', 'Single Tag Write'),
        ('WRITE_BATCH', 'Batch Write'),
        ('SETPOINT_CHANGE', 'Setpoint Change'),
        ('MODE_CHANGE', 'Mode Change'),
        ('RECIPE_DOWNLOAD', 'Recipe Download'),
        ('COMMAND', 'Command Execution'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('DENIED', 'Access Denied'),
        ('TIMEOUT', 'Timeout'),
        ('ERROR', 'Error'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low Impact'),
        ('MEDIUM', 'Medium Impact'),
        ('HIGH', 'High Impact - Production Affecting'),
        ('CRITICAL', 'Critical - Safety Related'),
    ]

    # Timestamp and identification
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    operation_id = models.UUIDField(auto_created=True, unique=True, db_index=True)

    # User and authorization
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='plc_writes')
    username = models.CharField(max_length=150)  # Preserved even if user deleted
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    auth_method = models.CharField(max_length=50, default='JWT')  # JWT, OAuth2, Certificate

    # PLC and tag information
    machine = models.ForeignKey('Machine', on_delete=models.SET_NULL, null=True, related_name='write_audits')
    plc_address = models.CharField(max_length=100)  # IP or hostname
    plc_type = models.CharField(max_length=50)  # OPC-UA, S7, Allen-Bradley, etc.

    # Operation details
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPE_CHOICES)
    tag_address = models.CharField(max_length=255)
    tag_name = models.CharField(max_length=255, blank=True)

    # Values
    previous_value = models.TextField(blank=True)  # JSON serialized
    new_value = models.TextField()  # JSON serialized
    data_type = models.CharField(max_length=50)  # BOOL, INT, REAL, etc.

    # Result and validation
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    error_message = models.TextField(blank=True)
    execution_time_ms = models.IntegerField(null=True)

    # Approval workflow (for critical operations)
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_writes')
    approval_timestamp = models.DateTimeField(null=True, blank=True)

    # Impact and categorization
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    production_impacting = models.BooleanField(default=False)
    safety_related = models.BooleanField(default=False)

    # Context and metadata
    session_id = models.CharField(max_length=100, blank=True)
    request_source = models.CharField(max_length=100, blank=True)  # Dashboard, API, Script, etc.
    reason = models.TextField(blank=True)  # User-provided reason for change
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'plc_write_audit'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['machine', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['status', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
            models.Index(fields=['plc_address', '-timestamp']),
        ]
        verbose_name = 'PLC Write Audit Log'
        verbose_name_plural = 'PLC Write Audit Logs'

    def __str__(self):
        return f"{self.timestamp} - {self.username} -> {self.tag_address} ({self.status})"

    @property
    def previous_value_parsed(self):
        """Parse previous value from JSON"""
        if not self.previous_value:
            return None
        try:
            return json.loads(self.previous_value)
        except:
            return self.previous_value

    @property
    def new_value_parsed(self):
        """Parse new value from JSON"""
        try:
            return json.loads(self.new_value)
        except:
            return self.new_value

    def get_value_change_summary(self):
        """Get human-readable change summary"""
        prev = self.previous_value_parsed
        new = self.new_value_parsed

        if prev is None:
            return f"Set to {new}"

        return f"Changed from {prev} to {new}"


class SystemAuditLog(models.Model):
    """
    General system audit log for non-PLC operations
    Configuration changes, user actions, system events
    """

    EVENT_TYPE_CHOICES = [
        ('CONFIG_CHANGE', 'Configuration Change'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
        ('PERMISSION_CHANGE', 'Permission Change'),
        ('SYSTEM_START', 'System Start'),
        ('SYSTEM_STOP', 'System Stop'),
        ('BACKUP', 'Backup Operation'),
        ('RESTORE', 'Restore Operation'),
        ('ALARM_ACK', 'Alarm Acknowledgment'),
        ('RECIPE_CHANGE', 'Recipe Change'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, db_index=True)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    username = models.CharField(max_length=150)
    user_ip = models.GenericIPAddressField(null=True, blank=True)

    component = models.CharField(max_length=100)  # Edge Gateway, MQTT Broker, API, etc.
    action = models.CharField(max_length=255)
    description = models.TextField()

    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)

    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'system_audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
        verbose_name = 'System Audit Log'
        verbose_name_plural = 'System Audit Logs'

    def __str__(self):
        return f"{self.timestamp} - {self.event_type}: {self.action}"


class DataIntegrityLog(models.Model):
    """
    Data integrity validation log
    Tracks sequence gaps, quality issues, data anomalies
    """

    ISSUE_TYPE_CHOICES = [
        ('SEQUENCE_GAP', 'Sequence Number Gap'),
        ('TIMESTAMP_ANOMALY', 'Timestamp Anomaly'),
        ('QUALITY_DEGRADED', 'Quality Degraded'),
        ('VALUE_OUT_OF_RANGE', 'Value Out of Range'),
        ('CHECKSUM_FAILED', 'Checksum Failed'),
        ('DUPLICATE_DATA', 'Duplicate Data'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    machine = models.ForeignKey('Machine', on_delete=models.SET_NULL, null=True)
    source = models.CharField(max_length=100)  # OPC-UA, Sparkplug, etc.

    issue_type = models.CharField(max_length=30, choices=ISSUE_TYPE_CHOICES, db_index=True)
    severity = models.CharField(max_length=20, choices=PLCWriteAudit.SEVERITY_CHOICES)

    description = models.TextField()
    expected_value = models.TextField(blank=True)
    actual_value = models.TextField(blank=True)

    auto_corrected = models.BooleanField(default=False)
    correction_action = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'data_integrity_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['machine', '-timestamp']),
            models.Index(fields=['issue_type', '-timestamp']),
        ]
        verbose_name = 'Data Integrity Log'
        verbose_name_plural = 'Data Integrity Logs'

    def __str__(self):
        return f"{self.timestamp} - {self.issue_type}: {self.description[:50]}"
