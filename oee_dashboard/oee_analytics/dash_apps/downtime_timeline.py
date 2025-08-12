import pandas as pd, plotly.express as px
from django_plotly_dash import DjangoDash
from dash import dcc, html, Output, Input
from datetime import timedelta
from django.utils import timezone
from oee_analytics.events.models import DowntimeEvent

app = DjangoDash("DowntimeTimeline")
app.layout = html.Div([
    dcc.Interval(id="tick", interval=2_000, n_intervals=0),
    dcc.Dropdown(id="window", options=[
        {"label":"Last 15 min", "value":"15"},
        {"label":"Last 60 min", "value":"60"},
        {"label":"Last 8 hr", "value":"480"},
    ], value="60", clearable=False, style={"width":"200px","marginBottom":"8px"}),
    dcc.Graph(id="timeline", config={"displayModeBar": False}),
])

@app.callback(Output("timeline","figure"), [Input("tick","n_intervals"), Input("window","value")])
def _update(_, minutes):
    try:
        minutes = int(minutes or 60)
    except Exception:
        minutes = 60
    since = timezone.now() - timedelta(minutes=minutes)
    qs = DowntimeEvent.objects.filter(ts__gte=since).order_by("ts").values(
        "ts","line_id","station_id","reason","detail","severity","duration_s"
    )
    df = pd.DataFrame(list(qs))
    if df.empty:
        empty = pd.DataFrame({"start":[],"finish":[],"lane":[]})
        return px.timeline(empty, x_start="start", x_end="finish", y="lane").update_layout(height=300)

    df["start"] = pd.to_datetime(df["ts"])
    df["finish"] = df["start"] + pd.to_timedelta(df["duration_s"].fillna(0.1), unit="s")
    df["lane"] = df["station_id"].replace("", "LINE")
    fig = px.timeline(df, x_start="start", x_end="finish", y="lane", color="reason", hover_data=["detail","severity"])
    fig.update_layout(height=340, margin=dict(l=20,r=20,t=10,b=10), legend_orientation="h")
    fig.update_yaxes(title=None)
    fig.update_xaxes(title=None)
    return fig
