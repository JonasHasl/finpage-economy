import pandas as pd
import plotly.graph_objects as go
from datetime import date
import dash_bootstrap_components as dbc
import dash
from dash import html, dcc, callback, Input, Output
import yfinance as yf
import numpy as np
from workbook_store import get_workbook_path
from portfolio_history import (
    build_combined_performance,
    calculate_returns_since_inclusion,
    calculate_strategy_max_drawdown,
    get_training_dates,
)
from theme import LIGHT_THEME


dash.register_page(__name__, path='/portfolio-daily')


# Decorative canvas for the hero.  assets/algorithm-hero.js draws a rising
# line with a subtle continuous pulse; it is deliberately not presented as
# portfolio data to assistive technology.
def _algo_trend_chart():
    return html.Canvas(
        id='algo-trend-canvas',
        className='algo-trend',
        **{'aria-hidden': 'true'},
    )


colors = {
    'background': LIGHT_THEME['page'],
    'surface': LIGHT_THEME['surface'],
    'content': LIGHT_THEME['surface_subtle'],
    'text-primary': LIGHT_THEME['text_primary'],
    'text': LIGHT_THEME['text_secondary'],
    'header': LIGHT_THEME['text_muted'],
    'border': LIGHT_THEME['border'],
    'grid': LIGHT_THEME['grid'],
    'accent': LIGHT_THEME['blue'],
    'positive': LIGHT_THEME['green'],
    'negative': LIGHT_THEME['red'],
    'warning': LIGHT_THEME['amber'],
    'violet': LIGHT_THEME['violet'],
    'cyan': LIGHT_THEME['cyan'],
    'rose': LIGHT_THEME['rose'],
    # Kept for existing call sites that expect the legacy key name.
    'text-white': LIGHT_THEME['text_primary'],
    'banner': LIGHT_THEME['surface'],
    'banner2': LIGHT_THEME['surface_subtle'],
}


ALGORITHM_GRAPH_CONFIG = {
    'displayModeBar': False,
    'responsive': True,
    'scrollZoom': False,
    'doubleClick': False,
}


def _lock_graph_navigation(fig):
    """Keep hover details available while preventing axis zoom and pan."""
    fig.update_layout(dragmode=False)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


description_2015 = '''The algorithm was fitted over 2015-2024 to optimize the Sharpe Ratio of a stock-selection strategy based on fundamental factors from Morningstar. The chart uses monthly observations in training and daily observations after training.'''
description_2020 = '''The algorithm was fitted over 2020-2024 to optimize the Sharpe Ratio of a stock-selection strategy based on fundamental factors from Morningstar. The chart uses monthly observations in training and daily observations after training.'''


CARD_STYLE = {
    'background': (
        f"linear-gradient(180deg, {colors['surface']} 0%, "
        'rgba(234,241,247,0.72) 100%)'
    ),
    'border': f"1px solid {colors['border']}",
    'borderRadius': '24px',
    'boxShadow': '0 12px 32px rgba(16,42,67,0.08)',
    'height': '100%'
}

SECTION_CARD_STYLE = {
    'background': (
        f"linear-gradient(180deg, {colors['surface']} 0%, "
        'rgba(234,241,247,0.58) 100%)'
    ),
    'borderRadius': '26px',
    'padding': '1.35rem',
    'border': f"1px solid {colors['border']}",
    'boxShadow': '0 12px 32px rgba(16,42,67,0.08)'
}

CARD_BODY_STYLE = {
    'padding': '1.6rem 1.75rem'
}


