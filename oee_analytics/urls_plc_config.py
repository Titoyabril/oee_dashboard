"""
URL Configuration for PLC Configuration Management
Routes for the custom web UI
"""

from django.urls import path
from . import views_plc_config

urlpatterns = [
    # Dashboard
    path('', views_plc_config.plc_config_dashboard, name='plc_config_dashboard'),

    # CRUD Operations
    path('connection/create/', views_plc_config.plc_connection_create, name='plc_connection_create'),
    path('connection/<int:pk>/edit/', views_plc_config.plc_connection_edit, name='plc_connection_edit'),
    path('connection/<int:pk>/delete/', views_plc_config.plc_connection_delete, name='plc_connection_delete'),

    # Actions
    path('connection/<int:pk>/test/', views_plc_config.plc_connection_test, name='plc_connection_test'),
    path('connection/<int:pk>/clone/', views_plc_config.plc_connection_clone, name='plc_connection_clone'),
    path('connection/<int:pk>/export/', views_plc_config.plc_connection_export, name='plc_connection_export'),
    path('connection/<int:pk>/template/<int:template_id>/', views_plc_config.plc_connection_apply_template, name='plc_connection_apply_template'),

    # Import/Export
    path('import/', views_plc_config.plc_config_import, name='plc_config_import'),
    path('export/all/', views_plc_config.plc_config_export_all, name='plc_config_export_all'),
]
