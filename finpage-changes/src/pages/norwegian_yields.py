# import dash
# from dash import dcc, html
# from dash.dependencies import Input, Output
# import plotly.graph_objects as go
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# import matplotlib.dates as mdates
# import dash_bootstrap_components as dbc
# from dash import html, callback, Input, Output
# import requests
# import io
# import requests
# import pandas as pd



# dash.register_page(__name__, path='/norwegian_yield_curve')

# # The API URL
# url = "https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.7Y+6M+5Y+3Y+3M+12M+10Y.GBON+TBIL.?format=csv&startPeriod=2000-10-17&endPeriod=2024-10-17&locale=en"

# # Send a GET request to the API
# response = requests.get(url)

# # Check if the request was successful
# if response.status_code == 200:
#     # Load the CSV data into a pandas DataFrame
#     csv_data = response.content.decode('utf-8')
#     data = pd.read_csv(io.StringIO(csv_data), sep=';')

#     # Display the first few rows of the data
#     print(data.head())
# else:
#     print(f"Failed to retrieve data: {response.status_code}")

# data = data[['Tenor', 'TIME_PERIOD','OBS_VALUE']].rename(columns={'TIME_PERIOD':'Date', 'OBS_VALUE':'Yield'})

# import pandas as pd

# # Assuming your current dataframe is named 'data', with columns: 'Tenor', 'TIME_PERIOD', 'OBS_VALUE'
# # We'll pivot the dataframe to create a wide format where Tenor is in columns and TIME_PERIOD in the index.

# wide_df = data.pivot(index='Date', columns='Tenor', values='Yield').reset_index()

# norwegian_yields = wide_df[['Date', '3 months', '6 months', '12 months', '3 years', '5 years', '7 years', '10 years']]
# norwegian_yields.rename(columns={'3 months' : '3M', '6 months':'6M', '12 months': '1Y', '3 years' : '3Y', '5 years': '5Y', '7 years':'7Y', '10 years':'10Y'}, inplace=True)

# norwegian_labels = ['3M', '6M', '1Y', '3Y', '5Y', '7Y', '10Y']
# norwegian_yields['Date'] = pd.to_datetime(norwegian_yields['Date'])

# norwegian_yields.set_index('Date', inplace=True)

# # Drop rows with all NaN values and fill forward to ensure continuous data
# norwegian_yields.dropna(how='all', inplace=True)
# norwegian_yields.fillna(method='ffill', inplace=True)

# # Resample data to quarterly frequency and include the last observation
# yield_df_quarterly = norwegian_yields.resample('ME').last()

# # Update the last date's yield values to today's date
# today = pd.Timestamp(datetime.today().date())

# # Check if the last date is earlier than today
# if not yield_df_quarterly.index.empty and yield_df_quarterly.index[-1] > today:
#     last_yields = yield_df_quarterly.iloc[-1]
#     yield_df_quarterly.loc[today] = last_yields

# # If today's date already exists in the DataFrame, keep the values intact
# yield_df_quarterly.sort_index(inplace=True)  # Sort index to ensure correct date ordering

# norwegian_yields = yield_df_quarterly.iloc[:-1,:].copy()

# # Get the latest yields for the table
# last_yields = yield_df_quarterly.iloc[-1]

# # Create a static yield table
# static_table_content = [
#     html.Tr([html.Td('Maturity')] + [html.Td(maturity) for maturity in norwegian_labels]),  # Header row
#     html.Tr([html.Td('Yield (%)')] + [html.Td(f"{last_yields[i]:.2f}") for i in norwegian_labels])  # Yield values
# ]

# # Create the static yield table
# static_yield_table = html.Table(
#     static_table_content,
#     style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid black'},
# )

# # Add header for the yields
# yield_table_header = html.Div(f"Yields as of {today.date()}", style={'fontWeight': 'bold', 'marginBottom': '10px'})

# # Define the layout of the app
# layout =  html.Div([
#     html.H1("Norwegian Government Historical Yield Curve 3D Visualization"),

#     # Static yield table
#     html.Div([yield_table_header, static_yield_table], style={'padding': '10px', 'backgroundColor': '#f9f9f9', 
#                                                                'borderRadius': '5px', 'marginBottom': '20px'}),
    
