# #!/usr/bin/env python
# # coding: utf-8
# import pandas as pd
# import plotly.express as px
# from datetime import datetime, timedelta
# import dash_bootstrap_components as dbc
# import dash
# from dash import html, dcc
# from update_script import update_dropbox_dataset
# from dash import dcc, callback, html
# from dash.dependencies import Input, Output
# import dash_bootstrap_components as dbc
# import plotly.graph_objects as go

# dash.register_page(__name__, path='/economy')


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

# economy = pd.read_csv('https://www.dropbox.com/scl/fi/lp58l9owrh4npi78c6lpd/econW.csv?rlkey=5fafzlx30n9wvir9w1xmfls7o&st=dkuh0em5&dl=1')
# latestdate = str(pd.to_datetime(economy['Date']).dt.date.tail(1).values[0])
# #'https://www.dropbox.com/scl/fi/zwcl7yhhlnk6nqg9j16r7/econW.csv?rlkey=1k0r4dnqxc4gmukgxphh0n591&dl=1'
# economy['InflationExp'] = economy['InflationExp'] / 100
# economy['unemp_rate'] = economy['unemp_rate'] / 100
# economy['TenYield'] = economy['TenYield'] / 100
# economy['Shiller_P/E'] = round(economy['Shiller_P/E'], 2)
# economy['Combined Economy Score'] = round(economy['Combined Economy Score'], 2)
# economy['Consumer Confidence'] = round(economy['ConsumerConfidence'], 2)
# economy['Close'] = round(economy['Close'], 2)
# from fredapi import Fred
# import pandas as pd
# import matplotlib.pyplot as plt
# # Initialize FRED API
# FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
# fred = Fred(FRED_API_KEY)
# # Retrieve data from FRED
# # Series ID for Interest Payments: FGEXPND
# # Series ID for Government Receipts: FGRECPT
# interest_payments = fred.get_series('A091RC1Q027SBEA')
# government_revenue = fred.get_series('FGRECPT')
# #interesttogdp = fred.get_series('FYOIGDA188S')
# #tenyear = fred.get_series('DGS10').resample('AS-JAN').first()

# # Convert the data into a DataFrame for easier handling
# interest_df = pd.DataFrame(interest_payments, columns=['Interest Payments'])
# revenue_df = pd.DataFrame(government_revenue, columns=['Total Revenue'])
# #interesttogdp_df = pd.DataFrame(interesttogdp, columns=['Interest to GDP'])
# #tenyear_df = pd.DataFrame(tenyear, columns=['10-year'])
# # Merge the two datasets on the date index
# df = pd.merge(interest_df, revenue_df, left_index=True, right_index=True)
# #df = pd.merge(df, interesttogdp_df,  left_index=True, right_index=True)
# #df = pd.merge(df, tenyear_df,  left_index=True, right_index=True)
# # Convert the index to a datetime index and extract the year
# df.index = pd.to_datetime(df.index)
# df.reset_index(inplace=True)
# df.rename(columns={'index':'Date'}, inplace=True)

# # Calculate the interest-to-income ratio
# df['Interest to Income Ratio'] = ((df['Interest Payments'])/df['Total Revenue'])
# df['Interest to Income Ratio'] = round(df['Interest to Income Ratio'] , 2)



# def create_graph(color, yaxis, title, dataframe, y, tick, starts, ends, hline1=False, textbox=False, pred=False, hline0=False,
#                  legend=False, YoY=False, Score=False):
#     dataframe = dataframe.ffill().fillna(0)
#     mask = (dataframe['Date'] > starts) & (dataframe['Date'] <= ends)
#     dataframe = dataframe.loc[mask]

#     # Check if there are any values below 0
#     has_below_zero = (dataframe[y] < 0).any()

#     # Create the figure
#     fig = go.Figure()

#     if has_below_zero:
#         # Split the data into above 0 and below 0 for coloring only when there are negative values
#         dataframe['above_0'] = dataframe[y].apply(lambda val: val if val > 0 else 0)
#         dataframe['below_0'] = dataframe[y].apply(lambda val: val if val < 0 else 0)
        
#         # Add the area for values above 0 (green) without a legend
#         fig.add_trace(go.Scatter(
#             x=dataframe['Date'],
#             y=dataframe['above_0'],
#             fill='tozeroy',
#             mode='none',  # No lines, just fill
#             fillcolor='rgba(61, 181, 105, 0.5)',
#             #line_color = 'black',
#             showlegend=False,  # Remove legend for Above 0
#         ))

#         # Add the area for values below 0 (red) without a legend
#         fig.add_trace(go.Scatter(
#             x=dataframe['Date'],
#             y=dataframe['below_0'],
#             fill='tozeroy',
#             mode='none',
#             #line_color='black',
#             fillcolor = 'rgba(255, 0, 0, 0.5)',
#             showlegend=False,  # Remove legend for Below 0
#         ))
    
#     else:
#         # If no negative values, use a black line with dark blue (50% transparency) area chart
#         fig.add_trace(go.Scatter(
#             x=dataframe['Date'],
#             y=dataframe[y],
#             fill='tozeroy',
#             mode='lines',  # Add line with area fill
#             line_color='black',  # Black line color
#             fillcolor='rgba(0, 0, 139, 0.5)',  # Dark blue with 50% transparency
#             showlegend=False  # No legend needed for the single color
#         ))

