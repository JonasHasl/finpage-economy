import time
import os

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Change the current working directory to the script's directory
os.chdir(script_dir)

# Record the start time
start_time = time.time()

import pandas as pd
from matplotlib import pyplot
# from keras.models import Sequential
# from keras.layers import Dense
# from keras.layers import LSTM
# from tensorflow.keras import layers
# from tensorflow.keras.callbacks import ModelCheckpoint
# from tensorflow.keras.callbacks import EarlyStopping
# from tensorflow.keras.optimizers import SGD
# from keras.models import load_model
from numpy import array
from numpy import hstack
#import dropbox
import io
import pandas_datareader.data as web
import datetime
import numpy as np
import matplotlib.pyplot as plt
#from pandas_datareader import wb
import matplotlib.dates as mdates
import sys 
sys.version
from fredapi import Fred

FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
token = 'sl.u.AFjjQNO3MVo7z6zjW1yPvaECsPeQxJSSK-pSyNB_lzRRvhdAf_Yta04g4UhsGWFZ5yidFS81E_c472AdQU_KM4daRjA-eWqHjfBsG32cqClBFVYShrFURRkxooHaMTeA46TkX3147_SeIdYcfJHbfnPVwlk9MY4phWGjJc8zTLt3a0qNlyz-h_kAWYhQUJw2ik3QegCmhAUNW5qn9cTi8ba9HwF-R0aDv_GEcPoajRSvp9C-N59zrCiFuAKbPrvOXKItJGJ_YTY006Lpxo__oNE2kzTMOyIh9qnzDcIioxT0bJnGo7tA4-3to-tmeeILZyh1xMT-75mCDnNN54Ys9B6Bawmfyi5wp2DGvQlGZ5jgD5mux3fGdwezx75spblhHFf-ha5ZGKmzZWlIbGWx7zYwfxN9CDemMEZ1Y5-dQuWiyjTasM5cAr1C_uH9meriN7poaBMJr1wxQIs4Nuw1KTs4nq5Xp7mV2EY0yy6Rkk-ugiyYzcnswBTahsngnvDyJ0D6s_4fmfJRW8Zji3wotpYFzmuWrf2-fG-C8xXGqWXae9qBatS9FmyQNpuOAVP5Jjhp_6GvZz8np6lb-mMbnL_S1ieTKmb_aPFl01vlwfGw44OxY6ys741_MVCf2sl6q3q2HDuIb2P5NEAkDhpBNcMmoOJtRXqBudrhF7Oj9jEb1dZ47ZooFe2Rk21mk00j6MyHW7Ro4wblwSib3P-ZULQn6MwIPP4CTmyZxTfVHosgY9F2t9hmHlW9umQuw7LeC8riA_fw5Hk-PSqUhDio0KMRc-IujybUVXkcwaLXvAqYpBIq1H8T-YlJXNcnLF1rRne9kk8EZaStyY28Vsns8p5sNzHZAQ4mfD9U-hhIS05nlli7p2Go2uJx_QXIRUxCyeCzCHHMlsEHBh548N3evwVkXNDYImMx61lG-h8vjNqKK7VPKSkdSjV2FHzS4VWoGixIMGLgrY-d4PrQTGeiA5lwOsL4i7S4aokNxx8VN-9Ym8FHmkvu3fPvX2FQmLPBe9Pt1-mi66D3Q6j34YKz45NO3cg36gfyFlmKfkkkn8868HaBYyhh7tYVQJ2-iK7wAM7HoBugTLVPo1FPie6tXnn0m8W-B6PhrBps2ebSJHBHru7-HFrd2INlN0Rn7K1bqHvvthlTQoxGV2LbJb3Fk2ks9VnlJzUv7ZYAioRgQPvNfXvUU2xbJXwRfbmGVUXeeYtmCQToEUB7wi4A4OWAWjMhi6rO_w83gk6hGmIeymQ06nLl8SL-RJVSP78yLp5v_jWAvTX2KUJKyBYRXFSTeJ88EvRLw10UR-pF00Vpzo6fLA'

fred = Fred(FRED_API_KEY)

#%matplotlib inline
from IPython.core.pylabtools import figsize
from bs4 import BeautifulSoup as bs
import requests
import requests_html
from requests_html import HTMLSession
#from requests_html import AsyncHTMLSession
from requests import get
import itertools
import re
from scipy import signal
from fredapi import Fred
import yfinance as yf

#SP = yf.Ticker("^GSPC").history(period='max')


start = datetime.datetime(1980, 1, 1)
#end = datetime(2022, 5, 27)
end = datetime.datetime.now()
spread = web.DataReader('T10Y2Y', 'fred', start, end)
spread.reset_index(inplace=True)
#plt.plot(spread.DATE, spread.T10Y2Y.add(0))
spread.rename(columns={'DATE':'Date'}, inplace=True)
spread['Date']=pd.to_datetime(spread['Date'])

#spread = spread.resample('D', on="Date").min()
#.apply(lambda x : x.iloc[0])

#spread.rename(columns={'Date':'NotDate'}, inplace=True)
#spread.set_index('Date', inplace=True)
#spread.reset_index(inplace=True)
#spread = spread.drop('NotDate', axis=1)
#spread.tail(50)
spread.loc[spread['T10Y2Y'].rolling(window=153, min_periods=1).min() < 0, 'Inverted12months'] = 1
spread.loc[spread['T10Y2Y'].rolling(window=153, min_periods=1).min() > 0, 'Inverted12months'] = 0
    
