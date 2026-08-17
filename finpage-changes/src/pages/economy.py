# #!/usr/bin/env python
# # coding: utf-8
# import pandas as pd
# import plotly.express as px

# import dash_bootstrap_components as dbc
# import dash
# from dash import html, dcc
# #from update_script import update_dropbox_dataset
# from dash import dcc, callback, html
# from dash.dependencies import Input, Output
# import dash_bootstrap_components as dbc
# import plotly.graph_objects as go
# from updateEcon import updateEcon
# from datetime import datetime, timedelta
# import os
# #dash.register_page(__name__, path='/economy')


# colors = {
#     'background': 'rgb(240,241,245)',
#     'text': 'black',
#     'accent': '#004172',
#     'text-white':'white',
#     'content':'#EDF3F4'
# }

# fonts = {
#     'heading': 'Helvetica',
#     'body': 'Helvetica'
# }

# COLORS = {
#     'background': '#f4f4f4',
#     'banner': '#0a213b',
#     'banner2': '#1e3a5a',
#     'content': '#859db3',
#     'text': '#859db3',
#     'accent': '#004172',
#     'border': '#bed6eb',
#     'header': '#7a7a7a',
#     'element': '#1f8c44',
#     'text-white': 'white',
# }




# # # Get the directory of the current script
# # current_dir = os.path.dirname(os.path.abspath(__file__))

# # # Go up one folder
# # parent_dir = os.path.dirname(current_dir)

# # # Construct the file path
# # file_path = os.path.join(parent_dir, 'econW_updated.csv')

# # Read the CSV
# #updateEcon('full') 
# economy = pd.read_csv('econW_updated.csv', parse_dates=['Date'])

# economy['Date'] = pd.to_datetime(economy['Date'])

# latestdate = str(pd.to_datetime(economy['Date']).dt.date.tail(1).values[0])
# economy['unemp_rate'] = economy['unemp_rate'] / 100
# economy['TenYield'] = economy['TenYield'] / 100
# economy['Shiller_PE'] = round(economy['Shiller_PE'], 2)
# economy['Close'] = round(economy['Close'], 2)
# from fredapi import Fred
# import pandas as pd
# import matplotlib.pyplot as plt
# # Initialize FRED API
# FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
# fred = Fred(FRED_API_KEY)
# interest_payments = fred.get_series('A091RC1Q027SBEA', observation_start='2000-01-01')
# government_revenue = fred.get_series('FGRECPT', observation_start='2000-01-01')


# interest_df = pd.DataFrame(interest_payments, columns=['Interest Payments'])
# revenue_df = pd.DataFrame(government_revenue, columns=['Total Revenue'])

# df = pd.merge(interest_df, revenue_df, left_index=True, right_index=True)

# df.index = pd.to_datetime(df.index)
# df.reset_index(inplace=True)
# df.rename(columns={'index':'Date'}, inplace=True)


# df['Interest to Income Ratio'] = ((df['Interest Payments'])/df['Total Revenue'])
# df['Interest to Income Ratio'] = round(df['Interest to Income Ratio'] , 2)

# def create_graph(color, yaxis, title, dataframe, y, tick, starts, ends, hline1=False, textbox=False, pred=False, hline0=False,
#                  legend=False, YoY=False, Score=False):
#     dataframe = dataframe.ffill().fillna(0)
#     mask = (dataframe['Date'] > starts) & (dataframe['Date'] <= ends)
#     dataframe = dataframe.loc[mask]

#     # Create the figure
#     fig = go.Figure()

#     # Add trace with no fill color (black line)
#     fig.add_trace(go.Scatter(
#         x=dataframe['Date'],
#         y=dataframe[y],
#         mode='lines',  # Just the line, no fill
#         line_color='black',  # Black line color
#         showlegend=False  # No legend needed for this trace
#     ))

#     # Update layout for the figure
#     fig.update_layout(
#         yaxis_title=yaxis,
#         xaxis_title='Date',
#         title=title,
#         title_x=0.5,
#         margin={'l': 0, 'r': 35},
#         font=dict(family="Abel", size=15, color=colors['text']),
#         plot_bgcolor='white',  # Ensures the plot area has a white background
#         paper_bgcolor='white',  # Ensures the overall background is white
#     )

#     fig.update_xaxes(showgrid=False)
#     fig.update_yaxes(tickformat=".1" + str(tick))
    
#     # Conditional traces and other configurations
#     #if pred == True:
#         # fig.add_traces(
#         #     list(go.Scatter(x=dataframe['Date'], y=dataframe['Forward Return'], fill='tozeroy', fillcolor='skyblue').select_traces()))
#         # fig.add_traces(
#         #     list(go.Scatter(x=dataframe['Date'], y=dataframe['SP Trailing 4 Weeks Return'], fill='tozeroy', fillcolor='red').select_traces()))
    
