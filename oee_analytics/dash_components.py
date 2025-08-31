"""
Reusable Dash components for the OEE Dashboard
Phase 2: Converting HTML dashboard sections to Dash/Plotly components
"""

from dash import dcc, html
import plotly.graph_objs as go
import plotly.express as px
import numpy as np


def create_kpi_card(title, value, metric_id, sparkline_data=None, indicator_text="", indicator_color="green"):
    """
    Create a KPI card component matching the original dashboard design
    
    Args:
        title: KPI title (e.g., "Availability")
        value: Current value (e.g., "95%")
        metric_id: Unique ID for callbacks
        sparkline_data: List of values for sparkline
        indicator_text: Change indicator (e.g., "+2.5")
        indicator_color: Color for indicator ("green" or "red")
    """
    
    # Create sparkline figure if data provided
    sparkline_fig = None
    if sparkline_data:
        sparkline_fig = go.Figure()
        sparkline_fig.add_trace(go.Scatter(
            y=sparkline_data,
            mode='lines',
            line=dict(color='#007bff', width=2),
            fill='tozeroy',
            fillcolor='rgba(0, 123, 255, 0.1)',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Add dots for min/max points
        min_idx = sparkline_data.index(min(sparkline_data))
        max_idx = sparkline_data.index(max(sparkline_data))
        
        sparkline_fig.add_trace(go.Scatter(
            x=[min_idx],
            y=[sparkline_data[min_idx]],
            mode='markers',
            marker=dict(color='red', size=4),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        sparkline_fig.add_trace(go.Scatter(
            x=[max_idx],
            y=[sparkline_data[max_idx]],
            mode='markers',
            marker=dict(color='green', size=4),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        sparkline_fig.update_layout(
            height=40,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False)
        )
    
    # Build the card
    card = html.Div([
        # Header
        html.Div([
            html.Span(title, className='kpi-label', 
                     style={'fontSize': '14px', 'color': '#6c757d', 'fontWeight': '500', 'textTransform': 'uppercase'})
        ], className='kpi-header', style={'marginBottom': '10px'}),
        
        # Main value
        html.Div([
            html.Div(value, id=f'{metric_id}-value', className='kpi-value',
                    style={
                        'fontSize': '4.5rem',
                        'fontWeight': '700',
                        'color': '#007bff' if 'oee' in metric_id.lower() else '#2d3748',
                        'lineHeight': '1'
                    })
        ], className='kpi-main', style={'marginBottom': '15px'}),
        
        # Sparkline and indicators
        html.Div([
            dcc.Graph(
                figure=sparkline_fig,
                config={'displayModeBar': False},
                style={'height': '40px', 'marginBottom': '5px'}
            ) if sparkline_fig else None,
            
            # Mini indicators
            html.Div([
                html.Span(indicator_text, 
                         style={
                             'fontSize': '12px',
                             'color': '#28a745' if indicator_color == 'green' else '#dc3545',
                             'fontWeight': '600',
                             'float': 'right'
                         })
            ], className='mini-indicators') if indicator_text else None
        ], className='kpi-sparkline-container')
    ], className='kpi-card', 
    style={
        'backgroundColor': 'white',
        'borderRadius': '12px',
        'padding': '20px',
        'height': '100%',
        'boxShadow': '0 4px 12px rgba(0,0,0,0.1)',
        'display': 'flex',
        'flexDirection': 'column',
        'justifyContent': 'space-between'
    })
    
    return card


def create_trend_chart(time_window="4 Hours", trend_data=None):
    """
    Create the trend chart component for the right side of KPI row
    """
    if trend_data is None:
        # Generate sample data
        trend_data = [82, 84, 83, 85, 87, 86, 88, 85, 87, 86, 85, 85.3]
    
    fig = go.Figure()
    
    # Add area fill
    fig.add_trace(go.Scatter(
        y=trend_data,
        mode='lines',
        line=dict(color='#28a745', width=2),
        fill='tozeroy',
        fillcolor='rgba(40, 167, 69, 0.2)',
        name='OEE Trend',
        hovertemplate='OEE: %{y:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        height=120,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor='white',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#e9ecef', showticklabels=False, zeroline=False),
        showlegend=False,
        title=dict(
            text=time_window,
            font=dict(size=14, color='#6c757d'),
            x=0.5,
            xanchor='center'
        )
    )
    
    trend_card = html.Div([
        dcc.Graph(
            id='trend-chart',
            figure=fig,
            config={'displayModeBar': False}
        ),
        html.Div([
            html.Span("↑ 0.8%", style={'color': '#28a745', 'fontWeight': 'bold', 'fontSize': '14px'}),
            html.Span(" vs prev", style={'color': '#6c757d', 'fontSize': '12px', 'marginLeft': '5px'})
        ], style={'textAlign': 'center', 'marginTop': '10px'})
    ], className='trend-card',
    style={
        'backgroundColor': 'white',
        'borderRadius': '12px',
        'padding': '15px',
        'height': '100%',
        'boxShadow': '0 4px 12px rgba(0,0,0,0.1)'
    })
    
    return trend_card


def create_top_kpi_section():
    """
    Create the complete top KPI section with all cards
    """
    # Sample sparkline data for each metric
    availability_sparkline = [88, 90, 92, 89, 93, 91, 95]
    performance_sparkline = [92, 88, 90, 87, 89, 90, 88]
    quality_sparkline = [94, 96, 95, 97, 95, 96, 98]
    oee_sparkline = [82, 84, 86, 83, 87, 85, 82]
    
    section = html.Div([
        html.Div([
            # Availability Card
            html.Div([
                create_kpi_card(
                    title="Availability",
                    value="95%",
                    metric_id="availability",
                    sparkline_data=availability_sparkline,
                    indicator_text="+2.5",
                    indicator_color="green"
                )
            ], className='col-3'),
            
            # Performance Card
            html.Div([
                create_kpi_card(
                    title="Performance",
                    value="88%",
                    metric_id="performance",
                    sparkline_data=performance_sparkline,
                    indicator_text="-1.2",
                    indicator_color="red"
                )
            ], className='col-2'),
            
            # Quality Card
            html.Div([
                create_kpi_card(
                    title="Quality",
                    value="98%",
                    metric_id="quality",
                    sparkline_data=quality_sparkline,
                    indicator_text="+0.8",
                    indicator_color="green"
                )
            ], className='col-2'),
            
            # Overall OEE Card
            html.Div([
                create_kpi_card(
                    title="Overall OEE",
                    value="82%",
                    metric_id="oee",
                    sparkline_data=oee_sparkline,
                    indicator_text="+1.5",
                    indicator_color="green"
                )
            ], className='col-3'),
            
            # Trend Chart
            html.Div([
                create_trend_chart("4 Hours")
            ], className='col-2'),
            
        ], className='row gx-2 h-100')
    ], className='kpi-row container-fluid', 
    style={
        'height': '22vh',
        'minHeight': '170px',
        'maxHeight': '220px',
        'padding': '1rem',
        'backgroundColor': '#f8f9fa',
        'overflow': 'hidden'  # Prevent content overflow - KEY FIX
    })
    
    return section