SP = yf.Ticker("^GSPC").history(period='max').reset_index()
Stock = pd.DataFrame(SP[['Date', 'Close']]).copy()

Stock.reset_index(inplace=True)

Stock['Date'] = pd.to_datetime(Stock['Date'])

#Stock = Stock.resample('W-MON', on="Date").apply(lambda x : x.iloc[0])
#Stock
#Stock.rename(columns={'Date':'NotDate'}, inplace=True)
#Stock.set_index('Date', inplace=True)
#Stock.reset_index(inplace=True)
#Stock = Stock.drop('NotDate', axis=1)

Stock['SP Daily Return'] = Stock['Close'].pct_change()
Stock['SP Trailing 4 Weeks Return'] = Stock['SP Daily Return'].shift(1).rolling(21, min_periods=21).apply(lambda x: np.prod(1 + x) - 1).fillna(0)
Stock['SP Trailing 1 Week Return'] = Stock['SP Daily Return'].shift(1).rolling(7, min_periods=7).apply(lambda x: np.prod(1 + x) - 1).fillna(0)

#Stock['SP Daily Return'].apply(lambda x: np.prod(1 + x) - 1)
#.rolling
#.prod()#.cumprod()
#Stock
Stock.isnull().sum()

Stock['Cumulative Returns'] = (1 + Stock['SP Daily Return']).cumprod() - 1
Stock.rename(columns={'DATE':'Date'}, inplace=True)
completedates = pd.DataFrame(pd.date_range(start=start, end=datetime.datetime.now(), freq='B'), columns=['Date'])

#df = pd.read_excel('sample.xlsx')

#print(df)

release_dates = pd.read_excel('https://alfred.stlouisfed.org/release/downloaddates?rid=10&ff=xls',skiprows= range(1,36))['Release: Consumer Price Index'].copy()

release_dates = pd.to_datetime(release_dates)

release_dates = pd.DataFrame(release_dates)
release_dates.rename(columns={'Release: Consumer Price Index':'Release Date'}, inplace=True)

#import datetime
#import dateutil.relativedelta

#years_ago = datetime.datetime.now() - relativedelta(years=7)
release_dates['Date'] = release_dates['Release Date'] - pd.DateOffset(months=1)

#

#d = ("2013-03-31", "%Y-%m-%d")
release_dates['Date'] = release_dates['Date'].to_numpy().astype('datetime64[M]')
release_dates['Date'] = pd.to_datetime(release_dates['Date'])
FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
fred = Fred(FRED_API_KEY)

cpius = fred.get_series_all_releases('CPIAUCNS', realtime_start=start.date())

cpius = cpius.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')
cpius = cpius.sort_index()

cpius.reset_index(inplace= True)
cpius = cpius.drop_duplicates(subset='Date', keep='last')
# cpius = cpius.drop_duplicates('Date', keep='last')
cpius['MoM'] = cpius['value'].pct_change()
cpius['YoY'] = cpius['value'].pct_change(periods=12)
cpius['RollingMean12'] = cpius['value'].pct_change(periods=12).rolling(12, min_periods=1).mean()

#cpius.reset_index(inplace= True)
cpius['Date'] = pd.to_datetime(cpius['Date']) 

# cpius = cpius.merge(release_dates, on="Date")

# cpius = cpius.drop('Date', axis=1).rename(columns={'Release Date' : 'Date'}).set_index('Date')
# cpius.reset_index(inplace= True)
cpius.rename({'value':'CPIUS'}, axis=1, inplace=True)


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
tradebalance.rename({'MoM':'Trade Balance MoM'}, axis=1, inplace=True)
tradebalance.rename({'YoY':'Trade Balance YoY'}, axis=1, inplace=True)


    
#%matplotlib inline
#from requests_html import AsyncHTMLSession
figsize(20, 5)
pd.options.display.max_colwidth = 60

m2 = fred.get_series_all_releases('M2SL', realtime_start=start.date())
m2['date'] = pd.to_datetime(m2['date'])
m2['value'] = m2['value'].astype(float)
m2['m2_growth'] = m2['value'].pct_change(periods=12)
m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
meanvalues = pd.DataFrame(m2.groupby(['date'])['value'].mean()).rename(columns={'value':'meanvalue'}).drop_duplicates(subset='meanvalue', keep='first')

m2 = m2.merge(meanvalues, on='date', how='left').drop_duplicates(subset = ['date'],keep='first').copy()
m2['m2_growth'] = m2['value'].pct_change(periods=12)
m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
m2.tail(10)
m2 = m2.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

m2.reset_index(inplace= True)
m2 = m2.drop_duplicates('Date', keep='last')
m2['Date'] = pd.to_datetime(m2['Date'])
m2.rename(columns={'value':'m2'}, inplace=True)
    
#     # lei = fred.get_series_all_releases('USALOLITONOSTSAM')
#     # lei['date'] = pd.to_datetime(lei['date'])
#     # lei['value'] = lei['value'].astype(float)
#     # lei['lei_growth'] = lei['value'].pct_change(periods=12)
#     # lei['MoMGrowthChange'] = lei['lei_growth'].pct_change() # Theory: Effect on stock market is shown next month
#     # meanvalues = pd.DataFrame(lei.groupby(['date'])['value'].mean()).rename(columns={'value':'meanvalue'}).drop_duplicates(subset='meanvalue', keep='first')
    
