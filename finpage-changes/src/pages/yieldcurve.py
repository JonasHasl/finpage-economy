# import dash
# from dash import dcc, html
# from dash.dependencies import Input, Output
# import plotly.graph_objects as go
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# import matplotlib.dates as mdates
# from fredapi import Fred
# import dash
# import dash_bootstrap_components as dbc
# from dash import html, callback, Input, Output

# dash.register_page(__name__, path='/yield_curve')
# # Initialize FRED API
# FRED_API_KEY = '6188d31bebbdca093493a1077d095284'
# fred = Fred(FRED_API_KEY)

# # Define the observation period (e.g., last 10 years)
# observation_start = (datetime.today() - timedelta(days=20 * 365)).strftime('%Y-%m-%d')  # 10 years ago

# # List of maturities and their corresponding FRED series IDs
# maturity_labels = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y']
# series_ids = ['DGS1MO', 'DGS3MO', 'DGS6MO', 'DGS1', 'DGS2', 'DGS3', 'DGS5',
#               'DGS7', 'DGS10', 'DGS20', 'DGS30']

# # Fetch data for each series over the entire historical period
# yield_data = {}
# for series_id in series_ids:
#     yield_data[series_id] = fred.get_series(series_id, observation_start=observation_start)

# # Combine all series into a single DataFrame
# yield_df = pd.DataFrame(yield_data)
# yield_df.index = pd.to_datetime(yield_df.index)

# # Drop rows with all NaN values and fill forward to ensure continuous data
# yield_df.dropna(how='all', inplace=True)
# yield_df.fillna(method='ffill', inplace=True)

# # Resample data to quarterly frequency and include the last observation
# yield_df_quarterly = yield_df.resample('Q').last()

# # Update the last date's yield values to today's date
# today = pd.Timestamp(datetime.today().date())

# # Check if the last date is earlier than today
# if not yield_df_quarterly.index.empty and yield_df_quarterly.index[-1] > today:
#     last_yields = yield_df_quarterly.iloc[-1]
#     yield_df_quarterly.loc[today] = last_yields

# # If today's date already exists in the DataFrame, keep the values intact
# yield_df_quarterly.sort_index(inplace=True)  # Sort index to ensure correct date ordering

# # Create a Dash app
# #app = dash.Dash(__name__)

# # Initialize static yield table data
# last_yields = yield_df_quarterly.iloc[-1]  # Get the latest yields
# static_table_content = [
#     html.Tr([html.Td('Maturity')] + [html.Td(maturity) for maturity in maturity_labels]),  # Header row
#     html.Tr([html.Td('Yield (%)')] + [html.Td(f"{last_yields[i]:.2f}") for i in range(len(maturity_labels))])  # Yield values
# ]

# # Create the static yield table
# static_yield_table = html.Table(
#     static_table_content,
#     style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid black'},
# )

# # Add header for the yields
# yield_table_header = html.Div(f"Yields as of {today.date()}", style={'fontWeight': 'bold', 'marginBottom': '10px'})

# # Define the layout of the app
# layout = html.Div([
#     html.H1("Historical Yield Curve 3D Visualization"),

#     # Static yield table
#     html.Div([yield_table_header, static_yield_table], style={'padding': '10px', 'backgroundColor': '#f9f9f9', 
#                                                                'borderRadius': '5px', 'marginBottom': '20px'}),
    
#     # Date range picker
#     dcc.DatePickerRange(
#         id='date-picker-range',
#         start_date=yield_df_quarterly.index.min().date(),  # Start date is the minimum in the data
#         end_date=datetime.today().date(),  # End date is today
#         display_format='YYYY-MM-DD',  # Format for displaying the date
#         style={'marginBottom': '20px'}
#     ),
    
#     dcc.Graph(id='yield-curve-3d', config={'scrollZoom': True}, style={'height': '1000px'}),
# ])

# @callback(
#     Output('yield-curve-3d', 'figure'),
#     [Input('date-picker-range', 'start_date'),
#      Input('date-picker-range', 'end_date')]
# )
# def update_graph(start_date, end_date):
#     # Filter the data based on selected date range
#     mask = (yield_df_quarterly.index >= start_date) & (yield_df_quarterly.index <= end_date)
#     filtered_data = yield_df_quarterly.loc[mask]

#     # # Ensure today's date is included in the DataFrame if not already present
#     # today = pd.Timestamp(datetime.today().date())
#     # if today not in filtered_data.index:
#     #     last_yields = filtered_data.iloc[-1]
#     #     filtered_data.loc[today] = last_yields

#     # Create the 3D surface plot
#     fig = go.Figure(data=[go.Surface(
#         z=filtered_data.T.values,  # Use filtered quarterly data
#         x=mdates.date2num(filtered_data.index),  # Convert dates for plotting
#         y=np.arange(len(maturity_labels)), 
#         colorscale='GnBu',  # Color scale
#         colorbar_title='Yield (%)'
#     )])

#     # Create semi-annual ticks including today's date

#     # Calculate the number of years in the selected date range
#     start_date = pd.to_datetime(start_date)
#     end_date = pd.to_datetime(end_date)
#     num_years = (end_date - start_date).days / 365.25
    
#     # Determine tick frequency based on the number of years
#     if num_years <= 1:
#         tick_freq = '3M'  # 4 ticks per year (quarterly)
#     elif 1 < num_years <= 5:
#         tick_freq = '6M'  # 2 ticks per year (semi-annually)
#     elif 5 < num_years <= 20:
#         tick_freq = '1Y'  # 1 tick per year (annually)
#     else:
#         tick_freq = '5Y'
    
#     # Create the ticks based on the determined frequency
#     x_ticks = pd.date_range(start=start_date, end=end_date, freq=tick_freq).to_list()
#     #x_ticks = pd.date_range(start=start_date, end=end_date, freq='6M').to_list()
    
#     # Include today's date in x_ticks if it isn't already
#     if today not in x_ticks:
#         x_ticks.append(today)

#     x_ticks = sorted(x_ticks)  # Sort to maintain order
#     x_tick_values = mdates.date2num(x_ticks)  # Convert to numerical format for plotting

#     # Update layout for the 3D plot
#     fig.update_layout(
#         title=f"Yield Curve (1-month to 30-year) from {start_date} to {end_date}",
#         scene=dict(
#             xaxis_title=' ',
#             yaxis_title='Maturity',
#             zaxis_title='Yield (%)',
#             xaxis=dict(
#                 tickmode='array',
#                 tickvals=x_ticks,  # Set the custom tick values for semi-annually
#                 ticktext=[d.strftime('%Y-%m-%d') for d in x_ticks],  # Formatted tick text
#                 dtick=None,  # No automatic dtick, we use tickvals
#                 backgroundcolor='white'  # Set background color to white
#             ),
#             yaxis=dict(
#                 tickvals=np.arange(len(maturity_labels)), 
#                 ticktext=maturity_labels,
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
#                 text="Data Source: FRED - Federal Reserve Economic Data",
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
    
#     return fig  # Return the figure



# # Run the Dash app
# # import socket
# # from contextlib import closing

# # def find_free_port():
# #      with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
# #        s.bind(('', 0))
# #        return s.getsockname()[1]

# #if __name__ == '__main__':
# #    app.run_server(debug=True, port=find_free_port())