from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new-dashboard/', views.new_dashboard, name='new_dashboard'),
    path('threejs-dashboard/', views.threejs_dashboard, name='threejs_dashboard'),  # Three.js version
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
]