#     # lei = lei.merge(meanvalues, on='date', how='left').drop_duplicates(subset = ['date'],keep='first').copy()
#     # lei['lei_growth'] = lei['value'].pct_change(periods=12)
#     # lei['MoMGrowthChange'] = lei['lei_growth'].pct_change() # Theory: Effect on stock market is shown next month
#     # lei.tail(10)
#     # lei = lei.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')
    
#     # lei.reset_index(inplace= True)
#     # lei =lei.drop_duplicates('Date', keep='last')
#     # lei['Date'] = pd.to_datetime(lei['Date'])
#     # lei.rename(columns={'value':'lei'}, inplace=True)
    
unemp = fred.get_series_all_releases('UNRATE', realtime_start=start.date())
unemp['date'] = pd.to_datetime(unemp['date'])
unemp['value'] = unemp['value'].astype(float)

unemp['unemp_growth'] = unemp['value'].pct_change()
#m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
meanvalues = pd.DataFrame(unemp.groupby(['date'])['value'].mean()).rename(columns={'value':'meanvalue'}).drop_duplicates(subset='meanvalue', keep='first')

unemp = unemp.merge(meanvalues, on='date', how='left').drop_duplicates(subset = ['date'],keep='first').copy()
#m2['m2_growth'] = m2['value'].pct_change(periods=12)
#m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
unemp.tail(10)
unemp = unemp.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

unemp.reset_index(inplace= True)
unemp = unemp.drop_duplicates('Date', keep='last')
unemp['Date'] = pd.to_datetime(unemp['Date'])
unemp.rename(columns={'value':'unemp_rate'}, inplace=True)
    
    
tenyearmin = yf.Ticker("^TNX").history(period='max')

#tenyearmin = web.DataReader('DGS10', 'fred', start=start, end=end)
tenyearmin = pd.DataFrame(tenyearmin['Close']).copy()

tenyearmin.reset_index(inplace=True)

tenyearmin['Date'] = pd.to_datetime(tenyearmin['Date'])

oneyearmin = yf.Ticker("^IRX").history(period='max')
#oneyearmin = web.DataReader('DGS1', 'fred', start=start, end=end)
oneyearmin = pd.DataFrame(oneyearmin['Close']).copy()

oneyearmin.reset_index(inplace=True)

oneyearmin['Date'] = pd.to_datetime(oneyearmin['Date'])

yieldmin = oneyearmin.merge(tenyearmin, on="Date")
yieldmin['spread'] = yieldmin['Close_y'] - yieldmin['Close_x']

yieldmin.rename(columns={'Close_x':'OneYearYield', 'Close_y':'TenYield'}, inplace=True)
yieldmin.fillna(0, inplace=True)
yieldmin.rename(columns={'DATE':'Date'}, inplace=True)

completedates = pd.DataFrame(pd.date_range(start=start, end=datetime.datetime.now(), freq='B'), columns=['Date'])

import numpy as np
from bs4 import BeautifulSoup as bs
import requests
import requests_html
from requests_html import HTMLSession
#from requests_html import AsyncHTMLSession
from requests import get
import itertools
import re
from scipy import signal
my_url = "https://www.multpl.com/shiller-pe/table/by-month"
session = HTMLSession()
response = session.get(my_url)
page_content = response.text
soup = bs(page_content, 'html.parser')


#soup.find_all("h2", string = re.compile("header"))
table = soup.select("table")[0]

#actual_values = [link['left'] for link in table]

columns = soup.find('th', class_="left")
#columns

table_rows = table.find_all("tr")
l = []
for tr in table_rows:
    td = tr.find_all('td')
    row = [str(tr.get_text()).strip() for tr in td]
    l.append(row) 
#print(table_rows)
l=list(itertools.chain(*l))
Dates = l[0::2]
Values = l[1::2]
shillers = pd.DataFrame(columns = [Dates, Values]).T.reset_index()
shillers.columns = ['Date', 'Value']
shillers['Date'] = pd.to_datetime(shillers['Date'], format='mixed')
shillers['Value'] = shillers['Value'].astype(float)

shiller = shillers


#shiller = pd.read_csv(r'C:\Users\jonas\OneDrive\Skrivebord\shillers.csv')
shiller['Date'] = pd.to_datetime(shiller['Date'],  format='mixed')
shiller.columns = ['Date', 'Shiller_P/E'] 

# consumer_credit = fred.get_series_all_releases('TOTLL') #Total Consumer Credit
# consumer_credit['date'] = pd.to_datetime(consumer_credit['date'])
# #lei.drop_duplicates(subset='date', keep='first', inplace=True)

# consumer_credit['value'] = consumer_credit['value'].astype(float)
# consumer_credit['consumer_credit_growth_yoy'] = consumer_credit['value'].pct_change(periods=12)
# consumer_credit['MoMGrowthChange'] = consumer_credit['consumer_credit_growth_yoy'].pct_change()
# consumer_credit
# meanvalues = pd.DataFrame(consumer_credit.groupby(['date'])['value'].mean()).rename(columns={'value':'meanvalue'}).drop_duplicates(subset='meanvalue', keep='first')

# consumer_credit = consumer_credit.merge(meanvalues, on='date', how='left').drop_duplicates(subset = ['date'],keep='first').copy()
# consumer_credit['consumer_credit_growth'] = consumer_credit['value'].pct_change(periods=12)
# consumer_credit['MoMGrowthChange'] = consumer_credit['consumer_credit_growth'].pct_change() # Theory: Effect on stock market is shown next month
# consumer_credit.tail(10)
# consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

