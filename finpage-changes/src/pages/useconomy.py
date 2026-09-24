import pandas as pd
from datetime import datetime, date

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html, dcc, callback, callback_context
from dash.dependencies import Input, Output, State

import data_sources as ds
from theme import LIGHT_THEME

dash.register_page(__name__, path="/economy")

ECONOMY_THEME = LIGHT_THEME

colors = {
    "background": ECONOMY_THEME["page"],
    "text": ECONOMY_THEME["text_primary"],
    "accent": ECONOMY_THEME["blue"],
    "text-white": ECONOMY_THEME["surface"],
    "content": ECONOMY_THEME["surface_subtle"],
}

COLORS = {
    "background": ECONOMY_THEME["page"],
    "banner": ECONOMY_THEME["surface"],
    "banner2": ECONOMY_THEME["surface_subtle"],
    "content": ECONOMY_THEME["text_secondary"],
    "text": ECONOMY_THEME["text_primary"],
    "accent": ECONOMY_THEME["blue"],
    "border": ECONOMY_THEME["border"],
    "header": ECONOMY_THEME["text_secondary"],
    "element": ECONOMY_THEME["green"],
    "text-white": ECONOMY_THEME["surface"],
}

# Per-series chart colors use darker, light-surface-safe hues so the financial
# distinctions remain clear without changing any series semantics.
CHART_COLORS = {
    "blue": ECONOMY_THEME["blue"],
    "green": ECONOMY_THEME["green"],
    "amber": ECONOMY_THEME["amber"],
    "red": ECONOMY_THEME["red"],
    "violet": ECONOMY_THEME["violet"],
    "cyan": ECONOMY_THEME["cyan"],
    "rose": ECONOMY_THEME["rose"],
}

# Dash renders responsive Graph components with an inline ``height: 100%``.
# Without a definite container height, a figure update can resolve that
# percentage to zero and make a populated chart appear empty.  Keep the
# desktop height users already see while remaining compact on phones.
ECONOMY_GRAPH_STYLE = {
    "height": "clamp(380px, 42vw, 450px)",
    "minHeight": "380px",
}

GRID_COLOR = ECONOMY_THEME["grid"]
AXIS_TEXT_COLOR = ECONOMY_THEME["text_muted"]
TOOLTIP_BG = ECONOMY_THEME["tooltip_bg"]
TOOLTIP_TEXT = ECONOMY_THEME["tooltip_text"]
CARD_COLOR = ECONOMY_THEME["surface"]