#     # Date range picker
#     dcc.DatePickerRange(
#         id='date-picker-range-nor',
#         start_date=yield_df_quarterly.index.min().date(),  # Start date is the minimum in the data
#         end_date=datetime.today().date(),  # End date is today
#         display_format='YYYY-MM-DD',  # Format for displaying the date
#         style={'marginBottom': '20px'}
#     ),
    
#     dcc.Graph(id='yield-curve-3d-nor', config={'scrollZoom': True}, style={'height': '1000px'}),
# ])

# @callback(
#     Output('yield-curve-3d-nor', 'figure'),
#     [Input('date-picker-range-nor', 'start_date'),
#      Input('date-picker-range-nor', 'end_date')]
# )
# def update_graph(start_date, end_date):
#     # Filter the data based on selected date range
#     mask = (yield_df_quarterly.index >= start_date) & (yield_df_quarterly.index <= end_date)
#     filtered_data = yield_df_quarterly.loc[mask]
    
#     # Calculate the number of years in the selected date range
#     start_date = pd.to_datetime(start_date)
#     end_date = pd.to_datetime(end_date)
#     num_years = (end_date - start_date).days / 365.25
    
#     # Determine tick frequency based on the number of years
#     if num_years <= 1:
#         tick_freq = '3M'  # 4 ticks per year (quarterly)
#     elif 1 < num_years <= 5:
#         tick_freq = '6M'  # 2 ticks per year (semi-annually)
#     else:
#         tick_freq = '1Y'  # 1 tick per year (annually)
    
#     # Create the ticks based on the determined frequency
#     x_ticks = pd.date_range(start=start_date, end=end_date, freq=tick_freq).to_list()
    
#     # Include today's date in x_ticks if it isn't already
#     if today not in x_ticks:
#         x_ticks.append(today)

#     x_ticks = sorted(x_ticks)  # Sort to maintain order
#     x_tick_values = x_ticks #mdates.date2num(x_ticks)  # Convert to numerical format for plotting

#     def num_to_date(num):
#         return datetime.fromordinal(int(num)).strftime('%Y-%m-%d')
#     x_dates = [num_to_date(d) for d in mdates.date2num(filtered_data.index)]
#     customdata = np.array([[date] * filtered_data.shape[1] for date in x_dates])
#     # Create the 3D surface plot
#     fig = go.Figure(data=[go.Surface(
#         z=filtered_data.T.values,  # Use filtered quarterly data
#         x=filtered_data.index,#mdates.date2num(filtered_data.index),  # Convert dates for plotting
#         y=np.arange(len(norwegian_labels)), 
#         colorscale='GnBu',  # Color scale
#         colorbar_title='Yield (%)',
#         #hovertemplate= '<b>Date</b>: %{x}<br><b>Maturity</b>: %{y}<br><b>Yield (%)</b>: %{z:.2f}',  # Custom hover text
#         #customdata=customdata  # Provide date string in hovertemplate
#     )])

#     # Update layout for the 3D plot
#     fig.update_layout(
#         title=f"Norwegian Yield Curve (3M to 10Y) from {start_date.date()} to {end_date.date()}",
#         scene=dict(
#             xaxis_title=' ',
#             yaxis_title='Maturity',
#             zaxis_title='Yield (%)',
#             xaxis=dict(
#                 tickmode='array',
#                 tickvals=x_tick_values,  # Set the custom tick values
#                 ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],  # Formatted tick text
#                 backgroundcolor='white'  # Set background color to white
#             ),
#             yaxis=dict(
#                 tickvals=np.arange(len(norwegian_labels)), 
#                 ticktext=norwegian_labels,
#                 backgroundcolor='white'  # Set background color to white
#             ),
#             zaxis=dict(backgroundcolor='white')  # Set background color to white for z-axis
#         ),
#         scene_camera=dict(
#             eye=dict(x=1.25, y=1.25, z=1.25),  # Controls the 3D view
#             up=dict(x=0, y=0, z=1),
#             center=dict(x=0, y=0, z=0)
#         ),
#         margin=dict(l=0, r=0, b=10, t=40),
#         annotations=[
#             dict(
#                 text="Data Source: Norges Bank",
#                 x=0.0,
#                 y=0.1,
#                 align="right",
#                 xref="paper",
#                 yref="paper",
#                 showarrow=False
#             )
#         ]
#     )
#     fig.update_layout(showlegend=False)
#     fig.update_annotations(font=dict(family="Helvetica", size=12))
    
#     return fig
