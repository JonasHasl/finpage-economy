"""One-screen dashboard variant of the Economy page (/economy-dashboard).

The same indicators, sources and headline numbers as ``pages/useconomy.py``,
laid out so a whole market -- KPI strip plus every chart -- fits on one desktop
screen.  A "Layout" switch turns the same page into a long, scrolling layout
with large charts.  Styles live in ``assets/economy-dashboard.css`` (``.ed-*``
classes) and the layout switch in ``assets/economy-dashboard.js``.

Design notes
- All controls are static (never rebuilt by a callback), so every control can
  be an Input of the one render callback without input-in-output cycles.
- The page root carries ``data-market`` (set by the callback together with the
  new content) so the CSS can shape the grid and reveal market-specific
  controls atomically with the data.
"""

import logging
import math
from datetime import datetime

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import (
    ClientsideFunction,
    Input,
    Output,
    callback,
    callback_context,
    clientside_callback,
    dcc,
    html,
)

import data_sources as ds
import economy_dashboard_model as model
from theme import LIGHT_THEME as THEME


dash.register_page(
    __name__,
    path='/economy-dashboard',
    name='Economy Dashboard',
    title='Economy Dashboard',
)

logger = logging.getLogger(__name__)


GRAPH_CONFIG = {
    'displayModeBar': False,
    'responsive': True,
    'scrollZoom': False,
    'doubleClick': False,
}

DEFAULT_VIEW = 'dashboard'
DEFAULT_MARKET = 'us'
DEFAULT_RANGE = 'full'
LOADING_TEXT = 'Loading economic data…'
REFRESH_INTERVAL_MS = 6 * 3600 * 1000

VIEW_OPTIONS = [
    {'label': 'Dashboard', 'value': 'dashboard'},
    {'label': 'Scroll', 'value': 'scroll'},
]
# The one-screen layout needs this much room (the same numbers as the dashboard
# media query in assets/economy-dashboard.css); smaller windows always scroll.
DASHBOARD_MIN_WIDTH = 1180
DASHBOARD_MIN_HEIGHT = 601
VIEW_HINT = f'Dashboard needs a window of at least {DASHBOARD_MIN_WIDTH} × {DASHBOARD_MIN_HEIGHT} px'
MARKET_OPTIONS = [{'label': market.label, 'value': key} for key, market in model.MARKETS.items()] + [
    {'label': 'Comparison', 'value': 'comparison'},
]
RANGE_OPTIONS = [{'label': label, 'value': key} for key, label in model.RANGE_OPTIONS]
EU_COUNTRY_OPTIONS = [{'label': c['label'], 'value': key} for key, c in ds.EU_COUNTRIES.items()]
COMPARISON_OPTIONS = [{'label': label, 'value': key} for key, label, _, _ in model.COMPARISON_COUNTRIES]
COMPARISON_DEFAULT = [key for key, *_ in model.COMPARISON_COUNTRIES]
COUNTRY_CODES = {key: code for key, _, code, _ in model.COMPARISON_COUNTRIES}
COUNTRY_LABELS = {key: label for key, label, _, _ in model.COMPARISON_COUNTRIES}
COUNTRY_COLORS = {key: THEME[color] for key, _, _, color in model.COMPARISON_COUNTRIES}

HERO_TEXT = (
    'Latest readings and long-run trends for the US, Norway, the Euro Area and the UK, '
    'with a side-by-side comparison. Every card and chart shows the source and date of its '
    'latest observation.'
)
CHART_LEGEND = (
    ('ed-key--dot', 'Red dot: the latest observation.'),
    ('ed-key--gap', 'A gap at the right edge means the latest release is older than today.'),
    ('ed-key--zero', 'Dotted line: zero.'),
)
CHART_LEGEND_NOTE = ' '.join(text for _, text in CHART_LEGEND)

UNAVAILABLE_TEXT = 'Source unavailable<br>Press Refresh to retry'
NO_COUNTRY_TEXT = 'Select at least one country'