def create_portfolio_graph(
    title,
    dataframe,
    y_column,
    start_date,
    end_date,
    height=700,
    training_end=None,
    currency=None,
):
    dataframe = pd.DataFrame(dataframe).ffill().fillna(0)

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    if 'Date' not in dataframe.columns:
        dataframe = dataframe.reset_index().rename(columns={'index': 'Date'})

    dataframe['Date'] = pd.to_datetime(dataframe['Date'])

    mask = (dataframe['Date'] >= start_date) & (dataframe['Date'] <= end_date)
    filtered_df = dataframe.loc[mask].copy()

    if filtered_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            showarrow=False,
            font=dict(size=16, color=colors['header']),
        )
        fig.update_layout(
            height=height,
            font=dict(family="Helvetica", size=15, color=colors['text']),
            plot_bgcolor=LIGHT_THEME['transparent'],
            paper_bgcolor=LIGHT_THEME['transparent'],
        )
        return _lock_graph_navigation(fig)

    fig = go.Figure()

    has_phases = 'Phase' in filtered_df.columns and filtered_df['Phase'].nunique() > 1
    if has_phases:
        phase_styles = {
            'Training': {'dash': 'dot', 'opacity': 0.82, 'marker_size': 4},
            'Testing': {'dash': 'solid', 'opacity': 1.0, 'marker_size': 0},
        }
        for phase in ['Training', 'Testing']:
            phase_df = filtered_df[filtered_df['Phase'] == phase].copy()
            if phase_df.empty:
                continue

            style = phase_styles[phase]
            portfolio_marker_sizes = [style['marker_size']] * len(phase_df)
            portfolio_marker_colors = [colors['accent']] * len(phase_df)
            if phase == 'Testing':
                portfolio_marker_sizes[-1] = 8
                portfolio_marker_colors[-1] = colors['negative']

            fig.add_trace(go.Scatter(
                x=phase_df['Date'],
                y=phase_df['Portfolio_Cumulative_Period'],
                mode='lines+markers',
                name=f'Portfolio · {phase}',
                legendgroup='Portfolio',
                line=dict(color=colors['accent'], width=4, dash=style['dash']),
                opacity=style['opacity'],
                marker=dict(color=portfolio_marker_colors, size=portfolio_marker_sizes),
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=phase_df['Date'],
                y=phase_df['ACWI_Cumulative_Period'],
                mode='lines+markers',
                name=f'ACWI · {phase}',
                legendgroup='ACWI',
                line=dict(color=colors['header'], width=2.5, dash=style['dash']),
                opacity=style['opacity'],
                marker=dict(color=colors['header'], size=[style['marker_size']] * len(phase_df)),
                hoverinfo='skip',
            ))

        training_boundary = filtered_df[filtered_df['Phase'] == 'Training'].tail(1)
        testing_start = filtered_df[filtered_df['Phase'] == 'Testing'].head(1)
        if not training_boundary.empty and not testing_start.empty:
            connector_df = pd.concat([training_boundary, testing_start])
            for column, color, width in [
                ('Portfolio_Cumulative_Period', colors['accent'], 4),
                ('ACWI_Cumulative_Period', colors['header'], 2.5),
            ]:
                fig.add_trace(go.Scatter(
                    x=connector_df['Date'],
                    y=connector_df[column],
                    mode='lines',
                    line=dict(color=color, width=width),
                    showlegend=False,
                    hoverinfo='skip',
                ))

        for column, label in [
            ('Portfolio_Cumulative_Period', 'Portfolio'),
            ('ACWI_Cumulative_Period', 'ACWI'),
        ]:
            fig.add_trace(go.Scatter(
                x=filtered_df['Date'],
                y=filtered_df[column],
                mode='markers',
                name=f'{label} phase hover',
                showlegend=False,
                marker=dict(size=14, color='rgba(0,0,0,0)'),
                customdata=filtered_df['Phase'],
                hovertemplate=(
                    f'<b>{label} · %{{customdata}}</b>'
                    '<br>Date: %{x|%Y-%m-%d}'
                    '<br>Return: %{y:.1%}<extra></extra>'
                ),
            ))
    else:
        n_points = len(filtered_df)
        marker_sizes = [3] * (n_points - 1) + [8]
        fig.add_trace(go.Scatter(
            x=filtered_df['Date'],
            y=filtered_df['Portfolio_Cumulative_Period'],
            mode='lines+markers',
            name='Portfolio',
            line=dict(color=colors['accent'], width=4),
            marker=dict(
                color=[colors['accent']] * (n_points - 1) + [colors['negative']],
                size=marker_sizes,
                symbol='circle'
            ),
            hovertemplate='<b>Portfolio</b><br>Date: %{x|%Y-%m-%d}<br>Return: %{y:.1%}<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=filtered_df['Date'],
            y=filtered_df['ACWI_Cumulative_Period'],
            mode='lines+markers',
            name='ACWI (Benchmark)',
            line=dict(color=colors['header'], width=2.5),
            marker=dict(color=colors['header'], size=[3] * n_points, symbol='circle'),
            hovertemplate='<b>ACWI</b><br>Date: %{x|%Y-%m-%d}<br>Return: %{y:.1%}<extra></extra>'
        ))

    y_min = min(
        filtered_df['Portfolio_Cumulative_Period'].min() - 0.05,
        filtered_df['ACWI_Cumulative_Period'].min() - 0.05
    )
    y_max = max(
        filtered_df['Portfolio_Cumulative_Period'].max() + 0.1,
        filtered_df['ACWI_Cumulative_Period'].max() + 0.1
    )

    fig.update_layout(
        title='',
        yaxis_title=f"Cumulative Return ({currency})" if currency else "Cumulative Return",
        xaxis_title='Date',
        font=dict(family="Helvetica", size=15, color=colors['text']),
        plot_bgcolor=LIGHT_THEME['transparent'],
        paper_bgcolor=LIGHT_THEME['transparent'],
        yaxis=dict(range=[y_min, y_max]),
        height=height,
        margin={'l': 38, 'r': 10, 't': 105 if has_phases else 58, 'b': 44},
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.13 if has_phases else 1.02,
            xanchor="center",
            x=0.5,
            bgcolor='rgba(255,255,255,0.94)',
            bordercolor=colors['border'],
            borderwidth=1,
            font=dict(size=12, color=colors['text-primary']),
            tracegroupgap=2,
        ),
        hoverlabel=dict(
            bgcolor=LIGHT_THEME['tooltip_bg'],
            bordercolor=LIGHT_THEME['tooltip_bg'],
            font=dict(color=LIGHT_THEME['tooltip_text']),
        ),
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=colors['grid'],
        linecolor=colors['border'],
        zerolinecolor=colors['border'],
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=colors['grid'],
        linecolor=colors['border'],
        zerolinecolor=colors['border'],
        tickformat=".1%",
    )
    fig.update_layout(uirevision='constant')
    _lock_graph_navigation(fig)

    if training_end is not None and start_date <= pd.to_datetime(training_end) <= end_date:
        boundary = pd.to_datetime(training_end)
        fig.add_shape(
            type='line',
            x0=boundary,
            x1=boundary,
            y0=0,
            y1=1,
            xref='x',
            yref='paper',
            line=dict(color=colors['warning'], width=2, dash='dash')
        )
        fig.add_annotation(
            x=boundary,
            y=0.96,
            xref='x',
            yref='paper',
            text='Testing starts',
            showarrow=False,
            xanchor='left',
            yanchor='top',
            font=dict(color=colors['warning'], size=13),
            bgcolor='rgba(255,255,255,0.94)',
            bordercolor=colors['warning'],
            borderwidth=1,
            borderpad=5,
        )

    return fig


