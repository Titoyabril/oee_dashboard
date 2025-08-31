"""
Main Dash application for OEE Dashboard - Phase 2
Converting the complete 3-section dashboard to Dash/Plotly components
"""

from django_plotly_dash import DjangoDash
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from .dash_components import create_top_kpi_section

# Create the Django Dash application for Phase 2
app = DjangoDash('OEEDashboardPhase2', 
                 add_bootstrap_links=True,
                 external_stylesheets=[
                     'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
                 ],
                 external_scripts=[])

# Define the app layout - Phase 2: Starting with Top KPI Section
app.layout = html.Div([
    # Header
    html.Div([
        html.H2("OEE Dashboard - Phase 2: Top KPI Section", 
                style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '10px'}),
        html.P("Dash/Plotly version with real components", 
               style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '14px', 'marginBottom': '20px'}),
    ], style={'padding': '15px', 'backgroundColor': '#ecf0f1'}),
    
    # Phase 2: Top KPI Section
    create_top_kpi_section(),
    
    # Placeholder for future sections
    html.Div([
        html.P("Middle Section - Coming in Phase 2b", 
               style={'textAlign': 'center', 'color': '#6c757d', 'fontSize': '16px', 'padding': '40px'})
    ], style={'backgroundColor': '#f8f9fa', 'marginTop': '20px'}),
    
    html.Div([
        html.P("Bottom Machine Rail - Coming in Phase 2c", 
               style={'textAlign': 'center', 'color': '#6c757d', 'fontSize': '16px', 'padding': '40px'})
    ], style={'backgroundColor': '#e9ecef', 'marginTop': '20px'}),
    
    # Auto-refresh component for real-time updates
    dcc.Interval(
        id='interval-component',
        interval=5000,  # Update every 5 seconds
        n_intervals=0
    ),
])

# Callback to update KPI values with simulated real-time data
@app.callback(
    [Output('availability-value', 'children'),
     Output('performance-value', 'children'),
     Output('quality-value', 'children'),
     Output('oee-value', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_kpi_values(n):
    """Update all KPI values with simulated real-time data"""
    # Generate realistic variations around base values
    base_values = {'availability': 95, 'performance': 88, 'quality': 98, 'oee': 82}
    
    updated_values = {}
    for metric, base in base_values.items():
        variation = np.random.normal(0, 1.5)  # Small random variation
        new_value = max(75, min(100, base + variation))  # Keep within reasonable bounds
        updated_values[metric] = f"{new_value:.1f}%"
    
    return (
        updated_values['availability'],
        updated_values['performance'],
        updated_values['quality'],
        updated_values['oee']
    )

# Future: Additional callbacks for Middle and Bottom sections will be added here

# Placeholder for Celery integration
def get_real_time_metrics():
    """
    Future: This will integrate with Celery tasks to get real OEE data
    For Phase 2, using simulated data
    """
    return {
        'availability': 95.0,
        'performance': 88.0,
        'quality': 98.0,
        'oee': 82.0,
        'timestamp': datetime.now()
    }