# Decimals kept per unit when a series is sent to the browser.  Hover text and
# headline numbers are built from the unrounded values.
Y_DECIMALS = {'%': 8, 'bps': 2, 'ratio': 3, 'usd_tn': 4, 'usd_bn': 3, 'fx': 5, 'index': 2}


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _rgba(hex_color, opacity):
    value = hex_color.lstrip('#')
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{opacity})'


def empty_reason(frame, start, end, period=None):
    """What to tell the user when a tile has nothing to draw, by cause."""
    if model.series_state(frame, start, end) == 'unavailable':
        return UNAVAILABLE_TEXT
    tidy = model.clean_series(frame)
    latest = model.format_observation_date(
        tidy['Date'].iloc[-1], period or model.infer_observation_period(tidy),
    )
    return f'No observations in this range<br>Latest: {latest}'


def empty_figure(message=''):
    """A blank, axis-less figure that just shows a message."""
    fig = go.Figure()
    if message:
        fig.add_annotation(
            text=message,
            showarrow=False,
            font=dict(size=12, color=THEME['text_muted']),
        )
    fig.update_layout(
        plot_bgcolor=THEME['transparent'],
        paper_bgcolor=THEME['transparent'],
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        margin=dict(l=8, r=8, t=8, b=8),
        dragmode=False,
    )
    return fig


def _ticks_at(step, low, high):
    value = math.ceil(low / step - 1e-9) * step
    ticks = []
    while value <= high + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def nice_ticks(low, high, count=4):
    """Round tick values inside [low, high].

    Steps follow a 1-2-2.5-5 progression.  The coarsest step that puts three to
    ``count + 1`` ticks on the axis wins; failing that, the coarsest with two.
    """
    span = high - low
    if span <= 0:
        return [low]
    exponent = math.floor(math.log10(span / max(count - 1, 1)))
    steps = sorted(
        {multiple * 10 ** power for power in (exponent + 1, exponent, exponent - 1) for multiple in (1, 2, 2.5, 5)},
        reverse=True,
    )
    options = [_ticks_at(step, low, high) for step in steps]
    for ticks in options:
        if 3 <= len(ticks) <= count + 1:
            return ticks
    for ticks in options:
        if len(ticks) >= 2:
            return ticks
    return options[-1] or [low]


def _tick_decimals(values):
    """The fewest decimals that write every tick exactly (17.5 must not read 18)."""
    for decimals in range(4):
        if all(abs(round(v, decimals) - v) < 1e-9 for v in values):
            return decimals
    return 3


def money_tick_text(value, unit, decimals):
    """'$20tn' / '−$50bn': plotly's own prefix would give '$-50bn'."""
    sign = '−' if value < 0 else ''
    return f'{sign}${abs(value):,.{decimals}f}{unit}'


# The smallest span (in the series' own unit) a value axis will zoom in to, so
# a couple of near-identical readings do not look like a dramatic move.
MIN_AXIS_SPAN = {'%': 0.005, 'bps': 20, 'ratio': 2.0, 'usd_tn': 0.5, 'usd_bn': 10.0}
MIN_RELATIVE_SPAN = {'fx': 0.02, 'index': 0.02}


def _y_axis_format(tick, span):
    """tickformat / prefix / suffix for a compact value axis."""
    if tick == '%':
        decimals = '.0%' if span >= 0.04 else '.1%' if span >= 0.01 else '.2%'
        return {'tickformat': decimals}
    if tick == 'bps':
        return {'tickformat': ',.0f', 'ticksuffix': ' bp'}
    if tick == 'ratio':
        return {'tickformat': ',.0f', 'ticksuffix': '×'}
    if tick == 'fx':
        return {'tickformat': ',.1f' if span >= 1 else ',.2f'}
    return {'tickformat': ',~s'}


def _x_axis_format(first, last):
    days = max((pd.Timestamp(last) - pd.Timestamp(first)).days, 1)
    if days > 3 * 365:
        return '%Y'
    if days > 400:
        return "%b '%y"
    if days > 100:
        return '%b'
    # Fewer than about three months: ticks fall every few days, so a bare month
    # would repeat ("Jan Jan Jan").
    return '%d %b'


