import dash
from dash import html, dcc
import plotly.express as px
import pandas as pd
from django_plotly_dash import DjangoDash

# Sample data
df = pd.DataFrame({
    "Shift": ["A", "B", "C"],
    "OEE": [82, 76, 91]
})

# Create Dash app
app = DjangoDash("SimpleExample")  # Unique name
app.layout = html.Div([
    html.H3("OEE by Shift"),
    dcc.Graph(
        figure=px.bar(df, x="Shift", y="OEE", title="Shift Performance")
    )
])