#     if hline1 == True:
#         fig.add_hline(y=35, line_width=3, line_dash="dash", line_color="orange")
#         fig.add_hline(y=20, line_width=3, line_dash="dash", line_color="red")
#     if hline0 == True:
#         fig.add_hline(y=0, line_width=3, line_dash="dash", line_color="black")
    
#     if YoY == True:
#         fig.add_hline(y=0.02, line_width=3, line_dash="dash", line_color="orange")
#         fig.add_annotation(
#             text='Yellow Line: FED Target Rate',
#             align='left',
#             showarrow=False,
#             xref='paper',
#             yref='paper',
#             x=0.05,
#             y=1.0,
#             bordercolor='black',
#             borderwidth=1)

#     if textbox == True:
#         fig.add_annotation(
#             text='Yellow Line Recommendation: 70 % Long <br> 30% Short <br> Red Line Recommendation: Risk Neutral <br> i.e 50 % Long, 50 % Short',
#             align='left',
#             showarrow=False,
#             xref='paper',
#             yref='paper',
#             x=0.05,
#             y=1.0,
#             bordercolor='black',
#             borderwidth=1)

#     if Score == True:
#         fig.update_layout()

#     if ((legend == True) & (y == 'Preds')):
#         fig['data'][0]['showlegend'] = True
#         fig['data'][0]['name'] = 'Predicted Forward Return'
#         fig['data'][1]['showlegend'] = True
#         fig['data'][1]['name'] = 'Actual Forward Return'

#     # Update final layout settings
#     fig.update_layout(
#         font=dict(family="Helvetica", size=15, color=COLORS['text']), 
#         paper_bgcolor=colors['background'], 
#         plot_bgcolor='white',  # Ensure plot background is white
#         yaxis_gridcolor=COLORS['border'], 
#         xaxis_gridcolor=COLORS['border'], 
#         height=700
#     )

#     fig.update_xaxes(showgrid=True) 
#     fig.update_yaxes(showgrid=True)
#     fig.update_layout(uirevision='constant')

#     return fig



# descriptioneconomy = f''' An overview of the US economy. Source of data is FRED API and multpl.com. Latest update: {latestdate}'''
# cardeconomy = dbc.Container([
#                     html.Div(children=[html.H1("Economy", style={'margin-right':'-5px'}, className='headerfinvest'),
#                                         html.H1("Overview", style={'color':'rgba(61, 181, 105)','margin-left':'0px'}, className='headerfinvest'),
#                                           ], className='page-intros', style={'margin':'15px', 'gap':'13px'}),
#             html.Div(children=[descriptioneconomy], className='normal-text', style={'max-width':'75%', 'textAlign':'center', 'font-size':'1,5rem'}),
#             html.Br(),
#             dcc.Loading(  # Wrap the output component with Loading
#                 id="loading",
#                 type="default",  # or "circle" or "dot" or "cube"
#                 children=html.Div(id="update-output-economy", style={'font-size':'11', 'color':'gray'})
#             ),
#             html.Hr(),

#         html.Div([
#             dcc.Graph(
#                 figure=create_graph(colors['accent'], 'Yield', '10-yr Treasury Yield %', economy, 'TenYield', tick='%',
#                                     starts='2010-01-01', ends=str(datetime.today())), style={},  className='graph'),
#                 # width={'size':5, 'offset':1, 'order':1},

#                 # xs=6, sm=6, md=6, lg=5, xl=5

                
#                 html.Div([

#                     dcc.Graph(figure=create_graph(colors['accent'], 'Shiller P/E Ratio', 'Shiller P/E Ratio', economy,
#                                                   'Shiller_PE',
#                                                   tick=' ', starts='2000-01-01', ends=str(datetime.today())), className='graph'),
#                 ], style={'margin':'5px'}  # className='six columns' #width={'size':5, 'offset':0, 'order':2},

#                 ), # className='graph-right')
#         ], className='parent-row', style={'margin':'5px'}),

#         html.Div([
            
#             dcc.Graph(figure=create_graph(colors['accent'], 'Price', 'S&P 500 Index', economy,
#                                           'Close', tick=' ', starts='1985-01-01',
#                                           ends=str(datetime.today())), className='graph'),

#                 html.Div([

#                     dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Inflation YoY', 'Inflation US YoY-Change %', economy, 'CPI YoY', tick='%',
#                                         starts='1995-01-01', ends=str(datetime.today()), YoY=True),  className='graph',
#                     style={'border-right': '1px rgba(1, 1, 1, 1)'})


                                            
#                 ], style={'margin':'5px'}  # className='six columns' #width={'size':5, 'offset':0, 'order':2},

#                 ),
#                 # width={'size':5, 'offset':1, 'order':1},

#                 # xs=6, sm=6, md=6, lg=5, xl=5

#         ], className='parent-row', style={}),