def _right_limit(end, span_days, tickformat):
    """The right edge of the x-axis.

    A little past ``end`` so the latest-observation dot is not cut off, but never
    far enough to reach the next month or year, whose tick label would then
    appear to the right of today ("Nov" on 30 October).
    """
    end = pd.Timestamp(end).normalize()
    limit = end + pd.Timedelta(days=max(span_days * 0.014, 1))
    if tickformat == '%Y':
        boundary = pd.Timestamp(year=end.year + 1, month=1, day=1)
    elif tickformat in ('%b', "%b '%y"):
        boundary = end + pd.offsets.MonthBegin(1)
    else:
        return limit
    return min(limit, boundary - pd.Timedelta(days=1))


def _y_range(values, tick, include_zero=False):
    low, high = float(values.min()), float(values.max())
    if include_zero:
        low, high = min(low, 0.0), max(high, 0.0)
    minimum = MIN_AXIS_SPAN.get(tick)
    if minimum is None:
        minimum = abs(high) * MIN_RELATIVE_SPAN.get(tick, 0.02)
    if high - low < minimum:
        # Centre the data in a window of the minimum span.
        middle = (high + low) / 2
        low, high = middle - minimum / 2, middle + minimum / 2
    buffer = (high - low) * 0.08
    return low - buffer, high + buffer


def _base_layout(fig, compact=True):
    fig.update_layout(
        font=dict(family='Helvetica, Arial, sans-serif', size=10, color=THEME['text_secondary']),
        plot_bgcolor=THEME['transparent'],
        paper_bgcolor=THEME['transparent'],
        margin=dict(l=4, r=8, t=6, b=4) if compact else dict(l=8, r=12, t=10, b=8),
        showlegend=False,
        hovermode='x',
        hoverlabel=dict(
            bgcolor=THEME['tooltip_bg'],
            bordercolor=THEME['tooltip_bg'],
            font=dict(color=THEME['tooltip_text'], size=12),
        ),
        dragmode=False,
        uirevision='ed',
    )
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=THEME['border'],
        tickfont=dict(size=10, color=THEME['text_muted']),
        fixedrange=True,
        automargin=True,
        nticks=5,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=THEME['grid'],
        showline=False,
        zeroline=False,
        tickfont=dict(size=10, color=THEME['text_muted']),
        fixedrange=True,
        automargin=True,
        nticks=4,
    )
    return fig


