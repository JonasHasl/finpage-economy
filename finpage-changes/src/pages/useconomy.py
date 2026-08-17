import pandas as pd
from datetime import datetime, date

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, callback, callback_context
from dash.dependencies import Input, Output, State

import updateEcon
import data_sources as ds

dash.register_page(__name__, path="/economy")

colors = {
    "background": "#0b0f19",
    "text": "#94a3b8",
    "accent": "#38bdf8",
    "text-white": "#e2e8f0",
    "content": "#0f172a",
}

COLORS = {
    "background": "#0b0f19",
    "banner": "hsl(222, 42%, 9%)",
    "banner2": "hsl(222, 34%, 13%)",
    "content": "#94a3b8",
    "text": "#94a3b8",
    "accent": "#38bdf8",
    "border": "#1e293b",
    "header": "#94a3b8",
    "element": "#34d399",
    "text-white": "#e2e8f0",
}

# Per-series chart colors, matching the reference app's palette. GRID/TICK
# colors are for the dark plot background -- transparent paper_bgcolor lets
# the surrounding card's own background show through.
CHART_COLORS = {
    "blue": "#38bdf8",
    "green": "#34d399",
    "amber": "#fbbf24",
    "red": "#f87171",
    "violet": "#a78bfa",
    "cyan": "#22d3ee",
    "rose": "#fb7185",
}
GRID_COLOR = "#1e293b"
AXIS_TEXT_COLOR = "#64748b"
TOOLTIP_BG = "#0b1424"
TOOLTIP_TEXT = "#e2e8f0"
CARD_COLOR = "hsl(222, 42%, 9%)"


