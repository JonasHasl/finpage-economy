"""Selected-window portfolio drawdown, shared by both Algorithm layouts."""

import pandas as pd
import plotly.graph_objects as go

from theme import LIGHT_THEME as THEME


def create_drawdown_figure(period_returns, *, currency='USD', height=380):
    """Measure underwater wealth from the window's peak, including opening capital.

    Input is the already currency-adjusted daily return stream for the selected
    window. Its first daily loss counts against an opening wealth of 1.0.
    Earlier windows and the supplied training maximum do not enter this chart.
    """
    returns = pd.to_numeric(
        pd.Series(period_returns, dtype=float), errors='coerce'
    ).dropna().sort_index()
    fig = go.Figure()
    fig.update_layout(
        height=height,
        font=dict(family='Helvetica, Arial, sans-serif', size=11, color=THEME['text_secondary']),
        paper_bgcolor=THEME['transparent'],
        plot_bgcolor=THEME['transparent'],
        margin=dict(l=48, r=18, t=22, b=24),
        showlegend=False,
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor=THEME['tooltip_bg'],
            font=dict(color=THEME['tooltip_text']),
        ),
        dragmode=False,
    )
    fig.update_xaxes(
        fixedrange=True, showgrid=False, linecolor=THEME['border'],
        tickfont=dict(color=THEME['text_muted']), hoverformat='%b %d, %Y', nticks=6,
    )
    fig.update_yaxes(
        fixedrange=True, tickformat='.1%', gridcolor=THEME['grid'],
        zeroline=True, zerolinecolor=THEME['border_strong'], nticks=3,
    )
    if returns.empty:
        fig.add_annotation(
            text='No drawdown data for this window', showarrow=False,
            x=0.5, y=0.5, xref='paper', yref='paper',
        )
        return fig

    wealth = (1 + returns).cumprod()
    peaks = wealth.cummax().clip(lower=1.0)
    drawdown = (wealth / peaks - 1).clip(upper=0.0)
    current = float(drawdown.iloc[-1])
    maximum = float(drawdown.min())
    peak_dates = wealth.index[wealth.eq(peaks.iloc[-1])]
    peak_date = peak_dates[-1] if len(peak_dates) else None
    peak_label = f'{pd.Timestamp(peak_date):%b %d, %Y}' if peak_date is not None else 'opening capital'
    dates = pd.to_datetime(drawdown.index)

    fig.add_trace(go.Scatter(
        x=dates, y=drawdown.to_list(), mode='lines+markers' if len(drawdown) == 1 else 'lines',
        name='Portfolio drawdown', line=dict(color=THEME['blue'], width=2),
        fill='tozeroy', fillcolor='rgba(3,105,161,0.09)',
        hovertemplate=f'<b>Portfolio drawdown ({currency})</b>: %{{y:.2%}}<extra></extra>',
    ))
    if current < 0:
        active = drawdown if peak_date is None else drawdown.loc[peak_date:]
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(active.index), y=active.to_list(), mode='lines',
            name='Current drawdown episode',
            line=dict(color=THEME['red'], width=2.8),
            fill='tozeroy', fillcolor='rgba(185,28,28,0.10)', hoverinfo='skip',
        ))
    fig.add_trace(go.Scatter(
        x=[dates[-1]], y=[current], mode='markers', name='Current drawdown',
        marker=dict(size=8, color=THEME['red'] if current < 0 else THEME['green']),
        hovertemplate=f'<b>Current drawdown</b>: %{{y:.2%}}<br>Peak: {peak_label}<extra></extra>',
    ))
    if maximum < 0:
        trough_date = drawdown.idxmin()
        fig.add_trace(go.Scatter(
            x=[pd.Timestamp(trough_date)], y=[maximum], mode='markers',
            name='Window maximum drawdown',
            marker=dict(size=8, symbol='diamond', color=THEME['amber']),
            hovertemplate='<b>Window maximum drawdown</b>: %{y:.2%}<extra></extra>',
        ))
    fig.add_shape(
        type='line', x0=0, x1=1, xref='paper', y0=maximum, y1=maximum,
        line=dict(color=THEME['amber'], width=1.8, dash='dash'),
    )
    fig.add_annotation(
        text=f'<b>Current: {current:.2%}</b> · peak: {peak_label}',
        x=1, y=1, xref='paper', yref='paper', xanchor='right', yanchor='bottom',
        showarrow=False, font=dict(size=11, color=THEME['red'] if current < 0 else THEME['green']),
    )
    fig.add_annotation(
        text=f'Window max: {maximum:.2%}', x=0.01, y=maximum,
        xref='paper', yref='y', xanchor='left', yshift=-12,
        showarrow=False, font=dict(size=10, color=THEME['amber']),
    )
    span = max(abs(maximum), 0.01)
    fig.update_yaxes(range=[maximum - span * 0.35, span * 0.12])
    left = dates[0]
    right = dates[-1]
    if left == right:
        left -= pd.Timedelta(days=1)
        right += pd.Timedelta(days=1)
    fig.update_xaxes(range=[left, right])
    return fig