def tile_figure(frame, chart, start, end):
    """A compact single-series figure for one tile."""
    # Step series (policy rates) list only the dates a rate changed; carry the rate
    # in force at the start of the window in so the line does not begin mid-window.
    tidy = model.clip_series(frame, start, end, carry_in=chart.step)
    if tidy.empty:
        return empty_figure(empty_reason(frame, start, end, chart.period))

    colour = THEME[chart.color]
    # From the whole series: a short window may hold a single point to judge by.
    period = chart.period or model.infer_observation_period(frame)
    dates = list(tidy['Date'])
    y = tidy['value']
    # Plain date strings and rounded values keep the response small.
    x = tidy['Date'].dt.strftime('%Y-%m-%d').tolist()
    sent = y.round(Y_DECIMALS.get(chart.tick, 6)).tolist()
    began = tidy['since'] if 'since' in tidy.columns else pd.Series(pd.NaT, index=tidy.index)
    carried = began.notna().tolist()
    hover = []
    for when, value, since in zip(dates, y, began):
        text = model.format_observation_value(value, chart.tick)
        if pd.notna(since):
            hover.append(f'In force since {model.format_observation_date(since, period)}<br>{text}')
        else:
            hover.append(f'{model.format_observation_date(when, period)}<br>{text}')
    y_min, y_max = _y_range(y, chart.tick, include_zero=chart.zero_line)
    crosses_zero = y.min() < 0 < y.max()

    fig = go.Figure()
    if crosses_zero or y_min > 0:
        # Zero is on the plot, or entirely below it, in which case the fill
        # simply runs to the bottom edge.
        fill = 'tozeroy'
    else:
        # Only reached when the whole range is negative or touches zero from
        # above: fill to the bottom of the visible range instead.
        fig.add_trace(go.Scatter(
            x=x, y=[y_min] * len(x), mode='lines', line=dict(width=0),
            hoverinfo='skip', showlegend=False,
        ))
        fill = 'tonexty'

    few = len(tidy) <= 24
    fig.add_trace(go.Scatter(
        x=x,
        y=sent,
        mode='lines+markers' if few and len(tidy) > 1 else 'lines' if len(tidy) > 1 else 'markers',
        line=dict(color=colour, width=1.9, shape='hv' if chart.step else 'linear'),
        # No marker on the carried-in point: it is not an observation.
        marker=dict(color=colour, size=[0 if held else 5 for held in carried] if any(carried) else 5),
        fill=fill,
        fillcolor=_rgba(colour, 0.10),
        text=hover,
        hovertemplate='%{text}<extra></extra>',
        connectgaps=False,
    ))
    fig.add_trace(go.Scatter(
        x=[x[-1]],
        y=[float(y.iloc[-1])],
        mode='markers',
        marker=dict(color=THEME['red'], size=7, line=dict(color=THEME['surface'], width=1.2)),
        hoverinfo='skip',
        showlegend=False,
        cliponaxis=False,
    ))

    if chart.zero_line:
        fig.add_hline(y=0, line_width=1.2, line_dash='dot', line_color=THEME['text_muted'])

    _base_layout(fig)
    span_days = max((pd.Timestamp(end) - pd.Timestamp(dates[0])).days, 1)
    tickformat = _x_axis_format(dates[0], end)
    fig.update_xaxes(range=[dates[0], _right_limit(end, span_days, tickformat)], tickformat=tickformat)
    fig.update_yaxes(range=[y_min, y_max], **_y_axis_format(chart.tick, y_max - y_min))
    if chart.tick in ('usd_tn', 'usd_bn'):
        unit = 'tn' if chart.tick == 'usd_tn' else 'bn'
        values = nice_ticks(y_min, y_max)
        decimals = _tick_decimals(values)
        fig.update_yaxes(
            tickmode='array',
            tickvals=values,
            ticktext=[money_tick_text(v, unit, decimals) for v in values],
        )
    return fig


def _metric_period(metric, key):
    return metric.periods.get(key) if isinstance(metric.periods, dict) else metric.periods


def comparison_figure(series_map, metric, selected, start, end):
    """Several countries on one set of axes, as actual published observations."""
    if not selected:
        return empty_figure(NO_COUNTRY_TEXT)

    fig = go.Figure()
    drawn = 0
    all_values = []
    daily = False
    for key in selected:
        tidy = model.clip_series(series_map.get(key), start, end)
        if tidy.empty:
            continue
        period = _metric_period(metric, key) or model.infer_observation_period(series_map.get(key))
        name = COUNTRY_LABELS[key]
        colour = COUNTRY_COLORS[key]
        if period is None:
            # Daily: the browser formats the value and the hover header shows the date.
            daily = True
            hover = dict(hovertemplate='%{fullData.name}: %{y:.2%}<extra></extra>')
        else:
            # One line per country, each with its own period ("Q3 2026", "Jun 2026").
            hover = dict(
                text=[
                    f'{name}: {model.format_observation_value(value, "%")}  ·  '
                    f'{model.format_observation_date(when, period)}'
                    for when, value in zip(tidy['Date'], tidy['value'])
                ],
                hovertemplate='%{text}<extra></extra>',
            )
        fig.add_trace(go.Scatter(
            x=tidy['Date'].dt.strftime('%Y-%m-%d').tolist(),
            y=tidy['value'].round(Y_DECIMALS['%']).tolist(),
            # A lone point has no line to draw.
            mode='markers' if len(tidy) == 1 else 'lines+markers' if period == 'quarter' else 'lines',
            name=name,
            line=dict(color=colour, width=1.9),
            marker=dict(color=colour, size=5),
            cliponaxis=False,
            connectgaps=False,
            **hover,
        ))
        all_values.extend(tidy['value'])
        drawn += 1

    if not drawn:
        states = {model.series_state(series_map.get(key), start, end) for key in selected}
        if states == {'unavailable'}:
            return empty_figure(UNAVAILABLE_TEXT)
        return empty_figure('No published observations in this range')

    values = pd.Series(all_values)
    y_min, y_max = _y_range(values, '%', include_zero=metric.key in ('gdpYoY',))
    _base_layout(fig)
    # One line per country keeps the unified tooltip short enough for a one-screen tile.
    fig.update_layout(hovermode='x unified', hoverlabel_font_size=11)
    fig.update_xaxes(range=[pd.Timestamp(start), pd.Timestamp(end)])
    first = min(trace.x[0] for trace in fig.data)
    fig.update_xaxes(
        tickformat=_x_axis_format(first, end),
        hoverformat='%d %b %Y' if daily else '%b %Y',
    )
    fig.update_yaxes(range=[y_min, y_max], **_y_axis_format('%', y_max - y_min))
    if metric.key == 'gdpYoY':
        fig.add_hline(y=0, line_width=1.2, line_dash='dot', line_color=THEME['text_muted'])
    return fig


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def _segmented(component_id, options, value, label, checklist=False, **props):
    component = dcc.Checklist if checklist else dcc.RadioItems
    return html.Div(
        component(
            id=component_id,
            options=options,
            value=value,
            className='ed-seg',
            labelClassName='ed-seg-option',
            inputClassName='ed-seg-input',
            **props,
        ),
        className='ed-control',
        **{'role': 'group', 'aria-label': label},
    )


