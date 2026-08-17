#!/usr/bin/env python
# coding: utf-8
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objs as go

from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

from dash import dash_table as dt

import dash

from dash import dcc, callback

dash.register_page(__name__, path='/Finvest')


colors = {
    'background': '#D6E4EA',
    'text': '#718BA5',
    'accent': '#004172',
    'text-white':'white',
    'content':'#EDF3F4'
}

plt.style.use('ggplot')
COLORS = {
    'background': '#f4f4f4',
    'banner': '#0a213b',
    'banner2': '#1e3a5a',
    'content': '#859db3',
    'text': '#859db3',
    'accent': '#004172',
    'border': '#bed6eb',
    'header': '#7a7a7a',
    'element': '#1f8c44',
    'text-white': 'white',
}


pd.options.mode.chained_assignment = None  # default='warn'

# test = frame[~frame['Sector'].isin(['Healthcare', 'Energy'])]
# test['size score'] = test.groupby('Sector')['Market Cap'].rank(ascending=True)
returns = pd.read_csv('https://www.dropbox.com/scl/fi/7rng3vi29j5g09tingkrq/returns.csv?rlkey=4l3xagb0bgmmio8v3kfjp16ri&st=ulwi8mo8&dl=1')  # index=False)
returns = returns[['Date', 'Symbols', 'Close']]
returns['Date'] = pd.to_datetime(returns['Date'])

df = pd.read_csv('https://www.dropbox.com/scl/fi/rhcxje5egbav9vq2uore2/Final.csv?rlkey=tq6oy2pob3ccadhw2egejdkc5&st=jbey1a4i&dl=1')
df['Next Earnings'] = pd.to_datetime(df['Next Earnings'])
df.rename(columns={'index': 'Company'}, inplace=True)
for i in range(len(df.columns)):
    if df[df.columns[i]].dtype == df[df.columns[1]].dtype:
        df[df.columns[i]] = df[df.columns[i]].round(2)
    else:
        pass
df = df[['Company', 'Sector', 'Dividend Growth Rate ANN',
         'Dividend Yield ANN',
         'Return on Equity TTM',
         'Return on Assets TTM',
         'Price to Sales TTM',
         'Price to Cash Flow MRQ',
         'P/E Ratio TTM',
         'Price to Book MRQ',
         '5 Year Sales Growth 5YA',
         'Gross Margin 5YA',
         'Ticker',
         'Revenue Growth Quarter',
         'Asset Turnover Quarter',
         'Gross Margin Quarter',
         'Operating Margin Quarter',
         'Market Cap',
         'Equity Growth Quarter']]
# frame['YTD'] = frame['YTD'].astype(str).str.replace("--","").str.replace("","").astype(str).str.replace("%", "").str.replace(",", "").replace("-", np.nan)
df.replace([np.inf, -np.inf], 0, inplace=True)
df = df.dropna()
millnames = ['', ' Thousand', ' Mn', ' Bn', ' Tn']
def millify(n):
    # n = float(n)
    millidx = max(0, min(len(millnames) - 1,
                         int(np.floor(0 if n == 0 else np.log10(abs(n)) / 3))))

    return '{:.0f}{}'.format(n / 10 ** (3 * millidx), millnames[millidx])
new_col = [0] * len(df)
for i in range(len(df['Market Cap'])):
    new_col[i] = millify(df['Market Cap'][i])
df.insert(loc=2, column="Market Capitalization", value=new_col)
tic = df['Ticker']
df = df.drop(columns=['Ticker'])
df.insert(loc=0, column='Ticker', value=tic)
df.rename(columns={'Revenue Growth Quarter': 'Revenue Growth Quarter %'}, inplace=True)
df.rename(columns={"Asset Turnover Quarter": "Asset Turnover Quarter %"}, inplace=True)
df.rename(columns={"Gross Margin Quarter": "Gross Margin Quarter %"}, inplace=True)
df.rename(columns={"Operating Margin Quarter": "Operating Margin Quarter %"}, inplace=True)
df.rename(columns={"Equity Growth Quarter": "Equity Growth Quarter %"}, inplace=True)
df.rename(columns={"Dividend Growth Rate ANN": "Dividend Growth Rate ANN %"}, inplace=True)
df.rename(columns={"Dividend Yield ANN": "Dividend Yield ANN %"}, inplace=True)
df.rename(columns={"Return on Equity TTM": "Return on Equity TTM %"}, inplace=True)
df.rename(columns={"Return on Assets TTM": "Return on Assets TTM %"}, inplace=True)
df.rename(columns={"5 Year Sales Growth 5YA": "5 Year Sales Growth 5YA %"}, inplace=True)
df.rename(columns={"Gross Margin 5YA": "Gross Margin 5YA %"}, inplace=True)


options = [{'label': x, 'value': x}
           for x in df.columns[4:]]