#         html.Div([
#                 dcc.Graph(
#                         figure=create_graph(colors['accent'], 'Interest to Income Ratio', 'Federal Interest Payments to Revenues Ratio', df,
#                                             'Interest to Income Ratio', tick='%', starts='1985-01-01',
#                                             ends=str(datetime.today())), className='graph'),
#                 # width={'size':5, 'offset':1, 'order':1},

#                 # xs=6, sm=6, md=6, lg=5, xl=5

                
#                 html.Div([

#                     dcc.Graph(
#                         figure=create_graph(colors['accent'], 'Money Supply M2', 'Money Supply US M2', economy,
#                                             'm2', tick=' ', starts='1985-01-01', ends=str(datetime.today())),
#                          className='graph')
#                 ], style={'margin':'5px'}
#                     # className='six columns' #width={'size':5, 'offset':0, 'order':2},

#                 ), # className='graph-right')
#         ], className='parent-row', style={'overflow': 'visible'}),


#         html.Div([
#             dcc.Graph(figure=create_graph(colors['accent'], 'T10Y2Y', '10-y 2-y Spread', economy,
#                                           'T10Y2Y', tick=' ', starts='1985-01-01', hline0=False,
#                                           ends=str(datetime.today())), className='graph'),
#                 # width={'size':5, 'offset':1, 'order':1},

#                 # xs=6, sm=6, md=6, lg=5, xl=5

#                 html.Div([

#                     dcc.Graph(
#                         figure=create_graph(colors['accent'], 'Unemployment Rate', 'Unemployment Rate US', economy,
#                                             'unemp_rate', tick='%', starts='1985-01-01',
#                                             ends=str(datetime.today())), className='graph'),
#                 ], style={'margin':'5px'}  # className='six columns' #width={'size':5, 'offset':0, 'order':2},

#                 ), # className='graph-right')
#         ], className='parent-row', style={'margin':'5px'}),



#         # html.Div([
#         #         html.H3(
#         #             "Below is a combined economy score visualized, which tries to give a score for the current state of the economy. The score is created by weighing fundamental factors in the economy, like the data visualized above. The data is stationary. The weights on each indicator are "
#         #             "optimized in a long-short strategy of the S&P500 SPY ETF where Sharpe Ratio is maximized. Note that this score does not take into account interactions between the factors. We use data from 1998 for this purpose because of changes in economic conditions.",
#         #             className='normal-text', style={'textAlign':'center'}),
#         #         html.Hr(),], style={'margin':'5%'}),

#         # html.Div([

#         #     dcc.Graph(
#         #         figure=create_graph(colors['accent'], 'Score', 'Combined Economy Score', economy, 'Combined Economy Score',
#         #                             tick=' ', starts='2000-01-01', ends=str(datetime.today()), hline1=True,
#         #                             textbox=True, Score=True), style={})  # 'height':'43vw'})
#         # ], className='graph' , style={'width':'80%'}

#         # ),
#         html.Br()
        
# ], className='parent-container2', fluid=True, style={})


# layout = dbc.Container([html.Div(className='beforediv'), cardeconomy],
#     className='')


# @callback(
#     Output("update-output-economy", "children"),
#     [Input("update-button", "n_clicks")],
#     prevent_initial_call=False
# )
# def run_update(n_clicks):
#     reload = 'full' if n_clicks is None else 'full'
#     print(reload)
#     updateEcon(reload)  # Call the update function
#     economy = pd.read_csv('econW_updated.csv', parse_dates=['Date'])

#     economy['Date'] = pd.to_datetime(economy['Date'])

#     latestdate = str(pd.to_datetime(economy['Date']).dt.date.tail(1).values[0])
#     economy['unemp_rate'] = economy['unemp_rate'] / 100
#     economy['TenYield'] = economy['TenYield'] / 100
#     economy['Shiller_PE'] = round(economy['Shiller_PE'], 2)
#     economy['Close'] = round(economy['Close'], 2)
#     from fredapi import Fred
#     import pandas as pd
#     import matplotlib.pyplot as plt
#     # Initialize FRED API
#     FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
#     fred = Fred(FRED_API_KEY)
#     interest_payments = fred.get_series('A091RC1Q027SBEA', observation_start='2000-01-01')
#     government_revenue = fred.get_series('FGRECPT', observation_start='2000-01-01')


#     interest_df = pd.DataFrame(interest_payments, columns=['Interest Payments'])
#     revenue_df = pd.DataFrame(government_revenue, columns=['Total Revenue'])

#     df = pd.merge(interest_df, revenue_df, left_index=True, right_index=True)

#     df.index = pd.to_datetime(df.index)
#     df.reset_index(inplace=True)
#     df.rename(columns={'index':'Date'}, inplace=True)


#     df['Interest to Income Ratio'] = ((df['Interest Payments'])/df['Total Revenue'])
#     df['Interest to Income Ratio'] = round(df['Interest to Income Ratio'] , 2)

#     return f"Dataset updated successfully!"
        