def kpi_card(snap, tooltip=None):
    delta = []
    if snap.delta_text:
        delta = [html.Span(
            snap.delta_text,
            className=f'ed-kpi-delta ed-kpi-delta--{snap.delta_direction}',
            title='Change since the previous reading',
        )]
    return html.Div(
        [
            html.Div(snap.label, className='ed-kpi-label'),
            html.Div([html.Span(snap.value_text, className='ed-kpi-value'), *delta], className='ed-kpi-main'),
            html.Div(snap.as_of, className='ed-kpi-meta'),
        ],
        className='ed-card ed-kpi' + ('' if snap.has_data else ' ed-kpi--empty'),
        title=tooltip,
    )


def placeholder_kpis(count=5):
    return [
        kpi_card(model.Snapshot('', '—', None, None, '', False))
        for _ in range(count)
    ]


def comparison_as_of(metric, series_map):
    """'As of Q3 2026 · UK Q2 2026 · NO Jun 2026': the date of the newest reading,
    then each economy whose latest reading is dated differently."""
    seen = []
    for key in COMPARISON_DEFAULT:
        _, when = model.latest_observation(series_map.get(key))
        if when is not None:
            seen.append((key, when, model.format_observation_date(when, _metric_period(metric, key))))
    if not seen:
        return 'No data'
    newest = max(when for _, when, _ in seen)
    base = next(stamp for _, when, stamp in seen if when == newest)
    others = [f'{COUNTRY_CODES[key]} {stamp}' for key, _, stamp in seen if stamp != base]
    return ' · '.join([f'As of {base}', *others])


def comparison_kpi_card(metric, series_map, selected):
    """All four economies, always: the ones switched off are dimmed so the card
    keeps its height while the chips are toggled."""
    rows = []
    tooltip = []
    for key in COMPARISON_DEFAULT:
        on = key in selected
        value, when = model.latest_observation(series_map.get(key))
        text = model.fmt_pct(value)
        period = _metric_period(metric, key)
        stamp = model.format_observation_date(when, period) if when is not None else 'no data'
        tooltip.append(f'{COUNTRY_LABELS[key]}: {text} ({stamp})' + ('' if on else ' · not shown'))
        classes = ['ed-cmp-row']
        if not on:
            classes.append('ed-cmp-row--off')
        if value is None:
            classes.append('ed-cmp-row--empty')
        rows.append(html.Span(
            [
                html.Span(className='ed-dot', style={'background': COUNTRY_COLORS[key]}),
                html.Span(COUNTRY_CODES[key], className='ed-cmp-code'),
                html.Span(text, className='ed-cmp-value'),
            ],
            className=' '.join(classes),
        ))
    as_of = comparison_as_of(metric, series_map)
    return html.Div(
        [
            html.Div(metric.label, className='ed-kpi-label'),
            html.Div(rows, className='ed-cmp'),
            html.Div(as_of, className='ed-kpi-meta', title=as_of),
        ],
        className='ed-card ed-kpi ed-kpi--compare',
        title='\n'.join(tooltip),
    )


