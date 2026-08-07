import pandas as pd
from datetime import datetime, date

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, callback, callback_context
from dash.dependencies import Input, Output, State
from fredapi import Fred

import updateEcon
import data_sources as ds

dash.register_page(__name__, path="/economy")

colors = {
    "background": "rgb(240,241,245)",
    "text": "black",
    "accent": "#004172",
    "text-white": "white",
    "content": "#Edf3F4",
}

COLORS = {
    "background": "#f4f4f4",
    "banner": "#0a213b",
    "banner2": "#1e3a5a",
    "content": "#859db3",
    "text": "#859db3",
    "accent": "#004172",
    "border": "#bed6eb",
    "header": "#7a7a7a",
    "element": "#1f8c44",
    "text-white": "white",
}

FRED_API_KEY = "29f9bb6865c0b3be320b44a846d539ea"


def load_economy_data():
    return pd.read_csv("econW_updated.csv", parse_dates=["Date"])


economy = pd.DataFrame()
df_with_econ = pd.DataFrame()
gdp_yoy = pd.DataFrame()
latestdate = date.today()
firstdate = date(2000, 1, 1)


def load_data():
    global economy, df_with_econ, latestdate, firstdate, gdp_yoy

    updateEcon.updateEcon(reload="incremental")
    economy = load_economy_data().copy()
    economy["Date"] = pd.to_datetime(economy["Date"])

    numeric_columns = [
        "unemp_rate",
        "TenYield",
        "Shiller_PE",
        "Close",
        "Trade Balance",
        "m2",
        "T10Y2Y",
        "CPI YoY",
    ]
    for col in numeric_columns:
        if col in economy.columns:
            economy[col] = pd.to_numeric(economy[col], errors="coerce")

    if "unemp_rate" in economy.columns:
        economy["unemp_rate"] = economy["unemp_rate"] / 100
    if "TenYield" in economy.columns:
        economy["TenYield"] = economy["TenYield"] / 100
    if "Shiller_PE" in economy.columns:
        economy["Shiller_PE"] = economy["Shiller_PE"].round(2)
    if "Close" in economy.columns:
        economy["Close"] = economy["Close"].round(2)
    if "Trade Balance" in economy.columns:
        economy["Trade Balance"] = economy["Trade Balance"].round(0)
        economy["Trade Balance"] = economy["Trade Balance"] * 1_000_000
        economy["Trade Balance"] = economy["Trade Balance"] / 1e12

    fred = Fred(api_key=FRED_API_KEY)
    interest_payments = fred.get_series("A091RC1Q027SBEA")
    government_revenue = fred.get_series("FGRECPT")

    interest_df = pd.DataFrame(interest_payments, columns=["Interest Payments"])
    revenue_df = pd.DataFrame(government_revenue, columns=["Total Revenue"])

    df_with_econ = pd.merge(
        interest_df,
        revenue_df,
        left_index=True,
        right_index=True,
        how="inner",
    )
    df_with_econ.index = pd.to_datetime(df_with_econ.index)
    df_with_econ = df_with_econ.reset_index().rename(columns={"index": "Date"})
    df_with_econ["Interest Payments"] = pd.to_numeric(df_with_econ["Interest Payments"], errors="coerce")
    df_with_econ["Total Revenue"] = pd.to_numeric(df_with_econ["Total Revenue"], errors="coerce")
    df_with_econ["Interest to Income Ratio"] = (
        df_with_econ["Interest Payments"] / df_with_econ["Total Revenue"]
    ).round(2)

    # Real GDP YoY -- not part of the incremental CSV pipeline above, fetched
    # directly (same source series used for every other market on this page).
    gdp_yoy = ds.yoy_change(ds.fetch_fred("GDPC1"), 4)

    latestdate = economy["Date"].dt.date.iloc[-1]
    firstdate = economy["Date"].dt.date.iloc[0]


try:
    load_data()
