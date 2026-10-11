import dash
from dash import dcc, html, dash_table, callback
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fredapi import Fred
import dash_bootstrap_components as dbc
import io
import requests
from theme import LIGHT_THEME

dash.register_page(__name__, path='/yield_curves')

BOND_MARKET_THEME = {
    'page': LIGHT_THEME['page'],
    'surface': LIGHT_THEME['surface'],
    'subtle': LIGHT_THEME['surface_subtle'],
    'text': LIGHT_THEME['text_primary'],
    'text_secondary': LIGHT_THEME['text_secondary'],
    'text_muted': LIGHT_THEME['text_muted'],
    'border': LIGHT_THEME['border'],
    'grid': LIGHT_THEME['grid'],
    'blue': LIGHT_THEME['blue'],
    'green': LIGHT_THEME['green'],
    'red': LIGHT_THEME['red'],
    'amber': LIGHT_THEME['amber'],
    'violet': LIGHT_THEME['violet'],
    'cyan': LIGHT_THEME['cyan'],
    'rose': LIGHT_THEME['rose'],
}

TRANSPARENT_BACKGROUND = LIGHT_THEME['transparent']

YIELD_PANEL_STYLE = {
    'padding': '10px',
    'backgroundColor': BOND_MARKET_THEME['surface'],
    'border': f"1px solid {BOND_MARKET_THEME['border']}",
    'borderRadius': '10px',
    'marginBottom': '20px',
    'marginLeft': 'auto',
    'marginRight': 'auto',
    'width': 'min(100%, 1000px)',
    'overflowX': 'auto',
    'WebkitOverflowScrolling': 'touch',
}

BOND_GRAPH_STYLE_3D = {
    'height': '1000px',
    'marginLeft': 'auto',
    'marginRight': 'auto',
    'width': 'min(100%, 1000px)',
}

BOND_GRAPH_STYLE_2D = {
    'height': '500px',
    'marginLeft': 'auto',
    'marginRight': 'auto',
    'width': 'min(100%, 1000px)',
}

BOND_GRAPH_CONFIG = {
    'displayModeBar': False,
    'responsive': True,
    'scrollZoom': False,
    'doubleClick': False,
}

BOND_MARKET_PAGE_STYLE = {
    'backgroundColor': BOND_MARKET_THEME['page'],
    'color': BOND_MARKET_THEME['text'],
    'minHeight': '100vh',
    '--surface-page': BOND_MARKET_THEME['page'],
    '--surface-raised': BOND_MARKET_THEME['surface'],
    '--surface-subtle': BOND_MARKET_THEME['subtle'],
    '--text-primary': BOND_MARKET_THEME['text'],
    '--text-secondary': BOND_MARKET_THEME['text_secondary'],
    '--text-muted': BOND_MARKET_THEME['text_muted'],
    '--border-subtle': BOND_MARKET_THEME['border'],
    '--grid-color': BOND_MARKET_THEME['grid'],
    '--interactive': BOND_MARKET_THEME['blue'],
    '--positive': BOND_MARKET_THEME['green'],
    '--negative': BOND_MARKET_THEME['red'],
    '--warning': BOND_MARKET_THEME['amber'],
    '--violet': BOND_MARKET_THEME['violet'],
    '--cyan': BOND_MARKET_THEME['cyan'],
    '--rose': BOND_MARKET_THEME['rose'],
    '--background-color': BOND_MARKET_THEME['page'],
    '--banner-color': BOND_MARKET_THEME['surface'],
    '--banner2-color': BOND_MARKET_THEME['subtle'],
    '--text-color': BOND_MARKET_THEME['text_secondary'],
    '--accent-color': BOND_MARKET_THEME['blue'],
    '--border-color': BOND_MARKET_THEME['border'],
    '--header-color': BOND_MARKET_THEME['text_muted'],
    '--element-color': BOND_MARKET_THEME['green'],
    '--text-white-color': BOND_MARKET_THEME['text'],
    '--card-color': BOND_MARKET_THEME['surface'],
}


def _lock_graph_navigation(fig, *, is_3d=False):
    """Keep hover details available while preventing chart navigation."""
    if is_3d:
        fig.update_scenes(dragmode=False)
    else:
        fig.update_layout(dragmode=False)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
    return fig


def bond_graph(graph_id, style):
    """Create a responsive graph with navigation locked consistently."""
    return dcc.Graph(
        id=graph_id,
        config=BOND_GRAPH_CONFIG.copy(),
        responsive=True,
        style=style,
    )