def sub_line(axis, source_text):
    """Axis description, then the source and observation date (which short
    screens keep when they drop the axis description)."""
    return html.Div(
        [
            html.Span(axis, className='ed-tile-axis'),
            html.Span(' · ', className='ed-tile-sep'),
            html.Span(source_text, className='ed-tile-asof'),
        ],
        className='ed-tile-sub',
        title=f'{axis} · {source_text}',
    )


def _graph(figure):
    return dcc.Graph(
        figure=figure,
        className='ed-graph',
        responsive=True,
        config=GRAPH_CONFIG,
    )


def chart_tile(chart, frame, start, end):
    tidy = model.clean_series(frame)
    latest, _ = model.latest_observation(tidy)
    chip = model.format_observation_value(latest, chart.tick) if latest is not None else '—'
    return html.Section(
        [
            html.Div(
                [
                    html.H3(chart.short, className='ed-tile-title', title=chart.title),
                    html.Span(chip, className='ed-tile-chip'),
                    sub_line(chart.axis, model.source_as_of(chart.source, tidy, chart.period)),
                ],
                className='ed-tile-head',
            ),
            _graph(tile_figure(tidy, chart, start, end)),
        ],
        className='ed-card ed-tile',
    )


def legend_items(selected, missing=()):
    """One chip per selected country; those with nothing to draw say so."""
    return html.Div(
        [
            html.Span(
                [
                    html.Span(className='ed-dot', style={'background': COUNTRY_COLORS[key]}),
                    COUNTRY_LABELS[key] + (' · no data' if key in missing else ''),
                ],
                className='ed-legend-item' + (' ed-legend-item--empty' if key in missing else ''),
                title='No observations in this range' if key in missing else None,
            )
            for key in selected
        ],
        className='ed-legend',
    )


def comparison_tile(metric, series_map, selected, start, end):
    missing = [key for key in selected if model.series_state(series_map.get(key), start, end) != 'ok']
    return html.Section(
        [
            html.Div(
                [
                    html.H3(metric.title, className='ed-tile-title', title=metric.title),
                    legend_items(selected, missing),
                    sub_line(metric.axis, metric.source),
                ],
                className='ed-tile-head ed-tile-head--legend',
            ),
            _graph(comparison_figure(series_map, metric, selected, start, end)),
        ],
        className='ed-card ed-tile',
    )


def notes_tile(notes):
    return html.Section(
        [
            html.H3('About these indicators', className='ed-tile-title'),
            html.Ul([html.Li(text) for text in notes], className='ed-notes-list'),
            html.H3('Reading the charts', className='ed-tile-title ed-tile-title--spaced'),
            html.Ul(
                [html.Li([html.Span(className=f'ed-key {key}'), text]) for key, text in CHART_LEGEND],
                className='ed-notes-legend',
            ),
        ],
        className='ed-card ed-tile ed-tile--notes',
    )


COMPARISON_LEGEND_NOTE = 'Dotted line: zero. Hover a chart for each economy\'s reading and its date.'


def footnote(notes, legend=CHART_LEGEND_NOTE):
    """Source notes, then the chart key (the comparison draws no red dot, so it has its own)."""
    return [html.Div(text, className='ed-footnote-line') for text in (*notes, legend)]