def _fill_from_line(hex_color, opacity=0.18):
    """Low-opacity rgba fill under a line trace, from a '#rrggbb' color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {opacity})"


def load_economy_data():
    return pd.read_csv("econW_updated.csv", parse_dates=["Date"])


economy = pd.DataFrame()
df_with_econ = pd.DataFrame()
gdp_yoy = pd.DataFrame()
latestdate = date.today()
firstdate = date(2000, 1, 1)


def load_data():
    global economy, df_with_econ, latestdate, firstdate, gdp_yoy

    try:
        updateEcon.updateEcon(reload="incremental")
    except Exception as exc:
        # A failed incremental fetch (e.g. FRED rejecting a realtime_start
        # that's "tomorrow" from its own US-timezone perspective -- which
        # happens for a few hours after local midnight in timezones ahead
        # of US Eastern, like CET/CEST) shouldn't block loading the CSV's
        # already-cached, still-valid historical data below.
        print(f"useconomy: incremental update failed, using cached econW_updated.csv ({exc})")

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

    # ds.fetch_fred fails soft (returns an empty frame on any error) so a
    # FRED hiccup here can't take down the whole callback -- see below.
    interest_df = ds.fetch_fred("A091RC1Q027SBEA").rename(columns={"value": "Interest Payments"})
    revenue_df = ds.fetch_fred("FGRECPT").rename(columns={"value": "Total Revenue"})

    df_with_econ = pd.merge(interest_df, revenue_df, on="Date", how="inner")
    if not df_with_econ.empty:
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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
    # Rows before the series' first real observation (e.g. a YoY column needs
    # a full prior year before it can compute a value) can't be forward-filled
    # and would otherwise plot as a blank gap at the start of the line.
    dataframe = dataframe.dropna(subset=[y])

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
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=_fill_from_line(color),
            showlegend=False,
            hoverinfo="x+y",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[dataframe["Date"].iloc[-1]],
            y=[dataframe[y].iloc[-1]],
            mode="markers",
            marker=dict(color=CHART_COLORS["red"], size=7, line=dict(color=CARD_COLOR, width=1)),
            showlegend=False,
            hoverinfo="skip",
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
        bordercolor=GRID_COLOR,
        borderwidth=1,
        font=dict(color=TOOLTIP_TEXT),
        bgcolor=TOOLTIP_BG,
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
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(range=[y_min, y_max]),
        height=560,
        uirevision="constant",
        hoverlabel=dict(bgcolor=TOOLTIP_BG, bordercolor=GRID_COLOR, font=dict(color=TOOLTIP_TEXT)),
    )

    fig.update_xaxes(showgrid=False, showline=True, linecolor=GRID_COLOR, tickfont=dict(color=AXIS_TEXT_COLOR))
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, showline=False, tickfont=dict(color=AXIS_TEXT_COLOR))

    if tickformat:
        fig.update_yaxes(tickformat=tickformat)

    if pred and {"Forward Return", "SP Trailing 4 Weeks Return"}.issubset(dataframe.columns):
        fig.add_trace(
            go.Scatter(
                x=dataframe["Date"],
                y=dataframe["Forward Return"],
                fill="tozeroy",
                fillcolor=CHART_COLORS["blue"],
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
                fillcolor=CHART_COLORS["red"],
                name="Actual Forward Return",
                mode="lines",
                showlegend=legend,
            )
        )

    if hline1:
        fig.add_hline(y=35, line_width=3, line_dash="dash", line_color=CHART_COLORS["amber"])
        fig.add_hline(y=20, line_width=3, line_dash="dash", line_color=CHART_COLORS["red"])

    if hline0:
        fig.add_hline(y=0, line_width=3, line_dash="dash", line_color=AXIS_TEXT_COLOR)

    if yoy:
        fig.add_hline(y=0.02, line_width=3, line_dash="dash", line_color=CHART_COLORS["amber"])
        fig.add_annotation(
            text="Yellow Line: FED Target Rate",
            align="left",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.05,
            y=1.0,
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(color=TOOLTIP_TEXT),
            bgcolor=TOOLTIP_BG,
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
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(color=TOOLTIP_TEXT),
            bgcolor=TOOLTIP_BG,
        )

    return fig


# --------------------------------------------------------- comparison tab --
COMPARISON_COUNTRY_LABELS = {"us": "US", "eu": "EU", "uk": "UK", "norway": "Norway"}
COMPARISON_COUNTRY_COLORS = {
    "us": CHART_COLORS["blue"],
    "eu": CHART_COLORS["green"],
    "uk": CHART_COLORS["amber"],
    "norway": CHART_COLORS["red"],
}
COMPARISON_COUNTRY_OPTIONS = [
    {"label": label, "value": key} for key, label in COMPARISON_COUNTRY_LABELS.items()
]


def create_comparison_figure(title, yaxis, series_map, tick, selected):
    """One line per selected country, clipped to the earliest date where all
    selected countries have a value."""
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
                name=COMPARISON_COUNTRY_LABELS.get(key, key.upper()),
                line=dict(color=COMPARISON_COUNTRY_COLORS.get(key, CHART_COLORS["blue"]), width=2),
                hoverinfo="x+y+name",
            )
        )

    fig.update_layout(
        title=title,
        title_x=0.5,
        yaxis_title=yaxis,
        xaxis_title="Date",
        margin=dict(l=20, r=20, t=60, b=50),
        font=dict(family="Helvetica", size=15, color=colors["text"]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color=colors["text"])),
        height=460,
        uirevision="constant",
        hoverlabel=dict(bgcolor=TOOLTIP_BG, bordercolor=GRID_COLOR, font=dict(color=TOOLTIP_TEXT)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=GRID_COLOR, tickfont=dict(color=AXIS_TEXT_COLOR))
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, showline=False, tickfont=dict(color=AXIS_TEXT_COLOR))
    if tick == "%":
        fig.update_yaxes(tickformat=".1%")

    return fig


# ------------------------------------------------------- shared UI bits ----
def stat_card(label, value, source=None):
    children = [
        html.Div(label, className="economy-stat-label"),
        html.Div(value, className="economy-stat-value"),
    ]
    if source:
        children.append(html.Div(source, className="economy-stat-source"))
    return html.Div(children, className="economy-stat-card")


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


def source_caption(source):
    return html.Div(f"Source: {source}", className="economy-graph-source") if source else None


def graph_wrap(fig, full=True, source=None, graph_id=None):
    classes = "economy-graph-wrap economy-graph-wrap-full" if full else "economy-graph-wrap"
    inner = [dcc.Graph(id=graph_id, figure=fig, className="graph economy-graph", responsive=True)] if graph_id \
        else [dcc.Graph(figure=fig, className="graph economy-graph", responsive=True)]
    caption = source_caption(source)
    if caption:
        inner.append(caption)
    return html.Div(html.Div(inner, className="economy-graph-inner"), className=classes)


def graph_slot(graph_id, source=None, wide=False):
    """A graph placeholder for the static US-tab layout -- figure is filled
    in later by update_all_graphs()."""
    classes = "graph economy-graph economy-graph-wide" if wide else "graph economy-graph"
    inner = [dcc.Graph(id=graph_id, className=classes, responsive=True)]
    caption = source_caption(source)
    if caption:
        inner.append(caption)
    return html.Div(html.Div(inner, className="economy-graph-inner"), className="economy-graph-wrap")


# ------------------------------------------------- Norway / EU / UK tabs ---
def render_country_graphs(rows, starts, ends):
    children = []
    for title, subtitle, df, tick, source, color in rows:
        fig = create_graph(color, subtitle or title, title, df, "value", tick, starts, ends)
        children.append(graph_wrap(fig, source=source))
    return children


def render_norway(d, starts, ends):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y"))), "Norges Bank"),
        stat_card("Policy Rate", fmt_pct(ds.last_value(d.get("policyRate"))), "Norges Bank"),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), "SSB"),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), "SSB"),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment"))), "SSB"),
    )
    graphs = render_country_graphs(
        [
            ("OSEBX", "Oslo Børs benchmark", d.get("stockIndex"), " ", "Yahoo Finance", CHART_COLORS["blue"]),
            ("10Y Govt Yield", "Norway", d.get("bondYield10y"), "%", "Norges Bank", CHART_COLORS["amber"]),
            ("Policy Rate", "Norges Bank", d.get("policyRate"), "%", "Norges Bank", CHART_COLORS["violet"]),
            ("10Y-3Y Spread", "10Y minus 3Y", d.get("spread10y3y"), "%", "Norges Bank", CHART_COLORS["green"]),
            ("CPI YoY", "Norway inflation", d.get("cpiYoY"), "%", "SSB", CHART_COLORS["red"]),
            ("GDP YoY", "Real GDP", d.get("gdpYoY"), "%", "SSB", CHART_COLORS["green"]),
            ("Unemployment", "Norway", d.get("unemployment"), "%", "SSB", CHART_COLORS["cyan"]),
            ("USD / NOK", None, d.get("usdFx"), " ", "Norges Bank", CHART_COLORS["amber"]),
            ("EUR / NOK", None, d.get("eurFx"), " ", "Norges Bank", CHART_COLORS["green"]),
        ],
        starts,
        ends,
    )
    return html.Div([stats, html.Hr(className="economy-divider")] + graphs, style={"width": "100%"})


def render_eu_country_detail(d, country_key, starts, ends):
    d = d or {}
    countries = d.get("countries", {})
    c = countries.get(country_key)
    if not c:
        return html.Div("No data for this country.", className="economy-empty-note")
    stats = stat_row(
        stat_card("10Y", fmt_pct(ds.last_value(c.get("bondYield10y"))), "FRED"),
        stat_card("CPI", fmt_pct(ds.last_value(c.get("cpiYoY"))), "FRED"),
        stat_card("GDP", fmt_pct(ds.last_value(c.get("gdpYoY"))), "FRED"),
        stat_card("Unemp", fmt_pct(ds.last_value(c.get("unemployment"))), "FRED"),
    )
    fig = create_graph(
        CHART_COLORS["green"],
        "Index",
        f"{c.get('label', country_key.title())} Stock Index",
        c.get("stockIndex"),
        "value",
        " ",
        starts,
        ends,
    )
    return html.Div([stats, graph_wrap(fig, source="Yahoo Finance")], style={"width": "100%"})


def render_eu(d, starts, ends, country_key="germany"):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y"))), "ECB"),
        stat_card("Policy Rate", fmt_pct(ds.last_value(d.get("policyRate"))), "FRED"),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), "FRED"),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), "FRED"),
    )
    graphs = render_country_graphs(
        [
            ("EU 10Y Govt Yield", None, d.get("bondYield10y"), "%", "ECB", CHART_COLORS["amber"]),
            ("ECB Policy Rate", None, d.get("policyRate"), "%", "FRED", CHART_COLORS["violet"]),
            ("CPI YoY", "Euro area inflation", d.get("cpiYoY"), "%", "FRED", CHART_COLORS["red"]),
            ("GDP YoY", "Euro area real GDP", d.get("gdpYoY"), "%", "FRED", CHART_COLORS["green"]),
            ("Euro Stoxx 50", None, d.get("stockIndex"), " ", "Yahoo Finance", CHART_COLORS["blue"]),
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
                inputStyle={"marginRight": "6px", "marginLeft": "12px"},
                labelStyle={"display": "inline-block", "marginRight": "12px"},
            ),
        ],
        className="economy-controls",
    )
    detail = html.Div(
        render_eu_country_detail(d, country_key, starts, ends),
        id="eu-country-detail",
        style={"width": "100%"},
    )
    return html.Div(
        [stats, html.Hr(className="economy-divider")]
        + graphs
        + [html.Hr(className="economy-divider"), country_picker, detail],
        style={"width": "100%"},
    )


def render_uk(d, starts, ends):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y"))), "FRED"),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), "ONS"),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), "ONS"),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment"))), "ONS"),
    )
    graphs = render_country_graphs(
        [
            ("FTSE 100", "UK equity benchmark", d.get("stockIndex"), " ", "Yahoo Finance", CHART_COLORS["blue"]),
            ("10Y Gilt Yield", None, d.get("bondYield10y"), "%", "FRED", CHART_COLORS["amber"]),
            ("CPI YoY", "UK inflation", d.get("cpiYoY"), "%", "ONS", CHART_COLORS["red"]),
            ("GDP YoY", "Real GDP", d.get("gdpYoY"), "%", "ONS", CHART_COLORS["green"]),
            ("Unemployment", "UK", d.get("unemployment"), "%", "ONS", CHART_COLORS["cyan"]),
        ],
        starts,
        ends,
    )
    return html.Div([stats, html.Hr(className="economy-divider")] + graphs, style={"width": "100%"})


def render_comparison_panel(selected=None):
    selected = selected or ["us", "eu", "uk", "norway"]
    data = ds.get_comparison_data()

    gdp = create_comparison_figure("GDP Growth YoY", "Real GDP, YoY %", data.get("gdpYoY", {}), "%", selected)
    cpi = create_comparison_figure("CPI Growth YoY", "Consumer prices, YoY %", data.get("cpiYoY", {}), "%", selected)
    yld = create_comparison_figure("10Y Government Bond Yield", "Yield, %", data.get("bondYield10y", {}), "%", selected)
    unemp = create_comparison_figure(
        "Unemployment Rate", "% of labor force", data.get("unemployment", {}), "%", selected
    )

    country_toggle = dbc.Checklist(
        id="comparison-countries",
        className="comparison-toggle-group",
        inputClassName="btn-check",
        labelClassName="btn btn-outline-secondary comparison-toggle-btn",
        labelCheckedClassName="active",
        options=COMPARISON_COUNTRY_OPTIONS,
        value=selected,
        inline=True,
    )

    return html.Div(
        [
            html.Div(
                "Cross-country macro metrics, aligned from the earliest common date.",
                className="economy-subheading",
            ),
            country_toggle,
            html.Hr(className="economy-divider"),
            graph_wrap(gdp, source="FRED, ONS, SSB", graph_id="gdp-comparison-graph"),
            graph_wrap(cpi, source="FRED, ONS, SSB", graph_id="cpi-comparison-graph"),
            graph_wrap(yld, source="FRED, ECB, Norges Bank", graph_id="yield-comparison-graph"),
            graph_wrap(unemp, source="FRED, Eurostat, ONS, SSB", graph_id="unemployment-comparison-graph"),
        ],
        style={"width": "100%"},
    )


def render_market_panel(market, starts, ends, eu_country="germany"):
    if market == "norway":
        return render_norway(ds.get_market_data("norway"), starts, ends)
    if market == "eu":
        return render_eu(ds.get_market_data("eu"), starts, ends, eu_country)
    if market == "uk":
        return render_uk(ds.get_market_data("uk"), starts, ends)
    if market == "comparison":
        return render_comparison_panel()
    return html.Div()


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
        dcc.Loading(
            id="loading",
            type="default",
            children=html.Div(
                id="update-output",
                className="economy-update-text",
            ),
        ),
        dcc.Tabs(
            id="market-selector",
            value="us",
            className="economy-market-tabs",
            parent_className="economy-market-tabs-parent",
            children=[
                dcc.Tab(label="US", value="us", className="economy-tab", selected_className="economy-tab--selected"),
                dcc.Tab(label="Norway", value="norway", className="economy-tab", selected_className="economy-tab--selected"),
                dcc.Tab(label="EU", value="eu", className="economy-tab", selected_className="economy-tab--selected"),
                dcc.Tab(label="UK", value="uk", className="economy-tab", selected_className="economy-tab--selected"),
                dcc.Tab(label="Comparison", value="comparison", className="economy-tab", selected_className="economy-tab--selected"),
            ],
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
                    inputStyle={"marginRight": "6px", "marginLeft": "12px"},
                    labelStyle={"display": "inline-block", "marginRight": "12px"},
                ),
            ],
            className="economy-controls",
        ),
        html.Hr(className="economy-divider"),
        html.Div(
            id="us-economy-panel",
            children=[
                html.Div(id="us-stats-row", className="economy-stat-row"),
                html.Div(
                    [
                        graph_slot("ten-year-yield-graph", source="Yahoo Finance"),
                        graph_slot("shiller-pe-graph", source="multpl.com"),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        graph_slot("sp500-graph", source="Yahoo Finance"),
                        graph_slot("inflation-graph", source="FRED"),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        graph_slot("interest-to-income-graph", source="FRED"),
                        graph_slot("money-supply-graph", source="FRED"),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        graph_slot("t10y2y-graph", source="FRED"),
                        graph_slot("unemployment-graph", source="FRED"),
                    ],
                    className="parent-row economy-row",
                ),
                html.Div(
                    [
                        graph_slot("gdp-graph", source="FRED"),
                        graph_slot("trade-graph", source="FRED", wide=True),
                    ],
                    className="parent-row economy-row",
                ),
            ],
        ),
        dcc.Loading(
            id="loading-other-economy",
            type="default",
            parent_style={"width": "100%"},
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
    global economy, df_with_econ, firstdate, latestdate

    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "refresh-button":
            try:
                load_data()
            except Exception as exc:
                # A failed refresh (FRED/Yahoo/multpl hiccup) shouldn't crash
                # the callback and blank every graph -- keep showing the last
                # successfully loaded data instead.
                print(f"useconomy: refresh failed, keeping last-known data ({exc})")

    if n_intervals and n_intervals > 0:
        try:
            load_data()
        except Exception as exc:
            print(f"useconomy: interval refresh failed, keeping last-known data ({exc})")

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
        CHART_COLORS["amber"], "Yield", "10-yr Treasury Yield %",
        economy, "TenYield", tick="%", starts=start_date, ends=end_date
    )

    shiller_pe = create_graph(
        CHART_COLORS["green"], "Shiller P/E Ratio", "Shiller P/E Ratio",
        economy, "Shiller_PE", tick=" ", starts=start_date, ends=end_date
    )

    sp500 = create_graph(
        CHART_COLORS["blue"], "Price", "S&P 500 Index",
        economy, "Close", tick=" ", starts=start_date, ends=end_date
    )

    inflation = create_graph(
        CHART_COLORS["red"], "Inflation YoY", "Inflation US YoY-Change %",
        economy, "CPI YoY", tick="%", starts=start_date_infl, ends=end_date, yoy=True
    )

    interest_to_income = create_graph(
        CHART_COLORS["rose"], "Interest to Income Ratio", "Federal Interest Payments to Revenues Ratio",
        df_with_econ, "Interest to Income Ratio", tick="%", starts=start_date, ends=end_date
    )

    money_supply = create_graph(
        CHART_COLORS["cyan"], "Money Supply M2", "Money Supply US M2",
        economy, "m2", tick=" ", starts=start_date, ends=end_date
    )

    t10y2y = create_graph(
        CHART_COLORS["violet"], "T10Y2Y", "10-y 2-y Spread",
        economy, "T10Y2Y", tick=" ", starts=start_date, ends=end_date, hline0=False
    )

    unemployment = create_graph(
        CHART_COLORS["cyan"], "Unemployment Rate", "Unemployment Rate US",
        economy, "unemp_rate", tick="%", starts=start_date, ends=end_date
    )

    tradebalance = create_graph(
        CHART_COLORS["blue"],
        "Trade Balance (Exports-Imports) in Trillions $, Monthly",
        "Trade Balance US in Trillions $, Monthly",
        economy, "Trade Balance", tick=" ", starts=start_date, ends=end_date, trade=True
    )

    gdp = create_graph(
        CHART_COLORS["green"], "GDP YoY", "US Real GDP YoY %",
        gdp_yoy, "value", tick="%", starts=start_date, ends=end_date
    )

    us_stats = stat_row(
        stat_card("10Y Yield", fmt_pct(col_last(economy, "TenYield")), "Yahoo Finance"),
        stat_card("Unemployment", fmt_pct(col_last(economy, "unemp_rate")), "FRED"),
        stat_card("CPI YoY", fmt_pct(col_last(economy, "CPI YoY")), "FRED"),
        stat_card("GDP YoY", fmt_pct(ds.last_value(gdp_yoy)), "FRED"),
        stat_card("Shiller P/E", fmt_num(col_last(economy, "Shiller_PE"), 1), "multpl.com"),
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
    other_style = {"display": "none"} if market == "us" else {"width": "100%"}

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


@callback(
    Output("gdp-comparison-graph", "figure"),
    Output("cpi-comparison-graph", "figure"),
    Output("yield-comparison-graph", "figure"),
    Output("unemployment-comparison-graph", "figure"),
    Input("comparison-countries", "value"),
    prevent_initial_call=True,
)
def switch_comparison_countries(selected):
    selected = selected or []
    data = ds.get_comparison_data()
    gdp = create_comparison_figure("GDP Growth YoY", "Real GDP, YoY %", data.get("gdpYoY", {}), "%", selected)
    cpi = create_comparison_figure("CPI Growth YoY", "Consumer prices, YoY %", data.get("cpiYoY", {}), "%", selected)
    yld = create_comparison_figure("10Y Government Bond Yield", "Yield, %", data.get("bondYield10y", {}), "%", selected)
    unemp = create_comparison_figure(
        "Unemployment Rate", "% of labor force", data.get("unemployment", {}), "%", selected
    )
    return gdp, cpi, yld, unemp