# consumer_credit.reset_index(inplace= True)
# consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
# consumer_credit['Date'] = pd.to_datetime(consumer_credit['Date'])
# consumer_credit.rename(columns={'value':'consumer_credit_growth'}, inplace=True)
# consumer_credit
composite_confidence = fred.get_series_all_releases('CSCICP03USM665S', realtime_start=start.date()) 
composite_confidence['date'] = pd.to_datetime(composite_confidence['date'])
composite_confidence.drop_duplicates(subset='date', keep='first', inplace=True)
composite_confidence.head(20)
composite_confidence['adjusted_value'] = composite_confidence['value'].shift(2).astype(float)
composite_confidence['composite_confidence_growth_yoy'] = composite_confidence['adjusted_value'].pct_change(periods=12)
composite_confidence['MoMConfidence'] = composite_confidence['composite_confidence_growth_yoy'].pct_change()
composite_confidence

#consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

#
#consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
composite_confidence['date'] = pd.to_datetime(composite_confidence['date'])
composite_confidence.rename(columns={'date':'Date'}, inplace=True)

composite_confidence = composite_confidence.drop(['realtime_start', 'value'], axis=1).set_index('Date').reset_index()
#consumer_credit.reset_index(inplace= True)
composite_confidence['RollingComp'] = composite_confidence.adjusted_value.rolling(12).mean()
composite_confidence

inflation_exp = fred.get_series_all_releases('MICH', realtime_start=start.date()) #Total Consumer Credit
inflation_exp['date'] = pd.to_datetime(inflation_exp['date'])
inflation_exp.drop_duplicates(subset='date', keep='first', inplace=True)
inflation_exp.head(20)
inflation_exp['adjusted_value'] = inflation_exp['value'].shift(2).astype(float)
inflation_exp['inflation_exp_yoy'] = inflation_exp['adjusted_value'].pct_change(periods=12)
inflation_exp['MoMInflationExp'] = inflation_exp['inflation_exp_yoy'].pct_change()
inflation_exp

#consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

#consumer_credit.reset_index(inplace= True)
#consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
inflation_exp['date'] = pd.to_datetime(inflation_exp['date'])
inflation_exp.rename(columns={'date':'Date'}, inplace=True)

inflation_exp = inflation_exp.drop(['realtime_start', 'value', 'adjusted_value'], axis=1).set_index('Date').reset_index()
inflation_exp['RollingExpInfl'] = inflation_exp.inflation_exp_yoy.rolling(12).mean()
inflation_exp

consumer_confidence = fred.get_series_all_releases('UMCSENT', realtime_start=start.date()) #Total Consumer Credit
consumer_confidence.dropna(inplace=True)
consumer_confidence['date'] = pd.to_datetime(consumer_confidence['date'])
consumer_confidence.drop_duplicates(subset='date', keep='first', inplace=True)
consumer_confidence.head(20)
consumer_confidence['adjusted_value'] = consumer_confidence['value'].shift(2).astype(float)
consumer_confidence['consumer_conf_yoy'] = consumer_confidence['adjusted_value'].pct_change(periods=12)
consumer_confidence['MoMConsumerConf'] = consumer_confidence['consumer_conf_yoy'].pct_change()
consumer_confidence

#consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

#consumer_credit.reset_index(inplace= True)
#consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
consumer_confidence['date'] = pd.to_datetime(consumer_confidence['date'])
consumer_confidence.rename(columns={'date':'Date'}, inplace=True)

consumer_confidence = consumer_confidence.drop(['realtime_start', 'value', 'adjusted_value'], axis=1).set_index('Date').reset_index()
consumer_confidence['RollingConsConf'] = consumer_confidence.consumer_conf_yoy.rolling(12).mean()
consumer_confidence

import_end = time.time()

# Calculate the elapsed time
elapsed_time = import_end - start_time
print(f"Elapsed time imports: {elapsed_time:.2f} seconds")

# df = fred.search('ism')
# #TOTALNS# ( Consumer Credit)
# #TOTLL # Loans and leases
# #CCLACBW027SBOGc
# #PAYEMS (NON FARM PAYROLL)
# # UMCSENT ( Consumer Confidence)
# # MICH (Inflation Expectations)
# # CSCICP03USM665S ( Composite Confidence Indicatiors) , two previous best

# df.iloc[0,3]
# df

# housing = fred.get_series_all_releases('HSN1F') #Total Consumer Credit
# housing.dropna(inplace=True)
# housing['date'] = pd.to_datetime(housing['date'])

# housing.drop_duplicates(subset='date', keep='first', inplace=True)
# housing['adjusted_value'] = housing['value'].shift(2).astype(float)
# housing['housing_yoy'] = housing['adjusted_value'].pct_change(periods=12)
# housing['MoMRetail'] = housing['housing_yoy'].pct_change()
# housing

# #consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

# #consumer_credit.reset_index(inplace= True)
# #consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
# housing['date'] = pd.to_datetime(housing['date'])
# housing.rename(columns={'date':'Date'}, inplace=True)

# housing = housing.drop(['realtime_start', 'value', 'adjusted_value'], axis=1).set_index('Date').reset_index()
# housing['RollingHousing'] = housing.housing_yoy.rolling(12).mean()


# claims = fred.get_series_all_releases('CFSBCACTIVITYNMFG') #Total Consumer Credit
# claims.dropna(inplace=True)

# claims = fred.get_series_all_releases('CFSBCACTIVITYNMFG') #Total Consumer Credit
# claims.dropna(inplace=True)
# claims['date'] = pd.to_datetime(claims['date'])

