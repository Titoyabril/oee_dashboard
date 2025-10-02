"""
GraphQL Schema for OEE Analytics
Provides comprehensive query and mutation interface
"""

import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.utils import timezone
from datetime import timedelta

from oee_analytics.models import ProductionMetrics, MLFeatureStore, MLModelRegistry, MLInference
from oee_analytics.events.models import DowntimeEvent
from oee_analytics.sparkplug.models import (
    SparkplugNode, SparkplugDevice, SparkplugMetric,
    SparkplugMetricHistory, SparkplugNodeState
)

# Try to import SQL Server models (may not exist)
try:
    from oee_analytics.sql_server_models import Machine, ProductionLine, Site
    HAS_SQL_SERVER_MODELS = True
except ImportError:
    HAS_SQL_SERVER_MODELS = False
    # Create placeholder models for GraphQL
    class Site:
        pass
    class ProductionLine:
        pass
    class Machine:
        pass


# ============================================================================
# Object Types
# ============================================================================

class ProductionMetricsType(DjangoObjectType):
    class Meta:
        model = ProductionMetrics
        fields = '__all__'


class MLFeatureStoreType(DjangoObjectType):
    class Meta:
        model = MLFeatureStore
        fields = '__all__'


class MLModelRegistryType(DjangoObjectType):
    class Meta:
        model = MLModelRegistry
        fields = '__all__'


class MLInferenceType(DjangoObjectType):
    class Meta:
        model = MLInference
        fields = '__all__'


class DowntimeEventType(DjangoObjectType):
    class Meta:
        model = DowntimeEvent
        fields = '__all__'


class SparkplugNodeType(DjangoObjectType):
    class Meta:
        model = SparkplugNode
        fields = '__all__'


class SparkplugDeviceType(DjangoObjectType):
    class Meta:
        model = SparkplugDevice
        fields = '__all__'


class SparkplugMetricType(DjangoObjectType):
    class Meta:
        model = SparkplugMetric
        fields = '__all__'


class SparkplugMetricHistoryType(DjangoObjectType):
    class Meta:
        model = SparkplugMetricHistory
        fields = '__all__'


class SparkplugNodeStateType(DjangoObjectType):
    class Meta:
        model = SparkplugNodeState
        fields = '__all__'


# Conditional SQL Server model types
if HAS_SQL_SERVER_MODELS:
    class SiteType(DjangoObjectType):
        class Meta:
            model = Site
            fields = '__all__'

    class ProductionLineType(DjangoObjectType):
        class Meta:
            model = ProductionLine
            fields = '__all__'

    class MachineType(DjangoObjectType):
        class Meta:
            model = Machine
            fields = '__all__'


# ============================================================================
# Custom Types for Complex Queries
# ============================================================================

class OEESnapshotType(graphene.ObjectType):
    """Current OEE snapshot for a machine/line"""
    line_id = graphene.String()
    timestamp = graphene.DateTime()
    oee = graphene.Float()
    availability = graphene.Float()
    performance = graphene.Float()
    quality = graphene.Float()
    good_count = graphene.Int()
    total_count = graphene.Int()
    downtime_minutes = graphene.Float()


class TrendDataPointType(graphene.ObjectType):
    """Time-series data point"""
    timestamp = graphene.DateTime()
    value = graphene.Float()


class TrendSeriesType(graphene.ObjectType):
    """Time-series trend data"""
    metric_name = graphene.String()
    data_points = graphene.List(TrendDataPointType)


class ActiveFaultType(graphene.ObjectType):
    """Active fault summary"""
    machine_id = graphene.String()
    fault_code = graphene.String()
    severity = graphene.String()
    duration_seconds = graphene.Float()
    start_time = graphene.DateTime()


# ============================================================================
# Query Root
# ============================================================================

