import pandas as pd
import datetime
import yfinance as yf
import numpy as np
from pandas_datareader import data as web
from fredapi import Fred
from bs4 import BeautifulSoup as bs
from requests_html import HTMLSession

# --- CONFIGURATION ---
FRED_API_KEY = '29f9bb6865c0b3be320b44a846d539ea'
fred = Fred(FRED_API_KEY)
oldecon_path = r"econW_updated.csv"
updated_path = r"econW_updated.csv"

# --- UTILITY FUNCTIONS ---
def load_existing_data(path):
    """Load existing dataset with conflict detection and date parsing."""
    import os
    if not os.path.exists(path):
        print(f"No existing data at {path}. Starting fresh.")
        return pd.DataFrame()  # Empty DataFrame
    
    df = pd.read_csv(path).reset_index(drop=True)
    
    # Detect and remove Git conflict rows
    conflict_mask = df['Date'].astype(str).str.contains(r'<<<<<<<|=======|>>>>>>>', na=False, regex=True)
    if conflict_mask.any():
        print(f"Warning: Found {conflict_mask.sum()} Git conflict rows in {path}. Removing them.")
        df = df[~conflict_mask].copy()
    
    # Parse dates with coercion
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
    
    if df.empty:
        print("No valid dates after cleaning. Starting fresh.")
    
    return df


def get_new_dates(existing_df):
    """Determine date range for incremental update"""
    max_date = existing_df['Date'].max()
    start = max_date + pd.Timedelta(days=1)
    end = datetime.datetime.now()
    return start, end

def ensure_naive_dates(dfs):
    """Convert all Date columns to timezone-naive datetime"""
    for df in dfs:
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    return dfs


# --- DATA FETCHING FUNCTIONS (RAW DATA ONLY) ---
def fetch_spread(start, end):
    """10Y-2Y Treasury Spread"""
    df = web.DataReader('T10Y2Y', 'fred', start, end).reset_index()
    return df.rename(columns={'DATE': 'Date'})[['Date', 'T10Y2Y']]

def fetch_yahoo(ticker, name):
    series = yf.Ticker(ticker).history(period='max').reset_index()
    return series[['Date', 'Close']].rename(columns={'Close': name})

def fetch_fred_series(series_id, start, name):
    """Generic FRED Series Fetcher"""
    df = fred.get_series_all_releases(series_id, realtime_start=start.date())
    return (df.rename(columns={'date': 'Date', 'value': name})
            .drop('realtime_start', axis=1)
            .drop_duplicates('Date'))


def fetch_shiller_pe():
    """Shiller P/E Ratio from multpl.com"""
    session = HTMLSession()
    response = session.get("https://www.multpl.com/shiller-pe/table/by-month")
    soup = bs(response.text, 'html.parser')
    
    data = []
    for tr in soup.select("table")[0].find_all("tr"):
        td = tr.find_all('td')
        if len(td) == 2:
            data.append([
                pd.to_datetime(td[0].get_text().strip(), errors='coerce'),
                float(td[1].get_text().strip().replace(',', ''))
            ])
    
    return pd.DataFrame(data, columns=['Date', 'Shiller_PE']).dropna()