# claims.drop_duplicates(subset='date', keep='first', inplace=True)
# claims['adjusted_value'] = claims['value'].shift(2).astype(float)
# claims['housing_yoy'] = claims['adjusted_value'].pct_change(periods=12)
# claims['MoMRetail'] = claims['housing_yoy'].pct_change()
# claims

# #consumer_credit = consumer_credit.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

# #consumer_credit.reset_index(inplace= True)
# #consumer_credit =consumer_credit.drop_duplicates('Date', keep='last')
# claims['date'] = pd.to_datetime(claims['date'])
# claims.rename(columns={'date':'Date'}, inplace=True)

# claims = claims.drop(['realtime_start', 'value', 'adjusted_value'], axis=1).set_index('Date').reset_index()
# claims['RollingHousing'] = claims.housing_yoy.rolling(12).mean()
# claims
# claims = fred.get_series_all_releases('ICSA')
# claims.dropna(inplace=True)
# claims['date'] = pd.to_datetime(claims['date'])
# claims['value'] = claims['value'].astype(float)

# claims['claims_growth'] = claims['value'].pct_change()
# claims['claims_yoy'] = claims['value'].pct_change(periods=12)
# #m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
# meanvalues = pd.DataFrame(claims.groupby(['date'])['value'].mean()).rename(columns={'value':'meanvalue'}).drop_duplicates(subset='meanvalue', keep='first')

# claims = claims.merge(meanvalues, on='date', how='left').drop_duplicates(subset = ['date'],keep='first').copy()
# #m2['m2_growth'] = m2['value'].pct_change(periods=12)
# #m2['MoMGrowthChange'] = m2['m2_growth'].pct_change() # Theory: Effect on stock market is shown next month
# claims.tail(10)
# claims = claims.drop('date', axis=1).rename(columns={'realtime_start' : 'Date'}).set_index('Date')

# claims.reset_index(inplace= True)
# claims = claims.drop_duplicates('Date', keep='last')
# claims['Date'] = pd.to_datetime(claims['Date'])
# claims.rename(columns={'value':'claims'}, inplace=True)
# claims

import pytz

time_zone = 'America/New_York'
dfs = [completedates, Stock, cpius, m2, yieldmin, unemp, spread, shiller, consumer_confidence, inflation_exp, composite_confidence, tradebalance]
for df in dfs:
    #df = df.reset_index()
    for col in df.columns:
        if col == "Date":
            df[col] = pd.to_datetime(df[col])

            # extract just the date component
            df[col] = df[col].dt.date
            #df[col] = df[col].Date
            

    


econ = completedates.merge(Stock, on='Date', how='left').merge(cpius, on='Date', how='left').merge(m2, on='Date', how='left').merge(yieldmin, on='Date', how='left').merge(unemp, on='Date', how='left').merge(spread, on='Date', how='left').merge(shiller, on='Date', how='left').merge(consumer_confidence, on='Date', how='left').merge(inflation_exp, on='Date', how='left').merge(composite_confidence, on='Date', how='left').merge(tradebalance, on='Date', how='left').ffill()
#.apply(lambda x : x.iloc[0]).head(32)
econ.reset_index(inplace=True)



econ['real_yield'] = econ['TenYield'] - (econ['YoY']*100)
#plt.plot(econ.Date, econ.real_yield)

from scipy import signal

econ = econ.dropna(axis=0).copy()
detrended = signal.detrend(econ.m2)

detrended_df = pd.DataFrame(detrended)


econ['detrendedm2'] = detrended
#econ['M2Detrend'] = econ.detrendedm2.diff(252)
#econ['CPIDeviation'] = abs(econ['CPIDetrend'] - econ['CPIDetrend'].mean())

#plt.plot(econ['Date'], econ['m2'].apply(np.log).diff(252).rolling(120).mean())
econ['mom2diff'] = econ['m2'].apply(np.log).diff(252).diff(252).rolling(1).mean()

#def calc_MDD(Stock):
df = pd.Series(econ['TenYield'], name="nw").to_frame()

min_peaks_idx = df.nw.expanding(min_periods=1).apply(lambda x: x.argmin()).fillna(0).astype(int)
df['max_peaks_idx'] = pd.Series(min_peaks_idx).to_frame()

min_peaks = pd.Series(df.nw.iloc[min_peaks_idx.values].values, index=df.nw.index)

df['dd'] = ((df.nw-min_peaks)/min_peaks)
df['maxtightening'] = df.groupby('max_peaks_idx').dd.apply(lambda x: x.expanding(min_periods=1).apply(lambda y: y.max())).fillna(0).reset_index(drop=True)

#  return df

econ['maxtight'] = df['maxtightening']

econ['TenYieldNorm'] = econ.TenYield.rolling(window=104).mean().copy()
econ['TenYieldNorm'] =(((econ['TenYieldNorm']  -
econ['TenYieldNorm'] .min()) /
(econ['TenYieldNorm'] .max() -
econ['TenYieldNorm'] .min())) * 100).copy()

from scipy import signal

econ = econ.ffill().dropna(axis=0).copy()
detrended = signal.detrend(econ.TenYieldNorm)

detrended_df = pd.DataFrame(detrended)
econ['detrendedyield'] = detrended
plt.plot(econ['Date'], econ.detrendedyield.add(200).apply(np.log))
plt.plot(econ['Date'], econ.detrendedyield)

econ['Shiller_P/E']

