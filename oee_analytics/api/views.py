"""
REST API Views for OEE Analytics
CRUD endpoints for machines, sites, lines, and configuration
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max
from datetime import timedelta

from oee_analytics.models import ProductionMetrics, MLModelRegistry, MLFeatureStore, MLInference
from oee_analytics.events.models import DowntimeEvent
from oee_analytics.sparkplug.models import SparkplugNode, SparkplugDevice, SparkplugMetric

from .serializers import (
    ProductionMetricsSerializer, DowntimeEventSerializer,
    SparkplugNodeSerializer, SparkplugDeviceSerializer, SparkplugMetricSerializer,
    MLModelRegistrySerializer, MLFeatureStoreSerializer, MLInferenceSerializer,
    OEEDashboardSerializer, MachineSummarySerializer, TrendDataSerializer,
    AcknowledgeFaultSerializer, TriggerMLPipelineSerializer,
)

# Try to import SQL Server models and serializers
try:
    from oee_analytics.sql_server_models import Machine, ProductionLine, Site, Area, Plant
    from .serializers import (
        MachineSerializer, MachineDetailSerializer, ProductionLineSerializer,
        SiteSerializer, AreaSerializer, PlantSerializer
    )
    HAS_SQL_SERVER_MODELS = True
except ImportError:
    HAS_SQL_SERVER_MODELS = False


# ============================================================================
# Pagination
# ============================================================================

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000


# ============================================================================
# Configuration ViewSets (CRUD)
# ============================================================================

if HAS_SQL_SERVER_MODELS:
    class PlantViewSet(viewsets.ModelViewSet):
        """
        API endpoint for managing plants

        list: Get all plants
        retrieve: Get a specific plant
        create: Create a new plant
        update: Update a plant
        destroy: Delete a plant
        """
        queryset = Plant.objects.all()
        serializer_class = PlantSerializer
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = StandardResultsSetPagination


    class SiteViewSet(viewsets.ModelViewSet):
        """
        API endpoint for managing sites

        list: Get all sites
        retrieve: Get a specific site
        create: Create a new site
        update: Update a site
        destroy: Delete a site
        """
        queryset = Site.objects.all()
        serializer_class = SiteSerializer
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = StandardResultsSetPagination
        filterset_fields = ['plant']


    class AreaViewSet(viewsets.ModelViewSet):
        """
        API endpoint for managing areas

        list: Get all areas
        retrieve: Get a specific area
        create: Create a new area
        update: Update an area
        destroy: Delete an area
        """
        queryset = Area.objects.all()
        serializer_class = AreaSerializer
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = StandardResultsSetPagination
        filterset_fields = ['site']


    class ProductionLineViewSet(viewsets.ModelViewSet):
        """
        API endpoint for managing production lines

        list: Get all production lines
        retrieve: Get a specific line
        create: Create a new line
        update: Update a line
        destroy: Delete a line
        """
        queryset = ProductionLine.objects.all()
        serializer_class = ProductionLineSerializer
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = StandardResultsSetPagination
        filterset_fields = ['area', 'area__site']

        @action(detail=True, methods=['get'])
        def machines(self, request, pk=None):
            """Get all machines for this line"""
            line = self.get_object()
            machines = Machine.objects.filter(line=line)
            serializer = MachineSerializer(machines, many=True)
            return Response(serializer.data)


    class MachineViewSet(viewsets.ModelViewSet):
        """
        API endpoint for managing machines

        list: Get all machines
        retrieve: Get a specific machine
        create: Create a new machine
        update: Update a machine
        destroy: Delete a machine
        """
        queryset = Machine.objects.all()
        serializer_class = MachineSerializer
        permission_classes = [permissions.IsAuthenticated]
        pagination_class = StandardResultsSetPagination
        filterset_fields = ['line', 'line__area__site', 'machine_type']

        def get_serializer_class(self):
            if self.action == 'retrieve':
                return MachineDetailSerializer
            return MachineSerializer

        @action(detail=True, methods=['get'])
        def current_status(self, request, pk=None):
            """Get current status for this machine"""
            machine = self.get_object()

            # Get latest metrics
            latest_metric = ProductionMetrics.objects.filter(
                line_id=machine.line.line_id
            ).order_by('-timestamp').first()

            # Get active faults
            active_faults = DowntimeEvent.objects.filter(
                station_id=machine.machine_id,
                ts__gte=timezone.now() - timedelta(hours=24)
            ).count()

            status_data = {
                'machine_id': machine.machine_id,
                'machine_name': machine.machine_name,
                'line_id': machine.line.line_id if machine.line else None,
                'status': 'RUNNING' if latest_metric and latest_metric.oee > 50 else 'IDLE',
                'current_oee': latest_metric.oee if latest_metric else None,
                'last_production_time': latest_metric.timestamp if latest_metric else None,
                'active_faults': [f"Fault {i}" for i in range(active_faults)]
            }

            serializer = MachineSummarySerializer(status_data)
            return Response(serializer.data)

        @action(detail=True, methods=['get'])
        def metrics(self, request, pk=None):
            """Get metrics history for this machine"""
            machine = self.get_object()

            hours = int(request.query_params.get('hours', 24))
            from_time = timezone.now() - timedelta(hours=hours)

            metrics = ProductionMetrics.objects.filter(
                line_id=machine.line.line_id if machine.line else '',
                timestamp__gte=from_time
            ).order_by('timestamp')

            serializer = ProductionMetricsSerializer(metrics, many=True)
            return Response(serializer.data)


# ============================================================================
# Metrics ViewSets
# ============================================================================

class ProductionMetricsViewSet(viewsets.ModelViewSet):
    """
    API endpoint for OEE metrics

    list: Get OEE metrics with filtering
    retrieve: Get specific metric record
    """
    queryset = ProductionMetrics.objects.all()
    serializer_class = ProductionMetricsSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['line_id', 'shift_start']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by time range
        from_time = self.request.query_params.get('from_time')
        to_time = self.request.query_params.get('to_time')

        if from_time:
            queryset = queryset.filter(timestamp__gte=from_time)
        if to_time:
            queryset = queryset.filter(timestamp__lte=to_time)

        return queryset.order_by('-timestamp')


class DowntimeEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint for downtime events

    list: Get downtime events
    retrieve: Get specific event
    create: Log a new downtime event
    """
    queryset = DowntimeEvent.objects.all()
    serializer_class = DowntimeEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['line_id', 'station_id', 'severity']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by time range
        from_time = self.request.query_params.get('from_time')
        to_time = self.request.query_params.get('to_time')

        if from_time:
            queryset = queryset.filter(ts__gte=from_time)
        if to_time:
            queryset = queryset.filter(ts__lte=to_time)

        return queryset.order_by('-ts')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active downtime events"""
        active_events = self.get_queryset().filter(
            ts__gte=timezone.now() - timedelta(hours=1)
        )
        serializer = self.get_serializer(active_events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge a downtime event"""
        event = self.get_object()
        serializer = AcknowledgeFaultSerializer(data=request.data)

        if serializer.is_valid():
            # Update event with acknowledgement
            acknowledged_by = serializer.validated_data['acknowledged_by']
            notes = serializer.validated_data.get('notes', '')

            event.detail = f"Acknowledged by {acknowledged_by} at {timezone.now()}. {notes}"
            event.save()

            return Response({
                'status': 'acknowledged',
                'event_id': event.id,
                'acknowledged_by': acknowledged_by
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Sparkplug ViewSets
# ============================================================================

class SparkplugNodeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Sparkplug nodes (read-only)

    list: Get all Sparkplug nodes
    retrieve: Get specific node
    """
    queryset = SparkplugNode.objects.all()
    serializer_class = SparkplugNodeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['group_id', 'status', 'is_active']

    @action(detail=True, methods=['get'])
    def devices(self, request, pk=None):
        """Get devices for this node"""
        node = self.get_object()
        devices = SparkplugDevice.objects.filter(node=node)
        serializer = SparkplugDeviceSerializer(devices, many=True)
        return Response(serializer.data)


class SparkplugDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Sparkplug devices (read-only)

    list: Get all Sparkplug devices
    retrieve: Get specific device
    """
    queryset = SparkplugDevice.objects.all()
    serializer_class = SparkplugDeviceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['node', 'device_name']

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Get metrics for this device"""
        device = self.get_object()
        metrics = SparkplugMetric.objects.filter(device=device)
        serializer = SparkplugMetricSerializer(metrics, many=True)
        return Response(serializer.data)


class SparkplugMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Sparkplug metrics (read-only)

    list: Get all Sparkplug metrics
    retrieve: Get specific metric
    """
    queryset = SparkplugMetric.objects.all()
    serializer_class = SparkplugMetricSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['device', 'name', 'sparkplug_type']


# ============================================================================
# ML ViewSets
# ============================================================================

class MLModelRegistryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for ML model registry

    list: Get all ML models
    retrieve: Get specific model
    create: Register a new model
    update: Update model configuration
    """
    queryset = MLModelRegistry.objects.all()
    serializer_class = MLModelRegistrySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['model_type', 'is_active']

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate this model and deactivate others of same type"""
        model = self.get_object()

        # Deactivate other models of same type
        MLModelRegistry.objects.filter(model_type=model.model_type).update(is_active=False)

        # Activate this model
        model.is_active = True
        model.save()

        return Response({'status': 'activated', 'model_name': model.model_name})


class MLInferenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for ML predictions (read-only)

    list: Get ML predictions
    retrieve: Get specific prediction
    """
    queryset = MLInference.objects.all()
    serializer_class = MLInferenceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['line_id', 'model_name', 'prediction_type']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by time range
        from_time = self.request.query_params.get('from_time')
        to_time = self.request.query_params.get('to_time')

        if from_time:
            queryset = queryset.filter(timestamp__gte=from_time)
        if to_time:
            queryset = queryset.filter(timestamp__lte=to_time)

        return queryset.order_by('-timestamp')


# ============================================================================
# Dashboard API Views
# ============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
def dashboard_summary(request):
    """
    Get dashboard summary for all lines

    Query parameters:
    - site_id: Filter by site
    """
    site_id = request.query_params.get('site_id')

    # Get latest metrics for each line
    lines = ProductionMetrics.objects.values('line_id').distinct()

    summaries = []
    for line in lines:
        line_id = line['line_id']

        latest = ProductionMetrics.objects.filter(
            line_id=line_id
        ).order_by('-timestamp').first()

        if latest:
            active_events = DowntimeEvent.objects.filter(
                line_id=line_id,
                ts__gte=timezone.now() - timedelta(hours=1)
            ).count()

            summaries.append({
                'line_id': line_id,
                'current_oee': latest.oee,
                'current_availability': latest.availability,
                'current_performance': latest.performance,
                'current_quality': latest.quality,
                'shift_production_count': latest.actual_count,
                'shift_target_count': latest.target_count,
                'active_downtime_events': active_events,
                'last_update': latest.timestamp
            })

    serializer = OEEDashboardSerializer(summaries, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
def trend_data(request):
    """
    Get trend data for metrics

    Query parameters:
    - line_id: Line ID (required)
    - metric: oee, availability, performance, quality (required)
    - from_time: Start time
    - to_time: End time
    - aggregation: raw, 1min, 5min, 1hour (default: raw)
    """
    line_id = request.query_params.get('line_id')
    metric = request.query_params.get('metric', 'oee')

    if not line_id:
        return Response(
            {'error': 'line_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    hours = int(request.query_params.get('hours', 24))
    from_time = timezone.now() - timedelta(hours=hours)

    metrics = ProductionMetrics.objects.filter(
        line_id=line_id,
        timestamp__gte=from_time
    ).order_by('timestamp')

    # Extract data points
    data_points = []
    for m in metrics:
        value = getattr(m, metric, None)
        if value is not None:
            data_points.append({
                'timestamp': m.timestamp,
                'value': value
            })

    trend_data = {
        'metric_name': metric,
        'data_points': data_points,
        'unit': '%',
        'aggregation': 'raw'
    }

    serializer = TrendDataSerializer(trend_data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
def machines_status(request):
    """
    Get current status of all machines

    Returns machine status overview with latest metrics and active issues

    Query parameters:
    - site_id: Filter by site
    - line_id: Filter by production line
    """
    site_id = request.query_params.get('site_id')
    line_id = request.query_params.get('line_id')

    # Get latest metrics for each machine/line
    lines = ProductionMetrics.objects.values('line_id').distinct()

    machine_statuses = []
    for line in lines:
        line_id_val = line['line_id']

        # Get latest metrics
        latest = ProductionMetrics.objects.filter(
            line_id=line_id_val
        ).order_by('-timestamp').first()

        if latest:
            # Check for active downtime events
            active_downtime = DowntimeEvent.objects.filter(
                line_id=line_id_val,
                ts__gte=timezone.now() - timedelta(hours=1)
            ).count()

            # Determine status based on metrics
            if active_downtime > 0:
                status_val = 'fault'
            elif latest.oee >= 85:
                status_val = 'running'
            elif latest.oee >= 60:
                status_val = 'degraded'
            else:
                status_val = 'stopped'

            machine_statuses.append({
                'machine_id': line_id_val,
                'status': status_val,
                'oee': latest.oee,
                'availability': latest.availability,
                'performance': latest.performance,
                'quality': latest.quality,
                'current_production': latest.actual_count,
                'target_production': latest.target_count,
                'active_faults': active_downtime,
                'last_update': latest.timestamp
            })

    # Apply filters if provided
    if site_id:
        machine_statuses = [m for m in machine_statuses if m.get('site_id') == site_id]
    if line_id:
        machine_statuses = [m for m in machine_statuses if m['machine_id'] == line_id]

    return Response({
        'count': len(machine_statuses),
        'machines': machine_statuses
    })
