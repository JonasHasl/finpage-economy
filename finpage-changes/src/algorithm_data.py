"""Data loading for the one-screen Algorithm dashboard (/algorithm-dashboard).

The return maths mirrors ``pages/algorithm.py`` so both pages report the same
numbers.  The difference is that the Yahoo Finance download -- by far the
slowest step -- is cached per (training window, currency), which keeps the
dashboard controls snappy after the first load.
"""

import threading
import time
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

from portfolio_history import build_combined_performance, get_training_dates
from workbook_store import get_workbook_path


CACHE_TTL_SECONDS = 15 * 60

_cache = {}
_cache_lock = threading.Lock()


def _series_on_dates(series, dates):
    values = pd.Series(series).dropna().sort_index()
    values.index = pd.DatetimeIndex(pd.to_datetime(values.index)).tz_localize(None)
    dates = pd.DatetimeIndex(pd.to_datetime(dates)).tz_localize(None)
    return values.reindex(values.index.union(dates).sort_values()).ffill().reindex(dates)


def _download_usd_nok_history(composition_sheet, end_date):
    training_start, _ = get_training_dates(composition_sheet)
    download_start = training_start - pd.offsets.MonthEnd(1) - pd.Timedelta(days=7)
    fx_data = yf.download(
        'NOK=X',
        start=download_start,
        end=pd.to_datetime(end_date) + pd.Timedelta(days=1),
        interval='1d',
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    fx_close = fx_data['Close']
    if isinstance(fx_close, pd.DataFrame):
        if 'NOK=X' in fx_close.columns:
            fx_close = fx_close['NOK=X']
        else:
            fx_close = fx_close.iloc[:, 0]
    return pd.Series(fx_close).dropna().sort_index()


def load_returns(composition_sheet='2020', currency='USD'):
    """Download prices and build daily portfolio / benchmark / per-symbol returns."""
    composition = pd.read_excel(get_workbook_path(), sheet_name=composition_sheet)
    composition['ValidFrom'] = pd.to_datetime(composition['ValidFrom'], dayfirst=False)
    composition['ValidTo'] = pd.to_datetime(composition['ValidTo'], dayfirst=False)

    min_date = composition['ValidFrom'].min()
    today = date.today()
    tickers = list(composition.Symbol.unique())

    df = yf.download(
        tickers + ['ACWI'],
        start=min_date,
        end=today,
        interval='1d',
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    portfolio_cols = [col for col in df['Close'].columns if col != 'ACWI']

    symbol_df = df['Close'][portfolio_cols].stack().reset_index()
    symbol_df.columns = ['Date', 'Symbol', 'Close']
    symbol_df['Date'] = pd.to_datetime(symbol_df['Date'])
    symbol_df = symbol_df.sort_values(['Symbol', 'Date']).reset_index(drop=True)
    symbol_df['Return'] = symbol_df.groupby('Symbol')['Close'].pct_change().fillna(0)

    names = composition[['Symbol', 'Company']].drop_duplicates()
    full_symbol_df = symbol_df.merge(names, on='Symbol', how='left')
    portfolio_df = full_symbol_df.copy()

    active_positions = []
    for _, row in composition.iterrows():
        mask = (
            (portfolio_df['Date'] >= row['ValidFrom']) &
            (portfolio_df['Date'] <= row['ValidTo']) &
            (portfolio_df['Symbol'] == row['Symbol'])
        )
        active = portfolio_df.loc[mask].copy()
        active['Weight'] = row.get('Weight', 1.0 / len(composition))
        active_positions.append(active)

    portfolio_df = pd.concat(active_positions, ignore_index=True)
    portfolio_df = portfolio_df.sort_values(['Date', 'Symbol']).reset_index(drop=True)
    portfolio_df = portfolio_df.drop_duplicates(['Date', 'Symbol'], keep='last')

    portfolio_returns = (
        (portfolio_df['Return'] * portfolio_df['Weight'])
        .groupby(portfolio_df['Date'])
        .sum()
        .rename('Portfolio_Return')
        .to_frame()
    )
    portfolio_returns.index = pd.to_datetime(portfolio_returns.index)
    portfolio_returns = portfolio_returns.sort_index()
    portfolio_returns['Portfolio_Return'] = portfolio_returns['Portfolio_Return'].round(8)

    acwi_levels = _series_on_dates(df['Close']['ACWI'], portfolio_returns.index)
    acwi_returns = acwi_levels.pct_change().fillna(0)

    fx_history = None
    if currency == 'NOK':
        fx_history = _download_usd_nok_history(composition_sheet, today)

        fx_returns = _series_on_dates(
            fx_history, portfolio_returns.index
        ).pct_change().fillna(0)
        portfolio_returns['Portfolio_Return'] = (
            (1 + portfolio_returns['Portfolio_Return']) * (1 + fx_returns) - 1
        )
        acwi_returns = (1 + acwi_returns) * (1 + fx_returns) - 1

        full_fx_dates = pd.DatetimeIndex(full_symbol_df['Date'].drop_duplicates().sort_values())
        full_fx_returns = _series_on_dates(
            fx_history, full_fx_dates
        ).pct_change().fillna(0)
        full_symbol_df['FX_Return'] = full_symbol_df['Date'].map(full_fx_returns)
        full_symbol_df['Return'] = (
            (1 + full_symbol_df['Return']) * (1 + full_symbol_df['FX_Return']) - 1
        )

    portfolio_returns['ACWI_Return'] = acwi_returns.round(8)

    return portfolio_returns, full_symbol_df, composition, fx_history


def ytd_return_by_symbol(full_symbol_df, year_start):
    """Year-to-date cumulative return per symbol in the frame's base currency."""
    ytd_source = full_symbol_df[full_symbol_df['Date'] >= year_start].copy()
    if ytd_source.empty:
        return pd.Series(dtype=float)

    ytd_source = ytd_source.sort_values(['Symbol', 'Date'])
    return ytd_source.groupby('Symbol')['Return'].apply(
        lambda s: (1 + s.fillna(0)).cumprod().iloc[-1] - 1 if len(s) else np.nan
    )


def _missing_symbols(composition, full_symbol_df):
    return set(composition['Symbol'].unique()) - set(full_symbol_df['Symbol'].unique())


def _build_bundle(composition_sheet, currency):
    portfolio_returns, full_symbol_df, composition, fx_history = load_returns(
        composition_sheet, currency
    )

    # Yahoo Finance occasionally drops a ticker from a batch download.  Retry
    # once; if the data is still incomplete the bundle is flagged so it is not
    # cached and the next interaction fetches a fresh copy.
    complete = not _missing_symbols(composition, full_symbol_df)
    if not complete:
        portfolio_returns, full_symbol_df, composition, fx_history = load_returns(
            composition_sheet, currency
        )
        complete = not _missing_symbols(composition, full_symbol_df)

    bundle = {
        'portfolio_returns': portfolio_returns,
        'full_symbol_df': full_symbol_df,
        'composition': composition,
        'combined_performance': None,
        'training_end': None,
        'today': None,
        'complete': complete,
    }
    if portfolio_returns.empty:
        return bundle

    combined_performance, training_end = build_combined_performance(
        composition_sheet,
        portfolio_returns,
        currency=currency,
        fx_close=fx_history,
    )
    bundle.update(
        combined_performance=combined_performance,
        training_end=training_end,
        today=portfolio_returns.index.max(),
    )
    return bundle


def get_dashboard_data(composition_sheet, currency):
    """Return the cached data bundle for a training window + currency.

    Failures and incomplete downloads are never cached, so a transient Yahoo
    Finance error does not stick for the whole TTL.  The workbook's mtime and
    size are part of the key, so a composition change (an algo-helper save, or
    a freshly downloaded GitHub copy) is picked up immediately instead of after
    the TTL.
    """
    workbook = get_workbook_path()
    stat = workbook.stat()
    key = (
        str(composition_sheet),
        str(currency),
        date.today().isoformat(),
        stat.st_mtime_ns,
        stat.st_size,
    )
    now = time.monotonic()

    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]

    bundle = _build_bundle(composition_sheet, currency)
    if not bundle['complete']:
        return bundle

    with _cache_lock:
        # Keep the dict small: drop expired entries, entries from earlier days,
        # and superseded versions of this sheet/currency (older workbook).
        def is_stale(cached_key, stamp):
            return (
                now - stamp >= CACHE_TTL_SECONDS
                or cached_key[2] != key[2]
                or (cached_key[:2] == key[:2] and cached_key != key)
            )

        for stale_key in [k for k, (stamp, _) in _cache.items() if is_stale(k, stamp)]:
            _cache.pop(stale_key, None)
        _cache[key] = (now, bundle)

    return bundle