except Exception as exc:
    # A transient FRED/Yahoo/multpl outage at boot shouldn't take the whole
    # app down -- the page falls back to "No data available" until the next
    # successful refresh (interval tick or Refresh button).
    print(f"useconomy: initial data load failed, starting with empty data ({exc})")


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
        height=560,
        margin=dict(l=20, r=20, t=60, b=40),
    )
    return fig


def create_graph(
    color,
    yaxis,
    title,
    dataframe,
    y,
    tick,
    starts,
    ends,
    hline1=False,
    textbox=False,
    pred=False,
    hline0=False,
    legend=False,
    yoy=False,
    score=False,
    trade=False,
):
    dataframe = pd.DataFrame(dataframe).copy()

    if dataframe.empty or "Date" not in dataframe.columns or y not in dataframe.columns:
        return create_empty_figure(title, "No data available")

    dataframe = dataframe.ffill()
    dataframe["Date"] = pd.to_datetime(dataframe["Date"]).dt.date
    dataframe[y] = pd.to_numeric(dataframe[y], errors="coerce")

    if not isinstance(starts, date):
        starts = pd.to_datetime(starts).date()
    if not isinstance(ends, date):
        ends = pd.to_datetime(ends).date()

    mask = (dataframe["Date"] >= starts) & (dataframe["Date"] <= ends)
    dataframe = dataframe.loc[mask].copy()

    if dataframe.empty:
        return create_empty_figure(title, "No data available for the selected date range")

    dataframe = dataframe.reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=dataframe["Date"],
            y=dataframe[y],
            mode="lines",
            line=dict(color="#2a3f5f", width=2),
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[dataframe["Date"].iloc[-1]],
            y=[dataframe[y].iloc[-1]],
            mode="markers",
            marker=dict(color="red", size=7),
            showlegend=False,
        )
    )

    last_y_value = dataframe[y].iloc[-1]
    last_x_value = dataframe["Date"].iloc[-1]

    if tick == "%":
        formatted_y = f"{last_y_value:.2%}"
        tickformat = ".1%"
    else:
        formatted_y = f"{last_y_value:.2f}"
        tickformat = None

    fig.add_annotation(
        x=1,
        y=1,
        xref="paper",
        yref="paper",
        text=f"{last_x_value}: {formatted_y}",
        showarrow=False,
        xanchor="right",
        yanchor="top",
        bordercolor="black",
        borderwidth=0.8,
        bgcolor="rgba(255,255,255,0.85)",
    )

    y_min = dataframe[y].min()
    y_max = dataframe[y].max()
    y_range_buffer = (y_max - y_min) * 0.05 if y_max != y_min else 1
    y_min -= y_range_buffer
    y_max += y_range_buffer

    fig.update_layout(
        yaxis_title=yaxis,
        xaxis_title="Date",
        title=title,
        title_x=0.5,
        margin=dict(l=20, r=20, t=60, b=40),
        font=dict(family="Helvetica", size=15, color=colors["text"]),
        plot_bgcolor="white",
        paper_bgcolor=colors["background"],
        yaxis=dict(range=[y_min, y_max]),
        height=560,
        uirevision="constant",
    )

    fig.update_xaxes(showgrid=True, gridcolor=COLORS["border"])
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["border"])

    if tickformat:
        fig.update_yaxes(tickformat=tickformat)

    if pred and {"Forward Return", "SP Trailing 4 Weeks Return"}.issubset(dataframe.columns):
        fig.add_trace(
            go.Scatter(
                x=dataframe["Date"],
                y=dataframe["Forward Return"],
                fill="tozeroy",
                fillcolor="skyblue",
                name="Predicted Forward Return",
                mode="lines",
                showlegend=legend,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dataframe["Date"],
                y=dataframe["SP Trailing 4 Weeks Return"],
                fill="tozeroy",
                fillcolor="red",
                name="Actual Forward Return",
                mode="lines",
                showlegend=legend,
            )
        )

    if hline1:
        fig.add_hline(y=35, line_width=3, line_dash="dash", line_color="orange")
        fig.add_hline(y=20, line_width=3, line_dash="dash", line_color="red")

    if hline0:
        fig.add_hline(y=0, line_width=3, line_dash="dash", line_color="black")

    if yoy:
        fig.add_hline(y=0.02, line_width=3, line_dash="dash", line_color="orange")
        fig.add_annotation(
            text="Yellow Line: FED Target Rate",
            align="left",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.05,
            y=1.0,
            bordercolor="black",
            borderwidth=1,
            bgcolor="rgba(255,255,255,0.85)",
        )

    if textbox:
        fig.add_annotation(
            text="Yellow Line Recommendation: 70 % Long 30% Short. Red Line Recommendation: Risk Neutral, i.e. 50 % Long, 50 % Short.",
            align="left",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.05,
            y=1.0,
            bordercolor="black",
            borderwidth=1,
            bgcolor="rgba(255,255,255,0.85)",
        )

    return fig