detrended = signal.detrend(econ['Shiller_P/E'])

detrended_df = pd.DataFrame(detrended)


econ['detrendedshiller'] = detrended


            
        # .add(200).apply(np.log))
        
econ.loc[econ['detrendedshiller'] >= 0, 'ShillerOver'] = econ['detrendedshiller']
econ.loc[econ['detrendedshiller'] < 0, 'ShillerOver'] = 0

plt.plot(econ['Date'], econ['detrendedshiller'])

econ['CPIDetrend'] = econ['YoY'].rolling(window=104).mean().diff()
econ['CPIDeviation'] = abs(econ['CPIDetrend'] - econ['CPIDetrend'].mean())
econ['CPIGoalDev'] = abs(econ['CPIDetrend'] - 0.02) 

#plt.plot(econ['Date'],)

#plt.plot(econ['Date'], econ['CPIGoalDev'])

econ['CPIDev'] = econ['YoY'].rolling(window=104).max()

econ.loc[econ['CPIDev'] >= 0.02, 'CPIOver'] = econ['CPIDev']
econ.loc[econ['CPIDev'] < 0.02, 'CPIOver'] = 0.02

#scoreddf.loc[scoreddf['Combined Economy Score'] < 28, 'Long-Short'] = -1
#scoreddf.loc[scoreddf['Combined Economy Score'] >= 28, 'Long-Short'] = 1

#plt.plot(econ['Date'], econ['CPIOver'])
# =============================================================================
#         plt.plot(econ.Date, econ['spread'].rolling(window=104).mean().diff(50))
# 
#         plt.plot(econ.Date, econ['YoY'].rolling(window=20).max())
# =============================================================================

scoreddf = econ[['Date', 'Shiller_P/E', 'detrendedshiller', 'ShillerOver', 'SP Daily Return', 'YoY', 'MoM', 'spread', 'm2', 'CPIOver', 'unemp_rate', 'unemp_growth', 'CPIDeviation', 'mom2diff', 'TenYield', 'real_yield', 'Inverted12months', 'Close', 'T10Y2Y', 'detrendedyield']].copy()
#scoreddf = scoreddf[scoreddf['Date'] > '2000-01-01'].copy()

#scoreddf['DeviationCPI'] = abs(scoreddf['YoYCPI']-0.02)

scoreddf['rollingtight'] = scoreddf['detrendedyield'].rank(method= "average",ascending=False)
#scoreddf['rollingtight'] = scoreddf['maxtight'].rolling(window=52).max().pct_change(periods=52).astype(float).rank(method= "average",ascending=False)
scoreddf['UnempScore'] = scoreddf['unemp_rate'].astype(float).rank(method= "average",ascending=False)# pct=True).copy()*100
scoreddf['Yield%Score'] = scoreddf['real_yield'].astype(float).astype(float).rank(method= "average",ascending=False)#, pct=True).copy()*100
scoreddf['SPReturn'] = scoreddf['SP Daily Return'].shift().astype(float).astype(float).rank(method= "average",ascending=True)#, pct=True).copy()*100
scoreddf['Rolling CPI'] = scoreddf['YoY'].astype(float).astype(float).rank(method= "average",ascending=False)#, pct=True).copy()*100
scoreddf['MoMCPI'] = scoreddf['MoM'].rolling(100).mean().astype(float).astype(float).rank(method= "average",ascending=False)#, pct=True).copy()*100
scoreddf['MoMM2'] = scoreddf['mom2diff'].astype(float).astype(float).rank(method= "average",ascending=True)#", pct=True).copy()*100
#scoreddf['maxtightscore'] = scoreddf['maxtight'].astype(float).astype(float).rank(method= "average",ascending=False)#", pct=True).copy()*100
#scoreddf['spreadscore'] = scoreddf['spread'].rolling(window=104).mean().diff().astype(float).rank(method= "average",ascending=True)#", pct=True).copy()*100
scoreddf['CPIDevScore'] = scoreddf['YoY'].rolling(window=20).max().astype(float).rank(method= "average",ascending=False)#", pct=True).copy()*100
scoreddf['CPIOverScore'] = scoreddf['CPIOver'].astype(float).rank(method= "average",ascending=False)#", pct=True).copy()*100
scoreddf['realspread'] =  scoreddf['T10Y2Y'].rank(method= "average",ascending=True)#", pct=True).copy()*100
#scoreddf['shillerscore'] =  scoreddf['Shiller_P/E'].apply(np.log).diff(10).rolling(126).mean().rank(method= "average",ascending=True)#", pct=True).copy()*100
scoreddf['shillerscoreBear'] =  scoreddf['ShillerOver'].rank(method= "average",ascending=False)



scoreddf['Combined Economy Score'] = (scoreddf['UnempScore']*15  +
                                            scoreddf['Yield%Score']*222  +
                                            #scoreddf['SPReturn'] * 2+
                                            scoreddf['Rolling CPI']*400 +
                                            #scoreddf['MoMCPI'] * 100 +
                                            scoreddf['MoMM2']*100  +
                                            scoreddf['rollingtight']*295+
                                            #scoreddf['spreadscore']*100 +
                                            scoreddf['CPIDevScore']*600+
                                            scoreddf['CPIOverScore']*0+
                                            scoreddf['shillerscoreBear']*0)



                                        
scoreddf['Combined Economy Score'] = (
(scoreddf['Combined Economy Score'] -
scoreddf['Combined Economy Score'].min()) /
(scoreddf['Combined Economy Score'].max() -
scoreddf['Combined Economy Score'].min())) * 100