class Query(graphene.ObjectType):
    """Root query type"""

    # ========================================================================
    # OEE Metrics Queries
    # ========================================================================

    oee_current = graphene.Field(
        OEESnapshotType,
        line_id=graphene.String(required=True),
        description="Get current OEE metrics for a line"
    )

    oee_trend = graphene.List(
        ProductionMetricsType,
        line_id=graphene.String(required=True),
        from_time=graphene.DateTime(),
        to_time=graphene.DateTime(),
        limit=graphene.Int(default_value=100),
        description="Get OEE trend data for a time window"
    )

    production_metrics = graphene.List(
        ProductionMetricsType,
        line_id=graphene.String(),
        shift_start=graphene.DateTime(),
        limit=graphene.Int(default_value=50)
    )

    # ========================================================================
    # Machine Status Queries
    # ========================================================================

    machines_status = graphene.List(
        graphene.String,
        site_id=graphene.String(),
        description="Get status of all machines in a site"
    )

    active_faults = graphene.List(
        ActiveFaultType,
        line_id=graphene.String(),
        machine_id=graphene.String(),
        description="Get active faults for line or machine"
    )

    downtime_events = graphene.List(
        DowntimeEventType,
        line_id=graphene.String(),
        from_time=graphene.DateTime(),
        to_time=graphene.DateTime(),
        limit=graphene.Int(default_value=50)
    )

    # ========================================================================
    # Sparkplug Queries
    # ========================================================================

    sparkplug_nodes = graphene.List(
        SparkplugNodeType,
        group_id=graphene.String(),
        status=graphene.String(),
        description="Get Sparkplug nodes"
    )

    sparkplug_devices = graphene.List(
        SparkplugDeviceType,
        node_id=graphene.ID(),
        description="Get Sparkplug devices for a node"
    )

    sparkplug_metrics = graphene.List(
        SparkplugMetricType,
        device_id=graphene.ID(),
        metric_name=graphene.String(),
        description="Get Sparkplug metrics"
    )

    metric_history = graphene.List(
        SparkplugMetricHistoryType,
        metric_id=graphene.ID(required=True),
        from_time=graphene.DateTime(),
        to_time=graphene.DateTime(),
        limit=graphene.Int(default_value=1000),
        description="Get metric history"
    )

    # ========================================================================
    # ML Queries
    # ========================================================================

    ml_models = graphene.List(
        MLModelRegistryType,
        model_type=graphene.String(),
        is_active=graphene.Boolean(),
        description="Get ML models"
    )

    ml_predictions = graphene.List(
        MLInferenceType,
        line_id=graphene.String(required=True),
        prediction_type=graphene.String(),
        from_time=graphene.DateTime(),
        limit=graphene.Int(default_value=100),
        description="Get ML predictions for a line"
    )

    ml_features = graphene.List(
        MLFeatureStoreType,
        line_id=graphene.String(required=True),
        feature_name=graphene.String(),
        description="Get ML features for a line"
    )

    # ========================================================================
    # Resolvers
    # ========================================================================

    def resolve_oee_current(self, info, line_id):
        """Get current OEE snapshot"""
        latest = ProductionMetrics.objects.filter(
            line_id=line_id
        ).order_by('-timestamp').first()

        if not latest:
            return None

        return OEESnapshotType(
            line_id=latest.line_id,
            timestamp=latest.timestamp,
            oee=latest.oee,
            availability=latest.availability,
            performance=latest.performance,
            quality=latest.quality,
            good_count=latest.good_count,
            total_count=latest.actual_count,
            downtime_minutes=latest.total_downtime_minutes
        )

    def resolve_oee_trend(self, info, line_id, from_time=None, to_time=None, limit=100):
        """Get OEE trend data"""
        queryset = ProductionMetrics.objects.filter(line_id=line_id)

        if from_time:
            queryset = queryset.filter(timestamp__gte=from_time)
        if to_time:
            queryset = queryset.filter(timestamp__lte=to_time)

        return queryset.order_by('-timestamp')[:limit]

    def resolve_production_metrics(self, info, line_id=None, shift_start=None, limit=50):
        """Get production metrics"""
        queryset = ProductionMetrics.objects.all()

        if line_id:
            queryset = queryset.filter(line_id=line_id)
        if shift_start:
            queryset = queryset.filter(shift_start=shift_start)

        return queryset.order_by('-timestamp')[:limit]

    def resolve_active_faults(self, info, line_id=None, machine_id=None):
        """Get active faults"""
        queryset = DowntimeEvent.objects.filter(
            ts__gte=timezone.now() - timedelta(hours=24)
        )

        if line_id:
            queryset = queryset.filter(line_id=line_id)

        # Convert to ActiveFaultType
        faults = []
        for event in queryset:
            faults.append(ActiveFaultType(
                machine_id=event.station_id,
                fault_code=event.reason,
                severity=str(event.severity),
                duration_seconds=event.duration_s,
                start_time=event.ts
            ))

        return faults

    def resolve_downtime_events(self, info, line_id=None, from_time=None, to_time=None, limit=50):
        """Get downtime events"""
        queryset = DowntimeEvent.objects.all()

        if line_id:
            queryset = queryset.filter(line_id=line_id)
        if from_time:
            queryset = queryset.filter(ts__gte=from_time)
        if to_time:
            queryset = queryset.filter(ts__lte=to_time)

        return queryset.order_by('-ts')[:limit]

    def resolve_sparkplug_nodes(self, info, group_id=None, status=None):
        """Get Sparkplug nodes"""
        queryset = SparkplugNode.objects.all()

        if group_id:
            queryset = queryset.filter(group_id=group_id)
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-last_data_timestamp')

    def resolve_sparkplug_devices(self, info, node_id=None):
        """Get Sparkplug devices"""
        queryset = SparkplugDevice.objects.all()

        if node_id:
            queryset = queryset.filter(node_id=node_id)

        return queryset.order_by('device_name')

    def resolve_sparkplug_metrics(self, info, device_id=None, metric_name=None):
        """Get Sparkplug metrics"""
        queryset = SparkplugMetric.objects.all()

        if device_id:
            queryset = queryset.filter(device_id=device_id)
        if metric_name:
            queryset = queryset.filter(name__icontains=metric_name)

        return queryset.order_by('name')

    def resolve_metric_history(self, info, metric_id, from_time=None, to_time=None, limit=1000):
        """Get metric history"""
        queryset = SparkplugMetricHistory.objects.filter(metric_id=metric_id)

        if from_time:
            queryset = queryset.filter(timestamp_utc__gte=from_time)
        if to_time:
            queryset = queryset.filter(timestamp_utc__lte=to_time)

        return queryset.order_by('-timestamp_utc')[:limit]

    def resolve_ml_models(self, info, model_type=None, is_active=None):
        """Get ML models"""
        queryset = MLModelRegistry.objects.all()

        if model_type:
            queryset = queryset.filter(model_type=model_type)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset.order_by('-created_at')

    def resolve_ml_predictions(self, info, line_id, prediction_type=None, from_time=None, limit=100):
        """Get ML predictions"""
        queryset = MLInference.objects.filter(line_id=line_id)

        if prediction_type:
            queryset = queryset.filter(prediction_type=prediction_type)
        if from_time:
            queryset = queryset.filter(timestamp__gte=from_time)

        return queryset.order_by('-timestamp')[:limit]

    def resolve_ml_features(self, info, line_id, feature_name=None):
        """Get ML features"""
        queryset = MLFeatureStore.objects.filter(line_id=line_id)

        if feature_name:
            queryset = queryset.filter(feature_name=feature_name)

        return queryset.order_by('-timestamp')[:100]


