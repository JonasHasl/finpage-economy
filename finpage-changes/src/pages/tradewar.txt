import dash
from dash import dcc, html, dash_table, callback
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from fredapi import Fred
import dash_bootstrap_components as dbc
import io
import requests

#dash.register_page(__name__, path='/trade_war')

# --- Imports ---
from pandas_datareader import wb
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

import pandas as pd
from numpy import array
from numpy import hstack
#import dropbox

import numpy as np
#from pandas_datareader import wb
import sys 
sys.version
from fredapi import Fred

FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
fred = Fred(FRED_API_KEY)

#%matplotlib inline
from IPython.core.pylabtools import figsize
from fredapi import Fred

# --- Data Fetching and Preparation ---
def fetch_worldbank_gdp_data(start_year=2000, end_year=None):
    if end_year is None:
        end_year = datetime.now().year

    # Get country metadata
    df_info = wb.get_countries()
    df_info = df_info[['name', 'region', 'incomeLevel', 'iso3c']].rename(
        columns={'name': 'country', 'iso3c': 'iso_alpha'})
    df_info = df_info[(df_info['region'] != 'Aggregates') | (df_info['country'] == 'European Union')].copy()
    
    # Define indicators (now includes trade data)
    indicators = [
        'NY.GDP.MKTP.CD',  # GDP (current US$)
        'NY.GDP.PCAP.CD',  # GDP per capita (current US$)
        'SP.POP.TOTL',     # Population
        'NE.EXP.GNFS.CD',  # Exports of goods/services (current US$)
        'NE.IMP.GNFS.CD'   # Imports of goods/services (current US$)
    ]
    
    # Download data
    df = wb.download(
        indicator=indicators,
        country='all',
        start=start_year,
        end=end_year
    ).reset_index()
    
    # Rename columns and calculate trade metrics
    df = df.rename(columns={
        'NY.GDP.MKTP.CD': 'gdp',
        'NY.GDP.PCAP.CD': 'gdp_per_capita',
        'SP.POP.TOTL': 'population',
        'NE.EXP.GNFS.CD': 'exports',
        'NE.IMP.GNFS.CD': 'imports'
    })
    
    # Merge with country metadata and calculate trade balance
    df = pd.merge(df, df_info, on='country', how='left').dropna()
    df['trade_balance'] = df['exports'] - df['imports']
    df['trade_balance_pct_gdp'] = 100 * df['trade_balance'] / df['gdp']
    df = df.sort_values('year', ascending=True)  # Add assignment here
    return df

# --- Minimalistic Line Plot Function ---
def minimalistic_lineplot(
    df, y_col, top_n=10, by_col='population', 
    label_fmt=None, title='', y_label='', return_fig=False,
    include_country='Norway', palette=None
):
    latest_year = df['year'].max()
    top_countries = df[df['year'] == latest_year].nlargest(top_n, by_col)['country'].tolist()
    if include_country and include_country not in top_countries:
        top_countries.append(include_country)
    plot_df = df[df['country'].isin(top_countries)].copy()
    if palette is None:
        palette = px.colors.qualitative.Pastel

    fig = px.line(
        plot_df,
        x='year', y=y_col,
        color='country',
        title=title,
        labels={y_col: y_label, 'year': ''},
        color_discrete_sequence=palette
    )

    # Add labels at the end of each line
    for country in top_countries:
    # Filter for the current country and latest year
        country_data = plot_df[(plot_df['country'] == country) & (plot_df['year'] == latest_year)]
        if not country_data.empty:
            x_val = latest_year
            y_val = country_data[y_col].values[0]
            iso_alpha = country_data['iso_alpha'].values[0]  # Access iso_alpha value
            label_text = f"{iso_alpha}: {y_val/1e12:.2f}T"

            fig.add_trace(go.Scatter(
                x=[x_val], y=[y_val],
                mode='text',
                text=[label_text],
                textposition='middle right',
                showlegend=False,
                textfont=dict(size=12, color='black')
            ))

            x_offset = 0.5  # or 0.2, depending on your x-axis scale

            # fig.add_trace(go.Scatter(
            #     x=[float(x_val) - x_offset],  # Move label left
            #     y=[y_val],
            #     mode='text',
            #     text=[label_text],
            #     textposition='middle right',
            #     showlegend=False,
            #     textfont=dict(size=12, color='black')
            # ))

    # Minimalistic layout
    fig.update_layout(
        hovermode='x unified',
        height=600,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial', size=12, color='black'),
        legend_title_text='',
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor='lightgrey',
            ticks='outside',
            tickcolor='lightgrey'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgrey',
            zeroline=False,
            showline=True,
            linecolor='lightgrey',
            ticks='outside',
            tickcolor='lightgrey',
            tickformat=',.0f' if 'pct' not in y_col else ',.2f'
        ))

    # After finding x_val = latest_year, add a small offset:


    if return_fig:
        return fig
    else:
        fig.show()