def create_yield_table(data, columns, labels, table_id):
    """Create standardized yield table component for Dash"""
    return html.Div([
        dash_table.DataTable(
            id=table_id,
            columns=[{'name': col, 'id': col} for col in columns],
            data=data.to_dict('records'),
            editable=False,
            filter_action="none",
            row_selectable=False,
            fixed_columns={'headers': True},
            style_data={
                'whiteSpace': 'normal',
                'height': 'auto',
                'width': 'auto',
                'font-family': 'Arial',
                'color': BOND_MARKET_THEME['text'],
                'font-size': '14px',
            },
            style_cell={
                'padding': '10px',
                'textAlign': 'right',
                'backgroundColor': BOND_MARKET_THEME['surface'],
                'border': f"1px solid {BOND_MARKET_THEME['border']}",
            },
            style_cell_conditional=[{
                'if': {'column_id': 'Date'},
                'textAlign': 'left'
            }] + [{
                'if': {'column_id': col},
                'textAlign': 'left'
            } for col in labels],
            style_header={
                'fontWeight': 'bold',
                'color': BOND_MARKET_THEME['text'],
                'backgroundColor': BOND_MARKET_THEME['subtle'],
                'whiteSpace': 'normal',
                'border': f"2px solid {BOND_MARKET_THEME['border']}",
                'borderRadius': '0px',
                'font-family': 'Arial',
                'font-size': '20px'
            },
            style_table={
                'height': 'auto',
                'border-radius':'0px',
                'overflowX': 'auto',
                'width': 'auto'
            }
        )
    ], style=YIELD_PANEL_STYLE)