def add_rangeselector(figure):
    """This function takes a plotly figure object and adds buttons to the figure that allows the user
    to zoom in on several pre-defined periods. Source: https://plotly.com/python/range-slider/."""

    figure.update_layout(xaxis=dict(rangeselector=dict(buttons=list([
        dict(count=1, label="1M", step="month", stepmode="backward"),
        dict(count=6, label="6M", step="month", stepmode="backward"),
        dict(count=1, label="YTD", step="year", stepmode="todate"),
        dict(count=1, label="1Y", step="year", stepmode="backward"),
        dict(label="All",step="all")
    ])),
        rangeslider=dict(visible=True),
        type="date"))


datepicker = dcc.DatePickerRange(
    id='my_dates',
    min_date_allowed=datetime(2015, 1, 1),  # allow user to go back as far as January the 1st, 2015
    max_date_allowed=datetime.today(),  # user cannot select future dates
    start_date=datetime(2021, 1, 1),
    end_date=datetime.today(),
    className='normal-text',
    style={}
)
factors = dcc.Dropdown(
    id='factors',
    options=options,
    value=options[0]['value'],
    multi=True,
    clearable=True,
    searchable=True,
    # optionHeight= 50,
    placeholder="Select Factors",
    style={'color': 'black', 'border-radius': '10px', 'textAlign': 'center', 'minWidth': '300px', 'minHeight': '40px', 'fontSize': '0.95em', 'option': {'font-size': '0.95em', 'overflow': 'visible'}},
    className='dropdownmenu',
    optionHeight=40
    # 'display': 'inline-block',

)



import dash_bootstrap_components as dbc
from dash import Input, Output, State, html

description = """
Find the optimal companies to buy based on your investing strategy. Select your desired factors for the companies you wish to invest in and weigh the factors according to your preference. 
The stocks are then ranked, providing you with the top stocks to buy according to your inputs.
"""

explanation = """ ## **Abbreviations** ##

MRQ : Most Recent Quarter

ANN: Annualized Value

5YA : Five Year Average

TTM : Trailing Twelve Months

## **Factors** ##

Assets Turnover: Revenue MRQ / Average of Total Assets Most Recent Year

P/E Ratio : Price Per Share / Earnings TTM

Market Cap : Number of Shares Outstanding * Price Per Share (i.e Market Value of the Company)


"""

def build_banner():
    return html.Div(id="banner", className="banner", children=[html.Div(
        children=[html.Div(
            id="banner-logo",
            children=[
                html.Button(id="learn-more-button",
                            children=["DEFINITIONS"],
                            n_clicks=0),
            ],

        )
        ])])

def generate_modal():
    return html.Div(id="markdown",
                    className="modal",
                    style={'z-index': '9999'},
                    children=(html.Div(
                        id="markdown-container",
                        className="markdown-container",
                        style={'background-color': colors['accent'], 'border-radius':'10px', 'margin':'10%', 'z-index': '9999', 'width':'600px'},
                        children=[
                            html.Div([
                                html.Div(
                                style={'textAlign':'center'},
                                className="close-container",
                                children=html.Button("Close",
                                                     id="markdown_close",
                                                     n_clicks=0,
                                                     className="buttonDefinitions"),

                                ),
                                html.Div(
                                    style={'margin-bottom':'0px'},
                                    className="markdown-text",
                                    children=  dcc.Markdown(children=(
                                                            explanation),
                                                            style={'fontSize': '14px', 'font-family': "Arial", 'color': 'white', 'textAlign':'center'}

                                    ),
                                ),html.Br(),
                                ], style={'margin-bottom':'50px'},
                            ),
                        ],
                    )))

def generate_modal():
    return html.Div(
        id="markdown",
        className="modal",
        style={
            'z-index': '9999',
            'position': 'fixed',
            'top': '0', # Starting at the top
            'left': '50%',
            'transform': 'translateX(-50%)',  # Horizontally centering it
            'width': '100%',
        },
        children=html.Div(
            id="markdown-container",
            className="markdown-container",
            style={
                'background-color': colors['accent'],
                'border-radius': '10px',
                'width': '50%',
                'margin': '0 auto',
                'position': 'relative',
                'top': '150px',  # This should push the markdown-container 200px down from its current position
            },
            children=[
                html.Div([
                    html.Div(
                        style={'textAlign': 'center'},
                        className="close-container",
                        children=html.Button("Close",
                                             id="markdown_close",
                                             n_clicks=0,
                                             className="buttonDefinitions"),
                    ),
                    html.Div(
                        style={'margin-bottom': '0px'},
                        className="markdown-text",
                        children=dcc.Markdown(children=(explanation),
                                              style={'fontSize': '14px',
                                                     'font-family': "Arial",
                                                     'color': 'white',
                                                     'textAlign': 'center'}
                                              ),
                    ), html.Br(),
                ], style={'margin-bottom': '50px'},
                ),
            ],
        )
    )












