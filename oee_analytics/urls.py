from django.urls import path
from . import views
from . import views_plc_monitor

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new-dashboard/', views.new_dashboard, name='new_dashboard'),
    path('threejs-dashboard/', views.threejs_dashboard, name='threejs_dashboard'),  # Three.js version
    path('threejs-dashboard-clone/', views.threejs_dashboard_clone, name='threejs_dashboard_clone'),  # Clone for development
    path('dataflow-monitor/', views.dataflow_monitor, name='dataflow_monitor'),  # Data flow monitoring dashboard

    # PLC Real-time Monitoring
    path('plc-monitor/', views_plc_monitor.plc_monitor_dashboard, name='plc_monitor_dashboard'),
    path('plc-monitor/stream/', views_plc_monitor.plc_stream, name='plc_stream'),
    path('api/plc-data/', views_plc_monitor.plc_data_api, name='plc_data_api'),
    path('shifts/', views.dashboard, name='shifts'),  # Placeholder
    path('challenges/', views.dashboard, name='challenges'),  # Placeholder
    path('achievements/', views.dashboard, name='achievements'),  # Placeholder
    path('leaderboard/', views.dashboard, name='leaderboard'),  # Placeholder
    path('training/', views.dashboard, name='training'),  # Placeholder
    path('profile/', views.dashboard, name='profile'),  # Placeholder
    path('settings/', views.dashboard, name='settings'),  # Placeholder
    path('api/current-metrics/', views.current_metrics_api, name='current_metrics_api'),
    path('api/trigger-event/', views.trigger_event_api, name='trigger_event_api'),
    path('api/trigger-oee/', views.trigger_oee_calculation, name='trigger_oee_calculation'),
    
    # ML API Endpoints (Phase 2)
    path('api/ml/forecast/oee/', views.ml_forecast_oee, name='ml_forecast_oee'),
    path('api/ml/score/quality/', views.ml_score_quality, name='ml_score_quality'),
    path('api/ml/predict/downtime/', views.ml_predict_downtime, name='ml_predict_downtime'),
    path('api/ml/explain/', views.ml_explain_prediction, name='ml_explain_prediction'),
    path('api/ml/features/current/', views.ml_features_current, name='ml_features_current'),
    path('api/ml/trigger/', views.ml_trigger_pipeline, name='ml_trigger_pipeline'),
]