def serve_layout():
    global nor_cur_data, nor_yield_df, nor_yield_monthly, nor_yield_monthly_reset, nor_last_yields, norwegian_labels
    global yield_df, yield_df_quarterly, maturity_labels, table_yields, last_yields, static_yield_table, yield_table_header
    global tab1_content, norwegian_yield_curve_layout
    
    # Fetch data here
    today = datetime.now().date().strftime('%Y-%m-%d')
    
    nor_url_cur = f"https://data.norges-bank.no/api/data/EXR/B.USD+EUR+SEK+DKK.NOK.SP?format=csv&startPeriod=2010-01-01&endPeriod={today}&locale=en"
    nor_url_cur_response = requests.get(nor_url_cur)
    
    if nor_url_cur_response.status_code == 200:
        nor_csv_data = nor_url_cur_response.content.decode('utf-8')
        nor_cur_data = pd.read_csv(io.StringIO(nor_csv_data), sep=';')[['BASE_CUR', 'QUOTE_CUR', 'TIME_PERIOD', 'OBS_VALUE']]
    
    nor_cur_data['Currency'] = nor_cur_data['BASE_CUR'] + "/" + nor_cur_data['QUOTE_CUR']
    nor_cur_data.drop(['BASE_CUR', 'QUOTE_CUR'], axis=1, inplace=True)
    nor_cur_data['TIME_PERIOD'] = pd.to_datetime(nor_cur_data['TIME_PERIOD'])
    
    nor_url = f"https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.7Y+6M+5Y+3Y+3M+12M+10Y.GBON+TBIL.?format=csv&startPeriod=2010-01-01&endPeriod={today}&locale=en"
    
    nor_response = requests.get(nor_url)
    
    if nor_response.status_code == 200:
        nor_csv_data = nor_response.content.decode('utf-8')
        nor_data = pd.read_csv(io.StringIO(nor_csv_data), sep=';')
        nor_data = nor_data[['Tenor', 'TIME_PERIOD', 'OBS_VALUE']].rename(columns={'TIME_PERIOD': 'Date', 'OBS_VALUE': 'Yield'})
    
    nor_yield_df = nor_data.pivot(index='Date', columns='Tenor', values='Yield').reset_index()
    nor_yield_df = nor_yield_df[['Date', '3 months', '6 months', '12 months', '3 years', '5 years', '7 years', '10 years']]
    nor_yield_df.rename(columns={
        '3 months': '3M', '6 months': '6M', '12 months': '1Y', '3 years': '3Y',
        '5 years': '5Y', '7 years': '7Y', '10 years': '10Y'
    }, inplace=True)
    
    nor_yield_df['Date'] = pd.to_datetime(nor_yield_df['Date'])
    nor_yield_df.set_index('Date', inplace=True)
    nor_yield_df.dropna(how='all', inplace=True)
    nor_yield_df.fillna(method='ffill', inplace=True)
    
    nor_yield_monthly = nor_yield_df.resample('ME').last()
    
    nor_today = datetime.today().date()
    nor_yield_monthly.sort_index(inplace=True)
    
    nor_yield_monthly_reset = nor_yield_monthly.reset_index()
    nor_yield_monthly_reset.sort_values('Date', ascending=False, inplace=True)
    nor_yield_monthly_reset['Date'] = nor_yield_monthly_reset['Date'].dt.strftime('%d-%m-%Y')
    nor_yield_monthly_reset.iloc[0,0] = nor_today.strftime('%d-%m-%Y')
    
    nor_last_yields = nor_yield_monthly.iloc[-1]
    norwegian_labels = ['3M', '6M', '1Y', '3Y', '5Y', '7Y', '10Y']
    
    nor_static_table_content = [
        html.Tr([html.Td('Maturity')] + [html.Td(maturity) for maturity in norwegian_labels]),
        html.Tr([html.Td('Yield (%)')] + [html.Td(f"{nor_last_yields[i]:.2f}") for i in range(len(norwegian_labels))])
    ]
    
    nor_static_yield_table = html.Table(
        nor_static_table_content,
        style={
            'width': '100%',
            'borderCollapse': 'collapse',
            'border': f"1px solid {BOND_MARKET_THEME['border']}",
            'backgroundColor': BOND_MARKET_THEME['surface'],
            'color': BOND_MARKET_THEME['text'],
        },
    )
    
    nor_yield_table_header = html.Div(f"Yields as of {nor_today}", style={'fontWeight': 'bold', 'marginBottom': '10px'})
    
    # Fetch US data
    FRED_API_KEY = '6188d31bebbdca093493a1077d095284'
    fred = Fred(FRED_API_KEY)
    
    observation_start = (datetime.today() - timedelta(days=10 * 365)).strftime('%Y-%m-%d')
    
    maturity_labels = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y']
    series_ids = ['DGS1MO', 'DGS3MO', 'DGS6MO', 'DGS1', 'DGS2', 'DGS3', 'DGS5',
                  'DGS7', 'DGS10', 'DGS20', 'DGS30']
    
    yield_data = {}
    for series_id in series_ids:
        yield_data[series_id] = fred.get_series(series_id, observation_start=observation_start)
    
    yield_df = pd.DataFrame(yield_data)
    yield_df.index = pd.to_datetime(yield_df.index)
    
    yield_df.dropna(how='all', inplace=True)
    yield_df.fillna(method='ffill', inplace=True)
    
    yield_df_quarterly = yield_df.resample('QE').last()
    
    today = pd.Timestamp(datetime.today().date())
    
    yield_df_quarterly.sort_index(inplace=True)
    yield_df_quarterly.columns = maturity_labels
    table_yields = yield_df_quarterly.reset_index()
    
    table_yields['index'] = pd.to_datetime(table_yields['index']).dt.strftime('%Y-%m-%d')
    table_yields.rename(columns={'index':'Date'}, inplace=True)
    table_yields.sort_values('Date', ascending=False, inplace=True)
    table_yields.iloc[0,0] = nor_today
    last_yields = yield_df_quarterly.iloc[-1]
    
    static_table_content = [
        html.Tr([html.Td('Maturity')] + [html.Td(maturity) for maturity in maturity_labels]),
        html.Tr([html.Td('Yield (%)')] + [html.Td(f"{last_yields[i]:.2f}") for i in range(len(maturity_labels))])
    ]
    
    static_yield_table = html.Table(
        static_table_content,
        style={
            'width': '100%',
            'borderCollapse': 'collapse',
            'border': f"1px solid {BOND_MARKET_THEME['border']}",
            'backgroundColor': BOND_MARKET_THEME['surface'],
            'color': BOND_MARKET_THEME['text'],
        },
    )
    
    yield_table_header = html.Div(f"Yields as of {today.date()}", style={'fontWeight': 'bold', 'marginBottom': '10px', 'textAlign':'center'})
    
    tab1_content = html.Div([
        html.H1("US Bond Market Data", style={'textAlign':'center', 'color': BOND_MARKET_THEME['text']}),
        dbc.Card(
            dbc.CardBody(
                html.Div([
                    html.Div([yield_table_header, static_yield_table], style={**YIELD_PANEL_STYLE, 'borderRadius': '5px'}),
                    dcc.RadioItems(
                        id='us-date-range',
                        options=[
                            {'label': 'Full Range', 'value': 'full'},
                            {'label': 'Year to Date', 'value': 'ytd'}
                        ],
                        value='full',
                        style={'marginBottom': '20px'},
                        inputStyle={'marginRight': '6px', 'marginLeft': '12px'},
                        labelStyle={'display': 'inline-block', 'marginRight': '12px'}
                    ),
                    bond_graph('yield-curve-3df', BOND_GRAPH_STYLE_3D),
                    html.Br(),
                    bond_graph('latest-yield-curve-us', BOND_GRAPH_STYLE_2D),
                    html.Br(),
                    create_yield_table(table_yields, table_yields.columns, ['Date'], 'us-yield-table')
                ], style={'textAlign': 'center', 'color': BOND_MARKET_THEME['text_secondary']})
            ),
            className="shadow my-2",
            style={
                'backgroundColor': BOND_MARKET_THEME['surface'],
                'borderColor': BOND_MARKET_THEME['border'],
                'color': BOND_MARKET_THEME['text'],
            },
        )
    ])
    
    norwegian_yield_curve_layout = html.Div([
        html.H1("Norwegian Bond Market Data", style={'textAlign':'center', 'color': BOND_MARKET_THEME['text']}),
        dbc.Card(
            dbc.CardBody(
                html.Div([
                    html.Div([nor_yield_table_header, nor_static_yield_table], style={**YIELD_PANEL_STYLE, 'borderRadius': '5px'}),
                    dcc.RadioItems(
                        id='nor-date-range',
                        options=[
                            {'label': 'Full Range', 'value': 'full'},
                            {'label': 'Year to Date', 'value': 'ytd'}
                        ],
                        value='full',
                        style={'marginBottom': '20px'},
                        inputStyle={'marginRight': '6px', 'marginLeft': '12px'},
                        labelStyle={'display': 'inline-block', 'marginRight': '12px'}
                    ),
                    bond_graph('nor-yield-curve-3d', BOND_GRAPH_STYLE_3D),
                    html.Br(),
                    bond_graph('latest-yield-curve-nor', BOND_GRAPH_STYLE_2D),
                    html.Br(),
                    bond_graph('nor-yield-curve-2d', BOND_GRAPH_STYLE_2D),
                    html.Br(),
                    bond_graph('nor-usd-eur-graph', BOND_GRAPH_STYLE_2D),
                    html.Br(),
                    bond_graph('nor-sek-dkk-graph', BOND_GRAPH_STYLE_2D),
                    create_yield_table(nor_yield_monthly_reset, nor_yield_monthly_reset.columns, ['Date'], 'nor-yield-table')
                ], style={'textAlign': 'center', 'color': BOND_MARKET_THEME['text_secondary']})
            ),
            className="shadow my-2",
            style={
                'backgroundColor': BOND_MARKET_THEME['surface'],
                'borderColor': BOND_MARKET_THEME['border'],
                'color': BOND_MARKET_THEME['text'],
            },
        )
    ])
    
    layout_page = dbc.Container([html.Div([
                dcc.Tabs(
                    id='tabs-example', value='tab-1',
                    className='economy-market-tabs', parent_className='economy-market-tabs-parent',
                    children=[
                        dcc.Tab(label='US Bond Market', value='tab-1', className='economy-tab', selected_className='economy-tab--selected'),
                        dcc.Tab(label='Norwegian Bond Market', value='tab-2', className='economy-tab', selected_className='economy-tab--selected'),
                    ],
                ),
                html.Div(id='tabs-content')
            ])
    ], className='', fluid=True, style=BOND_MARKET_PAGE_STYLE)
    
    layout = dbc.Container([html.Div(className='beforediv'), layout_page],
        className='', style=BOND_MARKET_PAGE_STYLE)
    
    return layout