finalscores = scoreddf[['Date', 'Combined Economy Score', 'Inverted12months', 'Close', 'SP Daily Return', 'rollingtight', 'UnempScore']].copy()

# 75 % percentile 283
# 25 % percentile 224

finalscores.head()
#scoreddf.tail(50)

#def calc_MDD(Stock):
df = pd.Series(finalscores['Close'], name="nw").to_frame()

max_peaks_idx = df.nw.expanding(min_periods=1).apply(lambda x: x.argmax()).fillna(0).astype(int)
df['max_peaks_idx'] = pd.Series(max_peaks_idx).to_frame()

nw_peaks = pd.Series(df.nw.iloc[max_peaks_idx.values].values, index=df.nw.index)

df['dd'] = ((df.nw-nw_peaks)/nw_peaks)
df['mdd'] = df.groupby('max_peaks_idx').dd.apply(lambda x: x.expanding(min_periods=1).apply(lambda y: y.min())).fillna(0).reset_index(drop=True)

#  return df

df

finalscores['maxdrawdown'] = df['mdd'].astype(float)

finalscores.loc[finalscores['maxdrawdown'] > -0.2 , 'BearMarket'] = 0
finalscores.loc[finalscores['maxdrawdown'] <= -0.2 , 'BearMarket'] = 1
#plt.plot(finalscores.Date, finalscores.maxdrawdown)#

finalscores['Rolling Bear'] = finalscores.loc[:,'BearMarket'].rolling(58).max().copy()

#finalscores['InvertandBear'] = finalscores['Rolling Bear']*finalscores['Inverted12months']

#finalscores['InvertandBear'] = finalscores['InvertandBear'].copy().fillna(0)
finalscores['InvertandBearFinal'] = finalscores['Inverted12months'] #- finalscores['InvertandBear']



finalscores = finalscores[['Date', 'Combined Economy Score', 'InvertandBearFinal', 'Inverted12months']].dropna().copy()



scoreddf['CumReturns'] = ((1+scoreddf.Close.pct_change()).cumprod()-1)*100

import numpy as np
from numpy.lib.stride_tricks import as_strided
import pandas as pd
import matplotlib.pyplot as plt


def max_dd(ser):
    #df['a'].cummax()
    max2here = ser.cummax()#pd.expanding_max(ser)
    dd2here = ser - max2here
    return dd2here.min()


s = scoreddf['CumReturns']
window_length = 15

#df['low'].rolling(2).apply(add_percentage_diff)
rolling_dd = s.rolling(window_length, min_periods=0).apply(max_dd)
#pd.rolling_apply(s, window_length, max_dd, min_periods=0)
df = pd.concat([s, rolling_dd], axis=1)
df.columns = ['s', 'rol_dd_%d' % window_length]
# =============================================================================
#         df.plot(linewidth=3, alpha=0.4)
#         #my_rmdd = rolling_max_dd(s.values, window_length, min_periods=1)
#         #plt.plot(my_rmdd, 'g.')
#         plt.show()
# =============================================================================

finalscores['rollingdrawdown'] = rolling_dd

#returns = -((1+df['Returns']).cumprod() -1).iloc[-1]

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
def max_dd(ser):
    #max2here = ser.cummax()
    max2here = ser.expanding().max()
    #max2here = pd.expanding_max(ser)
    dd2here = ser - max2here
    return dd2here.min()
    

#Let's set up a brief series to play with to try it out:


np.random.seed(0)
n = 100
#s = pd.Series(np.random.randn(n).cumsum())
s=scoreddf['Close']
#rolling_dd = s.rolling(s, 10, max_dd, min_periods=0)
def calc_rolling_drawdown(s, window):
    rolling_dd = s.rolling(window, min_periods=0).apply(max_dd)
    df = pd.concat([s, rolling_dd], axis=1)
    df.columns = ['s', 'rol_dd_10']
    #df.plot()

    df['SP'] = econ['Close']

    df['Drawdown%'] = (df['rol_dd_10'] / df['SP'].rolling(window).max())*100
    econ['Drawdown% ' + str(window)] = df['Drawdown%']
    return econ

calc_rolling_drawdown(s, 2)
calc_rolling_drawdown(s, 7)
calc_rolling_drawdown(s, 66)
calc_rolling_drawdown(s, 132)
calc_rolling_drawdown(s, 252)

econ['Forward Return'] = econ['SP Trailing 4 Weeks Return'].shift(-22)
econ.loc[econ['Forward Return'] >= 0, 'positive_ret'] = 1
econ.loc[econ['Forward Return'] < 0, 'positive_ret'] = 0
number_lags = 10
for lag in range(1, number_lags + 1):
    econ['Forward lag_' + str(lag)] = econ['Forward Return'].shift(lag)

econ[['Forward lag_1', 'Forward lag_2', 'Forward lag_3', 'Forward lag_4',
'Forward lag_5', 'Forward lag_6', 'Forward lag_7', 'Forward lag_8',
'Forward lag_9', 'Forward lag_10']] = econ[['Forward lag_1', 'Forward lag_2', 'Forward lag_3', 'Forward lag_4',
'Forward lag_5', 'Forward lag_6', 'Forward lag_7', 'Forward lag_8',
'Forward lag_9', 'Forward lag_10']].copy().fillna(0)
econ = econ.drop_duplicates(subset=['CPIUS', 'MoM',
        'YoY', 'm2', 'm2_growth', 'MoMGrowthChange', 'unemp_rate',
        'unemp_growth', 'consumer_conf_yoy', 'MoMConsumerConf',
        'RollingConsConf', 'inflation_exp_yoy', 'MoMInflationExp', 'composite_confidence_growth_yoy',
        'MoMConfidence', 'mom2diff', 'ShillerOver', 'CPIDeviation', 'CPIGoalDev', 'CPIDev', 'CPIOver', 'Trade Balance'])