card1and = html.Div([
                        html.Div(children=[

                                                  html.H1("Strategy", style={}, className='headerfinvest'),
                                                  html.H1("Finder", style={
                                                           'color': 'rgba(61, 181, 105)'}, className='headerfinvest'),
                                          html.Img(src=('assets/favicon.jpg'),
                                                            style={'border-radius': '200px', 'width': '20%', 'margin':'15px'},
                                                            ),
                                          ], className='parent-row'),

        html.Div(children=[description, html.Hr()], className='normal-text', style={'textAlign':'center', 'font-size':'1,5rem', 'margin-left':'10%', 'margin-right':'10%', 'font-weight':'bold'}),
        
        html.Div([
                html.Button(id="learn-more-button",
                        children=["DEFINITIONS"],
                        n_clicks=0,
                        className='buttonDefinitions',
                        style={'margin':'10px'}),
            # tooltip,
            factors,
            # dcc.Interval(max_intervals=1, id='inter'),

            # dbc.Table.from_dataframe(df),
            # dbc.Row(html.Div([html.Label('Revenue Growth MRQ', id='revenue_growth')]), style = {'display': 'block'}),

            html.Div([
            dbc.Row([
                html.Div(
                    id='slider_rev_growth_wrapper',
                    children=[
                        html.Label('Revenue Growth MRQ %', style={'margin-left': '1em',
                                                                  'font-style': ['bold'],
                                                                  'fontSize': 18}),
                        dcc.Slider(
                            id='revenue_growth',
                            min=0,
                            max=200,
                            step=1,
                            marks=None,
                            # vertical=True,
                            # handleLabel ={"label": "Weight", "showCurrentValue" : True},
                            value=0,
                            className='slider',
                            tooltip={
                                "placement": "bottom",
                                "always_visible": True
                            })
                    ],
                    style={'display': 'block'},
                    className='sliderinput')], style={'min-width':'300px', 'textAlign':'center'}),
            dbc.Row(
                html.Div(
                    id='slider_asset_turnover_wrapper',
                    children=[
                        html.Label(' Assets Turnover MRQ %', style={'margin-left': '1em',
                                                                    'font-style': ['bold'],
                                                                    'fontSize': 18}),
                        dcc.Slider(
                            id='asset_turnover',
                            min=0,
                            max=200,
                            marks=None,
                            step=1,
                            value=0,
                            className='slider',
                            # size=50,
                            tooltip={
                                "placement": "bottom",
                                "always_visible": True
                            })
                    ],
                    style={'display': 'block'},
                    className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(
                    id='slider_gross_margin_wrapper',
                    children=[
                        html.Label(' Gross Margin MRQ %', style={'margin-left': '1em',
                                                                 'font-style': ['bold'],
                                                                 'fontSize': 18}),
                        dcc.Slider(
                            id='gross_margin',
                            min=0,
                            max=200,
                            marks=None,
                            step=1,
                            className='slider',
                            # size=100,
                            value=0,
                            tooltip={
                                "placement": "bottom",
                                "always_visible": True
                            })
                    ],
                    style={'display': 'block'},
                    className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_operating_margin_wrapper',
                         children=[
                             html.Label(' Operating Margin MRQ %', style={'margin-left': '1em',
                                                                          'font-style': ['bold'],
                                                                          'fontSize': 18}),
                             dcc.Slider(id='operating_margin',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_market_cap_wrapper',
                         children=[
                             html.Label(' Market Capitalization', style={'margin-left': '1em',
                                                                         'font-style': ['bold'],
                                                                         'fontSize': 18}),
                             dcc.Slider(id='market_cap',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_equity_growth_wrapper',
                         children=[
                             html.Label(' Equity Growth MRQ %', style={'margin-left': '1em',
                                                                       'font-style': ['bold'],
                                                                       'fontSize': 18}),
                             dcc.Slider(id='equity_growth',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_div_growth_wrapper',
                         className='sliderinput',
                         children=[
                             html.Label(' Dividend Growth Rate ANN %', style={'margin-left': '1em',
                                                                              'font-style': ['bold'],
                                                                              'fontSize': 18}),
                             dcc.Slider(id='div_growth',

                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'}
                         ), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_div_yield_wrapper',
                         children=[
                             html.Label(' Dividend Yield ANN %', style={'margin-left': '1em',
                                                                        'font-style': ['bold'],
                                                                        'fontSize': 18}),
                             dcc.Slider(id='div_yield',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_ROE_wrapper',
                         children=[
                             html.Label(' Return on Equity TTM %', style={'margin-left': '1em',
                                                                          'font-style': ['bold'],
                                                                          'fontSize': 18}),
                             dcc.Slider(id='ROE',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_ROA_wrapper',
                         children=[
                             html.Label(' Return on Assets TTM %', style={'margin-left': '1em',
                                                                          'font-style': ['bold'],
                                                                          'fontSize': 18}),
                             dcc.Slider(id='ROA',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_PS_wrapper',
                         children=[
                             html.Label(' Price to Sales TTM', style={#'margin-left': '1em',
                                                                      'font-style': ['bold'],
                                                                      'fontSize': 18,
                                                                      'text-Align':'center'}),
                             dcc.Slider(id='PS',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='parent-container2'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_PCF_wrapper',
                         children=[
                             html.Label(' Price to Cash Flow MRQ', style={'margin-left': '1em',
                                                                          'font-style': ['bold'],
                                                                          'fontSize': 18}),
                             dcc.Slider(id='PCF',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_five_sales_wrapper',
                         children=[
                             html.Label(' 5 Year Sales Growth 5YA %', style={'margin-left': '1em',
                                                                             'font-style': ['bold'],
                                                                             'fontSize': 18,
                                                                             'margin-top':'5px'}),
                             dcc.Slider(id='fivesales',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_five_marg_wrapper',
                         children=[
                             html.Label(' Gross Margin 5YA %', style={'margin-left': '1em',
                                                                      'font-style': ['bold'],
                                                                      'fontSize': 18}),
                             dcc.Slider(id='five_marg',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        className='slider',
                                        value=0,
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput'), className='slider-row'
            ),
            dbc.Row(
                html.Div(id='slider_PE_wrapper',
                         children=[
                             html.Label(' P/E Ratio TTM', style={'margin-left': '1em',
                                                                 'font-style': ['bold'],
                                                                 'fontSize': 18}),
                             dcc.Slider(id='PE',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True
                                        })
                         ],
                         style={'display': 'block'},
                         className='parent-row'), className='slider-row'),
            dbc.Row(
                html.Div(id='slider_PB_wrapper',
                         children=[
                             html.Label(' Price to Book MRQ', style={'margin-left': '1em',
                                                                     'font-style': ['bold'],
                                                                     'fontSize': 18}),
                             dcc.Slider(id='PB',
                                        min=0,
                                        max=200,
                                        marks=None,
                                        step=1,
                                        value=0,
                                        className='slider',
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": True,
                                        })
                         ],
                         style={'display': 'block'},
                         className='sliderinput')),], className='slider-row'),

            dcc.Store(id='my_output2'),
            dcc.Store(id='my_output3')],
            style={'padding-bottom': '40px', 'min-width':'1200px'},
            className='parent-container')],
    className='parent-container',

    style={'margin-bottom': '15px'
           }
)

cardtable = html.Div([
                                                               dbc.Card(children=[html.Div(
                                                                   id='my_output')], style={'border-radius':'1000px'},
                                                                   # width={'size': 1700},,
                                                                   # style={'display':'block'}
                                                                   #           ),
                                                                   #   ], style={'height': 525},
                                                                   #   className='table-users',
                                                               )], style={'min-width':''}, className='')

card3 = html.Div(id='sectorwrapper',
                 children=[html.Div([
                                  # html.Br(),

                                  html.Div([html.H2('Resulting Stocks Performance',
                                                    style={'textAlign': 'center', 'font-family': ["Arial"]}),
                                            dbc.Row([datepicker], style={'textAlign': 'center', 'font-family': ["Arial"]} )], className='headers'),

                                  html.Div(children=[dcc.Graph(id='price_plot',
                                                                                 style={'background-color':colors['content'],
                                                                                        "transform": "scale(1)"})])], className='', style={'margin-bottom': '15px', 'min-height':'500px'}),
                     html.Br(),

                     html.Div([html.H2('Distribution of Sectors', className='headers', style={'textAlign': 'center'}),
                                        html.Div(
                                            children=[
                                                html.Div(id='sector_wrapper', children=[
                                                    dcc.Graph(id='sector_pie', style={'background-color':colors['content']})
                                                ], style={'display': 'block', "transform": "scale(1)"})
                                            ]),
                               ],),

                                        ], className='')


# dash_table.DataTable(df.to_dict('records'), [{"name": i, "id": i} for i in df.columns])
layout = dbc.Container(children=[html.Div(className='beforediv'),
                            card1and,
                            generate_modal(),
                            html.H2("To see results, please extend the width of your screen. If you're on iOS or Android please tilt your screen 90 degrees", className='informationtext'),
                            html.Div([
                            cardtable,
                            html.Br(),
                            card3], className='resultsFinvest')], className='parent-container', style={'min-height':'100vh', 'padding-bottom':'20px'})




# @callback(Output('tablewrapper', 'style'),
#              [Input('factors', 'value')])
# def update_results(factor):
#    if  (len(factor) > 1):
#        return {'display': 'block'}
#    else:
#        return {'display': 'none'}

# @callback(Output('sectorwrapper', 'style'),
#              [Input('factors', 'value')])
# def update_pie(factor):
#    if  (len(factor) > 1):
#        return {'display': 'block'}
#    else:
#        return {'display': 'none'}

@callback(
    Output('factors', 'options'),
    Input('stock-tabs', 'value')
)
def update_options(tab):
    if tab == 'us':
        df = pd.read_csv(r'Final.csv')
        df['Next Earnings'] = pd.to_datetime(df['Next Earnings'])
        df.rename(columns={'index': 'Company'}, inplace=True)
        for i in range(len(df.columns)):
            if df[df.columns[i]].dtype == df[df.columns[1]].dtype:
                df[df.columns[i]] = df[df.columns[i]].round(2)
            else:
                pass
        df = df[['Company', 'Sector', 'Dividend Growth Rate ANN',
                'Dividend Yield ANN',
                'Return on Equity TTM',
                'Return on Assets TTM',
                'Price to Sales TTM',
                'Price to Cash Flow MRQ',
                'P/E Ratio TTM',
                'Price to Book MRQ',
                '5 Year Sales Growth 5YA',
                'Gross Margin 5YA',
                'Ticker',
                'Revenue Growth Quarter',
                'Asset Turnover Quarter',
                'Gross Margin Quarter',
                'Operating Margin Quarter',
                'Market Cap',
                'Equity Growth Quarter']]
        # frame['YTD'] = frame['YTD'].astype(str).str.replace("--","").str.replace("","").astype(str).str.replace("%", "").str.replace(",", "").replace("-", np.nan)
        df.replace([np.inf, -np.inf], 0, inplace=True)
        df = df.dropna()
        millnames = ['', ' Thousand', ' Mn', ' Bn', ' Tn']
        def millify(n):
            # n = float(n)
            millidx = max(0, min(len(millnames) - 1,
                                int(np.floor(0 if n == 0 else np.log10(abs(n)) / 3))))

            return '{:.0f}{}'.format(n / 10 ** (3 * millidx), millnames[millidx])
        new_col = [0] * len(df)
        for i in range(len(df['Market Cap'])):
            new_col[i] = millify(df['Market Cap'][i])
        df.insert(loc=2, column="Market Capitalization", value=new_col)
        tic = df['Ticker']
        df = df.drop(columns=['Ticker'])
        df.insert(loc=0, column='Ticker', value=tic)
        df.rename(columns={'Revenue Growth Quarter': 'Revenue Growth Quarter %'}, inplace=True)
        df.rename(columns={"Asset Turnover Quarter": "Asset Turnover Quarter %"}, inplace=True)
        df.rename(columns={"Gross Margin Quarter": "Gross Margin Quarter %"}, inplace=True)
        df.rename(columns={"Operating Margin Quarter": "Operating Margin Quarter %"}, inplace=True)
        df.rename(columns={"Equity Growth Quarter": "Equity Growth Quarter %"}, inplace=True)
        df.rename(columns={"Dividend Growth Rate ANN": "Dividend Growth Rate ANN %"}, inplace=True)
        df.rename(columns={"Dividend Yield ANN": "Dividend Yield ANN %"}, inplace=True)
        df.rename(columns={"Return on Equity TTM": "Return on Equity TTM %"}, inplace=True)
        df.rename(columns={"Return on Assets TTM": "Return on Assets TTM %"}, inplace=True)
        df.rename(columns={"5 Year Sales Growth 5YA": "5 Year Sales Growth 5YA %"}, inplace=True)
        df.rename(columns={"Gross Margin 5YA": "Gross Margin 5YA %"}, inplace=True)

        options = [{'label': x, 'value': x}
                for x in df.columns[4:]]
        #df = df_us  # Assuming df_us is your US stocks dataframe
    else:
        df = None  # Assuming df_scan is your Scandinavian stocks dataframe

    #options = [{'label': x, 'value': x} for x in df.columns[4:]]
    return options




@callback(Output('sectorwrapper', 'style'),
              [Input('asset_turnover', 'value'),
               Input('revenue_growth', 'value'),
               Input('gross_margin', 'value'),
               Input('operating_margin', 'value'),
               Input('market_cap', 'value'),
               Input('div_growth', 'value'),
               Input('div_yield', 'value'),
               Input('ROE', 'value'),
               Input('ROA', 'value'),
               Input('PS', 'value'),
               Input('PCF', 'value'),
               Input('fivesales', 'value'),
               Input('five_marg', 'value'),
               Input('PE', 'value'),
               Input('PB', 'value'),
               Input('equity_growth', 'value')])
def update_sector(assetturns,
                  revenueg,
                  grossmarg,
                  opmarg,
                  market,
                  divg,
                  divy,
                  roe,
                  roa,
                  ps,
                  pcf,
                  fiverev,
                  fivemar,
                  pe,
                  pb,
                  eqgr):
    totalweight = sum([assetturns,
                       revenueg,
                       grossmarg,
                       opmarg,
                       market,
                       divg,
                       divy,
                       roe,
                       roa,
                       ps,
                       pcf,
                       fiverev,
                       fivemar,
                       pe,
                       pb,
                       eqgr])
    if totalweight > 0:
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@callback(Output('slider_rev_growth_wrapper', 'style'),
              [Input('factors', 'value')])
def update_rev_growth(factor):
    if 'Revenue Growth Quarter %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_asset_turnover_wrapper', 'style'),
              [Input('factors', 'value')])
def update_asset_turnover(factor):
    if 'Asset Turnover Quarter %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_gross_margin_wrapper', 'style'),
              [Input('factors', 'value')])
def update_gross_margin(factor):
    if 'Gross Margin Quarter %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_operating_margin_wrapper', 'style'),
              [Input('factors', 'value')])
def update_operating_margin(factor):
    if 'Operating Margin Quarter %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_market_cap_wrapper', 'style'),
              [Input('factors', 'value')])
def update_market_cap(factor):
    if 'Market Cap' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_equity_growth_wrapper', 'style'),
              [Input('factors', 'value')])
def update_equity_growth(factor):
    if 'Equity Growth Quarter %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_div_yield_wrapper', 'style'),
              [Input('factors', 'value')])
def update_div_yield(factor):
    if 'Dividend Yield ANN %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_div_growth_wrapper', 'style'),
              [Input('factors', 'value')])
def update_div_growth(factor):
    if 'Dividend Growth Rate ANN %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_ROE_wrapper', 'style'),
              [Input('factors', 'value')])
def update_roe(factor):
    if 'Return on Equity TTM %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_ROA_wrapper', 'style'),
              [Input('factors', 'value')])
def update_roa(factor):
    if 'Return on Assets TTM %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_PS_wrapper', 'style'),
              [Input('factors', 'value')])
def update_ps(factor):
    if 'Price to Sales TTM' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_PCF_wrapper', 'style'),
              [Input('factors', 'value')])
def update_pcf(factor):
    if 'Price to Cash Flow MRQ' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_five_sales_wrapper', 'style'),
              [Input('factors', 'value')])