layout = serve_layout

@callback(
    Output('tabs-content', 'children'),
    Input('tabs-example', 'value')
)
def render_content(tab):
    if tab == 'tab-1':
        return tab1_content
    elif tab == 'tab-2':
        return norwegian_yield_curve_layout
    


@callback(
    Output('latest-yield-curve-nor', 'figure'),
    [Input('nor-date-range', 'value')]
)
def update_latest_yield_curve_nor(date_range):
    if date_range == 'full':
        latest_yield_curve = nor_yield_monthly.iloc[-1]
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
        mask = (nor_yield_df.index >= start_date) & (nor_yield_df.index <= end_date)
        filtered_data = nor_yield_df.loc[mask]
        
        if filtered_data.empty:
            latest_yield_curve = nor_yield_df.iloc[-1]  # Default to latest if no YTD data
        else:
            latest_yield_curve = filtered_data.iloc[-1]
    
    fig = go.Figure(data=[go.Scatter(
        x=norwegian_labels,
        y=latest_yield_curve,
        mode='lines+markers',
        line=dict(color=BOND_MARKET_THEME['blue']),  # Blue line
        marker=dict(size=10, color=BOND_MARKET_THEME['blue']),  # Blue markers
        hoverinfo='x+y',
    )])
    
    fig.update_layout(
        title='Latest Norwegian Yield Curve',
        title_x=0.5,  # Center title
        xaxis_title='Maturity',
        yaxis_title='Yield (%)',
        font=dict(family='Arial', size=14, color=BOND_MARKET_THEME['text_secondary']),  # Font style
        margin=dict(l=50, r=50, t=100, b=50),  # Adjust margins
        paper_bgcolor=TRANSPARENT_BACKGROUND,  # Background color
        plot_bgcolor=TRANSPARENT_BACKGROUND,  # Plot background color
        xaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],  # Grid color
            zerolinecolor=BOND_MARKET_THEME['border']  # Zero line color
        ),
        yaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],  # Grid color
            zerolinecolor=BOND_MARKET_THEME['border']  # Zero line color
        )
    )
    
    return _lock_graph_navigation(fig)