# --- Minimalistic Choropleth Map Function ---
def minimalistic_choropleth(
    df, color_col, hover_col, title, color_label, return_fig=False,
    color_scale='Viridis_r', show_colorbar=False
):
    latest_year = df['year'].max()
    if 'gdp_log' not in df.columns:
        df['gdp_log'] = np.log10(df['gdp'] + 1)
    if 'gdp_tn' not in df.columns:
        df['gdp_tn'] = df['gdp'] / 1e12
    df_year = df[df['year'] == latest_year].dropna(subset=['iso_alpha'])

    fig = px.choropleth(
        df_year,
        locations='iso_alpha',
        color=color_col,
        hover_name='country',
        hover_data={hover_col: ':.2f', color_col: False, 'iso_alpha': False},
        color_continuous_scale=color_scale,
        title=title,
        labels={hover_col: color_label}
    )
    fig.update_layout(height=600)
    fig.update_coloraxes(showscale=show_colorbar)
    if return_fig:
        return fig
    else:
        fig.show()

# --- Reusable Table Function ---
def top_gdp_table(df, top_n=20, include_country='Norway', return_fig=False):
    latest_year = df['year'].max()
    if 'gdp_tn' not in df.columns:
        df['gdp_tn'] = df['gdp'] / 1e12
    df_year = df[df['year'] == latest_year].dropna(subset=['gdp_tn'])
    top_countries = df_year.nlargest(top_n, 'gdp_tn')[['country', 'gdp_tn']].copy()
    if include_country and include_country not in top_countries['country'].values:
        norway_row = df_year[df_year['country'] == include_country][['country', 'gdp_tn']]
        top_countries = pd.concat([top_countries, norway_row], ignore_index=True)
    top_countries = top_countries.sort_values('gdp_tn', ascending=False).reset_index(drop=True)
    top_countries['gdp_tn_fmt'] = top_countries['gdp_tn'].map(lambda x: f"{x:,.2f}")

    fig = go.Figure(data=[go.Table(
        header=dict(values=["Country", "GDP (Trillions USD)"],
                    fill_color='lavender',
                    align='left'),
        cells=dict(values=[top_countries["country"], top_countries["gdp_tn_fmt"]],
                   fill_color='white',
                   align='left'))
    ])
    fig.update_layout(title_text=f"Top {top_n} GDP Countries, {latest_year}", title_x=0.5)
    if return_fig:
        return fig
    else:
        fig.show()


import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

def minimalistic_lineplot_all_metrics(
    df, value_col='Month', metrics_col='None', date_col = 'Period',
    title='', y_label='', return_fig=False, palette=None, annotation = ''
):
    # Ensure Period is datetime for proper x-axis
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    if metrics_col != 'None':
        metrics = df[metrics_col].unique()
    latest_period = df[date_col].max()
    plot_df = df.copy()

    if palette is None:
        palette = px.colors.qualitative.Pastel
    
    if metrics_col != 'None':
        fig = px.line(
            plot_df,
            x=date_col, y=value_col,
            color=metrics_col,
            title=title,
            labels={value_col: y_label, date_col: ''},
            color_discrete_sequence=palette
        )
    else:
        fig = px.line(
            plot_df,
            x=date_col, y=value_col,
            title=title,
            labels={value_col: y_label, date_col: ''},
            color_discrete_sequence=palette
        )

    # Add labels at the end of each line
    if metrics_col != 'None':
        for metric in metrics:
            metric_data = plot_df[(plot_df[metrics_col] == metric) & (plot_df[date_col] == latest_period)]
            if not metric_data.empty:
                x_val = latest_period
                y_val = metric_data[value_col].values[0]
                label_text = f"{metric}: {y_val/1e12:.2f}T"
                fig.add_trace(go.Scatter(
                    x=[x_val], y=[y_val],
                    mode='text',
                    text=[label_text],
                    textposition='middle right',
                    showlegend=False,
                    textfont=dict(size=12, color='black')
                ))
    else: 
        metric_data = plot_df[(plot_df[date_col] == latest_period)]
        if not metric_data.empty:
            x_val = latest_period
            y_val = metric_data[value_col].values[0]
            label_text = f"{value_col}: {y_val/1e12:.2f}T"
            fig.add_trace(go.Scatter(
                x=[x_val], y=[y_val],
                mode='text',
                text=[label_text],
                textposition='middle right',
                showlegend=False,
                textfont=dict(size=12, color='black')
            ))

    fig.update_layout(
        hovermode='x unified',
        height=600,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial', size=12, color='black'),
        legend_title_text='',
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor='lightgrey',
            ticks='outside',
            tickcolor='lightgrey'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgrey',
            zeroline=False,
            showline=True,
            linecolor='lightgrey',
            ticks='outside',
            tickcolor='lightgrey',
            tickformat=',.0f'
        ),
        annotations=[
            dict(
                text=annotation,
                x=0.0,
                y=0.1,
                align="right",
                xref="paper",
                yref="paper",
                showarrow=False
            )
        ]
    )

    if return_fig:
        return fig
    else:
        fig.show()


start = datetime(2020, 1, 1)
#end = datetime(2022, 5, 27)
end = datetime.now()

completedates = pd.DataFrame(pd.date_range(start=start, end=datetime.now(), freq='B'), columns=['Date'])

FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
fred = Fred(FRED_API_KEY)

tradebalance = fred.get_series_all_releases('BOPGSTB', realtime_start=start.date())

tradebalance = tradebalance.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')
tradebalance = tradebalance.sort_index()

tradebalance.reset_index(inplace= True)
tradebalance = tradebalance.drop_duplicates(subset='Date', keep='last')
tradebalance.sort_values(by='Date', ascending=True, inplace=True)
# tradebalance = tradebalance.drop_duplicates('Date', keep='last')

# Convert 'value' to float to avoid integer division errors
tradebalance['value'] = tradebalance['value'].astype(float)

# Calculate MoM/YoY with safety checks
tradebalance['MoM'] = (tradebalance['value'] - tradebalance['value'].shift(1).fillna(0)) / tradebalance['value'].shift(1).abs().replace(0, np.nan)
tradebalance['YoY'] = (tradebalance['value'] - tradebalance['value'].shift(12).fillna(0)) / tradebalance['value'].shift(12).abs().replace(0, np.nan)

# Replace problematic values (inf, -inf, NaN) with 0
tradebalance['MoM'] = tradebalance['MoM'].replace([np.inf, -np.inf, np.nan], 0)
tradebalance['YoY'] = tradebalance['YoY'].replace([np.inf, -np.inf, np.nan], 0)

# Replace inf and -inf with 0
tradebalance['MoM'] = tradebalance['MoM'].replace([float('inf'), float('-inf')], 0)
tradebalance['YoY'] = tradebalance['YoY'].replace([float('inf'), float('-inf')], 0)


tradebalance['RollingMean12'] = tradebalance['value'].pct_change(periods=12).rolling(12, min_periods=1).mean()

#tradebalance.reset_index(inplace= True)
tradebalance['Date'] = pd.to_datetime(tradebalance['Date']) 

# tradebalance = tradebalance.merge(release_dates, on="Date")

# tradebalance = tradebalance.drop('Date', axis=1).rename(columns={'Release Date' : 'Date'}).set_index('Date')
# tradebalance.reset_index(inplace= True)
tradebalance.rename({'value':'Trade Balance'}, axis=1, inplace=True)
tradebalance['Trade Balance'] = tradebalance['Trade Balance'].astype(float)*1000000
tradebalance['Trade Balance TN'] = tradebalance['Trade Balance'] / 1e12

chinatrade = pd.read_csv('chinesetrade.csv')
chinatrade['Month'] = chinatrade['Month']*100000000
chinatrade['Month TN'] = chinatrade['Month'] / 1e12

chinaplot = minimalistic_lineplot_all_metrics(chinatrade, metrics_col='Metrics', date_col='Period', return_fig=True, title=f'Chinese Trade Data in USD', annotation = 'Source: http://www.customs.gov.cn/')
usplot = minimalistic_lineplot_all_metrics(tradebalance[tradebalance.Date > '2024-01-01'], value_col='Trade Balance', metrics_col='None', date_col='Date', return_fig=True, title=f'Trade Balance US', y_label='Trade Balance USD', annotation = 'Source: fredapi')


# ========================
# Example Usage
# ========================

# Fetch data (now includes trade metrics)
df = fetch_worldbank_gdp_data()
latest_year = df['year'].max()

fig_gdp = minimalistic_lineplot(
    df, 'gdp', top_n=4, by_col='population',
    label_fmt=lambda x: f"{x/1e12:.2f} TN",
    title=f'GDP of Most Populous Countries ({df.year.min()}–{latest_year})',
    y_label='GDP (current US$)',
    return_fig=True  # <-- Add this argument to your function to return the fig, not show it
)

# 2. Trade Balance for Top 5 GDP Countries + Norway
fig_trade = minimalistic_lineplot(
    df, 'trade_balance', top_n=5, by_col='gdp',
    label_fmt=lambda x: f"{x/1e12:.2f} TN",
    title=f'Trade Balance (Exports-Imports) for Top Economies ({df.year.min()}–{latest_year})',
    y_label='Trade Balance (Exports-Imports)',
    return_fig=True
)

# 3. Global GDP Choropleth Map
fig_choropleth = minimalistic_choropleth(
    df, color_col='gdp_log', hover_col='gdp_tn',
    title=f'Global GDP Distribution ({latest_year})',
    color_label='GDP (TN US$)',
    return_fig=True
)

# 4. Top 20 GDP Countries Table
fig_table = top_gdp_table(df, top_n=20, return_fig=True)

graphs = html.Div([
    html.H1("Trade War Data", className="headerfinvest", style={'textAlign':'center'}),
    dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_gdp), md=6),
        dbc.Col(dcc.Graph(figure=fig_trade), md=6),
    ], className="mb-4"),
    dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_choropleth), md=12),
    ], className="mb-4"),
    dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_table), md=12),
    ]),
     dbc.Row([
        dbc.Col(dcc.Graph(figure=usplot), md=6),
        dbc.Col(dcc.Graph(figure=chinaplot), md=6),
    ], className="mb-4"),
])

layout = dbc.Container([html.Div(className='beforediv'), graphs],
    className='')


