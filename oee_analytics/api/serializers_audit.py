"""
Serializers for Audit Log API endpoints
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import PLCWriteAudit, SystemAuditLog, DataIntegrityLog


class PLCWriteAuditSerializer(serializers.ModelSerializer):
    """Serializer for PLC write audit logs"""

    user_display = serializers.SerializerMethodField()
    machine_name = serializers.CharField(source='machine.name', read_only=True)
    change_summary = serializers.SerializerMethodField()
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PLCWriteAudit
        fields = [
            'id', 'operation_id', 'timestamp', 'username', 'user_display',
            'user_ip', 'auth_method', 'machine', 'machine_name',
            'plc_address', 'plc_type', 'operation_type', 'tag_address',
            'tag_name', 'previous_value', 'new_value', 'data_type',
            'status', 'status_display', 'error_message', 'execution_time_ms',
            'severity', 'severity_display', 'production_impacting',
            'safety_related', 'requires_approval', 'approved_by',
            'approval_timestamp', 'reason', 'request_source',
            'change_summary', 'metadata'
        ]
        read_only_fields = ['operation_id', 'timestamp']

    def get_user_display(self, obj):
        """Get user display name"""
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username} ({obj.username})"
        return obj.username

    def get_change_summary(self, obj):
        """Get human-readable change summary"""
        return obj.get_value_change_summary()


class SystemAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for system audit logs"""

    user_display = serializers.SerializerMethodField()
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = SystemAuditLog
        fields = [
            'id', 'timestamp', 'event_type', 'event_type_display',
            'username', 'user_display', 'user_ip', 'component',
            'action', 'description', 'before_state', 'after_state',
            'success', 'error_message', 'metadata'
        ]
        read_only_fields = ['timestamp']

    def get_user_display(self, obj):
        """Get user display name"""
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username}"
        return obj.username


class DataIntegrityLogSerializer(serializers.ModelSerializer):
    """Serializer for data integrity logs"""

    machine_name = serializers.CharField(source='machine.name', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = DataIntegrityLog
        fields = [
            'id', 'timestamp', 'detected_at', 'machine', 'machine_name',
            'source', 'issue_type', 'issue_type_display', 'severity',
            'severity_display', 'description', 'expected_value',
            'actual_value', 'auto_corrected', 'correction_action',
            'metadata'
        ]
        read_only_fields = ['timestamp', 'detected_at']


class AuditSearchSerializer(serializers.Serializer):
    """Serializer for audit log search parameters"""

    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    username = serializers.CharField(required=False, allow_blank=True)
    machine_id = serializers.IntegerField(required=False)
    plc_address = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=PLCWriteAudit.STATUS_CHOICES,
        required=False,
        allow_blank=True
    )
    severity = serializers.ChoiceField(
        choices=PLCWriteAudit.SEVERITY_CHOICES,
        required=False,
        allow_blank=True
    )
    tag_address = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(default=100, max_value=1000)
