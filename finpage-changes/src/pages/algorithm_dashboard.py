"""One-screen dashboard variant of the Algorithm page (/algorithm-dashboard).

Same data and numbers as ``pages/algorithm.py``, laid out for a desktop
viewport so the history chart, selected-window chart, KPIs and current
composition are all visible at once without scrolling.  Styles live in
``assets/algorithm-dashboard.css`` (``.ad-*`` classes).
"""

import logging
from html import escape as html_escape
from urllib.parse import quote

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from algorithm_data import get_dashboard_data, ytd_return_by_symbol
from portfolio_history import (
    calculate_returns_since_inclusion,
    calculate_strategy_max_drawdown,
)
from theme import LIGHT_THEME as THEME


dash.register_page(
    __name__,
    path='/algorithm-dashboard',
    name='Algorithm Dashboard',
    title='Algorithm Dashboard',
)

logger = logging.getLogger(__name__)


GRAPH_CONFIG = {
    'displayModeBar': False,
    'responsive': True,
    'scrollZoom': False,
    'doubleClick': False,
}

DESCRIPTIONS = {
    '2015': (
        'The algorithm was fitted over 2015-2024 to optimize the Sharpe Ratio of a '
        'stock-selection strategy based on fundamental factors from Morningstar. '
        'The charts use monthly observations in training and daily observations '
        'after training.'
    ),
    '2020': (
        'The algorithm was fitted over 2020-2024 to optimize the Sharpe Ratio of a '
        'stock-selection strategy based on fundamental factors from Morningstar. '
        'The charts use monthly observations in training and daily observations '
        'after training.'
    ),
}

WINDOW_LABELS = {'testing': 'Testing period', 'ytd': 'Year to date'}

TRAINING_YEARS = {'2015': '2015-2024', '2020': '2020-2024'}

LOADING_TEXT = 'Loading market data…'

KPI_LABELS = ('Portfolio return', 'ACWI benchmark', 'Annualized volatility', 'Max drawdown')