def _series_on_dates(series, dates):
    values = pd.Series(series).dropna().sort_index()
    values.index = pd.DatetimeIndex(pd.to_datetime(values.index)).tz_localize(None)
    dates = pd.DatetimeIndex(pd.to_datetime(dates)).tz_localize(None)
    return values.reindex(values.index.union(dates).sort_values()).ffill().reindex(dates)


def _download_usd_nok_history(composition_sheet, end_date):
    training_start, _ = get_training_dates(composition_sheet)
    download_start = training_start - pd.offsets.MonthEnd(1) - pd.Timedelta(days=7)
    fx_data = yf.download(
        'NOK=X',
        start=download_start,
        end=pd.to_datetime(end_date) + pd.Timedelta(days=1),
        interval='1d',
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    fx_close = fx_data['Close']
    if isinstance(fx_close, pd.DataFrame):
        if 'NOK=X' in fx_close.columns:
            fx_close = fx_close['NOK=X']
        else:
            fx_close = fx_close.iloc[:, 0]
    return pd.Series(fx_close).dropna().sort_index()


def load_data_and_calculate_returns(composition_sheet='2020', currency='USD'):
    composition = pd.read_excel(get_workbook_path(), sheet_name=composition_sheet)
    composition['ValidFrom'] = pd.to_datetime(composition['ValidFrom'], dayfirst=False)
    composition['ValidTo'] = pd.to_datetime(composition['ValidTo'], dayfirst=False)

    min_date = composition['ValidFrom'].min()
    today = date.today()
    tickers = list(composition.Symbol.unique())

    all_tickers = tickers + ['ACWI']

    df = yf.download(
        all_tickers,
        start=min_date,
        end=today,
        interval="1d",
        auto_adjust=True,
        threads=True,
        progress=False
    )

    portfolio_cols = [col for col in df['Close'].columns if col != 'ACWI']

    full_symbol_df_raw = df['Close'][portfolio_cols].stack().reset_index()
    full_symbol_df_raw.columns = ['Date', 'Symbol', 'Close']
    full_symbol_df_raw['Date'] = pd.to_datetime(full_symbol_df_raw['Date'])
    full_symbol_df_raw = full_symbol_df_raw.sort_values(['Symbol', 'Date']).reset_index(drop=True)
    full_symbol_df_raw['Return'] = full_symbol_df_raw.groupby('Symbol')['Close'].pct_change().fillna(0)

    names = composition[['Symbol', 'Company']].drop_duplicates()
    full_symbol_df_raw = full_symbol_df_raw.merge(names, on='Symbol', how='left')
    full_symbol_df = full_symbol_df_raw.copy()

    portfolio_df_raw = df['Close'][portfolio_cols].stack().reset_index()
    portfolio_df_raw.columns = ['Date', 'Symbol', 'Close']
    portfolio_df_raw['Date'] = pd.to_datetime(portfolio_df_raw['Date'])
    portfolio_df_raw = portfolio_df_raw.sort_values(['Symbol', 'Date']).reset_index(drop=True)
    portfolio_df_raw['Return'] = portfolio_df_raw.groupby('Symbol')['Close'].pct_change().fillna(0)
    portfolio_df_raw = portfolio_df_raw.merge(names, on='Symbol', how='left')

    active_positions = []
    for _, row in composition.iterrows():
        mask = (
            (portfolio_df_raw['Date'] >= row['ValidFrom']) &
            (portfolio_df_raw['Date'] <= row['ValidTo']) &
            (portfolio_df_raw['Symbol'] == row['Symbol'])
        )
        active = portfolio_df_raw.loc[mask].copy()
        active['Weight'] = row.get('Weight', 1.0 / len(composition))
        active_positions.append(active)

    portfolio_df = pd.concat(active_positions, ignore_index=True)
    portfolio_df = portfolio_df.sort_values(['Date', 'Symbol']).reset_index(drop=True)
    portfolio_df = portfolio_df.drop_duplicates(['Date', 'Symbol'], keep='last')

    portfolio_returns_list = []
    for date_val in sorted(portfolio_df['Date'].unique()):
        daily_data = portfolio_df[portfolio_df['Date'] == date_val]
        if not daily_data.empty:
            daily_portfolio_ret = (daily_data['Return'] * daily_data['Weight']).sum()
            portfolio_returns_list.append({'Date': date_val, 'Portfolio_Return': daily_portfolio_ret})

    portfolio_returns = pd.DataFrame(portfolio_returns_list)
    portfolio_returns['Date'] = pd.to_datetime(portfolio_returns['Date'])
    portfolio_returns = portfolio_returns.set_index('Date').sort_index()
    portfolio_returns['Portfolio_Return'] = portfolio_returns['Portfolio_Return'].round(8)

    acwi_data = _series_on_dates(df['Close']['ACWI'], portfolio_returns.index)
    acwi_returns = acwi_data.pct_change().fillna(0)

    usd_nok_series = None
    if currency == 'NOK':
        usd_nok_series = _download_usd_nok_history(composition_sheet, today)

        fx_levels_portfolio = _series_on_dates(usd_nok_series, portfolio_returns.index)
        fx_returns_portfolio = fx_levels_portfolio.pct_change().fillna(0)
        portfolio_returns['Portfolio_Return'] = (
            (1 + portfolio_returns['Portfolio_Return']) * (1 + fx_returns_portfolio) - 1
        )
        acwi_returns = ((1 + acwi_returns) * (1 + fx_returns_portfolio) - 1)

        portfolio_fx_dates = pd.DatetimeIndex(portfolio_df['Date'].drop_duplicates().sort_values())
        portfolio_fx_returns = _series_on_dates(
            usd_nok_series, portfolio_fx_dates
        ).pct_change().fillna(0)
        portfolio_df['FX_Return'] = portfolio_df['Date'].map(portfolio_fx_returns)
        portfolio_df['Return'] = (1 + portfolio_df['Return']) * (1 + portfolio_df['FX_Return']) - 1

        full_fx_dates = pd.DatetimeIndex(full_symbol_df['Date'].drop_duplicates().sort_values())
        full_fx_returns = _series_on_dates(
            usd_nok_series, full_fx_dates
        ).pct_change().fillna(0)
        full_symbol_df['FX_Return'] = full_symbol_df['Date'].map(full_fx_returns)
        full_symbol_df['Return'] = (1 + full_symbol_df['Return']) * (1 + full_symbol_df['FX_Return']) - 1

    portfolio_returns['ACWI_Return'] = acwi_returns.round(8)
    portfolio_returns['Portfolio_Cumulative'] = (1 + portfolio_returns['Portfolio_Return']).cumprod() - 1

    return portfolio_returns, portfolio_df, full_symbol_df, composition, usd_nok_series


def _ytd_return_by_symbol(full_symbol_df, year_start):
    """Year-to-date cumulative return per symbol, in the frame's base currency.

    ``full_symbol_df['Return']`` is already FX-adjusted when the NOK view is
    selected, so the YTD numbers stay consistent with the graph above.
    """
    ytd_source = full_symbol_df[full_symbol_df['Date'] >= year_start].copy()
    if ytd_source.empty:
        return pd.Series(dtype=float)

    ytd_source = ytd_source.sort_values(['Symbol', 'Date'])
    return ytd_source.groupby('Symbol')['Return'].apply(
        lambda s: (1 + s.fillna(0)).cumprod().iloc[-1] - 1 if len(s) else np.nan
    )


SECTION_LABEL_STYLE = {
    'fontSize': '0.92rem',
    'fontWeight': '700',
    'letterSpacing': '0.03em',
    'textTransform': 'uppercase',
    'color': colors['header'],
    'marginBottom': '0.8rem'
}

CONTROL_LABEL_STYLE = {
    'fontSize': '0.85rem',
    'fontWeight': '600',
    'color': colors['header'],
    'marginBottom': '0.55rem',
}

RADIO_LABEL_STYLE = {
    'display': 'inline-flex',
    'alignItems': 'center',
    'marginRight': '0.7rem',
    'marginBottom': '0.6rem',
    'padding': '0.7rem 1rem',
    'borderRadius': '999px',
    'backgroundColor': colors['content'],
    'border': f"1px solid {colors['border']}",
    'fontWeight': '500',
    'color': colors['text-primary'],
}


controls_panel = html.Div([
    dbc.Row([
        dbc.Col([
            html.Div("Training Period", style=CONTROL_LABEL_STYLE),
            dcc.Dropdown(
                id='composition-selector',
                options=[
                    {'label': '2015-2024', 'value': '2015'},
                    {'label': '2020-2024', 'value': '2020'}
                ],
                value='2020',
                clearable=False,
                style={'width': '100%'}
            )
        ], xs=12, md=4),
        dbc.Col([
            html.Div("Performance period", style=CONTROL_LABEL_STYLE),
            dcc.RadioItems(
                id='period-selector',
                options=[
                    {'label': 'Testing Period', 'value': 'testing'},
                    {'label': 'YTD', 'value': 'ytd'}
                ],
                value='testing',
                labelStyle=RADIO_LABEL_STYLE,
                inputStyle={'marginRight': '0.45rem', 'accentColor': colors['accent']}
            )
        ], xs=12, md=5),
        dbc.Col([
            html.Div("Base currency", style=CONTROL_LABEL_STYLE),
            dcc.RadioItems(
                id='currency-selector',
                options=[
                    {'label': 'USD Returns', 'value': 'USD'},
                    {'label': 'NOK Returns', 'value': 'NOK'}
                ],
                value='USD',
                labelStyle=RADIO_LABEL_STYLE,
                inputStyle={'marginRight': '0.45rem', 'accentColor': colors['accent']}
            )
        ], xs=12, md=3)
    ], className='g-3')
], className='algo-controls-panel', style={
    'maxWidth': '1120px',
    'margin': '0 auto 1.75rem auto',
    'padding': '1.4rem 1.5rem',
    'background': (
        f"linear-gradient(180deg, {colors['surface']} 0%, "
        'rgba(234,241,247,0.72) 100%)'
    ),
    'border': f"1px solid {colors['border']}",
    'borderRadius': '24px',
    'boxShadow': '0 12px 32px rgba(16,42,67,0.08)'
})


layout = html.Div(dbc.Container([
    html.Div(className='beforediv'),

    html.Div([
        _algo_trend_chart(),
        html.Div([
            html.Div("Factor investing dashboard", className='algo-hero-badge', style={
                'display': 'inline-block',
                'padding': '0.45rem 1rem',
                'borderRadius': '999px',
                'background': 'linear-gradient(135deg, rgba(3,105,161,0.12), rgba(109,40,217,0.10))',
                'border': '1px solid rgba(3,105,161,0.28)',
                'color': colors['accent'],
                'fontSize': '0.92rem',
                'letterSpacing': '0.04em',
                'textTransform': 'uppercase',
                'fontWeight': '600',
                'marginBottom': '1rem'
            }),
            html.H1("Optimized Factor Portfolio", className='headerfinvest', style={
                'textAlign': 'center',
                'marginBottom': '0.75rem',
                'color': colors['text-primary'],
                'fontWeight': '500',
                'letterSpacing': '-0.03em',
                'lineHeight': '1.05'
            }),
            html.Div(id='dynamic-description', className='normal-text', style={
                'textAlign': 'center',
                'fontSize': '1.05rem',
                'margin': '0 auto',
                'maxWidth': '860px',
                'fontWeight': '400',
                'lineHeight': '1.75',
                'color': colors['text'],
            })
        ], className='algo-hero-inner')
    ], className='algo-hero', style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.5rem auto',
        'padding': '2.6rem 2rem 2rem 2rem',
        'borderRadius': '28px',
        'background': (
            'radial-gradient(circle at 82% 14%, rgba(3,105,161,0.12), transparent 34%), '
            'radial-gradient(circle at 12% 92%, rgba(109,40,217,0.08), transparent 38%), '
            f"linear-gradient(180deg, {colors['surface']} 0%, {colors['content']} 100%)"
        ),
        'boxShadow': '0 12px 32px rgba(16,42,67,0.08)',
        'border': f"1px solid {colors['border']}",
        'position': 'relative',
        'overflow': 'hidden'
    }),

    # Always-on: the full training + testing history in the selected currency.
    dbc.Row([
        dbc.Col(html.Div([
            html.Div("Training + testing performance", className='algo-section-label', style=SECTION_LABEL_STYLE),
            dcc.Graph(
                id='portfolio-cumulative-chart',
                className='algo-performance-graph algo-full-history-graph',
                responsive=True,
                config=ALGORITHM_GRAPH_CONFIG,
                style={'height': '700px'},
            )
        ], className='algo-section-card algo-graph-card', style=SECTION_CARD_STYLE), width=12)
    ], className='algo-section-row', style={'maxWidth': '1120px', 'margin': '0 auto 1.5rem auto'}),

    # Selection options sit below the always-on graph.
    controls_panel,

    # Results for the selected performance window: graph, then metrics, then table.
    dbc.Row([
        dbc.Col(html.Div([
            html.Div("Selected-period performance", id='period-graph-label', className='algo-section-label', style=SECTION_LABEL_STYLE),
            dcc.Graph(
                id='period-cumulative-chart',
                className='algo-performance-graph algo-selected-period-graph',
                responsive=True,
                config=ALGORITHM_GRAPH_CONFIG,
                style={'height': '700px'},
            )
        ], className='algo-section-card algo-graph-card', style=SECTION_CARD_STYLE), width=12)
    ], className='algo-section-row', style={'maxWidth': '1120px', 'margin': '0 auto 1.5rem auto'}),

    html.Div([
        dbc.Row([
            dbc.Col(html.Div(id='portfolio-return-card'), xs=12, md=6, lg=4),
            dbc.Col(html.Div(id='volatility-card'), xs=12, md=6, lg=4),
            dbc.Col(html.Div(id='max-drawdown-card'), xs=12, md=6, lg=4)
        ], className='g-4 justify-content-center')
    ], className='algo-metrics', style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.5rem auto',
        'padding': '0.25rem 0'
    }),

    html.Div([
        dbc.Row([
            dbc.Col(html.Div([
                html.Div("Current composition", style={
                    **SECTION_LABEL_STYLE,
                    'padding': '0 0.2rem'
                }, className='algo-section-label'),
                html.Div(
                    "Swipe horizontally to view all columns",
                    className='algo-table-scroll-hint',
                ),
                html.Div(id='current-composition-table')
            ], className='algo-section-card algo-composition-card', style=SECTION_CARD_STYLE), width=12)
        ], className='algo-section-row', style={'marginTop': '1.25rem'})
    ], className='algo-composition-wrap', style={'maxWidth': '1120px', 'margin': '0 auto 2rem auto'}),

    html.Br(),
], fluid=True), className='algo-shell', style={
    'backgroundColor': colors['background'],
    'backgroundImage': (
        'radial-gradient(58rem 42rem at 88% -6%, rgba(3,105,161,0.08), transparent 60%), '
        'radial-gradient(48rem 40rem at 2% 8%, rgba(109,40,217,0.06), transparent 55%), '
        'radial-gradient(44rem 40rem at 50% 112%, rgba(4,120,87,0.05), transparent 60%)'
    ),
    'color': colors['text'],
})