# --- MAIN WORKFLOW ---
def updateEcon(reload='incremental', start_full='1998-12-26'):
    # 1. Load existing data
    print("Reload mode:", reload)
    oldecon = load_existing_data(oldecon_path)
    
    # 2. Determine date range for update
    start, end = get_new_dates(oldecon)

    if reload == 'full':
        start = pd.to_datetime(start_full)
        end = datetime.datetime.now()
    
    max_date = oldecon['Date'].max().date()
    print(max_date)
    print(datetime.datetime.now().date())
    print("Reload mode:", reload)
    if max_date == datetime.datetime.now().date() and reload == 'incremental':
        print("No new data to fetch. Existing data is up-to-date.")
        combined = oldecon
        combined.columns = oldecon.columns.str.lower().str.replace(' ', '_')
        return combined
    print(f"Fetching new data from {start.date()} to {end.date()}")
    
    # 3. Fetch all new raw data
    new_data = {
        'spread': fetch_fred_series('T10Y2Y',start, 'T10Y2Y'),
        'Close': fetch_yahoo('^GSPC', "Close"),
        'TenYield': fetch_yahoo('^TNX', "TenYield"),
        'CPIUS': fetch_fred_series('CPIAUCSL', start, 'CPIUS'),
        'm2': fetch_fred_series('M2SL', start, 'm2'),
        'unemp_rate': fetch_fred_series('UNRATE', start, 'unemp_rate'),
        'Trade Balance': fetch_fred_series('BOPGSTB', start, 'Trade Balance'),
        'Shiller_PE': fetch_shiller_pe()
    }

    # 4. Create complete date index
    date_range = pd.date_range(start=start, end=end, freq='D')
    combined = pd.DataFrame({'Date': date_range})

    # 5. Merge all datasets
    combined = pd.DataFrame({'Date': date_range})

    # Convert all Date columns to naive datetime first
    new_data = ensure_naive_dates(list(new_data.values()))  # Convert new data
    oldecon = ensure_naive_dates([oldecon])[0]  # Convert existing data

    for df in new_data:
        if not df.empty:
            combined = combined.merge(df, on='Date', how='left')

    # 6. Combine with historical data
    if reload == 'incremental':
        combined = pd.concat([oldecon, combined], ignore_index=True)
    else:
        combined = combined
    combined = combined.drop_duplicates('Date').sort_values('Date')

    # 7. Perform all calculations
    combined.ffill(inplace=True)  # Forward fill to handle NaNs
    combined = calculate_metrics(combined)
    if reload == 'full':
        combined = combined[combined['Date'] >= '2000-01-01']  # Filter for full reload
    combined.to_csv(updated_path, index=False)
    #combined.columns = combined.columns.str.lower().str.replace(' ', '_')
    # 8. Save updated data
    
    print(f"Update complete. New shape: {combined.shape}")
    combineddone = combined.copy()
    return combineddone

# --- CALCULATION ENGINE ---
def calculate_metrics(df):
    """Post-merge calculations with full historical context"""
    # Yield curve calculations
    df['Inverted12months'] = (df['T10Y2Y']
                             .rolling(153, min_periods=1)
                             .min() < 0).astype(int)
    
    # Stock market calculations
    df['SP Daily Return'] = df['Close'].pct_change()
    df['Cumulative Returns'] = (1 + df['SP Daily Return']).cumprod() - 1
    

    df['Trade Balance MoM'] = (df['Trade Balance'] - df['Trade Balance'].shift(1).fillna(0)) / df['Trade Balance'].shift(1).abs().replace(0, np.nan)
    df['Trade Balance YoY'] = (df['Trade Balance'] - df['Trade Balance'].shift(12).fillna(0)) / df['Trade Balance'].shift(12).abs().replace(0, np.nan)

    # Replace problematic values (inf, -inf, NaN) with 0
    df['Trade Balance MoM'] = df['Trade Balance MoM'].replace([np.inf, -np.inf, np.nan], 0)
    df['Trade Balance YoY'] = df['Trade Balance YoY'].replace([np.inf, -np.inf, np.nan], 0)

    # Replace inf and -inf with 0
    df['Trade Balance MoM'] = df['Trade Balance MoM'].replace([float('inf'), float('-inf')], 0)
    df['Trade Balance YoY'] = df['Trade Balance YoY'].replace([float('inf'), float('-inf')], 0)


    df['Trade Balance Rolling 12'] = df['Trade Balance'].pct_change(periods=12).rolling(12, min_periods=1).mean()
    # Economic calculations
    df['Real_Yield'] = df['T10Y2Y'] - (df['CPIUS'].pct_change(12) * 100)
    def get_yoy_shift(date):
        try:
            return date.replace(year=date.year - 1)
        except ValueError:
            return date.replace(year=date.year - 1, day=28)
    
    df['prev_date'] = df['Date'].apply(get_yoy_shift)
    cpi_shifted = df[['Date', 'CPIUS']].rename(columns={'Date':'prev_date', 'CPIUS':'CPIUS_prev'})
    df = df.merge(cpi_shifted, on='prev_date', how='left', suffixes=('', '_prev'))
    
    df['CPI YoY'] = (df['CPIUS'] / df['CPIUS_prev'].fillna(method='ffill')) - 1
    df.drop(['prev_date', 'CPIUS_prev'], axis=1, inplace=True)
    #df.ffill(inplace=True)  # Forward fill to handle NaNs
    return df

if __name__ == "__main__":
    combined = updateEcon(reload='full')