econ.tail(22)
econ.Date = pd.to_datetime(econ['Date'])

econ.set_index('Date', inplace=True)
econW = econ#.resample('W-FRI').last()
# data = econW[['Forward Return' , 'Close', 'SP Trailing 4 Weeks Return', 'MoMGrowthChange', 'unemp_rate', 'T10Y2Y', 'mom2diff', 'maxtight', 'ShillerOver', 'CPIDev', 'CPIOver', 'detrendedyield' , 'Drawdown% 252', 'Drawdown% 132', 'Drawdown% 66', 'Drawdown% 7', 'RollingConsConf', 'RollingExpInfl']].dropna(how='all', axis=0).fillna(0).copy()
# dataX = data.copy().drop(['Forward Return'],axis=1)
# dataX.head()
# testDataX = dataX
# testDataX.head()
# testDataY = data['Forward Return'].copy()
# testDataY.head()
# from sklearn import preprocessing as pp

# featuresToScale = dataX.columns

# sX = pp.StandardScaler(copy=True, with_mean=True, with_std=True)
# dataX.loc[:,featuresToScale] = sX.fit_transform(dataX[featuresToScale])
# featuresToScale = testDataX.columns
# testDataX.loc[:,featuresToScale] = sX.fit_transform(testDataX[featuresToScale])
# testDataX.head()

# def anomalyScores(originalDF, reducedDF):
#     loss = np.sum((np.array(originalDF) - \
#                     np.array(reducedDF))**2, axis=1)
#     loss = pd.Series(data=loss,index=originalDF.index)
#     loss = (loss-np.min(loss))/(np.max(loss)-np.min(loss))
    
#     print('Mean for anomaly scores: ', np.mean(loss))
    
#     return loss
# import tensorflow as tf
# from tensorflow import keras

# from tensorflow.keras import backend as K
# from tensorflow.keras.models import Sequential, Model
# from tensorflow.keras.layers import Activation, Dense, Dropout
# from tensorflow.keras.layers import BatchNormalization, Input, Lambda
# from tensorflow.keras import regularizers
# from tensorflow.keras.losses import mse, binary_crossentropy

# # Call neural network API
# model = Sequential()

# # Apply linear activation function to input layer
# # Generate hidden layer with 14 nodes, the same as the input layer
# model.add(Dense(units=len(dataX.columns), activation='linear',input_dim=len(dataX.columns)))
# model.add(Dense(units=14, activation='linear'))
# model.add(Dense(units=len(dataX.columns), activation='linear'))
# #model.add(Dropout=0.1)

# # Apply linear activation function to hidden layer
# # Generate output layer with 14 nodes
# model.add(Dense(units=len(dataX.columns), activation='linear'))
# # Compile the model
# model.compile(optimizer='adam',
#                 loss='mean_squared_error',
#                 metrics=['accuracy'])
# # Train the model
# num_epochs = 10
# batch_size = 256

# history = model.fit(x=dataX, y=dataX,
#                     epochs=num_epochs,
#                     batch_size=batch_size,
#                     shuffle=True,
#                     validation_data=(dataX, dataX),
#                     verbose=1)
# # Evaluate on test set
# predictions = model.predict(dataX, verbose=1)
# anomalyScoresAE = anomalyScores(dataX, predictions)


# anomaly = anomalyScoresAE.reset_index()

# anomaly.columns=['Date', 'Reconstruction Error']
# econW = econW.dropna(how='all', axis=0)
# econW['Anomaly'] = anomaly.set_index('Date')
# econW

econW.rename(columns={'inflation_exp_yoy':'InflationExp', 'consumer_conf_yoy':'ConsumerConfidence'}, inplace=True)
print(econW.columns)
econW.InflationExp

#econW['Combined Score']
#econW['Combined Score'] = finalscores['Combined Economy Score']
finalscores.Date = pd.to_datetime(finalscores.Date)
econW = econW.reset_index().merge(finalscores[['Date', 'Combined Economy Score']], on='Date')
econW.sort_values('Date', ascending=True)


#econW.to_csv(r'C:\Users\jonas\OneDrive\Skrivebord\App\econW.csv')
#econW.to_csv(r'C:\Users\jonas\Dropbox\econW.csv')

econW.to_csv(r'econW.csv')


import os.path
# Update google drive part::
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def updateEcon(file_id):
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("drive", "v3", credentials=creds)

        #file_id = "YOUR_FILE_ID_HERE"  # Replace with the actual file ID

        media = MediaFileUpload('econW.csv', mimetype='text/csv', resumable=True)

        updated_file = service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()

        print(f'Updated econW.csv with ID: {updated_file.get("id")}')

    except HttpError as error:
        print(f"An error occurred: {error}")





updateEcon(file_id='1J47a0_lyfhRzcYlniXUKE-5yVKNbWX6j')


# update_dropbox_dataset()

# Record the end time
end_time = time.time()

# Calculate the elapsed time
elapsed_time = end_time - start_time
print(f"econW updated in: {elapsed_time:.2f} seconds")