# ------------------------------------------------------- shared UI bits ----
def stat_card(label, value):
    return html.Div(
        [
            html.Div(label, className="economy-stat-label"),
            html.Div(value, className="economy-stat-value"),
        ],
        className="economy-stat-card",
    )


def stat_row(*cards):
    return html.Div(list(cards), className="economy-stat-row")


def fmt_pct(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:.2%}"


def fmt_num(v, decimals=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:.{decimals}f}"


def col_last(df, col):
    if df is None or df.empty or col not in df.columns:
        return None
    val = df[col].iloc[-1]
    return None if pd.isna(val) else val


def resolve_date_range(range_selector):
    today = date.today()
    if range_selector == "ytd":
        return date(today.year, 1, 1), today
    return date(2000, 1, 1), today


def graph_wrap(fig, full=True):
    classes = "economy-graph-wrap economy-graph-wrap-full" if full else "economy-graph-wrap"
    return html.Div(
        dcc.Graph(figure=fig, className="graph economy-graph", responsive=True),
        className=classes,
    )


# ------------------------------------------------- Norway / EU / UK tabs ---
def render_country_graphs(rows, starts, ends):
    children = []
    for title, subtitle, df, tick in rows:
        fig = create_graph(colors["accent"], subtitle or title, title, df, "value", tick, starts, ends)
        children.append(graph_wrap(fig))
    return children


def render_norway(d, starts, ends):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y")))),
        stat_card("Policy Rate", fmt_pct(ds.last_value(d.get("policyRate")))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY")))),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY")))),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment")))),
    )
    graphs = render_country_graphs(
        [
            ("OSEBX", "Oslo Børs benchmark", d.get("stockIndex"), " "),
            ("10Y Govt Yield", "Norway", d.get("bondYield10y"), "%"),
            ("Policy Rate", "Norges Bank", d.get("policyRate"), "%"),
            ("10Y-3Y Spread", "10Y minus 3Y", d.get("spread10y3y"), "%"),
            ("CPI YoY", "Norway inflation", d.get("cpiYoY"), "%"),
            ("GDP YoY", "Real GDP", d.get("gdpYoY"), "%"),
            ("Unemployment", "Norway", d.get("unemployment"), "%"),
            ("USD / NOK", None, d.get("usdFx"), " "),
            ("EUR / NOK", None, d.get("eurFx"), " "),
        ],
        starts,
        ends,
    )
    return html.Div([stats, html.Hr(className="economy-divider")] + graphs)


def render_eu_country_detail(d, country_key, starts, ends):
    d = d or {}
    countries = d.get("countries", {})
    c = countries.get(country_key)
    if not c:
        return html.Div("No data for this country.", className="economy-empty-note")
    stats = stat_row(
        stat_card("10Y", fmt_pct(ds.last_value(c.get("bondYield10y")))),
        stat_card("CPI", fmt_pct(ds.last_value(c.get("cpiYoY")))),
        stat_card("GDP", fmt_pct(ds.last_value(c.get("gdpYoY")))),
        stat_card("Unemp", fmt_pct(ds.last_value(c.get("unemployment")))),
    )
    fig = create_graph(
        colors["accent"],
        "Index",
        f"{c.get('label', country_key.title())} Stock Index",
        c.get("stockIndex"),
        "value",
        " ",
        starts,
        ends,
    )
    return html.Div([stats, graph_wrap(fig)])


