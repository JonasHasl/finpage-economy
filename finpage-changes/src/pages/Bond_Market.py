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

dash.register_page(__name__, path='/yield_curves')

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
                'color': '#e2e8f0',
                'font-size': '14px',
            },
            style_cell={
                'padding': '10px',
                'textAlign': 'right',
                'backgroundColor': '#0d1321'
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
                'color': '#e2e8f0',
                'whiteSpace': 'normal',
                'border': '2px solid #1e293b',
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
    ], style={'padding': '10px', 'backgroundColor': 'hsl(222, 42%, 9%)', 'border': '1px solid hsl(222, 30%, 16%)', 'borderRadius': '10px', 'marginBottom': '20px', 'marginLeft':'10%', 'marginRight':'10%'})

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
        style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid #1e293b', 'color': '#e2e8f0'},
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
        style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid #1e293b', 'color': '#e2e8f0'},
    )
    
    yield_table_header = html.Div(f"Yields as of {today.date()}", style={'fontWeight': 'bold', 'marginBottom': '10px', 'textAlign':'center'})
    
    tab1_content = html.Div([
        html.H1("US Bond Market Data", style={'textAlign':'center', 'color': 'var(--text-white-color)'}),
        dbc.Card(
            dbc.CardBody(
                html.Div([
                    html.Div([yield_table_header, static_yield_table], style={'padding': '10px', 'backgroundColor': 'hsl(222, 42%, 9%)', 'border': '1px solid hsl(222, 30%, 16%)',
                                                                           'borderRadius': '5px', 'marginBottom': '20px', 'marginLeft':'10%', 'marginRight':'10%'}),
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
                    dcc.Graph(id='yield-curve-3df', config={'scrollZoom': True}, style={'height': '1000px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    dcc.Graph(id='latest-yield-curve-us', style={'height': '500px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    create_yield_table(table_yields, table_yields.columns, ['Date'], 'us-yield-table')
                ], style={'textAlign': 'center'})
            ),
            className="shadow my-2"  # Adds a shadow effect to the card
        )
    ])
    
    norwegian_yield_curve_layout = html.Div([
        html.H1("Norwegian Bond Market Data", style={'textAlign':'center', 'color': 'var(--text-white-color)'}),
        dbc.Card(
            dbc.CardBody(
                html.Div([
                    html.Div([nor_yield_table_header, nor_static_yield_table], style={'padding': '10px', 'backgroundColor': 'hsl(222, 42%, 9%)', 'border': '1px solid hsl(222, 30%, 16%)',
                                                                                   'borderRadius': '5px', 'marginBottom': '20px', 'marginLeft':'10%', 'marginRight':'10%'}),
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
                    dcc.Graph(id='nor-yield-curve-3d', config={'scrollZoom': True}, style={'height': '1000px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    dcc.Graph(id='latest-yield-curve-nor', style={'height': '500px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    dcc.Graph(id='nor-yield-curve-2d', style={'height': '500px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    dcc.Graph(id='nor-usd-eur-graph', style={'height': '500px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    html.Br(),
                    dcc.Graph(id='nor-sek-dkk-graph', style={'height': '500px', 'marginLeft':'10%', 'marginRight':'10%'}),
                    create_yield_table(nor_yield_monthly_reset, nor_yield_monthly_reset.columns, ['Date'], 'nor-yield-table')
                ], style={'textAlign': 'center'})
            ),
            className="shadow my-2"  # Adds a shadow effect to the card
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
    ], className='', fluid=True, style={})
    
    layout = dbc.Container([html.Div(className='beforediv'), layout_page],
        className='')
    
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
        line=dict(color='#38bdf8'),  # Blue line
        marker=dict(size=10, color='#38bdf8'),  # Blue markers
        hoverinfo='x+y',
    )])
    
    fig.update_layout(
        title='Latest Norwegian Yield Curve',
        title_x=0.5,  # Center title
        xaxis_title='Maturity',
        yaxis_title='Yield (%)',
        font=dict(family='Arial', size=14, color='#94a3b8'),  # Font style
        margin=dict(l=50, r=50, t=100, b=50),  # Adjust margins
        paper_bgcolor='rgba(0,0,0,0)',  # Background color
        plot_bgcolor='rgba(0,0,0,0)',  # Plot background color
        xaxis=dict(
            gridcolor='#1e293b',  # Grid color
            zerolinecolor='#1e293b'  # Zero line color
        ),
        yaxis=dict(
            gridcolor='#1e293b',  # Grid color
            zerolinecolor='#1e293b'  # Zero line color
        )
    )
    
    return fig



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
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8'),
            scene=dict(
                xaxis_title=' ',
                yaxis_title='Maturity',
                zaxis_title='Yield (%)',
                xaxis=dict(
                    backgroundcolor='#0f172a'
                ),
                yaxis=dict(
                    tickvals=np.arange(len(maturity_labels)),
                    ticktext=maturity_labels,
                    backgroundcolor='#0f172a'
                ),
                zaxis=dict(backgroundcolor='#0f172a')
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
            title=f"Yield Curve (1-month to 30-year) from {start_date.date()} to {end_date.date()}",
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8'),
            scene=dict(
                xaxis=dict(
                    tickmode='array',
                    tickvals=x_ticks,
                    ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],
                    backgroundcolor='#0f172a'
                ), 
                xaxis_title=' ',
                yaxis_title='Maturity',
                zaxis_title='Yield (%)',
                yaxis=dict(
                    tickvals=np.arange(len(maturity_labels)), 
                    ticktext=maturity_labels,
                    backgroundcolor='#0f172a'
                ),
                zaxis=dict(backgroundcolor='#0f172a')
            ),
            scene_camera=dict(eye=dict(x=1.25, y=1.25, z=1.25)),
        )
        fig.update_layout(showlegend=False)
    
    return fig


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
        line=dict(color='#38bdf8'),  # Blue line
        marker=dict(size=10, color='#38bdf8'),  # Blue markers
        hoverinfo='x+y',
    )])
    
    fig.update_layout(
        title='Latest US Yield Curve',
        title_x=0.5,  # Center title
        xaxis_title='Maturity',
        yaxis_title='Yield (%)',
        font=dict(family='Arial', size=14, color='#94a3b8'),  # Font style
        margin=dict(l=50, r=50, t=100, b=50),  # Adjust margins
        paper_bgcolor='rgba(0,0,0,0)',  # Background color
        plot_bgcolor='rgba(0,0,0,0)',  # Plot background color
        xaxis=dict(
            gridcolor='#1e293b',  # Grid color
            zerolinecolor='#1e293b'  # Zero line color
        ),
        yaxis=dict(
            gridcolor='#1e293b',  # Grid color
            zerolinecolor='#1e293b'  # Zero line color
        )
    )
    
    return fig




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
        title=f"Norwegian Yield Curve (3M to 10Y) from {start_date.date()} to {end_date.date()}",
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94a3b8'),
        scene=dict(
            xaxis_title=' ',
            yaxis_title='Maturity',
            zaxis_title='Yield (%)',
            xaxis=dict(
                tickmode='array',
                tickvals=x_ticks,
                ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],
                backgroundcolor='#0f172a'
            ),
            yaxis=dict(
                tickvals=np.arange(len(norwegian_labels)),
                ticktext=norwegian_labels,
                backgroundcolor='#0f172a'
            ),
            zaxis=dict(backgroundcolor='#0f172a')
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
    
    return fig

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
        line=dict(color='#38bdf8')
    ))
    
    fig.add_trace(go.Scatter(
        x=filtered_data.index,
        y=filtered_data['3Y'],
        mode='lines',
        name='3Y',
        line=dict(color='#34d399')
    ))
    
    fig.add_trace(go.Scatter(
        x=filtered_data.index,
        y=filtered_data['10Y'],
        mode='lines',
        name='10Y',
        line=dict(color='#fbbf24')
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['3M'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color='#f87171', size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['3Y'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color='#f87171', size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[filtered_data.index[-1]],
        y=[filtered_data['10Y'].iloc[-1]],  # Use .iloc here for integer indexing
        mode='markers',
        marker=dict(color='#f87171', size=10),
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
        font=dict(family='Arial', size=14, color='#94a3b8'),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        ),
        yaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        )
    )
    
    return fig



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
        line=dict(color='#38bdf8')
    ))
    
    fig.add_trace(go.Scatter(
        x=eur_data['TIME_PERIOD'],
        y=eur_data['OBS_VALUE'],
        mode='lines',
        name='EUR/NOK',
        line=dict(color='#34d399')
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[usd_data['TIME_PERIOD'].iloc[-1]],
        y=[usd_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color='#f87171', size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[eur_data['TIME_PERIOD'].iloc[-1]],
        y=[eur_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color='#f87171', size=10),
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
        font=dict(family='Arial', size=14, color='#94a3b8'),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        ),
        yaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        )
    )
    
    return fig


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
        line=dict(color='#38bdf8')
    ))
    
    fig.add_trace(go.Scatter(
        x=dkk_data['TIME_PERIOD'],
        y=dkk_data['OBS_VALUE'],
        mode='lines',
        name='DKK/NOK',
        line=dict(color='#34d399')
    ))
    
    # Add final observation markers
    fig.add_trace(go.Scatter(
        x=[sek_data['TIME_PERIOD'].iloc[-1]],
        y=[sek_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color='#f87171', size=10),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=[dkk_data['TIME_PERIOD'].iloc[-1]],
        y=[dkk_data['OBS_VALUE'].iloc[-1]],
        mode='markers',
        marker=dict(color='#f87171', size=10),
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
        font=dict(family='Arial', size=14, color='#94a3b8'),
        margin=dict(l=50, r=50, t=100, b=50),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        ),
        yaxis=dict(
            gridcolor='#1e293b',
            zerolinecolor='#1e293b'
        )
    )
    
    return fig

