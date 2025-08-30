"""
Main Dash application for OEE Dashboard
This will replace the HTML/Canvas dashboard with Plotly Dash components
"""

from django_plotly_dash import DjangoDash
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Create the Django Dash application
app = DjangoDash('OEEDashboard', 
                 add_bootstrap_links=True,
                 external_stylesheets=[],
                 external_scripts=[])

# Define the app layout - starting with a simple test component
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("OEE Dashboard - Dash/Plotly Version", 
                style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),
        html.P("Phase 1: Testing Dash Integration", 
               style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '18px'}),
    ], style={'padding': '20px', 'backgroundColor': '#ecf0f1'}),
    
    # Test Component - Simple KPI Card
    html.Div([
        html.Div([
            html.Div([
                html.H3("Test KPI", style={'color': '#34495e', 'marginBottom': '10px'}),
                html.H1(id='test-kpi-value', children="85.3%", 
                       style={'color': '#3498db', 'fontSize': '48px', 'fontWeight': 'bold'}),
                html.P("Overall Equipment Effectiveness", style={'color': '#7f8c8d'}),
            ], className='card-body', style={'textAlign': 'center', 'padding': '30px'}),
        ], className='card', style={'boxShadow': '0 4px 6px rgba(0,0,0,0.1)', 'marginBottom': '20px'}),
    ], style={'maxWidth': '400px', 'margin': '0 auto', 'padding': '20px'}),
    
    # Test Graph - Simple line chart
    html.Div([
        dcc.Graph(
            id='test-graph',
            figure={
                'data': [
                    go.Scatter(
                        x=list(range(10)),
                        y=[85, 87, 86, 88, 85, 89, 87, 90, 88, 85.3],
                        mode='lines+markers',
                        name='OEE Trend',
                        line=dict(color='#3498db', width=3),
                        marker=dict(size=8)
                    )
                ],
                'layout': go.Layout(
                    title='OEE Trend - Last 10 Hours',
                    xaxis={'title': 'Hour'},
                    yaxis={'title': 'OEE %', 'range': [80, 95]},
                    height=300,
                    margin={'l': 50, 'r': 50, 't': 50, 'b': 50}
                )
            }
        )
    ], style={'maxWidth': '800px', 'margin': '0 auto', 'padding': '20px'}),
    
    # Auto-refresh component for testing real-time updates
    dcc.Interval(
        id='interval-component',
        interval=5000,  # Update every 5 seconds
        n_intervals=0
    ),
    
    # Hidden div to store intermediate values (for testing)
    html.Div(id='intermediate-value', style={'display': 'none'})
])

# Test callback - Update KPI value with random variation
@app.callback(
    Output('test-kpi-value', 'children'),
    [Input('interval-component', 'n_intervals')]
)
def update_kpi_value(n):
    """Simulate real-time KPI updates"""
    # Generate a random OEE value between 82 and 90
    base_value = 85.3
    variation = np.random.normal(0, 2)  # Random variation
    new_value = max(80, min(95, base_value + variation))  # Keep between 80-95
    return f"{new_value:.1f}%"

# Test callback - Update graph with new data point
@app.callback(
    Output('test-graph', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    """Update graph with simulated real-time data"""
    # Generate time series data
    hours = list(range(10))
    
    # Simulate OEE values with some randomness
    np.random.seed(n)  # For reproducibility in testing
    oee_values = [85 + np.random.normal(0, 3) for _ in range(10)]
    oee_values[-1] = 85.3  # Current value
    
    figure = {
        'data': [
            go.Scatter(
                x=hours,
                y=oee_values,
                mode='lines+markers',
                name='OEE Trend',
                line=dict(color='#3498db', width=3),
                marker=dict(size=8),
                hovertemplate='Hour: %{x}<br>OEE: %{y:.1f}%<extra></extra>'
            )
        ],
        'layout': go.Layout(
            title=f'OEE Trend - Last 10 Hours (Update #{n})',
            xaxis={'title': 'Hour', 'gridcolor': '#ecf0f1'},
            yaxis={'title': 'OEE %', 'range': [75, 95], 'gridcolor': '#ecf0f1'},
            height=300,
            margin={'l': 50, 'r': 50, 't': 50, 'b': 50},
            plot_bgcolor='white',
            paper_bgcolor='#f8f9fa',
            hovermode='x unified'
        )
    }
    
    return figure

# Placeholder for future Celery integration
def get_celery_data():
    """
    Future: This function will fetch data from Celery tasks
    For now, returns mock data
    """
    return {
        'oee': 85.3,
        'availability': 92.5,
        'performance': 89.1,
        'quality': 95.8,
        'timestamp': datetime.now()
    }

# Note: Additional callbacks and components will be added in Phase 2
# This is just the foundation for testing Dash integration