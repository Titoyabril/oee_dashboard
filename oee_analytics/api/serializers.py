"""
REST API Serializers for OEE Analytics
Handles data validation and serialization for CRUD operations
"""

from rest_framework import serializers
from oee_analytics.models import ProductionMetrics, MLFeatureStore, MLModelRegistry, MLInference
from oee_analytics.events.models import DowntimeEvent
from oee_analytics.sparkplug.models import SparkplugNode, SparkplugDevice, SparkplugMetric

# Try to import SQL Server models
try:
    from oee_analytics.sql_server_models import Machine, ProductionLine, Site, Area, Plant
    HAS_SQL_SERVER_MODELS = True
except ImportError:
    HAS_SQL_SERVER_MODELS = False


# ============================================================================
# Configuration Serializers (CRUD)
# ============================================================================

if HAS_SQL_SERVER_MODELS:
    class PlantSerializer(serializers.ModelSerializer):
        """Plant configuration"""
        class Meta:
            model = Plant
            fields = '__all__'


    class SiteSerializer(serializers.ModelSerializer):
        """Site configuration"""
        class Meta:
            model = Site
            fields = '__all__'


    class AreaSerializer(serializers.ModelSerializer):
        """Area configuration"""
        class Meta:
            model = Area
            fields = '__all__'


    class ProductionLineSerializer(serializers.ModelSerializer):
        """Production line configuration"""
        class Meta:
            model = ProductionLine
            fields = '__all__'


    class MachineSerializer(serializers.ModelSerializer):
        """Machine configuration"""
        line_name = serializers.CharField(source='line.line_name', read_only=True)
        site_name = serializers.CharField(source='line.area.site.site_name', read_only=True)

        class Meta:
            model = Machine
            fields = '__all__'


    class MachineDetailSerializer(serializers.ModelSerializer):
        """Machine with nested relationships"""
        line = ProductionLineSerializer(read_only=True)

        class Meta:
            model = Machine
            fields = '__all__'


# ============================================================================
# Metrics Serializers
# ============================================================================

class ProductionMetricsSerializer(serializers.ModelSerializer):
    """OEE metrics"""
    class Meta:
        model = ProductionMetrics
        fields = '__all__'
        read_only_fields = ['timestamp']


class DowntimeEventSerializer(serializers.ModelSerializer):
    """Downtime events"""
    class Meta:
        model = DowntimeEvent
        fields = '__all__'


# ============================================================================
# Sparkplug Serializers
# ============================================================================

class SparkplugNodeSerializer(serializers.ModelSerializer):
    """Sparkplug node"""
    device_count = serializers.IntegerField(source='devices.count', read_only=True)

    class Meta:
        model = SparkplugNode
        fields = '__all__'
        read_only_fields = ['last_birth_timestamp', 'last_data_timestamp', 'last_death_timestamp']


class SparkplugDeviceSerializer(serializers.ModelSerializer):
    """Sparkplug device"""
    node_name = serializers.CharField(source='node.node_id', read_only=True)
    metric_count = serializers.IntegerField(source='metrics.count', read_only=True)

    class Meta:
        model = SparkplugDevice
        fields = '__all__'


class SparkplugMetricSerializer(serializers.ModelSerializer):
    """Sparkplug metric"""
    device_name = serializers.CharField(source='device.device_name', read_only=True)
    node_name = serializers.CharField(source='device.node.node_id', read_only=True)

    class Meta:
        model = SparkplugMetric
        fields = '__all__'


# ============================================================================
# ML Serializers
# ============================================================================

class MLModelRegistrySerializer(serializers.ModelSerializer):
    """ML model registry"""
    class Meta:
        model = MLModelRegistry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class MLFeatureStoreSerializer(serializers.ModelSerializer):
    """ML feature store"""
    class Meta:
        model = MLFeatureStore
        fields = '__all__'


class MLInferenceSerializer(serializers.ModelSerializer):
    """ML inference results"""
    class Meta:
        model = MLInference
        fields = '__all__'


# ============================================================================
# Custom Serializers for Complex Operations
# ============================================================================

class OEEDashboardSerializer(serializers.Serializer):
    """Dashboard summary data"""
    line_id = serializers.CharField()
    current_oee = serializers.FloatField()
    current_availability = serializers.FloatField()
    current_performance = serializers.FloatField()
    current_quality = serializers.FloatField()
    shift_production_count = serializers.IntegerField()
    shift_target_count = serializers.IntegerField()
    active_downtime_events = serializers.IntegerField()
    last_update = serializers.DateTimeField()


class MachineSummarySerializer(serializers.Serializer):
    """Machine status summary"""
    machine_id = serializers.CharField()
    machine_name = serializers.CharField()
    line_id = serializers.CharField()
    status = serializers.ChoiceField(choices=['RUNNING', 'IDLE', 'DOWN', 'OFFLINE'])
    current_oee = serializers.FloatField(allow_null=True)
    last_production_time = serializers.DateTimeField(allow_null=True)
    active_faults = serializers.ListField(child=serializers.CharField())


class TimeSeriesDataPointSerializer(serializers.Serializer):
    """Time-series data point"""
    timestamp = serializers.DateTimeField()
    value = serializers.FloatField()


class TrendDataSerializer(serializers.Serializer):
    """Trend data for charting"""
    metric_name = serializers.CharField()
    data_points = TimeSeriesDataPointSerializer(many=True)
    unit = serializers.CharField()
    aggregation = serializers.ChoiceField(
        choices=['raw', '1min', '5min', '1hour', '1day'],
        default='raw'
    )


class BulkMachineStatusSerializer(serializers.Serializer):
    """Bulk machine status update"""
    machines = MachineSummarySerializer(many=True)
    timestamp = serializers.DateTimeField()


# ============================================================================
# Write-Only Serializers for Actions
# ============================================================================

class AcknowledgeFaultSerializer(serializers.Serializer):
    """Acknowledge a fault"""
    event_id = serializers.IntegerField()
    acknowledged_by = serializers.CharField(max_length=100)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class TriggerMLPipelineSerializer(serializers.Serializer):
    """Trigger ML pipeline"""
    line_id = serializers.CharField()
    pipeline_type = serializers.ChoiceField(
        choices=['all', 'features', 'predictions', 'quality_scoring', 'forecasting']
    )


class UpdateMachineConfigSerializer(serializers.Serializer):
    """Update machine configuration"""
    machine_id = serializers.CharField()
    ideal_cycle_time_seconds = serializers.FloatField(required=False, allow_null=True)
    target_availability = serializers.FloatField(required=False, allow_null=True)
    target_performance = serializers.FloatField(required=False, allow_null=True)
    target_quality = serializers.FloatField(required=False, allow_null=True)
    target_oee = serializers.FloatField(required=False, allow_null=True)
