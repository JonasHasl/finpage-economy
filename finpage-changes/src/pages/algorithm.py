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
    calculate_strategy_max_drawdown,
    get_training_dates,
)


dash.register_page(__name__, path='/portfolio-daily')


colors = {
    'background': '#0b0f19',
    'text': '#94a3b8',
    'accent': '#38bdf8',
    'text-white': '#e2e8f0',
    'content': '#0f172a',
    'banner': 'hsl(222, 42%, 9%)',
    'banner2': 'hsl(222, 34%, 13%)',
    'border': '#1e293b',
    'header': '#94a3b8'
}


description_2015 = '''The algorithm was fitted over 2015-2024 to optimize the Sharpe Ratio of a stock-selection strategy based on fundamental factors from Morningstar. The chart uses monthly observations in training and daily observations after training.'''
description_2020 = '''The algorithm was fitted over 2020-2024 to optimize the Sharpe Ratio of a stock-selection strategy based on fundamental factors from Morningstar. The chart uses monthly observations in training and daily observations after training.'''


CARD_STYLE = {
    'background': 'linear-gradient(180deg, rgba(19,27,45,0.96), rgba(13,19,33,0.94))',
    'border': '1px solid rgba(30,41,59,0.9)',
    'borderRadius': '24px',
    'boxShadow': 'none',
    'height': '100%'
}

SECTION_CARD_STYLE = {
    'background': 'linear-gradient(180deg, rgba(19,27,45,0.96), rgba(13,19,33,0.94))',
    'borderRadius': '26px',
    'padding': '1.35rem',
    'border': '1px solid rgba(30,41,59,0.9)',
    'boxShadow': 'none'
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
        fig.add_annotation(text="No data", showarrow=False, font=dict(size=16, color="#94a3b8"))
        fig.update_layout(height=height)
        return fig

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
            portfolio_marker_colors = ['#38bdf8'] * len(phase_df)
            if phase == 'Testing':
                portfolio_marker_sizes[-1] = 8
                portfolio_marker_colors[-1] = '#f87171'

            fig.add_trace(go.Scatter(
                x=phase_df['Date'],
                y=phase_df['Portfolio_Cumulative_Period'],
                mode='lines+markers',
                name=f'Portfolio · {phase}',
                legendgroup='Portfolio',
                line=dict(color='#38bdf8', width=4, dash=style['dash']),
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
                line=dict(color='#94a3b8', width=2.5, dash=style['dash']),
                opacity=style['opacity'],
                marker=dict(color='#94a3b8', size=[style['marker_size']] * len(phase_df)),
                hoverinfo='skip',
            ))

        training_boundary = filtered_df[filtered_df['Phase'] == 'Training'].tail(1)
        testing_start = filtered_df[filtered_df['Phase'] == 'Testing'].head(1)
        if not training_boundary.empty and not testing_start.empty:
            connector_df = pd.concat([training_boundary, testing_start])
            for column, color, width in [
                ('Portfolio_Cumulative_Period', '#38bdf8', 4),
                ('ACWI_Cumulative_Period', '#94a3b8', 2.5),
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
            line=dict(color='#38bdf8', width=4),
            marker=dict(
                color=['#38bdf8'] * (n_points - 1) + ['#f87171'],
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
            line=dict(color='#94a3b8', width=2.5),
            marker=dict(color='#94a3b8', size=[3] * n_points, symbol='circle'),
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
        yaxis_title="Cumulative Return",
        xaxis_title='Date',
        font=dict(family="Helvetica", size=15, color=colors['text']),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(range=[y_min, y_max]),
        height=height,
        margin={'l': 50, 'r': 50, 't': 115 if has_phases else 70, 'b': 50},
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.13 if has_phases else 1.02,
            xanchor="center",
            x=0.5,
            bgcolor='rgba(13,19,33,0.85)',
            bordercolor='#1e293b',
            borderwidth=1
        )
    )

    fig.update_xaxes(showgrid=True, gridcolor=colors['border'])
    fig.update_yaxes(showgrid=True, gridcolor=colors['border'], tickformat=".1%")
    fig.update_layout(uirevision='constant')

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
            line=dict(color='#fbbf24', width=2, dash='dash')
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
            font=dict(color='#fbbf24', size=13),
            bgcolor='rgba(13,19,33,0.88)',
            bordercolor='#fbbf24',
            borderwidth=1,
            borderpad=5,
        )

    return fig