#     # Update layout for the figure
#     fig.update_layout(
#         yaxis_title=yaxis,
#         xaxis_title='Date',
#         title=title,
#         title_x=0.5,
#         margin={'l': 0, 'r': 35},
#         font=dict(family="Abel", size=15, color=colors['text']),
#         plot_bgcolor='white',
#     )

#     fig.update_xaxes(showgrid=False)
#     fig.update_yaxes(tickformat=".1" + str(tick))
#     fig.layout.plot_bgcolor = 'white'
    
#     # Conditional traces and other configurations
#     if pred == True:
#         fig.add_traces(
#             list(go.Scatter(x=dataframe['Date'], y=dataframe['Forward Return'], fill='tozeroy', fillcolor='skyblue').select_traces()))
#         fig.add_traces(
#             list(go.Scatter(x=dataframe['Date'], y=dataframe['SP Trailing 4 Weeks Return'], fill='tozeroy', fillcolor='red').select_traces()))
    
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
#         plot_bgcolor='white',
#         yaxis_gridcolor=COLORS['border'], 
#         xaxis_gridcolor=COLORS['border'], 
#         height=700
#     )

#     fig.update_xaxes(showgrid=True) 
#     fig.update_yaxes(showgrid=True)
#     fig.update_layout(uirevision='constant')

#     return fig


# descriptioneconomy = f''' An overview of the US economy. Source of data is FRED API and multpl.com. Latest update: {latestdate}'''


# layout = dbc.Container([
#     html.Div(children=[
#         html.H1("Economy Overview", className='headerfinvest'),
#         html.P(f"Latest update: {latestdate}", className='normal-text'),
#     ], className='page-intros'),

#     html.Div([
#         dcc.Loading(  # Wrap the output component with Loading
#             id="loading",
#             type="default",  # or "circle" or "dot" or "cube"
#             children=html.Div(id="update-output", style={'font-size': '11', 'color': 'gray'})
#         ),
#         html.Hr(),
#         # Flex container for graphs
#         html.Div([
#             # First Row of Graphs (up to 4)
#             html.Div([
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Inflation YoY', 'Inflation US YoY-Change %', economy, 'YoY', tick='%',
#                                         starts='1995-01-01', ends=str(datetime.today()), YoY=True),
#                     className='graph'
#                 ),
#             ], className='parent-row-economy'),

#             # Second Row of Graphs
#             html.Div([
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Money Supply M2', 'Money Supply US M2', economy, 'm2', tick=' ',
#                                         starts='1985-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Yield', '10-yr Treasury Yield %', economy, 'TenYield', tick='%',
#                                         starts='2010-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Shiller P/E Ratio', 'Shiller P/E Ratio', economy, 'Shiller_P/E',
#                                         tick=' ', starts='2000-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#             ], className='parent-row-economy'),

#             # Third Row of Graphs
#             html.Div([
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Unemployment Rate', 'Unemployment Rate US', economy, 'unemp_rate', tick='%',
#                                         starts='1985-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Interest to Income Ratio', 'Federal Interest Payments to Revenues Ratio', df,
#                                         'Interest to Income Ratio', tick='%', starts='1985-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#             ], className='parent-row-economy'),

#             # Fourth Row of Graphs
#             html.Div([
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'S&P 500 Index', 'S&P 500 Index', economy, 'Close', tick=' ',
#                                         starts='1985-01-01', ends=str(datetime.today())),
#                     className='graph'
#                 ),
#                 dcc.Graph(
#                     figure=create_graph(colors['accent'], 'Combined Economy Score', 'Combined Economy Score', economy, 'Combined Economy Score',
#                                         tick=' ', starts='2000-01-01', ends=str(datetime.today()), hline1=True, textbox=True, Score=True),
#                     className='graph'
#                 ),
#             ], className='parent-row-economy'),
#         ]), #className='parent-container2'),
#     ])
# ], className='container', fluid=True)

# @callback(
#     Output("update-output", "children"),
#     [Input("update-button", "n_clicks")]
# )
# def run_update(n_clicks):
#     if n_clicks is None:
#         return ""
#     else:
#         try:
#             economy = update_dropbox_dataset()
#             latestdate = str(pd.to_datetime(economy['Date']).dt.date.tail(1).values[0])
#             #'https://www.dropbox.com/scl/fi/zwcl7yhhlnk6nqg9j16r7/econW.csv?rlkey=1k0r4dnqxc4gmukgxphh0n591&dl=1'
#             economy['InflationExp'] = economy['InflationExp'] / 100
#             economy['unemp_rate'] = economy['unemp_rate'] / 100
#             economy['TenYield'] = economy['TenYield'] / 100
#             economy['Shiller_P/E'] = round(economy['Shiller_P/E'], 2)
#             economy['Combined Economy Score'] = round(economy['Combined Economy Score'], 2)
#             economy['Consumer Confidence'] = round(economy['ConsumerConfidence'], 2)
#             return f"Dataset updated successfully!"
#         except Exception as e:
#             return f"Error updating dataset: {e}"