def render_eu(d, starts, ends, country_key="germany"):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y")))),
        stat_card("Policy Rate", fmt_pct(ds.last_value(d.get("policyRate")))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY")))),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY")))),
    )
    graphs = render_country_graphs(
        [
            ("EU 10Y Govt Yield", None, d.get("bondYield10y"), "%"),
            ("ECB Policy Rate", None, d.get("policyRate"), "%"),
            ("CPI YoY", "Euro area inflation", d.get("cpiYoY"), "%"),
            ("GDP YoY", "Euro area real GDP", d.get("gdpYoY"), "%"),
            ("Euro Stoxx 50", None, d.get("stockIndex"), " "),
        ],
        starts,
        ends,
    )
    country_options = [{"label": c["label"], "value": key} for key, c in ds.EU_COUNTRIES.items()]
    country_picker = html.Div(
        [
            html.Div("Country Detail", className="economy-subheading"),
            dcc.RadioItems(
                id="eu-country-selector",
                options=country_options,
                value=country_key,
                className="economy-radio",
                inputStyle={"margin-right": "6px", "margin-left": "12px"},
                labelStyle={"display": "inline-block", "margin-right": "12px"},
            ),
        ],
        className="economy-controls",
    )
    detail = html.Div(render_eu_country_detail(d, country_key, starts, ends), id="eu-country-detail")
    return html.Div(
        [stats, html.Hr(className="economy-divider")]
        + graphs
        + [html.Hr(className="economy-divider"), country_picker, detail]
    )


def render_uk(d, starts, ends):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y")))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY")))),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY")))),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment")))),
    )
    graphs = render_country_graphs(
        [
            ("FTSE 100", "UK equity benchmark", d.get("stockIndex"), " "),
            ("10Y Gilt Yield", None, d.get("bondYield10y"), "%"),
            ("CPI YoY", "UK inflation", d.get("cpiYoY"), "%"),
            ("GDP YoY", "Real GDP", d.get("gdpYoY"), "%"),
            ("Unemployment", "UK", d.get("unemployment"), "%"),
        ],
        starts,
        ends,
    )
    return html.Div([stats, html.Hr(className="economy-divider")] + graphs)


def render_market_panel(market, starts, ends, eu_country="germany"):
    if market == "norway":
        return render_norway(ds.get_market_data("norway"), starts, ends)
    if market == "eu":
        return render_eu(ds.get_market_data("eu"), starts, ends, eu_country)
    if market == "uk":
        return render_uk(ds.get_market_data("uk"), starts, ends)
    return html.Div()


descriptioneconomy = (
    "An overview of major economies — US, Norway, EU, and UK. "
    "Source: FRED, Yahoo Finance, Norges Bank, SSB, and multpl.com."
)

