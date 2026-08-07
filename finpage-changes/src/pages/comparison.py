from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback, callback_context
from dash.dependencies import Input, Output

import data_sources as ds

dash.register_page(__name__, path="/comparison", name="Comparison")

colors = {
    "background": "rgb(240,241,245)",
    "text": "black",
    "accent": "#004172",
}

COLORS = {
    "background": "#f4f4f4",
    "text": "#859db3",
    "border": "#bed6eb",
}

COUNTRY_LABELS = {"us": "US", "eu": "EU", "uk": "UK", "norway": "Norway"}
COUNTRY_COLORS = {
    "us": "#004172",
    "eu": "#3db569",
    "uk": "#c98a2e",
    "norway": "#a23b3b",
}
COUNTRY_OPTIONS = [{"label": label, "value": key} for key, label in COUNTRY_LABELS.items()]


def create_empty_figure(title, message):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        title_x=0.5,
        annotations=[
            dict(
                text=message,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS["text"]),
            )
        ],
        font=dict(family="Helvetica", size=15, color=COLORS["text"]),
        paper_bgcolor=colors["background"],
        plot_bgcolor="white",
        height=460,
        margin=dict(l=20, r=20, t=60, b=40),
    )
    return fig


def create_comparison_figure(title, yaxis, series_map, tick, selected):
    """One line per selected country, clipped to the earliest date where all
    selected countries have a value (mirrors the reference app's behaviour)."""
    frames = [(key, series_map.get(key)) for key in selected]
    frames = [(key, df) for key, df in frames if df is not None and not df.empty]
    if not frames:
        return create_empty_figure(title, "No data for selected countries")

    merged = None
    for key, df in frames:
        s = df[["Date", "value"]].rename(columns={"value": key}).set_index("Date")
        merged = s if merged is None else merged.join(s, how="outer")
    merged = merged.sort_index().ffill()

    complete = merged.dropna(how="any")
    if not complete.empty:
        merged = merged.loc[complete.index.min():]
    merged = merged.reset_index()

    fig = go.Figure()
    for key, _ in frames:
        if key not in merged.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=merged["Date"],
                y=merged[key],
                mode="lines",
                name=COUNTRY_LABELS.get(key, key.upper()),
                line=dict(color=COUNTRY_COLORS.get(key, "#2a3f5f"), width=2),
            )
        )

    fig.update_layout(
        title=title,
        title_x=0.5,
        yaxis_title=yaxis,
        xaxis_title="Date",
        margin=dict(l=20, r=20, t=60, b=50),
        font=dict(family="Helvetica", size=15, color=colors["text"]),
        plot_bgcolor="white",
        paper_bgcolor=colors["background"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=460,
        uirevision="constant",
    )
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["border"])
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["border"])
    if tick == "%":
        fig.update_yaxes(tickformat=".1%")

    return fig


def graph_wrap_id(graph_id):
    return html.Div(
        dcc.Graph(id=graph_id, className="graph economy-graph", responsive=True),
        className="economy-graph-wrap economy-graph-wrap-full",
    )


country_toggle = dbc.Checklist(
    id="comparison-countries",
    className="comparison-toggle-group",
    inputClassName="btn-check",
    labelClassName="btn btn-outline-secondary comparison-toggle-btn",
    labelCheckedClassName="active",
    options=COUNTRY_OPTIONS,
    value=["us", "eu", "uk", "norway"],
    inline=True,
)

cardcomparison = dbc.Container(
    [
        html.Div(
            children=[
                html.H1("Comparison", className="headerfinvest"),
                html.H1("Overview", className="headerfinvest economy-accent-title"),
            ],
            className="page-intros economy-title-row",
        ),
        html.Div(
            "Cross-country macro metrics — GDP growth, inflation, bond yields and "
            "unemployment for the US, EU, UK and Norway, aligned from the earliest "
            "common date. Source: FRED, Norges Bank and SSB.",
            className="normal-text economy-description",
        ),
        html.Div(
            id="comparison-update-output",
            className="economy-update-text",
        ),
        html.Div(
            [
                country_toggle,
                html.Button(
                    "Refresh",
                    id="comparison-refresh-button",
                    n_clicks=0,
                    className="economy-refresh-btn",
                ),
            ],
            className="economy-controls comparison-controls",
        ),
        html.Hr(className="economy-divider"),
        dcc.Loading(
            id="comparison-loading",
            type="default",
            children=html.Div(
                [
                    graph_wrap_id("gdp-comparison-graph"),
                    graph_wrap_id("cpi-comparison-graph"),
                    graph_wrap_id("yield-comparison-graph"),
                    graph_wrap_id("unemployment-comparison-graph"),
                ]
            ),
        ),
        dcc.Interval(
            id="comparison-interval",
            interval=3600 * 1000 * 6,
            n_intervals=0,
        ),
    ],
    className="parent-container2 economy-page",
    fluid=True,
)

layout = dbc.Container(
    [
        html.Div(className="beforediv"),
        cardcomparison,
    ],
    className="economy-layout-shell",
    fluid=True,
)


@callback(
    Output("gdp-comparison-graph", "figure"),
    Output("cpi-comparison-graph", "figure"),
    Output("yield-comparison-graph", "figure"),
    Output("unemployment-comparison-graph", "figure"),
    Output("comparison-update-output", "children"),
    Input("comparison-countries", "value"),
    Input("comparison-interval", "n_intervals"),
    Input("comparison-refresh-button", "n_clicks"),
    prevent_initial_call=False,
)
def update_comparison(selected, n_intervals, n_clicks):
    ctx = callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    if trigger_id == "comparison-refresh-button":
        ds.invalidate_market("comparison")

    data = ds.get_comparison_data()
    selected = selected or []

    gdp = create_comparison_figure("GDP Growth YoY", "Real GDP, YoY %", data.get("gdpYoY", {}), "%", selected)
    cpi = create_comparison_figure("CPI Growth YoY", "Consumer prices, YoY %", data.get("cpiYoY", {}), "%", selected)
    yld = create_comparison_figure("10Y Government Bond Yield", "Yield, %", data.get("bondYield10y", {}), "%", selected)
    unemp = create_comparison_figure(
        "Unemployment Rate", "% of labor force", data.get("unemployment", {}), "%", selected
    )

    return gdp, cpi, yld, unemp, f"Last check for new updates: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