@callback(
    [Output('portfolio-cumulative-chart', 'figure'),
     Output('period-cumulative-chart', 'figure'),
     Output('period-graph-label', 'children'),
     Output('portfolio-return-card', 'children'),
     Output('volatility-card', 'children'),
     Output('max-drawdown-card', 'children'),
     Output('current-composition-table', 'children'),
     Output('dynamic-description', 'children')],
    [Input('composition-selector', 'value'),
     Input('period-selector', 'value'),
     Input('currency-selector', 'value')]
)
def update_dashboard(composition_sheet, period, currency):
    if composition_sheet == '2015':
        description = [description_2015, html.Hr()]
    else:
        description = [description_2020, html.Hr()]

    portfolio_returns, portfolio_df, full_symbol_df, composition, fx_history = load_data_and_calculate_returns(composition_sheet, currency)

    if portfolio_returns.empty:
        empty_fig = go.Figure().add_annotation(
            text="No data available - check AlgoComposition.xlsx",
            showarrow=False,
            font=dict(size=16, color=colors['header'])
        )
        empty_fig.update_layout(
            height=400,
            font=dict(family="Helvetica", size=15, color=colors['text']),
            paper_bgcolor=LIGHT_THEME['transparent'],
            plot_bgcolor=LIGHT_THEME['transparent'],
        )
        _lock_graph_navigation(empty_fig)

        no_data_card = dbc.Card(
            dbc.CardBody(
                [html.H5("No data"), html.P("Check file format and dates")],
                style=CARD_BODY_STYLE
            ),
            style=CARD_STYLE
        )
        return (
            empty_fig, empty_fig, "Selected-period performance",
            no_data_card, no_data_card, no_data_card, no_data_card, description,
        )

    today = portfolio_returns.index.max()
    combined_performance, training_end = build_combined_performance(
        composition_sheet,
        portfolio_returns,
        currency=currency,
        fx_close=fx_history,
    )
    testing_returns = portfolio_returns[portfolio_returns.index > training_end].copy()

    # Always-on graph: the full training + testing history in the selected currency.
    fig_portfolio = create_portfolio_graph(
        title=f'Portfolio Cumulative Return ({currency})',
        dataframe=combined_performance.reset_index().rename(columns={'index': 'Date'}),
        y_column='Portfolio_Cumulative_Period',
        start_date=combined_performance.index.min(),
        end_date=today,
        training_end=training_end,
        currency=currency,
    )

    # Results below react to the selected performance window (testing vs YTD).
    if period == 'ytd':
        start_date = pd.Timestamp(today.year, 1, 1)
        total_return_title = "YTD Total Return"
        total_return_note = "Year-to-date growth compounded from daily testing returns."
        period_graph_label = f"Year-to-date performance ({currency})"
    else:
        start_date = testing_returns.index.min() if not testing_returns.empty else training_end
        total_return_title = "Testing-Period Total Return"
        total_return_note = "Calculated from daily returns in the selected testing period."
        period_graph_label = f"Testing-period performance ({currency})"

    period_returns = testing_returns[
        (testing_returns.index >= start_date) &
        (testing_returns.index <= today)
    ].copy()

    if not period_returns.empty:
        total_return = (1 + period_returns['Portfolio_Return']).cumprod().iloc[-1] - 1
    else:
        total_return = np.nan

    # Second graph: just the selected window, rebased to 0 at its start.
    period_graph_data = period_returns.copy()
    period_graph_data['Portfolio_Cumulative_Period'] = (
        1 + period_graph_data['Portfolio_Return']
    ).cumprod() - 1
    period_graph_data['ACWI_Cumulative_Period'] = (
        1 + period_graph_data['ACWI_Return']
    ).cumprod() - 1
    fig_period = create_portfolio_graph(
        title=period_graph_label,
        dataframe=period_graph_data.reset_index(),
        y_column='Portfolio_Cumulative_Period',
        start_date=start_date,
        end_date=today,
        currency=currency,
    )

    volatility = period_returns['Portfolio_Return'].std() * np.sqrt(252)
    max_drawdown = calculate_strategy_max_drawdown(
        composition_sheet, combined_performance
    )

    def create_card(title, value, subtitle, note, value_color=colors['accent']):
        fmt = "—" if pd.isna(value) else f"{value:.1%}"
        return dbc.Card(
            dbc.CardBody([
                html.Div(title, style={
                    'fontSize': '0.9rem',
                    'textTransform': 'uppercase',
                    'letterSpacing': '0.04em',
                    'fontWeight': '700',
                    'color': colors['header'],
                    'marginBottom': '0.8rem'
                }),
                html.Div(subtitle, style={
                    'textAlign': 'left',
                    'color': colors['text-primary'],
                    'fontSize': '1rem',
                    'marginBottom': '0.5rem',
                    'fontWeight': '600'
                }),
                html.Div(fmt, style={
                    'fontSize': '2.4rem',
                    'fontWeight': '700',
                    'color': value_color,
                    'marginBottom': '0.5rem',
                    'lineHeight': '1.05'
                }),
                html.Div(note, style={
                    'fontSize': '0.95rem',
                    'color': colors['text'],
                    'lineHeight': '1.5'
                })
            ], style=CARD_BODY_STYLE),
            style=CARD_STYLE,
            className='h-100'
        )

    portfolio_card = create_card(
        total_return_title,
        total_return,
        f"Measured in {currency}",
        total_return_note,
    )
    vol_card = create_card(
        "Testing Annualized Volatility",
        volatility,
        f"Daily testing returns · {currency}",
        "Annualized from the daily observations in the selected testing period.",
    )
    max_drawdown_card = create_card(
        "Max Drawdown",
        max_drawdown,
        f"Training + testing · {currency}",
        (
            "The supplied training maximum is the floor; the visible NOK training path uses monthly observations."
            if currency == 'NOK'
            else "The single worst peak-to-trough loss across the full strategy history."
        ),
        value_color=colors['negative'],
    )

    current_date = pd.to_datetime(today)
    current_comps = composition[
        (composition['ValidFrom'] <= current_date) &
        (composition['ValidTo'] >= current_date)
    ].copy()

    if not current_comps.empty:
        ytd_by_symbol = _ytd_return_by_symbol(
            full_symbol_df, pd.Timestamp(today.year, 1, 1)
        )
        since_inclusion = calculate_returns_since_inclusion(
            full_symbol_df,
            current_comps,
            today,
        )

        current_comps['ValidFrom'] = pd.to_datetime(current_comps['ValidFrom']).dt.strftime('%Y-%m-%d')
        current_comps['ValidTo'] = pd.to_datetime(current_comps['ValidTo']).dt.strftime('%Y-%m-%d')
        current_comps['YTD_Value'] = pd.to_numeric(
            current_comps['Symbol'].map(ytd_by_symbol), errors='coerce'
        ) * 100
        current_comps = current_comps.sort_values(
            'YTD_Value', ascending=False, na_position='last'
        )
        current_comps['YTD'] = current_comps['YTD_Value'].map(
            lambda v: '—' if pd.isna(v) else f'{v:+.1f}%'
        )
        current_comps['SinceInclusion_Value'] = pd.to_numeric(
            since_inclusion.reindex(current_comps.index), errors='coerce'
        ) * 100
        current_comps['SinceInclusion'] = current_comps['SinceInclusion_Value'].map(
            lambda v: '—' if pd.isna(v) else f'{v:+.1f}%'
        )

        current_comps_display = current_comps[[
            'Company',
            'Symbol',
            'YTD',
            'YTD_Value',
            'SinceInclusion',
            'SinceInclusion_Value',
            'ValidFrom',
            'ValidTo',
        ]].copy()

        current_comps_display['Company'] = [
            f'<a href="https://www.marketwatch.com/investing/stock/{row["Symbol"].lower()}" target="_blank" rel="noopener noreferrer">{row["Company"]}</a>'
            for _, row in current_comps_display.iterrows()
        ]

        table = dash.dash_table.DataTable(
            data=current_comps_display.to_dict('records'),
            columns=[
                {'name': 'Company', 'id': 'Company', 'presentation': 'markdown', 'type': 'text'},
                {'name': 'Symbol', 'id': 'Symbol'},
                {'name': 'YTD Return', 'id': 'YTD'},
                {'name': 'Since Inclusion', 'id': 'SinceInclusion'},
                {'name': 'Valid From', 'id': 'ValidFrom'}
            ],
            markdown_options={"html": True},
            style_cell={
                'textAlign': 'left',
                'padding': '16px 18px',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '14px',
                'lineHeight': '1.45',
                'color': colors['text-primary'],
                'backgroundColor': colors['surface'],
                'border': f"1px solid {colors['border']}",
            },
            style_cell_conditional=[
                {'if': {'column_id': 'Company'}, 'minWidth': '145px', 'width': '24%'},
                {'if': {'column_id': 'Symbol'}, 'minWidth': '70px', 'width': '12%'},
                {'if': {'column_id': 'YTD'}, 'minWidth': '95px', 'width': '18%'},
                {'if': {'column_id': 'SinceInclusion'}, 'minWidth': '120px', 'width': '24%'},
                {'if': {'column_id': 'ValidFrom'}, 'minWidth': '105px', 'width': '22%'},
            ],
            style_data={
                'backgroundColor': colors['surface'],
                'border': f"1px solid {colors['border']}",
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'Symbol'},
                    'fontWeight': 'bold',
                    'backgroundColor': colors['content'],
                    'textAlign': 'left',
                    'fontFamily': 'Arial, sans-serif',
                    'fontSize': '15px'
                },
                {
                    'if': {'column_id': 'YTD', 'filter_query': '{YTD_Value} > 0'},
                    'color': colors['positive'],
                    'fontWeight': '700'
                },
                {
                    'if': {'column_id': 'YTD', 'filter_query': '{YTD_Value} < 0'},
                    'color': colors['negative'],
                    'fontWeight': '700'
                },
                {
                    'if': {'column_id': 'SinceInclusion', 'filter_query': '{SinceInclusion_Value} > 0'},
                    'color': colors['positive'],
                    'fontWeight': '700'
                },
                {
                    'if': {'column_id': 'SinceInclusion', 'filter_query': '{SinceInclusion_Value} < 0'},
                    'color': colors['negative'],
                    'fontWeight': '700'
                },
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': colors['background'],
                }
            ],
            style_header={
                'backgroundColor': colors['content'],
                'color': colors['text-primary'],
                'fontWeight': 'bold',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '15px',
                'padding': '16px 18px',
                'border': f"1px solid {colors['border']}",
                'textAlign': 'center'
            },
            style_table={
                'overflowX': 'auto',
                'WebkitOverflowScrolling': 'touch',
                'borderRadius': '14px',
                'boxShadow': '0 8px 24px rgba(16,42,67,0.07)',
                'border': f"1px solid {colors['border']}",
                'margin': '0.75rem 0 0 0'
            },
            sort_action='native',
            row_selectable=False,
            cell_selectable=False,
            page_size=10
        )
    else:
        table = html.Div(
            "No current composition",
            style={
                'textAlign': 'center',
                'padding': '40px',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '16px',
                'color': colors['text']
            }
        )

    return (
        fig_portfolio,
        fig_period,
        period_graph_label,
        portfolio_card,
        vol_card,
        max_drawdown_card,
        table,
        description,
    )
