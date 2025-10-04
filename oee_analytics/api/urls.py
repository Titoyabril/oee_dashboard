"""
API URL Configuration for OEE Analytics
Routes for REST and GraphQL endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from graphene_django.views import GraphQLView

from .views import (
    ProductionMetricsViewSet, DowntimeEventViewSet,
    SparkplugNodeViewSet, SparkplugDeviceViewSet, SparkplugMetricViewSet,
    MLModelRegistryViewSet, MLInferenceViewSet,
    dashboard_summary, trend_data, machines_status, api_documentation
)
from .views_plc import MachineConfigurationViewSet, test_plc_connection_standalone, discover_plcs, scan_network, discover_tags_standalone

# Try to import SQL Server viewsets
try:
    from .views import (
        PlantViewSet, AreaViewSet,
        ProductionLineViewSet, MachineViewSet
    )
    HAS_SQL_SERVER_MODELS = True
except ImportError:
    HAS_SQL_SERVER_MODELS = False


# ============================================================================
# REST API Router
# ============================================================================

router = DefaultRouter()

# Configuration endpoints (if SQL Server models available)
if HAS_SQL_SERVER_MODELS:
    router.register(r'plants', PlantViewSet, basename='plant')
    router.register(r'areas', AreaViewSet, basename='area')
    router.register(r'lines', ProductionLineViewSet, basename='line')
    router.register(r'machines', MachineViewSet, basename='machine')

# Metrics endpoints
router.register(r'metrics', ProductionMetricsViewSet, basename='metrics')
router.register(r'downtime', DowntimeEventViewSet, basename='downtime')

# Sparkplug endpoints
router.register(r'sparkplug/nodes', SparkplugNodeViewSet, basename='sparkplug-node')
router.register(r'sparkplug/devices', SparkplugDeviceViewSet, basename='sparkplug-device')
router.register(r'sparkplug/metrics', SparkplugMetricViewSet, basename='sparkplug-metric')

# ML endpoints
router.register(r'ml/models', MLModelRegistryViewSet, basename='ml-model')
router.register(r'ml/predictions', MLInferenceViewSet, basename='ml-prediction')

# PLC Configuration endpoints
router.register(r'plc/machines', MachineConfigurationViewSet, basename='plc-machine')


# ============================================================================
# URL Patterns
# ============================================================================

urlpatterns = [
    # API Documentation
    path('docs/', api_documentation, name='api-docs'),

    # REST API
    path('', include(router.urls)),

    # Dashboard endpoints
    path('dashboard/summary/', dashboard_summary, name='dashboard-summary'),
    path('dashboard/trend/', trend_data, name='trend-data'),

    # REST API CRUD endpoints (clean aliases)
    path('kpi/current/', dashboard_summary, name='kpi-current'),
    path('trend/', trend_data, name='trend'),
    path('machines/status/', machines_status, name='machines-status'),

    # PLC Configuration standalone endpoints
    path('plc/test-connection/', test_plc_connection_standalone, name='test-plc-connection'),
    path('plc/discover/', discover_plcs, name='discover-plcs'),
    path('plc/scan-network/', scan_network, name='scan-network'),
    path('plc/discover-tags/', discover_tags_standalone, name='discover-tags'),

    # Authentication
    path('auth/token/', obtain_auth_token, name='api-token'),

    # GraphQL
    path('graphql/', GraphQLView.as_view(graphiql=True), name='graphql'),
]