def country_detail_tile(country_key, country, start, end):
    label = ds.EU_COUNTRIES[country_key]['label']
    stats = []
    for kpi in model.EU_DETAIL_KPIS:
        snap = model.snapshot(kpi, country.get(kpi.key))
        stats.append(html.Div(
            [
                html.Div(kpi.short or kpi.label, className='ed-mini-label', title=kpi.label),
                html.Div(snap.value_text, className='ed-mini-value'),
                html.Div(snap.as_of, className='ed-mini-meta'),
            ],
            className='ed-mini',
        ))
    chart = model.Chart(
        'stockIndex', f'{label} Stock Index', f'{label} stock index', 'Index level', 'index',
        'Yahoo Finance', model.EU_DETAIL_CHART_COLOR,
    )
    latest, _ = model.latest_observation(country.get('stockIndex'))
    chip = model.format_observation_value(latest, 'index') if latest is not None else '—'
    return html.Section(
        [
            html.Div(
                [
                    html.H3(f'Country detail · {label}', className='ed-tile-title'),
                    html.Span(chip, className='ed-tile-chip'),
                    sub_line(chart.axis, model.source_as_of(chart.source, country.get('stockIndex'))),
                ],
                className='ed-tile-head',
            ),
            html.Div(
                [
                    html.Div(stats, className='ed-detail-stats'),
                    _graph(tile_figure(country.get('stockIndex'), chart, start, end)),
                ],
                className='ed-detail-body',
            ),
        ],
        className='ed-card ed-tile ed-tile--detail',
    )


def message_tile(message):
    return html.Section(
        html.Div(message, className='ed-empty'),
        className='ed-card ed-tile ed-tile--message',
    )


# ---------------------------------------------------------------------------
# One render function per view
# ---------------------------------------------------------------------------

def render_market(market_key, data, window, eu_country=None):
    """(kpis, tiles, footnote) for a single-country view."""
    market = model.MARKETS[market_key]
    start, end = window
    data = data or {}

    kpis = [kpi_card(model.snapshot(kpi, data.get(kpi.key))) for kpi in market.kpis]
    tiles = [chart_tile(chart, data.get(chart.key), start, end) for chart in market.charts]

    if market.has_country_detail:
        key = eu_country if eu_country in ds.EU_COUNTRIES else next(iter(ds.EU_COUNTRIES))
        country = (data.get('countries') or {}).get(key) or {}
        tiles.append(country_detail_tile(key, country, start, end))

    # Norway (9 charts) and the UK (5) leave a cell free in their grid: use it for notes.
    if market_key in ('norway', 'uk'):
        tiles.append(notes_tile(market.notes))
    return kpis, tiles, footnote(market.notes)


def render_comparison(data, selected, window):
    start, end = window
    data = data or {}
    selected = [key for key in COMPARISON_DEFAULT if key in (selected or [])]
    kpis = [comparison_kpi_card(metric, data.get(metric.key, {}), selected) for metric in model.COMPARISON_METRICS]
    tiles = [comparison_tile(metric, data.get(metric.key, {}), selected, start, end) for metric in model.COMPARISON_METRICS]
    return kpis, tiles, footnote(model.COMPARISON_NOTES, COMPARISON_LEGEND_NOTE)


def render_unavailable(market_key, message):
    count = 4 if market_key in ('uk', 'comparison') else 5
    return placeholder_kpis(count), [message_tile(message)], []


def checked_at():
    return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _placeholder_tiles(count=10):
    return [
        html.Section(
            html.Div(className='ed-skeleton'),
            className='ed-card ed-tile ed-tile--skeleton',
        )
        for _ in range(count)
    ]