# ============================================================================
# Mutations
# ============================================================================

class UpdateMLModel(graphene.Mutation):
    """Update ML model active status"""

    class Arguments:
        model_name = graphene.String(required=True)
        is_active = graphene.Boolean(required=True)

    success = graphene.Boolean()
    model = graphene.Field(MLModelRegistryType)

    def mutate(self, info, model_name, is_active):
        try:
            model = MLModelRegistry.objects.get(model_name=model_name)
            model.is_active = is_active
            model.save()

            return UpdateMLModel(success=True, model=model)
        except MLModelRegistry.DoesNotExist:
            return UpdateMLModel(success=False, model=None)


class AcknowledgeFault(graphene.Mutation):
    """Acknowledge a downtime event"""

    class Arguments:
        event_id = graphene.ID(required=True)
        acknowledged_by = graphene.String(required=True)

    success = graphene.Boolean()
    event = graphene.Field(DowntimeEventType)

    def mutate(self, info, event_id, acknowledged_by):
        try:
            event = DowntimeEvent.objects.get(id=event_id)
            # Add acknowledgement (would need to add fields to model)
            # For now, just update detail
            event.detail = f"Acknowledged by {acknowledged_by} at {timezone.now()}"
            event.save()

            return AcknowledgeFault(success=True, event=event)
        except DowntimeEvent.DoesNotExist:
            return AcknowledgeFault(success=False, event=None)


class Mutation(graphene.ObjectType):
    """Root mutation type"""
    update_ml_model = UpdateMLModel.Field()
    acknowledge_fault = AcknowledgeFault.Field()


# ============================================================================
# Schema
# ============================================================================

schema = graphene.Schema(query=Query, mutation=Mutation)