@callback(
    Output('yield-curve-3df', 'figure'),
    [Input('us-date-range', 'value')]
)
def update_graph(date_range):
    if date_range == 'full':
        start_date = yield_df_quarterly.index.min()
        end_date = yield_df_quarterly.index.max()
        filtered_data = yield_df_quarterly.loc[(yield_df_quarterly.index >= start_date) & (yield_df_quarterly.index <= end_date)]
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
        filtered_data = yield_df.loc[(yield_df.index >= start_date) & (yield_df.index <= end_date)]

    if filtered_data.empty:
        # Handle the case where there is no data for the selected range
        fig = go.Figure(data=[go.Surface(
            z=np.zeros((1, len(maturity_labels))),
            x=[start_date],
            y=np.arange(len(maturity_labels)),
            colorscale='GnBu',
            colorbar_title='Yield (%)'
        )])
        
        fig.update_layout(
            title=f"No Yield Curve Data Available from {start_date.date()} to {end_date.date()}",
            paper_bgcolor=TRANSPARENT_BACKGROUND,
            font=dict(color=BOND_MARKET_THEME['text_secondary']),
            scene=dict(
                xaxis_title=' ',
                yaxis_title='Maturity',
                zaxis_title='Yield (%)',
                xaxis=dict(
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                ),
                yaxis=dict(
                    tickvals=np.arange(len(maturity_labels)),
                    ticktext=maturity_labels,
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                ),
                zaxis=dict(
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                )
            ),
            scene_camera=dict(eye=dict(x=1.25, y=1.25, z=1.25)),
        )
        fig.update_layout(showlegend=False)
    else:
        fig = go.Figure(data=[go.Surface(
            z=filtered_data.T.values,
            x=filtered_data.index,
            y=np.arange(len(maturity_labels)), 
            colorscale='GnBu',
            colorbar_title='Yield (%)'
        )])

        num_years = (end_date - start_date).days / 365.25
        
        if date_range == 'ytd':
            tick_freq = 'W'  # Weekly ticks for YTD
        elif num_years <= 1:
            tick_freq = '3M'
        elif 1 < num_years <= 5:
            tick_freq = '6M'
        elif 5 < num_years <= 20:
            tick_freq = '1Y'
        else:
            tick_freq = '5Y'
        
        x_ticks = pd.date_range(start=start_date, end=end_date, freq=tick_freq).to_list()
        
        if pd.Timestamp(datetime.today().date()) not in x_ticks:
            x_ticks.append(pd.Timestamp(datetime.today().date()))

        x_ticks = sorted(x_ticks)  # Sort to maintain order

        # Update layout for the 3D plot
        fig.update_layout(
            title=(
                "Yield Curve (1-month to 30-year)"
                f"<br><sup>{start_date.date()} to {end_date.date()}</sup>"
            ),
            paper_bgcolor=TRANSPARENT_BACKGROUND,
            font=dict(color=BOND_MARKET_THEME['text_secondary']),
            scene=dict(
                xaxis=dict(
                    tickmode='array',
                    tickvals=x_ticks,
                    ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                ), 
                xaxis_title=' ',
                yaxis_title='Maturity',
                zaxis_title='Yield (%)',
                yaxis=dict(
                    tickvals=np.arange(len(maturity_labels)), 
                    ticktext=maturity_labels,
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                ),
                zaxis=dict(
                    backgroundcolor=BOND_MARKET_THEME['subtle'],
                    gridcolor=BOND_MARKET_THEME['grid'],
                    zerolinecolor=BOND_MARKET_THEME['border'],
                )
            ),
            scene_camera=dict(eye=dict(x=1.25, y=1.25, z=1.25)),
        )
        fig.update_layout(showlegend=False)
    
    return _lock_graph_navigation(fig, is_3d=True)