def _fill_from_line(hex_color, opacity=0.18):
    """Low-opacity rgba fill under a line trace, from a '#rrggbb' color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {opacity})"


def load_economy_data():
    return pd.read_csv("econW_updated.csv", parse_dates=["Date"])


us_data = {}
latestdate = date.today()
firstdate = date(2000, 1, 1)


def _fallback_series(dataframe, column, scale=1.0):
    if dataframe.empty or column not in dataframe.columns:
        return pd.DataFrame(columns=["Date", "value"])
    frame = dataframe[["Date", column]].rename(columns={column: "value"}).copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce") * scale
    frame = frame.dropna(subset=["Date", "value"]).sort_values("Date")
    # The legacy cache is daily and forward-filled. Keep change dates so a
    # monthly fallback does not pretend its last observation occurred today.
    return frame.loc[frame["value"].ne(frame["value"].shift())].reset_index(drop=True)


def _cached_us_fallback():
    cached = load_economy_data().copy()
    return {
        "bondYield10y": _fallback_series(cached, "TenYield", 0.01),
        "stockIndex": _fallback_series(cached, "Close"),
        "cpiYoY": _fallback_series(cached, "CPI YoY"),
        "moneySupply": _fallback_series(cached, "m2", 0.001),
        "spread10y2y": _fallback_series(cached, "T10Y2Y", 100.0),
        "unemployment": _fallback_series(cached, "unemp_rate", 0.01),
        "tradeBalance": _fallback_series(cached, "Trade Balance", 0.001),
        "shillerPE": _fallback_series(cached, "Shiller_PE"),
    }


def load_data(force=False):
    global us_data, latestdate, firstdate

    loaded = ds.get_market_data("us", force=force)
    fallback = _cached_us_fallback()
    keys = set(loaded) | set(fallback)
    us_data = {}
    for key in keys:
        frame = loaded.get(key)
        if frame is None or frame.empty:
            frame = fallback.get(key, pd.DataFrame(columns=["Date", "value"]))
        us_data[key] = frame

    available_dates = [
        pd.to_datetime(frame["Date"]).max()
        for frame in us_data.values()
        if frame is not None and not frame.empty and "Date" in frame.columns
    ]
    if not available_dates:
        raise ValueError("No US economy data is available from live sources or the local cache")
    latestdate = max(available_dates).date()
    firstdate = date(2000, 1, 1)


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
        paper_bgcolor=ECONOMY_THEME["transparent"],
        plot_bgcolor=ECONOMY_THEME["transparent"],
        height=560,
        margin=dict(l=20, r=20, t=60, b=40),
    )
    return fig


def format_observation_date(value, period=None):
    """Format observation periods without implying false day-level precision."""
    timestamp = pd.Timestamp(value)
    if period == "quarter":
        return f"Q{timestamp.quarter} {timestamp.year}"
    if period == "month":
        return timestamp.strftime("%b %Y")
    return timestamp.strftime("%d %b %Y")


def format_observation_value(value, tick):
    if tick == "%":
        return f"{value:.2%}".replace("-", "−", 1)
    if tick == "bps":
        return f"{value:,.0f} bp".replace("-", "−", 1)
    if tick == "usd_tn":
        sign = "−" if value < 0 else ""
        return f"{sign}${abs(value):,.2f}tn"
    if tick == "usd_bn":
        sign = "−" if value < 0 else ""
        return f"{sign}${abs(value):,.1f}bn"
    if tick == "ratio":
        return f"{value:,.1f}×".replace("-", "−", 1)
    if tick == "fx":
        return f"{value:,.4f}".replace("-", "−", 1)
    return f"{value:,.2f}".replace("-", "−", 1)


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
    line_shape="linear",
    period=None,
):
    dataframe = pd.DataFrame(dataframe).copy()

    if dataframe.empty or "Date" not in dataframe.columns or y not in dataframe.columns:
        return create_empty_figure(title, "No data available")

    dataframe["Date"] = pd.to_datetime(dataframe["Date"], errors="coerce")
    dataframe[y] = pd.to_numeric(dataframe[y], errors="coerce")
    dataframe = (
        dataframe.dropna(subset=["Date", y])
        .sort_values("Date")
        .drop_duplicates("Date", keep="last")
    )
    dataframe["Date"] = dataframe["Date"].dt.date

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

    observation_labels = [format_observation_date(value, period) for value in dataframe["Date"]]
    hover_labels = [
        f"{date_label}<br>{format_observation_value(value, tick)}"
        for date_label, value in zip(observation_labels, dataframe[y])
    ]

    fig.add_trace(
        go.Scatter(
            x=dataframe["Date"],
            y=dataframe[y],
            mode="markers" if len(dataframe) == 1 else "lines",
            line=dict(color=color, width=2, shape=line_shape),
            marker=dict(color=color, size=7),
            customdata=observation_labels,
            text=hover_labels,
            showlegend=False,
            connectgaps=False,
            hovertemplate="%{text}<extra></extra>",
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

    formatted_y = format_observation_value(last_y_value, tick)
    if tick == "%":
        tickformat = ".1%"
    elif tick == "bps":
        tickformat = ",.0f"
    elif tick == "usd_tn":
        tickformat = ",.1f"
    elif tick == "usd_bn":
        tickformat = ",.0f"
    elif tick == "ratio":
        tickformat = ",.1f"
    elif tick == "fx":
        tickformat = ",.2f"
    else:
        tickformat = ",~s" if tick == "index" else ",.2f"

    last_date_label = format_observation_date(last_x_value, period)

    fig.add_annotation(
        x=1,
        y=1,
        xref="paper",
        yref="paper",
        text=f"{last_date_label} · {formatted_y}",
        showarrow=False,
        xanchor="right",
        yanchor="top",
        bordercolor=GRID_COLOR,
        borderwidth=1,
        font=dict(color=TOOLTIP_TEXT),
        bgcolor=TOOLTIP_BG,
    )

    reference_values = []
    if hline0 or trade:
        reference_values.append(0)
    if yoy:
        reference_values.append(0.02)

    y_min = min([dataframe[y].min(), *reference_values])
    y_max = max([dataframe[y].max(), *reference_values])
    if y_max != y_min:
        y_range_buffer = (y_max - y_min) * 0.08
    elif tick == "%":
        y_range_buffer = max(abs(y_max) * 0.08, 0.0025)
    elif tick == "bps":
        y_range_buffer = max(abs(y_max) * 0.08, 5)
    else:
        y_range_buffer = max(abs(y_max) * 0.08, 1)
    y_min -= y_range_buffer
    y_max += y_range_buffer
    if tick == "%" and (y_max - y_min) < 0.01:
        tickformat = ".2%"

    x_start = pd.Timestamp(dataframe["Date"].min())
    x_end = pd.Timestamp(ends)
    if x_start >= x_end:
        x_start = x_end - pd.Timedelta(days=30)

    fig.update_layout(
        yaxis_title=yaxis,
        xaxis_title="Date",
        title=title,
        title_x=0.5,
        margin=dict(l=20, r=20, t=60, b=40),
        font=dict(family="Helvetica", size=15, color=colors["text"]),
        plot_bgcolor=ECONOMY_THEME["transparent"],
        paper_bgcolor=ECONOMY_THEME["transparent"],
        yaxis=dict(range=[y_min, y_max]),
        height=560,
        uirevision="constant",
        hoverlabel=dict(bgcolor=TOOLTIP_BG, bordercolor=GRID_COLOR, font=dict(color=TOOLTIP_TEXT)),
    )

    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=GRID_COLOR,
        tickfont=dict(color=AXIS_TEXT_COLOR),
        range=[x_start, x_end],
    )
    if period in {"month", "quarter"} and len(dataframe) <= 12:
        fig.update_xaxes(
            tickmode="array",
            tickvals=list(dataframe["Date"]),
            ticktext=observation_labels,
        )
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, showline=False, tickfont=dict(color=AXIS_TEXT_COLOR))

    if tickformat:
        fig.update_yaxes(tickformat=tickformat)
    if tick in {"usd_tn", "usd_bn"}:
        fig.update_yaxes(tickprefix="$", ticksuffix="tn" if tick == "usd_tn" else "bn")
    elif tick == "bps":
        fig.update_yaxes(ticksuffix=" bp")
    elif tick == "ratio":
        fig.update_yaxes(ticksuffix="×")

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

    if trade:
        fig.add_hline(y=0, line_width=2, line_dash="dot", line_color=AXIS_TEXT_COLOR)

    if yoy:
        fig.add_hline(y=0.02, line_width=3, line_dash="dash", line_color=CHART_COLORS["amber"])
        fig.add_annotation(
            text="2% reference (the Fed's formal target uses PCE, not CPI)",
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
COMPARISON_COUNTRY_LABELS = {"us": "US", "eu": "Euro Area", "uk": "UK", "norway": "Norway"}
COMPARISON_COUNTRY_COLORS = {
    "us": CHART_COLORS["blue"],
    "eu": CHART_COLORS["green"],
    "uk": CHART_COLORS["amber"],
    "norway": CHART_COLORS["red"],
}
COMPARISON_COUNTRY_OPTIONS = [
    {"label": label, "value": key} for key, label in COMPARISON_COUNTRY_LABELS.items()
]


def create_comparison_figure(
    title,
    yaxis,
    series_map,
    tick,
    selected,
    starts=None,
    ends=None,
    period=None,
):
    """Plot actual observations for each selected country without interpolation."""
    requested = selected or []
    frames = []
    missing = []
    for key in requested:
        df = series_map.get(key)
        if df is None or df.empty:
            missing.append(COMPARISON_COUNTRY_LABELS.get(key, key.upper()))
            continue
        frame = df[["Date", "value"]].copy()
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame = frame.dropna().sort_values("Date")
        if starts is not None:
            frame = frame[frame["Date"] >= pd.to_datetime(starts)]
        if ends is not None:
            frame = frame[frame["Date"] <= pd.to_datetime(ends)]
        if frame.empty:
            missing.append(COMPARISON_COUNTRY_LABELS.get(key, key.upper()))
            continue
        frames.append((key, frame))

    if not frames:
        message = "No published observations in the selected date range"
        if missing:
            message += f" ({', '.join(missing)})"
        return create_empty_figure(title, message)

    plotted_start = min(frame["Date"].min() for _, frame in frames)

    fig = go.Figure()
    for key, frame in frames:
        trace_period = period.get(key) if isinstance(period, dict) else period
        observation_labels = [
            format_observation_date(value, trace_period) for value in frame["Date"]
        ]
        mode = (
            "markers"
            if len(frame) == 1
            else "lines+markers"
            if trace_period == "quarter"
            else "lines"
        )
        fig.add_trace(
            go.Scatter(
                x=list(frame["Date"]),
                y=list(frame["value"]),
                mode=mode,
                name=COMPARISON_COUNTRY_LABELS.get(key, key.upper()),
                line=dict(color=COMPARISON_COUNTRY_COLORS.get(key, CHART_COLORS["blue"]), width=2),
                marker=dict(color=COMPARISON_COUNTRY_COLORS.get(key, CHART_COLORS["blue"]), size=7),
                customdata=observation_labels,
                connectgaps=False,
                hovertemplate=(
                    "%{customdata}<br>%{fullData.name}: %{y:.2%}<extra></extra>"
                    if tick == "%"
                    else "%{customdata}<br>%{fullData.name}: %{y:,.2f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=title,
        title_x=0.5,
        yaxis_title=yaxis,
        xaxis_title="Date",
        margin=dict(l=20, r=20, t=60, b=50),
        font=dict(family="Helvetica", size=15, color=colors["text"]),
        plot_bgcolor=ECONOMY_THEME["transparent"],
        paper_bgcolor=ECONOMY_THEME["transparent"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(color=colors["text"])),
        height=460,
        uirevision="constant",
        hoverlabel=dict(bgcolor=TOOLTIP_BG, bordercolor=GRID_COLOR, font=dict(color=TOOLTIP_TEXT)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=GRID_COLOR, tickfont=dict(color=AXIS_TEXT_COLOR))
    if ends is not None:
        x_start = pd.to_datetime(starts) if starts is not None else plotted_start
        x_end = pd.to_datetime(ends)
        if x_start >= x_end:
            x_start = x_end - pd.Timedelta(days=30)
        fig.update_xaxes(range=[x_start, x_end])
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, showline=False, tickfont=dict(color=AXIS_TEXT_COLOR))
    if tick == "%":
        fig.update_yaxes(tickformat=".1%")

    if missing:
        fig.add_annotation(
            text=f"Unavailable in selected range: {', '.join(missing)}",
            xref="paper",
            yref="paper",
            x=0,
            y=-0.16,
            xanchor="left",
            showarrow=False,
            font=dict(size=11, color=CHART_COLORS["amber"]),
        )

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


def last_observation_date(df):
    if df is None or df.empty or "Date" not in df.columns:
        return None
    value = pd.to_datetime(df["Date"], errors="coerce").dropna()
    return None if value.empty else value.iloc[-1]


def infer_observation_period(df):
    if df is None or df.empty or "Date" not in df.columns:
        return None
    dates = pd.to_datetime(df["Date"], errors="coerce").dropna().drop_duplicates().sort_values()
    if len(dates) < 2:
        return None
    if (dates.dt.day == 1).all():
        month_numbers = dates.dt.year * 12 + dates.dt.month
        median_month_step = month_numbers.diff().dropna().median()
        if median_month_step <= 2:
            return "month"
        if median_month_step <= 4:
            return "quarter"
    return None


def source_as_of(source, df, period=None):
    observation_date = last_observation_date(df)
    if observation_date is None:
        return source
    inferred_period = period or infer_observation_period(df)
    date_label = format_observation_date(observation_date, inferred_period)
    return f"{source} · {date_label}"


def resolve_date_range(range_selector):
    today = date.today()
    if range_selector == "ytd":
        return date(today.year, 1, 1), today
    return date(2000, 1, 1), today


def should_refresh_us(trigger_id, active_market):
    return trigger_id == "interval-component-economy" or (
        trigger_id == "refresh-button" and active_market == "us"
    )


def source_caption(source):
    return html.Div(f"Source: {source}", className="economy-graph-source") if source else None


def graph_wrap(fig, full=True, source=None, graph_id=None):
    classes = "economy-graph-wrap economy-graph-wrap-full" if full else "economy-graph-wrap"
    graph_options = {
        "figure": fig,
        "className": "graph economy-graph",
        "responsive": True,
        "style": ECONOMY_GRAPH_STYLE.copy(),
    }
    if graph_id is not None:
        graph_options["id"] = graph_id
    inner = [dcc.Graph(**graph_options)]
    caption = source_caption(source)
    if caption:
        inner.append(caption)
    return html.Div(html.Div(inner, className="economy-graph-inner"), className=classes)


def graph_slot(graph_id, source=None, wide=False):
    """A graph placeholder for the static US-tab layout -- figure is filled
    in later by update_all_graphs()."""
    classes = "graph economy-graph economy-graph-wide" if wide else "graph economy-graph"
    inner = [
        dcc.Graph(
            id=graph_id,
            className=classes,
            responsive=True,
            style=ECONOMY_GRAPH_STYLE.copy(),
        )
    ]
    caption = source_caption(source)
    if caption:
        inner.append(caption)
    return html.Div(html.Div(inner, className="economy-graph-inner"), className="economy-graph-wrap")


# ------------------------------------------------- Norway / EU / UK tabs ---
def render_country_graphs(rows, starts, ends):
    children = []
    for title, subtitle, df, tick, source, color, *options in rows:
        chart_options = options[0] if options else {}
        fig = create_graph(
            color,
            subtitle or title,
            title,
            df,
            "value",
            tick,
            starts,
            ends,
            **chart_options,
        )
        children.append(graph_wrap(fig, source=source))
    return children


def render_norway(d, starts, ends):
    d = d or {}
    stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(d.get("bondYield10y"))), source_as_of("Norges Bank", d.get("bondYield10y"))),
        stat_card("Policy Rate", fmt_pct(ds.last_value(d.get("policyRate"))), source_as_of("Norges Bank", d.get("policyRate"))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), source_as_of("SSB", d.get("cpiYoY"))),
        stat_card("GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), source_as_of("SSB", d.get("gdpYoY"))),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment"))), source_as_of("SSB", d.get("unemployment"))),
    )
    graphs = render_country_graphs(
        [
            ("OSEBX", "Index level", d.get("stockIndex"), "index", "Yahoo Finance", CHART_COLORS["blue"]),
            ("Norway 10Y Government Bond Yield", "Percent per annum", d.get("bondYield10y"), "%", "Norges Bank", CHART_COLORS["amber"]),
            ("Norges Bank Policy Rate", "Percent per annum", d.get("policyRate"), "%", "Norges Bank", CHART_COLORS["violet"], {"line_shape": "hv"}),
            ("Norway 10Y–3Y Yield-Curve Slope", "Basis points", d.get("spread10y3y"), "bps", "Norges Bank", CHART_COLORS["green"], {"hline0": True}),
            ("Norway CPI Inflation", "Year-over-year change", d.get("cpiYoY"), "%", "SSB", CHART_COLORS["red"], {"period": "month"}),
            ("Norway Real GDP Growth", "Year-over-year change, monthly", d.get("gdpYoY"), "%", "SSB", CHART_COLORS["green"], {"hline0": True, "period": "month"}),
            ("Norway Unemployment Rate", "% of labor force, SA", d.get("unemployment"), "%", "SSB", CHART_COLORS["cyan"], {"period": "month"}),
            ("USD / NOK", "NOK per USD", d.get("usdFx"), "fx", "Norges Bank", CHART_COLORS["amber"]),
            ("EUR / NOK", "NOK per EUR", d.get("eurFx"), "fx", "Norges Bank", CHART_COLORS["green"]),
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
        stat_card("10Y Government Yield", fmt_pct(ds.last_value(c.get("bondYield10y"))), source_as_of("FRED", c.get("bondYield10y"))),
        stat_card("HICP YoY", fmt_pct(ds.last_value(c.get("cpiYoY"))), source_as_of("FRED", c.get("cpiYoY"))),
        stat_card("Real GDP YoY", fmt_pct(ds.last_value(c.get("gdpYoY"))), source_as_of("FRED", c.get("gdpYoY"), "quarter")),
        stat_card("Unemployment Rate", fmt_pct(ds.last_value(c.get("unemployment"))), source_as_of("FRED", c.get("unemployment"))),
    )
    fig = create_graph(
        CHART_COLORS["green"],
        "Index level",
        f"{c.get('label', country_key.title())} Stock Index",
        c.get("stockIndex"),
        "value",
        "index",
        starts,
        ends,
    )
    return html.Div([stats, graph_wrap(fig, source="Yahoo Finance")], style={"width": "100%"})


def render_eu(d, starts, ends, country_key="germany"):
    d = d or {}
    stats = stat_row(
        stat_card("AAA 10Y Spot Rate", fmt_pct(ds.last_value(d.get("bondYield10y"))), source_as_of("ECB", d.get("bondYield10y"))),
        stat_card("Deposit Facility Rate", fmt_pct(ds.last_value(d.get("policyRate"))), source_as_of("ECB", d.get("policyRate"))),
        stat_card("HICP YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), source_as_of("Eurostat", d.get("cpiYoY"))),
        stat_card("Real GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), source_as_of("Eurostat", d.get("gdpYoY"), "quarter")),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment"))), source_as_of("Eurostat", d.get("unemployment"))),
    )
    graphs = render_country_graphs(
        [
            ("Euro Area AAA 10Y Zero-Coupon Spot Rate", "Percent per annum", d.get("bondYield10y"), "%", "ECB", CHART_COLORS["amber"]),
            ("ECB Deposit Facility Rate", "Percent per annum", d.get("policyRate"), "%", "ECB", CHART_COLORS["violet"], {"line_shape": "hv"}),
            ("Euro Area HICP Inflation", "Year-over-year change", d.get("cpiYoY"), "%", "Eurostat · changing composition", CHART_COLORS["red"], {"period": "month"}),
            ("Euro Area Real GDP Growth", "Year-over-year change, quarterly", d.get("gdpYoY"), "%", "Eurostat · changing composition", CHART_COLORS["green"], {"hline0": True, "period": "quarter"}),
            ("Euro Stoxx 50", "Index level", d.get("stockIndex"), "index", "Yahoo Finance", CHART_COLORS["blue"]),
            ("Euro Area Unemployment Rate", "% of labor force, SA", d.get("unemployment"), "%", "Eurostat EA21", CHART_COLORS["cyan"], {"period": "month"}),
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
        stat_card("10Y Gilt Yield", fmt_pct(ds.last_value(d.get("bondYield10y"))), source_as_of("Bank of England", d.get("bondYield10y"))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(d.get("cpiYoY"))), source_as_of("ONS", d.get("cpiYoY"))),
        stat_card("Real GDP YoY", fmt_pct(ds.last_value(d.get("gdpYoY"))), source_as_of("ONS", d.get("gdpYoY"), "quarter")),
        stat_card("Unemployment", fmt_pct(ds.last_value(d.get("unemployment"))), source_as_of("ONS", d.get("unemployment"))),
    )
    graphs = render_country_graphs(
        [
            ("FTSE 100", "Index level", d.get("stockIndex"), "index", "Yahoo Finance", CHART_COLORS["blue"]),
            ("UK 10Y Nominal Par Gilt Yield", "Percent per annum", d.get("bondYield10y"), "%", "Bank of England", CHART_COLORS["amber"]),
            ("UK CPI Inflation", "Year-over-year change", d.get("cpiYoY"), "%", "ONS", CHART_COLORS["red"], {"period": "month"}),
            ("UK Real GDP Growth", "Year-over-year change, quarterly", d.get("gdpYoY"), "%", "ONS", CHART_COLORS["green"], {"hline0": True, "period": "quarter"}),
            ("UK Unemployment Rate", "% of labor force, SA", d.get("unemployment"), "%", "ONS", CHART_COLORS["cyan"], {"period": "month"}),
        ],
        starts,
        ends,
    )
    return html.Div([stats, html.Hr(className="economy-divider")] + graphs, style={"width": "100%"})


def render_comparison_panel(selected=None, starts=None, ends=None):
    selected = selected or ["us", "eu", "uk", "norway"]
    data = ds.get_comparison_data()

    gdp = create_comparison_figure(
        "Real GDP Growth",
        "Year-over-year change",
        data.get("gdpYoY", {}),
        "%",
        selected,
        starts,
        ends,
        {"us": "quarter", "eu": "quarter", "uk": "quarter", "norway": "month"},
    )
    cpi = create_comparison_figure(
        "Consumer-Price Inflation",
        "Year-over-year change",
        data.get("cpiYoY", {}),
        "%",
        selected,
        starts,
        ends,
        "month",
    )
    yld = create_comparison_figure(
        "10Y Sovereign / AAA Benchmark Yield",
        "Percent per annum",
        data.get("bondYield10y", {}),
        "%",
        selected,
        starts,
        ends,
    )
    unemp = create_comparison_figure(
        "Unemployment Rate",
        "% of labor force, SA",
        data.get("unemployment", {}),
        "%",
        selected,
        starts,
        ends,
        "month",
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
                "Actual published observations within the selected date window; frequencies and latest dates vary.",
                className="economy-subheading",
            ),
            country_toggle,
            html.Hr(className="economy-divider"),
            graph_wrap(gdp, source="FRED, Eurostat, ONS, SSB", graph_id="gdp-comparison-graph"),
            graph_wrap(cpi, source="FRED, Eurostat, ONS, SSB", graph_id="cpi-comparison-graph"),
            graph_wrap(yld, source="FRED, ECB, Bank of England, Norges Bank", graph_id="yield-comparison-graph"),
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
        return render_comparison_panel(starts=starts, ends=ends)
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
                dcc.Tab(label="Euro Area", value="eu", className="economy-tab", selected_className="economy-tab--selected"),
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
                        {"label": "All available", "value": "full"},
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
                        graph_slot("ten-year-yield-graph", source="FRED"),
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
    State("market-selector", "value"),
    prevent_initial_call=False,
)
def update_all_graphs(range_selector, n_intervals, n_clicks, active_market):
    global us_data, firstdate, latestdate

    ctx = callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    if should_refresh_us(trigger_id, active_market):
        try:
            load_data(force=True)
        except Exception as exc:
            # A failed refresh should not blank the page; data_sources keeps
            # valid cached frames when one upstream series is temporarily empty.
            print(f"useconomy: refresh failed, keeping last-known data ({exc})")

    firstdate_obj = pd.to_datetime(firstdate).date() if isinstance(firstdate, str) else firstdate
    latestdate_obj = pd.to_datetime(latestdate).date() if isinstance(latestdate, str) else latestdate

    if range_selector == "ytd":
        ytd_start = date(datetime.now().year, 1, 1)
        start_date = ytd_start
        start_date_infl = ytd_start
        end_date = latestdate_obj
    else:
        start_date = firstdate_obj
        start_date_infl = date(1990, 1, 1)
        end_date = latestdate_obj

    ten_year_yield = create_graph(
        CHART_COLORS["amber"], "Percent per annum", "U.S. 10-Year Treasury Yield",
        us_data.get("bondYield10y"), "value", tick="%", starts=start_date, ends=end_date
    )

    shiller_pe = create_graph(
        CHART_COLORS["green"], "Cyclically adjusted P/E (×)", "S&P 500 Shiller CAPE",
        us_data.get("shillerPE"), "value", tick="ratio", starts=start_date, ends=end_date
    )

    sp500 = create_graph(
        CHART_COLORS["blue"], "Index level", "S&P 500",
        us_data.get("stockIndex"), "value", tick="index", starts=start_date, ends=end_date
    )

    inflation = create_graph(
        CHART_COLORS["red"], "Year-over-year change", "U.S. CPI Inflation",
        us_data.get("cpiYoY"), "value", tick="%", starts=start_date_infl, ends=end_date, period="month"
    )

    interest_to_income = create_graph(
        CHART_COLORS["rose"], "% of federal current receipts, quarterly SAAR", "Federal Interest Payments / Current Receipts",
        us_data.get("interestToRevenue"), "value", tick="%", starts=start_date, ends=end_date, period="quarter"
    )

    money_supply = create_graph(
        CHART_COLORS["cyan"], "USD trillions, seasonally adjusted", "U.S. M2 Money Stock",
        us_data.get("moneySupply"), "value", tick="usd_tn", starts=start_date, ends=end_date, period="month"
    )

    t10y2y = create_graph(
        CHART_COLORS["violet"], "Basis points", "U.S. 10Y–2Y Treasury Curve",
        us_data.get("spread10y2y"), "value", tick="bps", starts=start_date, ends=end_date, hline0=True
    )

    unemployment = create_graph(
        CHART_COLORS["cyan"], "% of civilian labor force, SA", "U.S. Unemployment Rate",
        us_data.get("unemployment"), "value", tick="%", starts=start_date, ends=end_date, period="month"
    )

    tradebalance = create_graph(
        CHART_COLORS["blue"],
        "USD billions, seasonally adjusted, monthly",
        "U.S. Trade Balance",
        us_data.get("tradeBalance"), "value", tick="usd_bn", starts=start_date, ends=end_date, trade=True, period="month"
    )

    gdp = create_graph(
        CHART_COLORS["green"], "Year-over-year change, quarterly", "U.S. Real GDP Growth",
        us_data.get("gdpYoY"), "value", tick="%", starts=start_date, ends=end_date, hline0=True, period="quarter"
    )

    us_stats = stat_row(
        stat_card("10Y Yield", fmt_pct(ds.last_value(us_data.get("bondYield10y"))), source_as_of("FRED", us_data.get("bondYield10y"))),
        stat_card("Unemployment", fmt_pct(ds.last_value(us_data.get("unemployment"))), source_as_of("FRED", us_data.get("unemployment"))),
        stat_card("CPI YoY", fmt_pct(ds.last_value(us_data.get("cpiYoY"))), source_as_of("FRED", us_data.get("cpiYoY"))),
        stat_card("Real GDP YoY", fmt_pct(ds.last_value(us_data.get("gdpYoY"))), source_as_of("FRED", us_data.get("gdpYoY"), "quarter")),
        stat_card("Shiller CAPE", fmt_num(ds.last_value(us_data.get("shillerPE")), 1), source_as_of("multpl.com", us_data.get("shillerPE"))),
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
        f"Data checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · each card and chart shows its observation date",
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
        ds.refresh_market(market)

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
    State("date-range-selector", "value"),
    prevent_initial_call=True,
)
def switch_comparison_countries(selected, range_selector):
    selected = selected or []
    data = ds.get_comparison_data()
    starts, ends = resolve_date_range(range_selector)
    gdp = create_comparison_figure(
        "Real GDP Growth",
        "Year-over-year change",
        data.get("gdpYoY", {}),
        "%",
        selected,
        starts,
        ends,
        {"us": "quarter", "eu": "quarter", "uk": "quarter", "norway": "month"},
    )
    cpi = create_comparison_figure(
        "Consumer-Price Inflation",
        "Year-over-year change",
        data.get("cpiYoY", {}),
        "%",
        selected,
        starts,
        ends,
        "month",
    )
    yld = create_comparison_figure(
        "10Y Sovereign / AAA Benchmark Yield", "Percent per annum", data.get("bondYield10y", {}), "%", selected, starts, ends
    )
    unemp = create_comparison_figure(
        "Unemployment Rate",
        "% of labor force, SA",
        data.get("unemployment", {}),
        "%",
        selected,
        starts,
        ends,
        "month",
    )
    return gdp, cpi, yld, unemp
