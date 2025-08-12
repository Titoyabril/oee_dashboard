import plotly.graph_objects as go
from django_plotly_dash import DjangoDash
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import random
import json
from django.utils import timezone

# =============================================================================
# 1. OEE MAIN GAUGE
# =============================================================================

oee_gauge_app = DjangoDash("OEEMainGauge")

oee_gauge_app.layout = html.Div([
    dcc.Interval(id='oee-interval', interval=5000, n_intervals=0),
    dcc.Graph(id='main-oee-gauge', style={'height': '300px'})
])

@oee_gauge_app.callback(
    Output('main-oee-gauge', 'figure'),
    Input('oee-interval', 'n_intervals')
)
def update_oee_main_gauge(n):
    # Mock data - replace with actual database queries
    current_oee = random.uniform(80, 95)
    target_oee = 85
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current_oee,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Overall Equipment Effectiveness", 'font': {'size': 18, 'color': '#2c3e50'}},
        delta = {'reference': target_oee, 'position': "top"},
        gauge = {
            'axis': {
                'range': [None, 100],
                'tickwidth': 1,
                'tickcolor': "#34495e",
                'tickfont': {'size': 12, 'color': '#2c3e50'}
            },
            'bar': {'color': get_oee_color(current_oee), 'thickness': 0.4},
            'bgcolor': "white",
            'borderwidth': 3,
            'bordercolor': "#bdc3c7",
            'steps': [
                {'range': [0, 60], 'color': '#ffebee'},
                {'range': [60, 80], 'color': '#fff3e0'}, 
                {'range': [80, 90], 'color': '#e8f5e8'},
                {'range': [90, 100], 'color': '#e0f2f1'}
            ],
            'threshold': {
                'line': {'color': "#e74c3c", 'width': 4},
                'thickness': 0.75,
                'value': target_oee
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={'color': "#2c3e50", 'family': "Arial, sans-serif"},
        height=300,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

# =============================================================================
# 2. OEE COMPONENT GAUGES (Availability, Performance, Quality)
# =============================================================================

oee_components_app = DjangoDash("OEEComponents")

oee_components_app.layout = html.Div([
    dcc.Interval(id='components-interval', interval=5000, n_intervals=0),
    html.Div([
        html.Div([
            dcc.Graph(id='availability-gauge', style={'height': '250px'})
        ], className='col-md-4'),
        html.Div([
            dcc.Graph(id='performance-gauge', style={'height': '250px'})
        ], className='col-md-4'),
        html.Div([
            dcc.Graph(id='quality-gauge', style={'height': '250px'})
        ], className='col-md-4')
    ], className='row')
])

@oee_components_app.callback(
    [Output('availability-gauge', 'figure'),
     Output('performance-gauge', 'figure'), 
     Output('quality-gauge', 'figure')],
    Input('components-interval', 'n_intervals')
)
def update_component_gauges(n):
    # Mock data - replace with actual calculations
    availability = random.uniform(85, 98)
    performance = random.uniform(80, 95)
    quality = random.uniform(90, 99)
    
    def create_component_gauge(value, title, color):
        return go.Figure(go.Indicator(
            mode = "gauge+number",
            value = value,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': title, 'font': {'size': 16}},
            gauge = {
                'axis': {'range': [0, 100], 'tickfont': {'size': 10}},
                'bar': {'color': color, 'thickness': 0.3},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "#ecf0f1",
                'steps': [
                    {'range': [0, 80], 'color': '#ffebee'},
                    {'range': [80, 95], 'color': '#e8f5e8'}
                ]
            }
        )).update_layout(
            height=250,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            font={'color': "#2c3e50"}
        )
    
    availability_fig = create_component_gauge(availability, "Availability", "#27ae60")
    performance_fig = create_component_gauge(performance, "Performance", "#3498db") 
    quality_fig = create_component_gauge(quality, "Quality", "#9b59b6")
    
    return availability_fig, performance_fig, quality_fig

# =============================================================================
# 3. PERFORMANCE TIMELINE
# =============================================================================

performance_timeline_app = DjangoDash("PerformanceTimeline")

performance_timeline_app.layout = html.Div([
    dcc.Interval(id='timeline-interval', interval=10000, n_intervals=0),
    dcc.Graph(id='performance-timeline-chart', style={'height': '350px'})
])

@performance_timeline_app.callback(
    Output('performance-timeline-chart', 'figure'),
    Input('timeline-interval', 'n_intervals')
)
def update_performance_timeline(n):
    # Generate time series data for the last 8 hours
    now = datetime.now()
    times = [now - timedelta(hours=i) for i in range(8, 0, -1)]
    oee_values = [random.uniform(75, 95) for _ in times]
    availability_values = [random.uniform(85, 98) for _ in times]
    performance_values = [random.uniform(80, 95) for _ in times]
    quality_values = [random.uniform(90, 99) for _ in times]
    target = [85] * len(times)
    
    fig = go.Figure()
    
    # Add OEE line with markers
    fig.add_trace(go.Scatter(
        x=times, 
        y=oee_values,
        mode='lines+markers',
        name='OEE',
        line=dict(color='#2980b9', width=3),
        marker=dict(size=8, color='#2980b9'),
        hovertemplate='<b>%{fullData.name}</b><br>Time: %{x}<br>Value: %{y:.1f}%<extra></extra>'
    ))
    
    # Add component traces
    fig.add_trace(go.Scatter(
        x=times, y=availability_values, mode='lines', name='Availability',
        line=dict(color='#27ae60', width=2, dash='dot'),
        hovertemplate='<b>%{fullData.name}</b><br>Time: %{x}<br>Value: %{y:.1f}%<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=times, y=performance_values, mode='lines', name='Performance', 
        line=dict(color='#3498db', width=2, dash='dot'),
        hovertemplate='<b>%{fullData.name}</b><br>Time: %{x}<br>Value: %{y:.1f}%<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=times, y=quality_values, mode='lines', name='Quality',
        line=dict(color='#9b59b6', width=2, dash='dot'), 
        hovertemplate='<b>%{fullData.name}</b><br>Time: %{x}<br>Value: %{y:.1f}%<extra></extra>'
    ))
    
    # Add target line
    fig.add_trace(go.Scatter(
        x=times, y=target, mode='lines', name='Target',
        line=dict(color='#e74c3c', width=2, dash='dash'),
        hovertemplate='Target: %{y}%<extra></extra>'
    ))
    
    # Fill area where OEE is above target
    above_target = [max(oee, 85) if oee > 85 else None for oee in oee_values]
    below_target = [min(oee, 85) if oee <= 85 else None for oee in oee_values]
    
    fig.add_trace(go.Scatter(
        x=times, y=above_target, fill='tonexty', fillcolor='rgba(39, 174, 96, 0.2)',
        line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
    ))
    
    fig.update_layout(
        title={
            'text': 'OEE Performance Trend (Last 8 Hours)',
            'x': 0.5,
            'font': {'size': 18, 'color': '#2c3e50'}
        },
        xaxis_title="Time",
        yaxis_title="Percentage (%)",
        yaxis=dict(range=[65, 100], tickformat='.0f'),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        font={'color': "#2c3e50", 'family': "Arial, sans-serif"},
        height=350,
        margin=dict(l=60, r=30, t=60, b=50),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right", 
            x=1
        )
    )
    
    # Add grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(236, 240, 241, 0.8)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(236, 240, 241, 0.8)')
    
    return fig

# =============================================================================
# 4. DOWNTIME PARETO CHART
# =============================================================================

downtime_pareto_app = DjangoDash("DowntimePareto")

downtime_pareto_app.layout = html.Div([
    dcc.Interval(id='pareto-interval', interval=15000, n_intervals=0),
    dcc.Graph(id='downtime-pareto-chart', style={'height': '400px'})
])

@downtime_pareto_app.callback(
    Output('downtime-pareto-chart', 'figure'),
    Input('pareto-interval', 'n_intervals')
)
def update_downtime_pareto(n):
    # Mock downtime data
    reasons = ['Mechanical Fault', 'Material Shortage', 'Changeover', 'Electrical Issue', 'Quality Check', 'Maintenance', 'Other']
    durations = [45, 32, 28, 15, 12, 8, 5]  # minutes
    
    # Calculate cumulative percentage
    total = sum(durations)
    cumulative = []
    running_total = 0
    for duration in durations:
        running_total += duration
        cumulative.append((running_total / total) * 100)
    
    # Create Pareto chart
    fig = go.Figure()
    
    # Bar chart for durations
    fig.add_trace(go.Bar(
        x=reasons,
        y=durations,
        name='Downtime (min)',
        marker_color='#e74c3c',
        yaxis='y',
        hovertemplate='<b>%{x}</b><br>Duration: %{y} minutes<extra></extra>'
    ))
    
    # Line chart for cumulative percentage
    fig.add_trace(go.Scatter(
        x=reasons,
        y=cumulative,
        mode='lines+markers',
        name='Cumulative %',
        line=dict(color='#f39c12', width=3),
        marker=dict(size=8, color='#f39c12'),
        yaxis='y2',
        hovertemplate='<b>Cumulative</b><br>%{y:.1f}%<extra></extra>'
    ))
    
    # Add 80% line for Pareto principle
    fig.add_hline(y=80, line_dash="dash", line_color="#95a5a6", 
                  annotation_text="80% Line", annotation_position="bottom right")
    
    fig.update_layout(
        title={
            'text': 'Downtime Analysis - Pareto Chart (Today)',
            'x': 0.5,
            'font': {'size': 18, 'color': '#2c3e50'}
        },
        xaxis_title="Downtime Reasons",
        yaxis=dict(
            title="Duration (minutes)",
            side="left",
            color="#2c3e50"
        ),
        yaxis2=dict(
            title="Cumulative Percentage (%)",
            side="right",
            overlaying="y",
            color="#f39c12",
            range=[0, 100]
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        font={'color': "#2c3e50", 'family': "Arial, sans-serif"},
        height=400,
        margin=dict(l=60, r=60, t=60, b=100),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Rotate x-axis labels for better readability
    fig.update_xaxes(tickangle=45, showgrid=True, gridwidth=1, gridcolor='rgba(236, 240, 241, 0.8)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(236, 240, 241, 0.8)')
    
    return fig

# =============================================================================
# 5. PRODUCTION COUNTER
# =============================================================================

production_counter_app = DjangoDash("ProductionCounter")

production_counter_app.layout = html.Div([
    dcc.Interval(id='counter-interval', interval=2000, n_intervals=0),
    html.Div(id='production-metrics', style={'height': '200px'})
])

@production_counter_app.callback(
    Output('production-metrics', 'children'),
    Input('counter-interval', 'n_intervals')
)
def update_production_counter(n):
    # Mock production data
    current_count = random.randint(2800, 3000)
    target_count = 3000
    good_parts = random.randint(2750, current_count)
    rejected_parts = current_count - good_parts
    
    progress_percentage = (current_count / target_count) * 100
    quality_rate = (good_parts / current_count) * 100 if current_count > 0 else 0
    
    return html.Div([
        html.Div([
            html.H2(f"{current_count:,}", className="display-4 text-primary mb-0"),
            html.P("Units Produced", className="text-muted mb-2"),
            html.Div([
                html.Div(className="progress-bar bg-success", 
                        style={'width': f'{min(progress_percentage, 100)}%'},
                        role="progressbar")
            ], className="progress mb-2", style={'height': '8px'}),
            html.P(f"{progress_percentage:.1f}% of target ({target_count:,})", className="small text-muted")
        ], className="text-center mb-3"),
        
        html.Div([
            html.Div([
                html.H5(f"{good_parts:,}", className="text-success mb-0"),
                html.P("Good Parts", className="small text-muted")
            ], className="col-6 text-center"),
            html.Div([
                html.H5(f"{rejected_parts}", className="text-danger mb-0"),
                html.P("Rejected", className="small text-muted")
            ], className="col-6 text-center")
        ], className="row"),
        
        html.Div([
            html.P(f"Quality Rate: {quality_rate:.1f}%", 
                  className=f"text-center mb-0 {'text-success' if quality_rate >= 95 else 'text-warning' if quality_rate >= 90 else 'text-danger'}")
        ])
    ], className="p-3", style={'backgroundColor': '#f8f9fa', 'borderRadius': '8px'})

# =============================================================================
# 6. MACHINE STATUS GRID
# =============================================================================

machine_status_app = DjangoDash("MachineStatus")

machine_status_app.layout = html.Div([
    dcc.Interval(id='machine-interval', interval=3000, n_intervals=0),
    html.Div(id='machine-status-grid')
])

@machine_status_app.callback(
    Output('machine-status-grid', 'children'),
    Input('machine-interval', 'n_intervals')
)
def update_machine_status(n):
    machines = [
        {'name': 'Filler #1', 'status': random.choice(['running', 'stopped', 'warning'])},
        {'name': 'Capper #1', 'status': random.choice(['running', 'stopped', 'warning'])},
        {'name': 'Labeler #1', 'status': random.choice(['running', 'stopped', 'warning'])},
        {'name': 'Packager #1', 'status': random.choice(['running', 'stopped', 'warning'])},
        {'name': 'Conveyor A', 'status': random.choice(['running', 'stopped', 'warning'])},
        {'name': 'Conveyor B', 'status': random.choice(['running', 'stopped', 'warning'])}
    ]
    
    def get_status_color(status):
        return {
            'running': '#27ae60',
            'stopped': '#e74c3c', 
            'warning': '#f39c12'
        }.get(status, '#95a5a6')
    
    def get_status_icon(status):
        return {
            'running': 'fas fa-play',
            'stopped': 'fas fa-stop',
            'warning': 'fas fa-exclamation-triangle'
        }.get(status, 'fas fa-question')
    
    machine_cards = []
    for machine in machines:
        card = html.Div([
            html.Div([
                html.I(className=f"{get_status_icon(machine['status'])} fa-2x mb-2",
                      style={'color': get_status_color(machine['status'])}),
                html.H6(machine['name'], className="mb-1"),
                html.P(machine['status'].title(), className="small mb-0",
                      style={'color': get_status_color(machine['status'])})
            ], className="text-center p-3")
        ], className="col-md-4 col-sm-6 mb-3")
        machine_cards.append(card)
    
    return html.Div(machine_cards, className="row")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_oee_color(oee_value):
    """Return color based on OEE value"""
    if oee_value >= 90:
        return "#27ae60"  # Excellent - Green
    elif oee_value >= 80:
        return "#3498db"  # Good - Blue  
    elif oee_value >= 70:
        return "#f39c12"  # Warning - Orange
    else:
        return "#e74c3c"  # Critical - Red