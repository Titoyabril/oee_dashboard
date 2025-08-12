import plotly.graph_objects as go
from django_plotly_dash import DjangoDash
from dash import dcc, html, Input, Output
import plotly.express as px

# OEE Main Gauge
app1 = DjangoDash("OEEGauge")

app1.layout = html.Div([
    dcc.Interval(id='interval-component', interval=5000, n_intervals=0),
    dcc.Graph(id='oee-gauge-chart', style={'height': '350px'})
])

@app1.callback(
    Output('oee-gauge-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_oee_gauge(n):
    # Get current OEE (in production, fetch from database)
    current_oee = 85.3
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current_oee,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Current OEE", 'font': {'size': 24, 'color': '#2c3e50'}},
        delta = {'reference': 85, 'position': "top"},
        gauge = {
            'axis': {
                'range': [None, 100],
                'tickwidth': 1,
                'tickcolor': "darkblue",
                'tickfont': {'size': 14}
            },
            'bar': {'color': get_oee_color(current_oee), 'thickness': 0.3},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 60], 'color': '#ffebee'},
                {'range': [60, 80], 'color': '#fff3e0'},
                {'range': [80, 90], 'color': '#e8f5e8'},
                {'range': [90, 100], 'color': '#e0f2f1'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 85
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={'color': "#2c3e50", 'family': "Arial"},
        height=350,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    return fig

def get_oee_color(oee_value):
    """Return color based on OEE value"""
    if oee_value >= 90:
        return "#28a745"  # Excellent - Green
    elif oee_value >= 80:
        return "#17a2b8"  # Good - Blue  
    elif oee_value >= 70:
        return "#ffc107"  # Warning - Yellow
    else:
        return "#dc3545"  # Critical - Red


# Performance Timeline
app2 = DjangoDash("PerformanceTimeline")

app2.layout = html.Div([
    dcc.Interval(id='timeline-interval', interval=10000, n_intervals=0),
    dcc.Graph(id='performance-timeline-chart', style={'height': '300px'})
])

@app2.callback(
    Output('performance-timeline-chart', 'figure'),
    Input('timeline-interval', 'n_intervals')
)
def update_performance_timeline(n):
    # Mock data - replace with actual database queries
    hours = ['6:00', '7:00', '8:00', '9:00', '10:00', '11:00', '12:00', '13:00', '14:00']
    oee_values = [88, 92, 85, 78, 91, 89, 94, 87, 85]
    target = [85] * len(hours)
    
    fig = go.Figure()
    
    # Add OEE line
    fig.add_trace(go.Scatter(
        x=hours, 
        y=oee_values,
        mode='lines+markers',
        name='OEE',
        line=dict(color='#007bff', width=3),
        marker=dict(size=8, color='#007bff'),
        hovertemplate='Time: %{x}<br>OEE: %{y}%<extra></extra>'
    ))
    
    # Add target line
    fig.add_trace(go.Scatter(
        x=hours, 
        y=target,
        mode='lines',
        name='Target',
        line=dict(color='red', width=2, dash='dash'),
        hovertemplate='Target: %{y}%<extra></extra>'
    ))
    
    # Fill area where OEE is above target
    above_target = [max(oee, 85) if oee > 85 else 85 for oee in oee_values]
    fig.add_trace(go.Scatter(
        x=hours + hours[::-1],
        y=above_target + target[::-1],
        fill='toself',
        fillcolor='rgba(40, 167, 69, 0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        title={
            'text': 'OEE Performance Today',
            'x': 0.5,
            'font': {'size': 16, 'color': '#2c3e50'}
        },
        xaxis_title="Time",
        yaxis_title="OEE %",
        yaxis=dict(range=[70, 100]),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={'color': "#2c3e50"},
        height=300,
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode='x unified'
    )
    
    return fig