@callback(
    Output('latest-yield-curve-us', 'figure'),
    [Input('us-date-range', 'value')]
)
def update_latest_yield_curve_us(date_range):
    # Always show the latest yield curve
    latest_yield_curve = yield_df.iloc[-1]
    
    fig = go.Figure(data=[go.Scatter(
        x=maturity_labels,
        y=latest_yield_curve,
        mode='lines+markers',
        line=dict(color=BOND_MARKET_THEME['blue']),  # Blue line
        marker=dict(size=10, color=BOND_MARKET_THEME['blue']),  # Blue markers
        hoverinfo='x+y',
    )])
    
    fig.update_layout(
        title='Latest US Yield Curve',
        title_x=0.5,  # Center title
        xaxis_title='Maturity',
        yaxis_title='Yield (%)',
        font=dict(family='Arial', size=14, color=BOND_MARKET_THEME['text_secondary']),  # Font style
        margin=dict(l=50, r=50, t=100, b=50),  # Adjust margins
        paper_bgcolor=TRANSPARENT_BACKGROUND,  # Background color
        plot_bgcolor=TRANSPARENT_BACKGROUND,  # Plot background color
        xaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],  # Grid color
            zerolinecolor=BOND_MARKET_THEME['border']  # Zero line color
        ),
        yaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],  # Grid color
            zerolinecolor=BOND_MARKET_THEME['border']  # Zero line color
        )
    )
    
    return _lock_graph_navigation(fig)




@callback(
    Output('nor-yield-curve-3d', 'figure'),
    [Input('nor-date-range', 'value')]
)
def update_norwegian_graph(date_range):
    if date_range == 'full':
        start_date = nor_yield_monthly.index.min()
        end_date = nor_yield_monthly.index.max()
        filtered_data = nor_yield_monthly.loc[(nor_yield_monthly.index >= start_date) & (nor_yield_monthly.index <= end_date)]
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
        filtered_data = nor_yield_df.loc[(nor_yield_df.index >= start_date) & (nor_yield_df.index <= end_date)]

    num_years = (end_date - start_date).days / 365.25
    
    if date_range == 'ytd':
        tick_freq = 'W'  # Weekly ticks for YTD
    elif num_years <= 1:
        tick_freq = '3M'
    elif 1 < num_years <= 5:
        tick_freq = '6M'
    else:
        tick_freq = '1Y'

    x_ticks = pd.date_range(start=start_date, end=end_date, freq=tick_freq).to_list()

    fig = go.Figure(data=[go.Surface(
        z=filtered_data.T.values,
        x=filtered_data.index,
        y=np.arange(len(norwegian_labels)),
        colorscale='GnBu',
        colorbar_title='Yield (%)',
    )])

    fig.update_layout(
        title=(
            "Norwegian Yield Curve (3M to 10Y)"
            f"<br><sup>{start_date.date()} to {end_date.date()}</sup>"
        ),
        paper_bgcolor=TRANSPARENT_BACKGROUND,
        font=dict(color=BOND_MARKET_THEME['text_secondary']),
        scene=dict(
            xaxis_title=' ',
            yaxis_title='Maturity',
            zaxis_title='Yield (%)',
            xaxis=dict(
                tickmode='array',
                tickvals=x_ticks,
                ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],
                backgroundcolor=BOND_MARKET_THEME['subtle'],
                gridcolor=BOND_MARKET_THEME['grid'],
                zerolinecolor=BOND_MARKET_THEME['border'],
            ),
            yaxis=dict(
                tickvals=np.arange(len(norwegian_labels)),
                ticktext=norwegian_labels,
                backgroundcolor=BOND_MARKET_THEME['subtle'],
                gridcolor=BOND_MARKET_THEME['grid'],
                zerolinecolor=BOND_MARKET_THEME['border'],
            ),
            zaxis=dict(
                backgroundcolor=BOND_MARKET_THEME['subtle'],
                gridcolor=BOND_MARKET_THEME['grid'],
                zerolinecolor=BOND_MARKET_THEME['border'],
            )
        ),
        scene_camera=dict(
            eye=dict(x=1.25, y=1.25, z=1.25),
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0)
        ),
        margin=dict(l=0, r=0, b=10, t=40),
        annotations=[
            dict(
                text="Data Source: Norges Bank",
                x=0.0,
                y=0.1,
                align="right",
                xref="paper",
                yref="paper",
                showarrow=False
            )
        ]
    )
    fig.update_layout(showlegend=False)
    fig.update_annotations(font=dict(family="Helvetica", size=12))
    
    return _lock_graph_navigation(fig, is_3d=True)