def create_stocks_graph(stocks_data, start_date, end_date, height=700):
    if stocks_data.empty:
        fig = go.Figure()
        fig.add_annotation(text="No active stocks", showarrow=False, font=dict(size=16, color="#94a3b8"))
        fig.update_layout(height=height)
        return fig

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    stocks_data = stocks_data.copy()
    stocks_data['Date'] = pd.to_datetime(stocks_data['Date'])

    mask = (stocks_data['Date'] >= start_date) & (stocks_data['Date'] <= end_date)
    filtered_stocks = stocks_data.loc[mask].copy()

    if filtered_stocks.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data", showarrow=False, font=dict(size=16, color="#94a3b8"))
        fig.update_layout(height=height)
        return fig

    fig = go.Figure()

    symbols = filtered_stocks['Symbol'].unique()
    colors_list = ['#38bdf8', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb7185', '#facc15']

    for i, symbol in enumerate(symbols):
        symbol_data = filtered_stocks[filtered_stocks['Symbol'] == symbol].copy()
        color = colors_list[i % len(colors_list)]

        if len(symbol_data) > 0:
            marker_sizes = [2] * max(len(symbol_data) - 1, 0) + [8]
        else:
            marker_sizes = [8]

        fig.add_trace(go.Scatter(
            x=symbol_data['Date'],
            y=symbol_data['Cumulative_Return'],
            mode='lines+markers',
            name=symbol,
            line=dict(color=color, width=2.5),
            marker=dict(
                color=[color] * max(len(symbol_data) - 1, 0) + ['#f87171'] if len(symbol_data) > 0 else ['#f87171'],
                size=marker_sizes,
                symbol='circle'
            ),
            legendgroup=symbol,
            hovertemplate=f'<b>{symbol}</b><br>Date: %{{x}}<br>Return: %{{y:.1%}}<extra></extra>'
        ))

    all_returns = filtered_stocks['Cumulative_Return']
    y_min, y_max = all_returns.min(), all_returns.max()
    y_buffer = max((y_max - y_min) * 0.05, 0.02)
    y_min -= y_buffer
    y_max += y_buffer

    fig.update_layout(
        yaxis_title="Cumulative Return",
        xaxis_title='Date',
        font=dict(family="Helvetica", size=15, color=colors['text']),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(range=[y_min, y_max]),
        height=height,
        margin={'l': 50, 'r': 50, 't': 60, 'b': 50},
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        hovermode='x unified'
    )

    fig.update_xaxes(showgrid=True, gridcolor=colors['border'])
    fig.update_yaxes(showgrid=True, gridcolor=colors['border'], tickformat=".1%")
    fig.update_layout(uirevision='constant')

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


def get_current_active_stocks(full_symbol_df, composition, start_date, end_date):
    current_date = pd.to_datetime(full_symbol_df['Date'].max())
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    latest_comps = composition[
        (composition['ValidFrom'] <= current_date) &
        (composition['ValidTo'] >= current_date)
    ].copy()

    current_symbols = latest_comps.sort_values('Symbol')['Symbol'].unique()

    if len(current_symbols) == 0:
        current_symbols = composition['Symbol'].unique()
        latest_comps = composition.copy()

    stocks_data = full_symbol_df[
        (full_symbol_df['Date'] >= start_date) &
        (full_symbol_df['Date'] <= end_date) &
        (full_symbol_df['Symbol'].isin(current_symbols))
    ].copy()

    if stocks_data.empty:
        return pd.DataFrame(), pd.DataFrame()

    stocks_data = stocks_data.sort_values(['Symbol', 'Date']).reset_index(drop=True)
    stocks_data = stocks_data.drop_duplicates(['Date', 'Symbol'], keep='last')

    stocks_data['Cumulative_Return'] = (
        stocks_data.groupby('Symbol')['Return']
        .transform(lambda s: (1 + s.fillna(0)).cumprod() - 1)
    )

    stocks_data = stocks_data.dropna(subset=['Cumulative_Return'])

    return stocks_data, latest_comps


layout = dbc.Container([
    html.Div(className='beforediv'),

    html.Div([
        html.Div("Factor investing dashboard", style={
            'display': 'inline-block',
            'padding': '0.45rem 1rem',
            'borderRadius': '999px',
            'background': 'linear-gradient(135deg, rgba(56,189,248,0.14), rgba(30,58,90,0.28))',
            'border': '1px solid rgba(56,189,248,0.25)',
            'color': '#38bdf8',
            'fontSize': '0.92rem',
            'letterSpacing': '0.04em',
            'textTransform': 'uppercase',
            'fontWeight': '600',
            'marginBottom': '1rem'
        }),
        html.H1("Optimized Factor Portfolio", className='headerfinvest', style={
            'textAlign': 'center',
            'marginBottom': '0.75rem',
            'color': '#e2e8f0',
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
            'color': '#94a3b8'
        })
    ], style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.5rem auto',
        'padding': '2.6rem 2rem 2rem 2rem',
        'borderRadius': '28px',
        'background': 'linear-gradient(180deg, rgba(19,27,45,0.96), rgba(13,19,33,0.92))',
        'boxShadow': 'none',
        'border': '1px solid rgba(30,41,59,0.9)',
        'position': 'relative',
        'overflow': 'hidden'
    }),

    html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("Training Period", style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#94a3b8', 'marginBottom': '0.55rem'}),
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
                html.Div("Performance period", style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#94a3b8', 'marginBottom': '0.55rem'}),
                dcc.RadioItems(
                    id='period-selector',
                    options=[
                        {'label': 'Training + Testing', 'value': 'full'},
                        {'label': 'Testing Period', 'value': 'testing'},
                        {'label': 'YTD', 'value': 'ytd'}
                    ],
                    value='full',
                    labelStyle={
                        'display': 'inline-flex',
                        'alignItems': 'center',
                        'marginRight': '0.7rem',
                        'marginBottom': '0.6rem',
                        'padding': '0.7rem 1rem',
                        'borderRadius': '999px',
                        'backgroundColor': 'hsl(222, 34%, 13%)',
                        'border': '1px solid #1e293b',
                        'fontWeight': '500',
                        'color': '#e2e8f0'
                    },
                    inputStyle={'marginRight': '0.45rem'}
                )
            ], xs=12, md=5),
            dbc.Col([
                html.Div("Base currency", style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#94a3b8', 'marginBottom': '0.55rem'}),
                dcc.RadioItems(
                    id='currency-selector',
                    options=[
                        {'label': 'USD Returns', 'value': 'USD'},
                        {'label': 'NOK Returns', 'value': 'NOK'}
                    ],
                    value='USD',
                    labelStyle={
                        'display': 'inline-flex',
                        'alignItems': 'center',
                        'marginRight': '0.7rem',
                        'marginBottom': '0.6rem',
                        'padding': '0.7rem 1rem',
                        'borderRadius': '999px',
                        'backgroundColor': 'hsl(222, 34%, 13%)',
                        'border': '1px solid #1e293b',
                        'fontWeight': '500',
                        'color': '#e2e8f0'
                    },
                    inputStyle={'marginRight': '0.45rem'}
                )
            ], xs=12, md=3)
        ], className='g-3')
    ], style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.75rem auto',
        'padding': '1.4rem 1.5rem',
        'backgroundColor': 'rgba(19,27,45,0.9)',
        'border': '1px solid rgba(30,41,59,0.9)',
        'borderRadius': '24px',
        'boxShadow': 'none'
    }),

    dbc.Row([
        dbc.Col(html.Div([
            html.Div("Portfolio vs benchmark", style={
                'fontSize': '0.92rem',
                'fontWeight': '700',
                'letterSpacing': '0.03em',
                'textTransform': 'uppercase',
                'color': '#94a3b8',
                'marginBottom': '0.8rem'
            }),
            dcc.Graph(id='portfolio-cumulative-chart', style={'height': '100%'})
        ], style=SECTION_CARD_STYLE), width=12)
    ], style={'maxWidth': '1120px', 'margin': '0 auto 1.5rem auto'}),

    html.Div([
    dbc.Row([
        dbc.Col(html.Div(id='portfolio-return-card'), xs=12, md=6, lg=4),
        dbc.Col(html.Div(id='volatility-card'), xs=12, md=6, lg=4),
        dbc.Col(html.Div(id='max-drawdown-card'), xs=12, md=6, lg=4)
    ], className='g-4 justify-content-center')
    ], style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.5rem auto',
        'padding': '0.25rem 0'
    }),

    dbc.Row([
        dbc.Col(html.Div([
            html.Div("Latest holdings performance", style={
                'fontSize': '0.92rem',
                'fontWeight': '700',
                'letterSpacing': '0.03em',
                'textTransform': 'uppercase',
                'color': '#94a3b8',
                'marginBottom': '0.8rem'
            }),
            dcc.Graph(id='stocks-cumulative-chart', style={'height': '100%'})
        ], style=SECTION_CARD_STYLE), width=12)
    ], style={'maxWidth': '1120px', 'margin': '0 auto 1.5rem auto'}),

    html.Div([
        #dbc.Row([
        #    dbc.Col(html.Div(id='portfolio-return-card'), xs=12, md=10, lg=5),
        #    dbc.Col(html.Div(id='volatility-card'), xs=12, md=10, lg=5)
        #], className='g-4 justify-content-center'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div("Current composition", style={
                    'fontSize': '0.92rem',
                    'fontWeight': '700',
                    'letterSpacing': '0.03em',
                    'textTransform': 'uppercase',
                    'color': '#94a3b8',
                    'marginBottom': '0.8rem',
                    'padding': '0 0.2rem'
                }),
                html.Div(id='current-composition-table')
            ], style=SECTION_CARD_STYLE), width=12)
        ], style={'marginTop': '1.25rem'})
    ], style={'maxWidth': '1120px', 'margin': '0 auto 2rem auto'}),

    html.Br(),
], fluid=True)