cardeconomy = dbc.Container(
    [
        html.Div(
            children=[
                html.H1("Economy", className="headerfinvest"),
                html.H1(
                    "Overview",
                    className="headerfinvest economy-accent-title",
                ),
            ],
            className="page-intros economy-title-row",
        ),
        html.Div(
            id="description-output",
            children=[descriptioneconomy],
            className="normal-text economy-description",
        ),
        dcc.Loading(
            id="loading",
            type="default",
            children=html.Div(
                id="update-output",
                className="economy-update-text",
            ),
        ),
        html.Div(
            [
                dcc.RadioItems(
                    id="market-selector",
                    options=[
                        {"label": "US", "value": "us"},
                        {"label": "Norway", "value": "norway"},
                        {"label": "EU", "value": "eu"},
                        {"label": "UK", "value": "uk"},
                    ],
                    value="us",
                    className="economy-radio economy-market-radio",
                    inputStyle={"margin-right": "6px", "margin-left": "12px"},
                    labelStyle={"display": "inline-block", "margin-right": "12px"},
                ),
                html.Div(
                    [
                        html.Button(
                            "Refresh",
                            id="refresh-button",
                            n_clicks=0,
                            className="economy-refresh-btn",
                        ),
                        dcc.RadioItems(
                            id="date-range-selector",
                            options=[
                                {"label": "YTD", "value": "ytd"},
                                {"label": "Full Range", "value": "full"},
                            ],
                            value="full",
                            className="economy-radio",
                            inputStyle={"margin-right": "6px", "margin-left": "12px"},
                            labelStyle={"display": "inline-block", "margin-right": "12px"},
                        ),
                    ],
                    className="economy-controls",
                ),
            ],
            className="economy-controls-shell",
        ),
        html.Hr(className="economy-divider"),
        html.Div(
            id="us-economy-panel",
            children=[
                html.Div(id="us-stats-row", className="economy-stat-row"),
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="ten-year-yield-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                        html.Div(
                            [dcc.Graph(id="shiller-pe-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="sp500-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                        html.Div(
                            [dcc.Graph(id="inflation-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="interest-to-income-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                        html.Div(
                            [dcc.Graph(id="money-supply-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="t10y2y-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                        html.Div(
                            [dcc.Graph(id="unemployment-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        html.Div(
                            [dcc.Graph(id="gdp-graph", className="graph economy-graph", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                        html.Div(
                            [dcc.Graph(id="trade-graph", className="graph economy-graph economy-graph-wide", responsive=True)],
                            className="economy-graph-wrap",
                        ),
                    ],
                    className="parent-row economy-row",
                ),
            ],
        ),
        dcc.Loading(
            id="loading-other-economy",
            type="default",
            children=html.Div(id="other-economy-panel", style={"display": "none"}),
        ),
        dcc.Interval(
            id="interval-component-economy",
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
        cardeconomy,
    ],
    className="economy-layout-shell",
    fluid=True,
)


@callback(
    [
        Output("ten-year-yield-graph", "figure"),
        Output("shiller-pe-graph", "figure"),
        Output("sp500-graph", "figure"),
        Output("inflation-graph", "figure"),
        Output("interest-to-income-graph", "figure"),
        Output("money-supply-graph", "figure"),
        Output("t10y2y-graph", "figure"),
        Output("unemployment-graph", "figure"),
        Output("trade-graph", "figure"),
        Output("gdp-graph", "figure"),
        Output("us-stats-row", "children"),
        Output("description-output", "children"),
        Output("update-output", "children"),
    ],
    [
        Input("date-range-selector", "value"),
        Input("interval-component-economy", "n_intervals"),
        Input("refresh-button", "n_clicks"),
    ],
    prevent_initial_call=False,
)
def update_all_graphs(range_selector, n_intervals, n_clicks):
    global economy, df_with_econ, firstdate, latestdate, descriptioneconomy

    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "refresh-button":
            load_data()

    if n_intervals and n_intervals > 0:
        load_data()

    firstdate_obj = pd.to_datetime(firstdate).date() if isinstance(firstdate, str) else firstdate
    latestdate_obj = pd.to_datetime(latestdate).date() if isinstance(latestdate, str) else latestdate

    if range_selector == "ytd":
        ytd_start = date(datetime.now().year, 1, 1)
        if not economy.empty and "Date" in economy.columns:
            economy_max_date = pd.to_datetime(economy["Date"]).dt.date.max()
            if economy_max_date < ytd_start:
                ytd_start = date(economy_max_date.year, 1, 1)

        start_date = ytd_start
        start_date_infl = ytd_start
        end_date = latestdate_obj
    else:
        start_date = firstdate_obj
        start_date_infl = date(1990, 1, 1)
        end_date = latestdate_obj

    ten_year_yield = create_graph(
        colors["accent"], "Yield", "10-yr Treasury Yield %",
        economy, "TenYield", tick="%", starts=start_date, ends=end_date
    )

    shiller_pe = create_graph(
        colors["accent"], "Shiller P/E Ratio", "Shiller P/E Ratio",
        economy, "Shiller_PE", tick=" ", starts=start_date, ends=end_date
    )

    sp500 = create_graph(
        colors["accent"], "Price", "S&P 500 Index",
        economy, "Close", tick=" ", starts=start_date, ends=end_date
    )

    inflation = create_graph(
        colors["accent"], "Inflation YoY", "Inflation US YoY-Change %",
        economy, "CPI YoY", tick="%", starts=start_date_infl, ends=end_date, yoy=True
    )

    interest_to_income = create_graph(
        colors["accent"], "Interest to Income Ratio", "Federal Interest Payments to Revenues Ratio",
        df_with_econ, "Interest to Income Ratio", tick="%", starts=start_date, ends=end_date
    )

    money_supply = create_graph(
        colors["accent"], "Money Supply M2", "Money Supply US M2",
        economy, "m2", tick=" ", starts=start_date, ends=end_date
    )

    t10y2y = create_graph(
        colors["accent"], "T10Y2Y", "10-y 2-y Spread",
        economy, "T10Y2Y", tick=" ", starts=start_date, ends=end_date, hline0=False
    )

    unemployment = create_graph(
        colors["accent"], "Unemployment Rate", "Unemployment Rate US",
        economy, "unemp_rate", tick="%", starts=start_date, ends=end_date
    )

    tradebalance = create_graph(
        colors["accent"],
        "Trade Balance (Exports-Imports) in Trillions $, Monthly",
        "Trade Balance US in Trillions $, Monthly",
        economy, "Trade Balance", tick=" ", starts=start_date, ends=end_date, trade=True
    )

    gdp = create_graph(
        colors["accent"], "GDP YoY", "US Real GDP YoY %",
        gdp_yoy, "value", tick="%", starts=start_date, ends=end_date
    )

    us_stats = stat_row(
        stat_card("10Y Yield", fmt_pct(col_last(economy, "TenYield"))),
        stat_card("Unemployment", fmt_pct(col_last(economy, "unemp_rate"))),
        stat_card("CPI YoY", fmt_pct(col_last(economy, "CPI YoY"))),
        stat_card("GDP YoY", fmt_pct(ds.last_value(gdp_yoy))),
        stat_card("Shiller P/E", fmt_num(col_last(economy, "Shiller_PE"), 1)),
    )

    descriptioneconomy = (
        "An overview of major economies — US, Norway, EU, and UK. "
        "Source: FRED, Yahoo Finance, Norges Bank, SSB, and multpl.com."
    )

    return (
        ten_year_yield,
        shiller_pe,
        sp500,
        inflation,
        interest_to_income,
        money_supply,
        t10y2y,
        unemployment,
        tradebalance,
        gdp,
        us_stats,
        descriptioneconomy,
        f"Last check for new updates: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )


@callback(
    Output("us-economy-panel", "style"),
    Output("other-economy-panel", "style"),
    Output("other-economy-panel", "children"),
    Input("market-selector", "value"),
    Input("date-range-selector", "value"),
    Input("interval-component-economy", "n_intervals"),
    Input("refresh-button", "n_clicks"),
    prevent_initial_call=False,
)
def switch_market(market, range_selector, n_intervals, n_clicks):
    us_style = {} if market == "us" else {"display": "none"}
    other_style = {"display": "none"} if market == "us" else {}

    if market == "us":
        return us_style, other_style, dash.no_update

    ctx = callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    if trigger_id == "refresh-button":
        ds.invalidate_market(market)

    starts, ends = resolve_date_range(range_selector)
    content = render_market_panel(market, starts, ends)
    return us_style, other_style, content


@callback(
    Output("eu-country-detail", "children"),
    Input("eu-country-selector", "value"),
    State("date-range-selector", "value"),
    prevent_initial_call=True,
)
def switch_eu_country(country_key, range_selector):
    starts, ends = resolve_date_range(range_selector)
    data = ds.get_market_data("eu")
    return render_eu_country_detail(data, country_key, starts, ends)