def update_five_sales(factor):
    if '5 Year Sales Growth 5YA %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_five_marg_wrapper', 'style'),
              [Input('factors', 'value')])
def update_five_marg(factor):
    if 'Gross Margin 5YA %' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_PE_wrapper', 'style'),
              [Input('factors', 'value')])
def update_pe(factor):
    if 'P/E Ratio TTM' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback(Output('slider_PB_wrapper', 'style'),
              [Input('factors', 'value')])
def update_pb(factor):
    if 'Price to Book MRQ' in factor:
        return {'display': 'block', 'min-width':'300px', 'textAlign':'center'}
    else:
        return {'display': 'none'}


@callback([Output('my_output', "children"), Output('my_output2', "data"),
               Output('my_output3', "data")], [
                  Input('factors', 'value'),
                  Input('asset_turnover', 'value'),
                  Input('revenue_growth', 'value'),
                  Input('gross_margin', 'value'),
                  Input('operating_margin', 'value'),
                  Input('market_cap', 'value'),
                  Input('div_growth', 'value'),
                  Input('div_yield', 'value'),
                  Input('ROE', 'value'),
                  Input('ROA', 'value'),
                  Input('PS', 'value'),
                  Input('PCF', 'value'),
                  Input('fivesales', 'value'),
                  Input('five_marg', 'value'),
                  Input('PE', 'value'),
                  Input('PB', 'value'),
                  Input('equity_growth', 'value')
              ])
