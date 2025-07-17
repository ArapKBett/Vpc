# AEGIS-SHIELD :: Metric Guard :: Resilience Dashboard
# Path: /testing_framework/metric_guard/dashboard/dashboard.py
import dash
from dash import dcc, html
import pandas as pd
import plotly.express as px
import datetime

CODENAME = "RESILIENCE-VIEW"
VERSION = "1.2-DASH"

app = dash.Dash(__name__)

def load_data():
    return pd.read_csv('testing_framework/metric_guard/dashboard/resilience_data.csv')

def create_layout():
    df = load_data()
    return html.Div([
        html.H1(f"{CODENAME} (v{VERSION}) - Resilience Dashboard"),
        
        dcc.Graph(
            id='recovery-time',
            figure=px.bar(df, x='timestamp', y='mean_recovery',
                         title='Mean Recovery Time (seconds)')
        ),
        
        dcc.Graph(
            id='availability',
            figure=px.line(df, x='timestamp', y='availability',
                          title='System Availability (%)')
        ),
        
        html.Div([
            html.H3("Latest Metrics"),
            html.Pre(id='raw-data', children=str(df.tail(1).to_dict()))
        ]),
        
        dcc.Interval(
            id='interval-component',
            interval=60*1000,  # 1 minute
            n_intervals=0
        )
    ])

app.layout = create_layout()

@app.callback(
    dash.dependencies.Output('raw-data', 'children'),
    [dash.dependencies.Input('interval-component', 'n_intervals')]
)
def update_metrics(n):
    df = load_data()
    return str(df.tail(1).to_dict())

if __name__ == '__main__':
    print(f"Starting {CODENAME} (v{VERSION})")
    app.run_server(host='0.0.0.0', port=8050)