@callback(
    Output('nor-yield-curve-2d', 'figure'),
    [Input('nor-date-range', 'value')]
)
def update_norwegian_yield_curve_2d(date_range):
    if date_range == 'full':
        start_date = nor_yield_monthly.index.min()
        end_date = nor_yield_monthly.index.max()
        filtered_data = nor_yield_monthly.loc[(nor_yield_monthly.index >= start_date) & (nor_yield_monthly.index <= end_date)]
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
        filtered_data = nor_yield_df.loc[(nor_yield_df.index >= start_date) & (nor_yield_df.index <= end_date)]

    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=filtered_data.index,
        y=filtered_data['3M'],
        mode='lines',
        name='3M',
        line=dict(color=BOND_MARKET_THEME['blue'])
    ))
    
    fig.add_trace(go.Scatter(
        x=filtered_data.index,
        y=filtered_data['3Y'],
        mode='lines',
        name='3Y',
        line=dict(color=BOND_MARKET_THEME['green'])
    ))
    
    fig.add_trace(go.Scatter(
        x=filtered_data.index,
        y=filtered_data['10Y'],
        mode='lines',
        name='10Y',
        line=dict(color=BOND_MARKET_THEME['amber'])
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['3M'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['3Y'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['10Y'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    # Add annotations for final observations
    fig.add_annotation(
        x=filtered_data.index[-1],
        y=filtered_data['3M'].iloc[-1],
        text=f"3M: {filtered_data['3M'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.add_annotation(
        x=filtered_data.index[-1],
        y=filtered_data['3Y'].iloc[-1],
        text=f"3Y: {filtered_data['3Y'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.add_annotation(
        x=filtered_data.index[-1],
        y=filtered_data['10Y'].iloc[-1],
        text=f"10Y: {filtered_data['10Y'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.update_layout(
        title='Norwegian Government Yields (3M, 3Y, 10Y)',
        xaxis_title='Date',
        yaxis_title='Yield (%)',
        font=dict(family='Arial', size=14, color=BOND_MARKET_THEME['text_secondary']),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor=TRANSPARENT_BACKGROUND,
        plot_bgcolor=TRANSPARENT_BACKGROUND,
        xaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        ),
        yaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        )
    )
    
    return _lock_graph_navigation(fig)



@callback(
    Output('nor-usd-eur-graph', 'figure'),
    [Input('nor-date-range', 'value')]
)
def update_nor_usd_eur_graph(date_range):
    if date_range == 'full':
        start_date = nor_cur_data['TIME_PERIOD'].min()
        end_date = nor_cur_data['TIME_PERIOD'].max()
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
    
    mask = (nor_cur_data['TIME_PERIOD'] >= start_date) & (nor_cur_data['TIME_PERIOD'] <= end_date)
    filtered_data = nor_cur_data.loc[mask]

    # Filter for USD/NOK and EUR/NOK
    usd_data = filtered_data[filtered_data['Currency'] == 'USD/NOK']
    eur_data = filtered_data[filtered_data['Currency'] == 'EUR/NOK']
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=usd_data['TIME_PERIOD'],
        y=usd_data['OBS_VALUE'],
        mode='lines',
        name='USD/NOK',
        line=dict(color=BOND_MARKET_THEME['blue'])
    ))
    
    fig.add_trace(go.Scatter(
        x=eur_data['TIME_PERIOD'],
        y=eur_data['OBS_VALUE'],
        mode='lines',
        name='EUR/NOK',
        line=dict(color=BOND_MARKET_THEME['green'])
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[usd_data['TIME_PERIOD'].iloc[-1]],
        y=[usd_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[eur_data['TIME_PERIOD'].iloc[-1]],
        y=[eur_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    # Add annotations for final observations
    fig.add_annotation(
        x=usd_data['TIME_PERIOD'].iloc[-1],
        y=usd_data['OBS_VALUE'].iloc[-1],
        text=f"USD/NOK: {usd_data['OBS_VALUE'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.add_annotation(
        x=eur_data['TIME_PERIOD'].iloc[-1],
        y=eur_data['OBS_VALUE'].iloc[-1],
        text=f"EUR/NOK: {eur_data['OBS_VALUE'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.update_layout(
        title='USD/NOK and EUR/NOK Exchange Rates',
        xaxis_title='Date',
        yaxis_title='Exchange Rate',
        font=dict(family='Arial', size=14, color=BOND_MARKET_THEME['text_secondary']),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor=TRANSPARENT_BACKGROUND,
        plot_bgcolor=TRANSPARENT_BACKGROUND,
        xaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        ),
        yaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        )
    )
    
    return _lock_graph_navigation(fig)


@callback(
    Output('nor-sek-dkk-graph', 'figure'),
    [Input('nor-date-range', 'value')]
)
def update_nor_sek_dkk_graph(date_range):
    if date_range == 'full':
        start_date = nor_cur_data['TIME_PERIOD'].min()
        end_date = nor_cur_data['TIME_PERIOD'].max()
    elif date_range == 'ytd':
        start_date = pd.Timestamp(datetime.today().date().replace(month=1, day=1))
        end_date = pd.Timestamp(datetime.today().date())
    
    mask = (nor_cur_data['TIME_PERIOD'] >= start_date) & (nor_cur_data['TIME_PERIOD'] <= end_date)
    filtered_data = nor_cur_data.loc[mask]

    # Filter for SEK/NOK and DKK/NOK
    sek_data = filtered_data[filtered_data['Currency'] == 'SEK/NOK']
    dkk_data = filtered_data[filtered_data['Currency'] == 'DKK/NOK']
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sek_data['TIME_PERIOD'],
        y=sek_data['OBS_VALUE'],
        mode='lines',
        name='SEK/NOK',
        line=dict(color=BOND_MARKET_THEME['blue'])
    ))
    
    fig.add_trace(go.Scatter(
        x=dkk_data['TIME_PERIOD'],
        y=dkk_data['OBS_VALUE'],
        mode='lines',
        name='DKK/NOK',
        line=dict(color=BOND_MARKET_THEME['green'])
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[sek_data['TIME_PERIOD'].iloc[-1]],
        y=[sek_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[dkk_data['TIME_PERIOD'].iloc[-1]],
        y=[dkk_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color=BOND_MARKET_THEME['red'], size=10),
        showlegend=False
    ))
    
    # Add annotations for final observations
    fig.add_annotation(
        x=sek_data['TIME_PERIOD'].iloc[-1],
        y=sek_data['OBS_VALUE'].iloc[-1],
        text=f"SEK/NOK: {sek_data['OBS_VALUE'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.add_annotation(
        x=dkk_data['TIME_PERIOD'].iloc[-1],
        y=dkk_data['OBS_VALUE'].iloc[-1],
        text=f"DKK/NOK: {dkk_data['OBS_VALUE'].iloc[-1]:.2f}",
        showarrow=False,
        yshift=10
    )
    
    fig.update_layout(
        title='SEK/NOK and DKK/NOK Exchange Rates',
        xaxis_title='Date',
        yaxis_title='Exchange Rate',
        font=dict(family='Arial', size=14, color=BOND_MARKET_THEME['text_secondary']),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor=TRANSPARENT_BACKGROUND,
        plot_bgcolor=TRANSPARENT_BACKGROUND,
        xaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        ),
        yaxis=dict(
            gridcolor=BOND_MARKET_THEME['grid'],
            zerolinecolor=BOND_MARKET_THEME['border']
        )
    )
    
    return _lock_graph_navigation(fig)