# Input('inter', 'n_intervals')])
def update_frame(factors,
                 assetturns,
                 revenueg,
                 grossmarg,
                 opmarg,
                 market,
                 divg,
                 divy,
                 roe,
                 roa,
                 ps,
                 pcf,
                 fiverev,
                 fivemar,
                 pe,
                 pb,
                 eqgr,
                 df=df):
    if len(factors) > 0:
        cols = []
        # factors = ['Revenue Growth Quarter', 'Asset Turnover Quarter']
        cols = []
        if type(factors) != list:
            factors = [factors]
            cols = ['Ticker'] + ['Company'] + ['Sector'] + [
                'Market Capitalization'
            ] + factors
        else:
            comp = ['Ticker'] + ['Company'] + ['Sector'
                                               ] + ['Market Capitalization']
            cols = list(np.append(comp, factors))
        # else:
        #   cols=[]

        filtered_df = df[cols]

        filtered_df['Combined Score'] = 0
        if type(factors) == list:
            for i in range(len(factors)):
                try:
                    filtered_df[str(factors[i] + " Score")] = round(
                        filtered_df[factors[i]].astype(float).rank(
                            method="average", ascending=True, pct=True).copy() *
                        100, 2)
                except:
                    pass
        else:
            for i in range(len([factors])):
                try:
                    filtered_df[str(factors[i] + " Score")] = round(
                        filtered_df[factors[i]].astype(float).rank(
                            method="average", ascending=True, pct=True).copy() *
                        100, 2)
                except:
                    pass

        filtered_df = pd.DataFrame(filtered_df)

        filtered_df['Combined Score'] = 0
        if "Revenue Growth Quarter %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df["Revenue Growth Quarter % Score"] * revenueg, 3)

        else:
            next
        if "Asset Turnover Quarter %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Asset Turnover Quarter % Score"] * assetturns, 2)

        else:
            next
        if "Gross Margin Quarter %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Gross Margin Quarter % Score"] * grossmarg, 2)

        else:
            next
        if "Operating Margin Quarter %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Operating Margin Quarter % Score"] * opmarg, 2)

        else:
            next
        if "Market Cap" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Market Cap Score"] * market, 2)
        else:
            next
        if "Equity Growth Quarter %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Equity Growth Quarter % Score"] * eqgr, 2)

        else:
            next

        if "Dividend Growth Rate ANN %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Dividend Growth Rate ANN % Score"] * divg, 2)

        else:
            next
        if "Dividend Yield ANN %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Dividend Yield ANN % Score"] * divy, 2)

        else:
            next
        if "Return on Equity TTM %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Return on Equity TTM % Score"] * roe, 2)

        else:
            next
        if "Return on Assets TTM %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Return on Assets TTM % Score"] * roa, 2)

        else:
            next
        if "Price to Sales TTM" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Price to Sales TTM Score"] * ps, 2)
        else:
            next
        if "Price to Cash Flow MRQ" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Price to Cash Flow MRQ Score"] * pcf, 2)
        else:
            next
        if "5 Year Sales Growth 5YA %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["5 Year Sales Growth 5YA % Score"] * fiverev, 2)

        else:
            next
        if "Gross Margin 5YA %" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Gross Margin 5YA % Score"] * fivemar, 2)

        else:
            next
        if "P/E Ratio TTM" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["P/E Ratio TTM Score"] * pe, 2)
        else:
            next
        if "Price to Book MRQ" in factors:
            filtered_df['Combined Score'] = round(
                filtered_df['Combined Score'] +
                filtered_df["Price to Book MRQ Score"] * pb, 2)
        else:
            next

        filtered_df = filtered_df.sort_values('Combined Score', ascending=False)
        filtered_df = filtered_df[list(np.append(cols, 'Combined Score'))]
        # subset = df[df['ticker'] == ticker].copy()

        filtered_df['Combined Score'] = ((
                                                 filtered_df['Combined Score'] - filtered_df[
                                             'Combined Score'].min()) / (
                                                 filtered_df['Combined Score'].max() - filtered_df[
                                             'Combined Score'].min())) * 100
        # filtered_df = filtered_df.dropna()
        filtered_df = filtered_df.head(10)

        if 'Market Cap' in filtered_df.columns:
            filtered_df = filtered_df.drop('Market Cap', axis=1)

        newdf = filtered_df.T

        new_header = newdf.iloc[0]  # grab the first row for the header
        newdf = newdf[1:]  # take the data less the header row
        newdf.columns = new_header
        # newdf.columns.name = None
        newdf.index.names = ['Factors']
        newdf = newdf.reset_index()
        newdf = newdf.round(decimals=2)

        filtered_df = filtered_df.reset_index().reset_index().drop(['index'], axis=1).rename(
            columns={'level_0': 'Rank'})
        filtered_df['Rank'] = (filtered_df['Rank'] + 1).astype(int)
        #filtered_df.style.set_precision(0)
        filtered_df.style.format({
            'Rank': '{:,.0f}'.format
            # 'B': '{:,.3f}'.format,
        })
        tablee = filtered_df.to_json()

        tablee1 = dt.DataTable(data=
                               pd.read_json(tablee).to_dict('records'),
                               columns=
                               [{
                                   "name": 'Rank',
                                   "id": 'Rank',
                                   'type': 'numeric',
                                   'format': dict(specifier=',.0f')
                               }] +
                               [{
                                   "name": i,
                                   "id": i,
                                   'type': 'numeric',
                                   'format': dict(specifier=',.2f')
                               } for i in pd.read_json(tablee).columns[1:]],

                               editable=False,
                               filter_action="none",
                               # sort_action="native",
                               # sort_mode="multi",
                               column_selectable="single",
                               row_selectable=False,
                               row_deletable=False,
                               # page_current=0,
                               # page_size=10,
                               # selected_columns=[],
                               # selected_rows=[],
                               # scrollable = True,
                               # striped=True,
                               # virtualization=True,
                               # page_action="native",
                               # fixed_columns={'headers' : True, 'data': 9},
                               # page_current= 2,
                               # page_size= 5,
                               # style_as_list_view=True,
                               # fill_width=False,
                               style_data={
                                   'whiteSpace': 'normal',
                                   'height': 'auto',
                                   'width': 'auto',
                                   'font-family': ['Arial'],
                                   'color': 'black',
                                   'font-size':'14px',
                               },
                               style_cell={
                                   'padding': '10px',
                                   'textAlign': 'right',
                                   'backgroundColor': '#929bff'
                               },
                               style_cell_conditional=[{
                                   'if': {
                                       'column_id': 'Sector'
                                   },
                                   'textAlign': 'left',
                                   'backgroundColor': '#9fa4d8'
                               }] + [{
                                   'if': {
                                       'column_id': c
                                   },
                                   'textAlign': 'left',
                                   'backgroundColor': 'white'
                               } for c in ['Ticker', 'Company', 'Rank']],

                               style_header={
                                   'backgroundColor': colors['accent'],
                                   'fontWeight': 'bold',
                                   'color': 'white',
                                   'whiteSpace': 'normal',
                                   'border': '2px solid black',
                                   'font-family': ['Arial'],
                                   'font-size':'15px'
                               },
                               style_data_conditional=[  # style_data.c refers only to data rows
                                   # {
                                   #    'if': {
                                   #        'row_index': 'odd'
                                   #    },
                                   #    'backgroundColor': 'white'
                                   # },
                                   {
                                       'if': {
                                           'column_id': 'Ticker'
                                       },
                                       # 'backgroundColor': 'grey',
                                       'fontWeight': 'bold',
                                   },
                                   {
                                       'if': {
                                           'column_id': 'Combined Score'
                                       },
                                       # 'backgroundColor': 'grey',
                                       'fontWeight': 'bold',
                                   }

                               ],
                               style_table={
                                   'height': 'auto',
                                   'overflowX': 'auto',
                                   # 'overflowY': 'None',
                                   'width': 'auto',
                                   # 'font-family': ['Open Sans', 'sans-serif']
                               },
                               style_filter={'textAlign': 'center', 'font-style': ['bold'],
                                             'font-family': ['Arial']}
                               # style={'textAlign':'center','font-style': ['bold'],'font-family':['Open Sans','sans-serif']}, #style={'textAlign': 'center','backgroundColor':'#E23744',,

                               )
        table1 = filtered_df['Ticker'].to_json(date_format='iso', orient='split')
        table2 = filtered_df.to_json()
        return tablee1, table1, table2

    elif len(factors) == 0:
        raise dash.exceptions.PreventUpdate