@callback(
    [Output('portfolio-cumulative-chart', 'figure'),
     Output('stocks-cumulative-chart', 'figure'),
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
            font=dict(size=16, color="#94a3b8")
        )
        empty_fig.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

        no_data_card = dbc.Card(
            dbc.CardBody(
                [html.H5("No data"), html.P("Check file format and dates")],
                style=CARD_BODY_STYLE
            ),
            style=CARD_STYLE
        )
        return empty_fig, empty_fig, no_data_card, no_data_card, no_data_card, no_data_card, description

    today = portfolio_returns.index.max()
    combined_performance, training_end = build_combined_performance(
        composition_sheet,
        portfolio_returns,
        currency=currency,
        fx_close=fx_history,
    )
    testing_returns = portfolio_returns[portfolio_returns.index > training_end].copy()

    if period == 'ytd':
        start_date = pd.Timestamp(today.year, 1, 1)
    else:
        start_date = testing_returns.index.min() if not testing_returns.empty else training_end

    period_returns = testing_returns[
        (testing_returns.index >= start_date) &
        (testing_returns.index <= today)
    ].copy()

    if period == 'full':
        graph_data = combined_performance.reset_index().rename(columns={'index': 'Date'})
        graph_start_date = combined_performance.index.min()
        total_return = combined_performance['Portfolio_Cumulative_Period'].iloc[-1]
        total_return_title = "Full-History Total Return"
        total_return_note = "Monthly training observations are linked to daily testing returns."
    else:
        graph_data = period_returns.copy()
        graph_data['Portfolio_Cumulative_Period'] = (
            1 + graph_data['Portfolio_Return']
        ).cumprod() - 1
        graph_data['ACWI_Cumulative_Period'] = (
            1 + graph_data['ACWI_Return']
        ).cumprod() - 1
        graph_data = graph_data.reset_index()
        graph_start_date = start_date
        total_return = graph_data['Portfolio_Cumulative_Period'].iloc[-1]
        total_return_title = (
            "Testing-Period Total Return"
            if period == 'testing'
            else f"{period.upper()} Total Return"
        )
        total_return_note = "Calculated from daily returns in the selected testing period."

    fig_portfolio = create_portfolio_graph(
        title=f'{period.upper()} Portfolio Cumulative Return ({currency})',
        dataframe=graph_data,
        y_column='Portfolio_Cumulative_Period',
        start_date=graph_start_date,
        end_date=today,
        training_end=training_end if period == 'full' else None,
    )

    stocks_data, latest_stocks = get_current_active_stocks(
        full_symbol_df,
        composition,
        start_date,
        today
    )
    if not stocks_data.empty:
        stocks_data = stocks_data.drop_duplicates(['Date', 'Symbol'], keep='last')

    fig_stocks = create_stocks_graph(
        stocks_data=stocks_data,
        start_date=start_date,
        end_date=today
    )

    volatility = period_returns['Portfolio_Return'].std() * np.sqrt(252)
    max_drawdown = calculate_strategy_max_drawdown(
        composition_sheet, combined_performance
    )

    def create_card(title, value, subtitle, note, value_color='#38bdf8'):
        fmt = "—" if pd.isna(value) else f"{value:.1%}"
        return dbc.Card(
            dbc.CardBody([
                html.Div(title, style={
                    'fontSize': '0.9rem',
                    'textTransform': 'uppercase',
                    'letterSpacing': '0.04em',
                    'fontWeight': '700',
                    'color': '#94a3b8',
                    'marginBottom': '0.8rem'
                }),
                html.Div(subtitle, style={
                    'textAlign': 'left',
                    'color': '#e2e8f0',
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
                    'color': '#94a3b8',
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
        value_color='#f87171',
    )

    current_date = pd.to_datetime(today)
    current_comps = composition[
        (composition['ValidFrom'] <= current_date) &
        (composition['ValidTo'] >= current_date)
    ].copy()

    if not current_comps.empty:
        current_comps['ValidFrom'] = pd.to_datetime(current_comps['ValidFrom']).dt.strftime('%Y-%m-%d')
        current_comps['ValidTo'] = pd.to_datetime(current_comps['ValidTo']).dt.strftime('%Y-%m-%d')
        current_comps['Weight_Pct'] = (pd.to_numeric(current_comps['Weight'], errors='coerce') * 100).round(1)

        current_comps_display = current_comps[['Company', 'Symbol', 'Weight_Pct', 'ValidFrom', 'ValidTo']].sort_values('Weight_Pct', ascending=False)

        current_comps_display['Company'] = [
            f'<a href="https://www.marketwatch.com/investing/stock/{row["Symbol"].lower()}" target="_blank" rel="noopener noreferrer">{row["Company"]}</a>'
            for _, row in current_comps_display.iterrows()
        ]

        table = dash.dash_table.DataTable(
            data=current_comps_display.to_dict('records'),
            columns=[
                {'name': 'Company', 'id': 'Company', 'presentation': 'markdown', 'type': 'text'},
                {'name': 'Symbol', 'id': 'Symbol'},
                {'name': 'Weight (%)', 'id': 'Weight_Pct'},
                {'name': 'Valid From', 'id': 'ValidFrom'},
                {'name': 'Valid To', 'id': 'ValidTo'}
            ],
            markdown_options={"html": True},
            style_cell={
                'textAlign': 'left',
                'padding': '16px 18px',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '14px',
                'lineHeight': '1.45',
                'color': '#e2e8f0',
                'backgroundColor': 'hsl(222, 42%, 9%)',
                'border': '1px solid #1e293b'
            },
            style_data={
                'backgroundColor': 'hsl(222, 42%, 9%)',
                'border': '1px solid #1e293b'
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'Symbol'},
                    'fontWeight': 'bold',
                    'backgroundColor': 'hsl(222, 34%, 13%)',
                    'textAlign': 'left',
                    'fontFamily': 'Arial, sans-serif',
                    'fontSize': '15px'
                },
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'hsl(222, 44%, 11%)'
                }
            ],
            style_header={
                'backgroundColor': 'hsl(222, 34%, 13%)',
                'color': '#e2e8f0',
                'fontWeight': 'bold',
                'fontFamily': 'Arial, sans-serif',
                'fontSize': '15px',
                'padding': '16px 18px',
                'border': '1px solid #38bdf8',
                'textAlign': 'center'
            },
            style_table={
                'overflowX': 'auto',
                'borderRadius': '14px',
                'boxShadow': 'none',
                'border': '1px solid #1e293b',
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
        fig_stocks,
        portfolio_card,
        vol_card,
        max_drawdown_card,
        table,
        description,
    )