layout = html.Div(
    [
        dcc.Interval(id='ed-interval', interval=REFRESH_INTERVAL_MS, n_intervals=0),
        dcc.Loading(
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Canvas(
                                        id='algo-trend-canvas',
                                        className='ed-trend',
                                        **{'aria-hidden': 'true'},
                                    ),
                                    html.Div(
                                        [
                                            html.Div('Macro dashboard', className='ed-eyebrow'),
                                            html.H1('Economy Overview', className='ed-title'),
                                            html.Div(
                                                'Each card and chart shows its observation date',
                                                id='ed-asof',
                                                className='ed-subtitle',
                                            ),
                                            html.P(HERO_TEXT, className='ed-hero-description'),
                                        ],
                                        className='ed-title-text',
                                    ),
                                    html.Div(
                                        [
                                            _segmented(
                                                'ed-view',
                                                VIEW_OPTIONS,
                                                DEFAULT_VIEW,
                                                'Page layout',
                                                persistence=True,
                                                persistence_type='local',
                                            ),
                                            # Shown (by CSS) only when the window is too small for the dashboard.
                                            html.Div(VIEW_HINT, className='ed-view-hint'),
                                        ],
                                        className='ed-view-control',
                                    ),
                                ],
                                className='ed-head',
                            ),
                            html.Div(
                                [
                                    _segmented('ed-market', MARKET_OPTIONS, DEFAULT_MARKET, 'Market'),
                                    _segmented('ed-range', RANGE_OPTIONS, DEFAULT_RANGE, 'Date range'),
                                    html.Div(
                                        _segmented(
                                            'ed-eu-country', EU_COUNTRY_OPTIONS,
                                            next(iter(ds.EU_COUNTRIES)), 'Euro Area country detail',
                                        ),
                                        className='ed-context ed-context--eu',
                                    ),
                                    html.Div(
                                        _segmented(
                                            'ed-countries', COMPARISON_OPTIONS, COMPARISON_DEFAULT,
                                            'Countries to compare', checklist=True,
                                        ),
                                        className='ed-context ed-context--comparison',
                                    ),
                                    html.Button(
                                        'Refresh',
                                        id='ed-refresh',
                                        n_clicks=0,
                                        className='ed-refresh',
                                        title='Fetch fresh data from the sources',
                                    ),
                                ],
                                className='ed-controls',
                            ),
                        ],
                        className='ed-topbar',
                    ),
                    html.Section(placeholder_kpis(), id='ed-kpis', className='ed-kpis'),
                    html.Div(_placeholder_tiles(), id='ed-grid', className='ed-grid'),
                    html.Div([], id='ed-footnote', className='ed-footnote'),
                ],
                className='ed-body',
            ),
            custom_spinner=html.Div(LOADING_TEXT, className='ed-spinner'),
            parent_className='ed-loading',
            overlay_style={'visibility': 'visible', 'opacity': 0.55},
            delay_show=250,
        ),
    ],
    id='ed-page',
    className=f'ed-page ed-page--{DEFAULT_VIEW}',
    **{'data-market': DEFAULT_MARKET},
)

# Flip the layout class without a server round-trip (see assets/economy-dashboard.js).
clientside_callback(
    ClientsideFunction(namespace='economy_dashboard', function_name='set_layout'),
    Output('ed-page', 'className'),
    Input('ed-view', 'value'),
)


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

@callback(
    [
        Output('ed-kpis', 'children'),
        Output('ed-grid', 'children'),
        Output('ed-footnote', 'children'),
        Output('ed-asof', 'children'),
        Output('ed-page', 'data-market'),
    ],
    [
        Input('ed-market', 'value'),
        Input('ed-range', 'value'),
        Input('ed-refresh', 'n_clicks'),
        Input('ed-interval', 'n_intervals'),
        Input('ed-countries', 'value'),
        Input('ed-eu-country', 'value'),
    ],
    # Greyed out while a fetch is in flight, so an impatient second click does not
    # queue another one behind it.
    running=[(Output('ed-refresh', 'disabled'), True, False)],
)
def update_dashboard(market, range_key, n_clicks, n_intervals, countries, eu_country):
    market = market if market in model.MARKETS or market == 'comparison' else DEFAULT_MARKET
    window = model.resolve_window(range_key)
    force = callback_context.triggered_id == 'ed-refresh'

    try:
        if market == 'comparison':
            data = model.refresh_market('comparison') if force else model.load_comparison()
            kpis, tiles, notes = render_comparison(data, countries, window)
        else:
            data = model.refresh_market(market) if force else model.load_market(market)
            kpis, tiles, notes = render_market(market, data, window, eu_country)
    except Exception:  # noqa: BLE001 - show a friendly state and log the cause
        logger.exception('Economy dashboard failed to render %s', market)
        kpis, tiles, notes = render_unavailable(
            market, 'Economic data is unavailable right now. Please try again shortly.',
        )

    detail = (
        'each card shows the date of its latest observation'
        if market == 'comparison'
        else 'each card and chart shows its observation date'
    )
    return kpis, tiles, notes, f'Data checked {checked_at()} · {detail}', market