@callback(Output(component_id='price_plot', component_property='figure'),
              [Input(component_id='my_output2', component_property='data'),
               Input(component_id='my_dates', component_property='start_date'),
               Input(component_id='my_dates', component_property='end_date')])
def create_graph(df_f, starts, ends, df=returns):
    df_l = pd.read_json(df_f)

    tickers = df_l['data']
    #print(tickers)
    tickers = pd.concat([tickers, pd.Series(['SPY'])], axis=0).reset_index().drop('index',
                                                                                  axis=1)
    #    tickers.append(pd.Series(['SPY'])).reset_index().drop('index',
    #                                                                axis=1)
    tickers = list(tickers.iloc[:, 0])
   # print(tickers)
    returns = df
    mask = (returns['Date'] > starts) & (returns['Date'] <= ends)
    returns = returns.loc[mask]
    #print(returns)
    returnsf = returns[returns['Symbols'].isin(tickers)].copy().fillna(0)

    returnsf['Daily Percentage Return'] = returnsf.groupby('Symbols')['Close'].pct_change()
    returnsf['Daily Percentage Return Plus 1'] = 1 + returnsf['Daily Percentage Return']
    returnsf['Cumulative Percentage Return'] = returnsf.groupby('Symbols')[
                                                   'Daily Percentage Return Plus 1'].cumprod() - 1


    returnsf = returnsf.dropna()

    maskspy = (returnsf['Symbols'] != 'SPY')
    sumrets = returnsf.loc[maskspy]
    sumreturns = sumrets['Cumulative Percentage Return'].groupby(
        returns['Date']).mean()

    sumreturns = sumreturns.reset_index()
    #
    fig_close = px.line(returnsf,
                        x='Date',
                        y='Cumulative Percentage Return',
                        color='Symbols')
    add_rangeselector(fig_close)
    fig_close.update_layout(
        yaxis_title='Cumulative %-Returns',
        xaxis_title='Time',
        title='',
        title_x=0.5,
        margin={
            'l': 0,
            'r': 0
        },
        font=dict(family="Arial", size=15, color=COLORS['text']), # changed font to Arial
        paper_bgcolor=colors['background'], # using the background color
        plot_bgcolor='white', # using the content color for plot background
        yaxis_tickformat=".1%", # formatting y-axis ticks
        yaxis_gridcolor=COLORS['border'], # using border color for y-grid
        xaxis_gridcolor=COLORS['border'], # using border color for x-grid
        height=700
    )

    fig_close.update_xaxes(showgrid=True) # show x grid for better readability
    fig_close.update_yaxes(showgrid=True) # show y grid for better readability
    fig_close.add_trace(
        go.Scatter(x=sumreturns['Date'],
                   y=sumreturns['Cumulative Percentage Return'],
                   name="Strategy"))

    return fig_close