def _empty_figure(message):
    """A blank, axis-less figure that just shows a message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(size=14, color=THEME['text_muted']),
    )
    fig.update_layout(
        plot_bgcolor=THEME['transparent'],
        paper_bgcolor=THEME['transparent'],
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        margin=dict(l=10, r=10, t=10, b=10),
        dragmode=False,
    )
    return fig


def _subtitle(training):
    return (
        'Morningstar fundamentals · fitted '
        f'{TRAINING_YEARS.get(training, TRAINING_YEARS["2020"])} to maximize Sharpe ratio'
    )


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _segmented(component_id, label, options, value):
    label_id = f'{component_id}-label'
    return html.Div(
        [
            html.Div(label, id=label_id, className='ad-control-label'),
            dcc.RadioItems(
                id=component_id,
                options=options,
                value=value,
                className='ad-seg',
                labelClassName='ad-seg-option',
                inputClassName='ad-seg-input',
            ),
        ],
        className='ad-control',
    )


def _kpi_card(label, value='—', sub='', tone='neutral', tip=None):
    return html.Div(
        [
            html.Div(label, className='ad-kpi-label'),
            html.Div(value, className='ad-kpi-value'),
            html.Div(sub, className='ad-kpi-sub'),
        ],
        className=f'ad-card ad-kpi ad-kpi--{tone}',
        title=tip,
    )


def _legend_item(label, swatch_class):
    return html.Span(
        [html.Span(className=f'ad-swatch {swatch_class}'), label],
        className='ad-legend-item',
    )


def _chart_card(title_id, graph_id, title, legend):
    return html.Section(
        [
            html.Div(
                [
                    html.H2(title, id=title_id, className='ad-card-title'),
                    html.Div(legend, className='ad-legend'),
                ],
                className='ad-card-head',
            ),
            dcc.Graph(
                id=graph_id,
                className='ad-graph',
                responsive=True,
                config=GRAPH_CONFIG,
                figure=_empty_figure(''),
                style={'height': '100%'},
            ),
        ],
        className='ad-card ad-chart-card',
    )


_PORTFOLIO_LEGEND = [
    _legend_item('Portfolio', 'ad-swatch--portfolio'),
    _legend_item('ACWI benchmark', 'ad-swatch--benchmark'),
]


layout = html.Div(
    [
        html.Header(
            [
                html.Canvas(
                    id='algo-trend-canvas',
                    className='ad-trend',
                    **{'aria-hidden': 'true'},
                ),
                html.Div(
                    [
                        html.Div('Factor investing dashboard', className='ad-eyebrow'),
                        html.H1('Optimized Factor Portfolio', className='ad-title'),
                        html.Div(_subtitle('2020'), id='ad-subtitle', className='ad-subtitle'),
                    ],
                    className='ad-title-block',
                ),
                html.Div(
                    [
                        _segmented(
                            'ad-training',
                            'Training period',
                            [
                                {'label': '2015-2024', 'value': '2015'},
                                {'label': '2020-2024', 'value': '2020'},
                            ],
                            '2020',
                        ),
                        _segmented(
                            'ad-window',
                            'Performance window',
                            [
                                {'label': 'Testing period', 'value': 'testing'},
                                {'label': 'YTD', 'value': 'ytd'},
                            ],
                            'testing',
                        ),
                        _segmented(
                            'ad-currency',
                            'Base currency',
                            [
                                {'label': 'USD', 'value': 'USD'},
                                {'label': 'NOK', 'value': 'NOK'},
                            ],
                            'USD',
                        ),
                    ],
                    className='ad-controls',
                ),
            ],
            className='ad-card ad-topbar',
        ),

        dcc.Loading(
            html.Div(
                [
                    html.Section(
                        [_kpi_card(label) for label in KPI_LABELS],
                        id='ad-kpis',
                        className='ad-kpis',
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    _chart_card(
                                        'ad-full-title',
                                        'ad-full-graph',
                                        'Training + testing performance · USD',
                                        _PORTFOLIO_LEGEND,
                                    ),
                                    _chart_card(
                                        'ad-period-title',
                                        'ad-period-graph',
                                        'Testing period performance · USD',
                                        _PORTFOLIO_LEGEND,
                                    ),
                                ],
                                className='ad-charts',
                            ),
                            html.Div(
                                [
                                    html.Section(
                                        [
                                            html.Div(
                                                [
                                                    html.H2(
                                                        'Current composition',
                                                        className='ad-card-title',
                                                    ),
                                                    html.Span(
                                                        id='ad-holdings-count',
                                                        className='ad-chip',
                                                    ),
                                                ],
                                                className='ad-card-head',
                                            ),
                                            html.Div(
                                                'Swipe horizontally to view all columns',
                                                className='ad-scroll-hint',
                                            ),
                                            html.Div(
                                                html.Div('Loading composition…', className='ad-table-placeholder'),
                                                id='ad-table',
                                                className='ad-table-wrap',
                                            ),
                                        ],
                                        className='ad-card ad-composition-card',
                                    ),
                                    html.Section(
                                        [
                                            html.H2('About the model', className='ad-card-title'),
                                            html.P(DESCRIPTIONS['2020'], id='ad-description', className='ad-about-text'),
                                            html.Ul(
                                                [
                                                    html.Li('Shaded band: training period, monthly observations.'),
                                                    html.Li('Dashed line: where daily testing begins.'),
                                                    html.Li('Labels on the right edge: latest cumulative return.'),
                                                ],
                                                className='ad-about-list',
                                            ),
                                            html.Div(LOADING_TEXT, id='ad-asof', className='ad-asof'),
                                        ],
                                        className='ad-card ad-about-card',
                                    ),
                                ],
                                className='ad-side',
                            ),
                        ],
                        className='ad-main',
                    ),
                ],
                className='ad-body',
            ),
            custom_spinner=html.Div(LOADING_TEXT, className='ad-spinner'),
            parent_className='ad-loading',
            overlay_style={'visibility': 'visible', 'opacity': 0.55},
            delay_show=250,
        ),
    ],
    className='ad-page',
)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _performance_figure(frame, training_end=None):
    """Portfolio vs ACWI cumulative return, compact enough for a dashboard card.

    ``frame`` needs a ``Date`` column plus ``Portfolio_Cumulative_Period`` and
    ``ACWI_Cumulative_Period``.  When ``training_end`` falls inside the frame the
    training region is shaded and the testing boundary is marked.
    """
    if frame.empty:
        return _empty_figure('No data for this window')

    frame = frame.sort_values('Date')
    dates = frame['Date']
    portfolio = frame['Portfolio_Cumulative_Period']
    benchmark = frame['ACWI_Cumulative_Period']

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=portfolio,
        mode='lines',
        name='Portfolio',
        line=dict(color=THEME['blue'], width=2.6),
        fill='tozeroy',
        fillcolor='rgba(3,105,161,0.07)',
        hovertemplate='<b>Portfolio</b> %{y:+.1%}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=benchmark,
        mode='lines',
        name='ACWI',
        line=dict(color=THEME['border_strong'], width=1.9),
        hovertemplate='<b>ACWI</b> %{y:+.1%}<extra></extra>',
    ))

    last_date = dates.iloc[-1]
    last_portfolio = float(portfolio.iloc[-1])
    last_benchmark = float(benchmark.iloc[-1])

    low = min(0.0, float(portfolio.min()), float(benchmark.min()))
    high = max(0.0, float(portfolio.max()), float(benchmark.max()))
    span = max(high - low, 0.05)
    y_range = [low - span * 0.06, high + span * 0.08]

    # Keep the two end-of-line labels from sitting on top of each other.
    close = abs(last_portfolio - last_benchmark) < span * 0.09
    portfolio_shift = 0
    benchmark_shift = 0
    if close:
        portfolio_shift, benchmark_shift = (
            (8, -8) if last_portfolio >= last_benchmark else (-8, 8)
        )

    for value, color, shift in (
        (last_portfolio, THEME['blue'], portfolio_shift),
        (last_benchmark, THEME['border_strong'], benchmark_shift),
    ):
        fig.add_trace(go.Scatter(
            x=[last_date],
            y=[value],
            mode='markers',
            marker=dict(size=7, color=color, line=dict(color='#FFFFFF', width=1.5)),
            showlegend=False,
            hoverinfo='skip',
        ))
        fig.add_annotation(
            x=last_date,
            y=value,
            text=f'<b>{value:+.1%}</b>',
            showarrow=False,
            xanchor='left',
            xshift=9,
            yshift=shift,
            font=dict(size=11, color=color),
        )

    if training_end is not None:
        boundary = pd.to_datetime(training_end)
        if dates.iloc[0] < boundary < last_date:
            fig.add_shape(
                type='rect',
                x0=dates.iloc[0],
                x1=boundary,
                y0=0,
                y1=1,
                xref='x',
                yref='paper',
                fillcolor='rgba(3,105,161,0.055)',
                line=dict(width=0),
                layer='below',
            )
            fig.add_shape(
                type='line',
                x0=boundary,
                x1=boundary,
                y0=0,
                y1=1,
                xref='x',
                yref='paper',
                line=dict(color=THEME['amber'], width=1.5, dash='dash'),
            )
            fig.add_annotation(
                x=dates.iloc[0],
                y=1,
                xref='x',
                yref='paper',
                text='Training · monthly',
                showarrow=False,
                xanchor='left',
                yanchor='top',
                xshift=6,
                yshift=-4,
                font=dict(size=10, color=THEME['text_muted']),
            )
            fig.add_annotation(
                x=boundary,
                y=1,
                xref='x',
                yref='paper',
                text='Testing · daily',
                showarrow=False,
                xanchor='left',
                yanchor='top',
                xshift=6,
                yshift=-4,
                font=dict(size=10, color=THEME['amber']),
            )

    fig.update_layout(
        font=dict(family='Helvetica, Arial, sans-serif', size=11, color=THEME['text_secondary']),
        plot_bgcolor=THEME['transparent'],
        paper_bgcolor=THEME['transparent'],
        margin=dict(l=44, r=58, t=8, b=30),
        showlegend=False,
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor=THEME['tooltip_bg'],
            bordercolor=THEME['tooltip_bg'],
            font=dict(color=THEME['tooltip_text'], size=12),
        ),
        dragmode=False,
        uirevision='ad',
    )
    fig.update_xaxes(
        range=[dates.iloc[0], last_date],
        showgrid=False,
        linecolor=THEME['border'],
        tickfont=dict(size=11, color=THEME['text_muted']),
        hoverformat='%b %d, %Y',
        fixedrange=True,
        nticks=8,
    )
    fig.update_yaxes(
        range=y_range,
        showgrid=True,
        gridcolor=THEME['grid'],
        zeroline=True,
        zerolinecolor=THEME['border_strong'],
        zerolinewidth=1,
        tickformat='.0%',
        tickfont=dict(size=11, color=THEME['text_muted']),
        fixedrange=True,
        nticks=6,
    )
    return fig


# ---------------------------------------------------------------------------
# Composition table
# ---------------------------------------------------------------------------

def _signed_pct(value):
    return '—' if pd.isna(value) else f'{value:+.1f}%'


def _composition_table(bundle, today):
    composition = bundle['composition']
    full_symbol_df = bundle['full_symbol_df']
    current_date = pd.to_datetime(today)

    current = composition[
        (composition['ValidFrom'] <= current_date) &
        (composition['ValidTo'] >= current_date)
    ].copy()

    if current.empty:
        return html.Div('No current composition', className='ad-empty'), 0

    ytd = ytd_return_by_symbol(full_symbol_df, pd.Timestamp(current_date.year, 1, 1))
    since_inclusion = calculate_returns_since_inclusion(full_symbol_df, current, today)

    current['YTD_Value'] = pd.to_numeric(current['Symbol'].map(ytd), errors='coerce') * 100
    current['SinceInclusion_Value'] = pd.to_numeric(
        since_inclusion.reindex(current.index), errors='coerce'
    ) * 100
    current = current.sort_values('YTD_Value', ascending=False, na_position='last')

    current['YTD'] = current['YTD_Value'].map(_signed_pct)
    current['SinceInclusion'] = current['SinceInclusion_Value'].map(_signed_pct)
    current['ValidFrom'] = pd.to_datetime(current['ValidFrom']).dt.strftime('%Y-%m-%d')
    current['Company'] = [
        '<a href="https://www.marketwatch.com/investing/stock/'
        f'{quote(str(symbol).lower(), safe="")}" '
        'target="_blank" rel="noopener noreferrer">'
        f'{html_escape(str(company) if pd.notna(company) else str(symbol))}</a>'
        for symbol, company in zip(current['Symbol'], current['Company'])
    ]

    records = current[[
        'Company', 'Symbol', 'YTD', 'YTD_Value',
        'SinceInclusion', 'SinceInclusion_Value', 'ValidFrom',
    ]].to_dict('records')

    def tone(column, value_column, positive):
        op = '>' if positive else '<'
        return {
            'if': {'column_id': column, 'filter_query': f'{{{value_column}}} {op} 0'},
            'color': THEME['green'] if positive else THEME['red'],
            'fontWeight': '700',
        }

    table = dash_table.DataTable(
        data=records,
        columns=[
            {'name': 'Company', 'id': 'Company', 'presentation': 'markdown', 'type': 'text'},
            {'name': 'Symbol', 'id': 'Symbol'},
            {'name': 'YTD', 'id': 'YTD'},
            {'name': 'Since incl.', 'id': 'SinceInclusion'},
            {'name': 'Valid from', 'id': 'ValidFrom'},
        ],
        markdown_options={'html': True},
        sort_action='native',
        cell_selectable=False,
        row_selectable=False,
        page_size=10,
        style_as_list_view=True,
        style_cell={
            'textAlign': 'left',
            'padding': '8px 8px',
            'fontFamily': 'Arial, sans-serif',
            'fontSize': '12.5px',
            'lineHeight': '1.3',
            'color': THEME['text_primary'],
            'backgroundColor': THEME['surface'],
            'border': 'none',
            'borderBottom': f"1px solid {THEME['grid']}",
        },
        style_cell_conditional=[
            {'if': {'column_id': 'Company'}, 'width': '32%', 'minWidth': '96px'},
            {'if': {'column_id': 'Symbol'}, 'width': '14%', 'fontWeight': '700'},
            *[
                {'if': {'column_id': column}, 'textAlign': 'right'}
                for column in ('YTD', 'SinceInclusion')
            ],
        ],
        style_header={
            'backgroundColor': THEME['surface_subtle'],
            'color': THEME['text_muted'],
            'fontWeight': '700',
            'fontSize': '11px',
            'padding': '8px 8px',
            'border': 'none',
            'borderBottom': f"1px solid {THEME['border']}",
        },
        style_header_conditional=[
            {'if': {'column_id': c}, 'textAlign': 'right'}
            for c in ('YTD', 'SinceInclusion')
        ],
        style_data_conditional=[
            tone('YTD', 'YTD_Value', True),
            tone('YTD', 'YTD_Value', False),
            tone('SinceInclusion', 'SinceInclusion_Value', True),
            tone('SinceInclusion', 'SinceInclusion_Value', False),
        ],
        style_table={'overflowX': 'auto', 'maxHeight': '100%'},
    )
    return table, len(current)


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

def _unavailable_outputs(training, window, currency, message):
    placeholder = _empty_figure(message)
    return (
        [_kpi_card(label) for label in KPI_LABELS],
        placeholder,
        placeholder,
        f'Training + testing performance · {currency}',
        f'{WINDOW_LABELS.get(window, "Selected-period")} performance · {currency}',
        html.Div(message, className='ad-empty'),
        '',
        _subtitle(training),
        DESCRIPTIONS.get(training, DESCRIPTIONS['2020']),
        'Data unavailable',
    )


@callback(
    [
        Output('ad-kpis', 'children'),
        Output('ad-full-graph', 'figure'),
        Output('ad-period-graph', 'figure'),
        Output('ad-full-title', 'children'),
        Output('ad-period-title', 'children'),
        Output('ad-table', 'children'),
        Output('ad-holdings-count', 'children'),
        Output('ad-subtitle', 'children'),
        Output('ad-description', 'children'),
        Output('ad-asof', 'children'),
    ],
    [
        Input('ad-training', 'value'),
        Input('ad-window', 'value'),
        Input('ad-currency', 'value'),
    ],
)
def update_dashboard(training, window, currency):
    training = training or '2020'
    window = window or 'testing'
    currency = currency or 'USD'

    try:
        bundle = get_dashboard_data(training, currency)
    except Exception:  # noqa: BLE001 - surface a friendly state, log the cause
        logger.exception('Algorithm dashboard data load failed')
        return _unavailable_outputs(
            training, window, currency,
            'Market data or the composition workbook is unavailable right now. Please try again shortly.',
        )

    if bundle['portfolio_returns'].empty:
        return _unavailable_outputs(
            training, window, currency,
            'No data available - check AlgoComposition.xlsx.',
        )

    today = bundle['today']
    combined = bundle['combined_performance']
    training_end = bundle['training_end']
    portfolio_returns = bundle['portfolio_returns']
    testing_returns = portfolio_returns[portfolio_returns.index > training_end]

    # Selected window (testing period or YTD), rebased to 0 at its start.
    if window == 'ytd':
        start_date = pd.Timestamp(today.year, 1, 1)
    else:
        start_date = testing_returns.index.min() if not testing_returns.empty else training_end

    period_returns = testing_returns[
        (testing_returns.index >= start_date) & (testing_returns.index <= today)
    ].copy()

    if period_returns.empty:
        total_return = benchmark_return = volatility = np.nan
        period_frame = pd.DataFrame(columns=[
            'Date', 'Portfolio_Cumulative_Period', 'ACWI_Cumulative_Period',
        ])
    else:
        period_returns['Portfolio_Cumulative_Period'] = (
            1 + period_returns['Portfolio_Return']
        ).cumprod() - 1
        period_returns['ACWI_Cumulative_Period'] = (
            1 + period_returns['ACWI_Return']
        ).cumprod() - 1
        total_return = float(period_returns['Portfolio_Cumulative_Period'].iloc[-1])
        benchmark_return = float(period_returns['ACWI_Cumulative_Period'].iloc[-1])
        volatility = float(period_returns['Portfolio_Return'].std() * np.sqrt(252))
        period_frame = period_returns.rename_axis('Date').reset_index()

    max_drawdown = calculate_strategy_max_drawdown(training, combined)
    excess = total_return - benchmark_return if pd.notna(total_return) else np.nan

    since_label = f'Since {start_date:%b %d, %Y}' if window == 'testing' else f'Since Jan 1, {today.year}'

    def pct(value):
        return '—' if pd.isna(value) else f'{value:.1%}'

    def signed(value):
        return '—' if pd.isna(value) else f'{value:+.1%}'

    kpis = [
        _kpi_card(
            f'{WINDOW_LABELS[window]} return',
            signed(total_return),
            f'{since_label} · {currency}',
            tone='positive' if pd.notna(total_return) and total_return >= 0 else 'negative',
            tip='Compounded daily returns of the portfolio over the selected window.',
        ),
        _kpi_card(
            'ACWI benchmark',
            signed(benchmark_return),
            (
                f'Portfolio {excess * 100:+.1f} pp vs benchmark'
                if pd.notna(excess) else 'Same window'
            ),
            tone='neutral',
            tip='Compounded daily returns of the ACWI benchmark over the same window.',
        ),
        _kpi_card(
            'Annualized volatility',
            pct(volatility),
            f'Daily returns · {WINDOW_LABELS[window].lower()}',
            tone='accent',
            tip='Standard deviation of daily returns in the selected window, annualized.',
        ),
        _kpi_card(
            'Max drawdown',
            pct(max_drawdown),
            f'Training + testing · {currency}',
            tone='negative',
            tip=(
                'The supplied training maximum is the floor; the visible NOK '
                'training path uses monthly observations.'
                if currency == 'NOK'
                else 'The single worst peak-to-trough loss across the full strategy history.'
            ),
        ),
    ]

    full_frame = combined.rename_axis('Date').reset_index()
    full_figure = _performance_figure(full_frame, training_end=training_end)
    period_figure = _performance_figure(period_frame)

    table, holdings = _composition_table(bundle, today)

    return (
        kpis,
        full_figure,
        period_figure,
        f'Training + testing performance · {currency}',
        f'{WINDOW_LABELS[window]} performance · {currency}',
        table,
        f'{holdings} holdings',
        _subtitle(training),
        DESCRIPTIONS.get(training, DESCRIPTIONS['2020']),
        f'Data as of {today:%b %d, %Y} · prices via Yahoo Finance · returns in {currency}',
    )