@callback(Output(component_id='sector_pie', component_property='figure'),
              Input(component_id='my_output3', component_property='data'))
def create_sector_pie(dat):
    df_l = pd.read_json(dat).dropna()
    fig = px.histogram(df_l,
                       # histfunc='count',
                       x='Sector',
                       color='Sector')
    # x=[df_l['Sector'].value_counts()])
    # x=[df_l['Sector'].unique()])
    # hole=.7)
    fig.update_layout(
        yaxis_title='Count of Sector',
        xaxis=dict(
            showline=False,
        ),
        yaxis=dict(
            showline=False,
            dtick=1
        ),
        title="",
        title_x=0.19,
        title_y=0.5,
        margin={
            'l': 0,
            'r': 0
        },
        font=dict(family="Arial", size=15, color=COLORS['text']), # changed font to Arial
        paper_bgcolor=colors['background'], # using the background color
        plot_bgcolor='white', # using the content color for plot background
    )
    #fig.layout.plot_bgcolor = 'white'

    # fig.update_traces(textposition='inside', textinfo="label+percent")
    fig.layout.update(showlegend=True)
    return fig

@callback(
    Output("markdown", "style"),
    [
        Input("learn-more-button", "n_clicks"),
        Input("markdown_close", "n_clicks")
    ],
)
def update_click_output(button_click, close_click):
    ctx = dash.callback_context

    if ctx.triggered:
        prop_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if prop_id == "learn-more-button":
            return {"display": "block"}

    return {"display": "none"}





