"""Indicator definitions, formatting and data access for the Economy dashboard.

Everything the dashboard page needs that is not layout: which indicators each
market shows (copied from the classic ``pages/useconomy.py`` so both pages stay
in step), how values and changes are written, how a date range becomes a
window, and how data is loaded.  There are no Dash imports here, so it can be
tested without an app or the network.
"""

from __future__ import annotations

import functools
import math
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

import data_sources as ds


# --------------------------------------------------------------------------
# Indicator specs
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Kpi:
    """One headline number: the latest observation of a series."""

    label: str
    key: str
    source: str
    kind: str = 'pct'          # 'pct' -> 4.12%   |  'num1' -> 40.9
    tick: str = '%'            # unit used to describe the change since the prior reading
    period: str | None = None  # 'month' | 'quarter' | None (inferred from the dates)
    short: str | None = None   # label for very small cards; ``label`` is used when absent


@dataclass(frozen=True)
class Chart:
    """One time-series tile."""

    key: str
    title: str
    short: str                 # header text on a small tile; ``title`` is the tooltip
    axis: str                  # what the axis measures
    tick: str                  # '%', 'bps', 'usd_tn', 'usd_bn', 'ratio', 'fx', 'index'
    source: str
    color: str                 # name in theme.LIGHT_THEME
    period: str | None = None
    zero_line: bool = False
    step: bool = False         # policy rates change in steps, so draw them as such


@dataclass(frozen=True)
class Market:
    key: str
    label: str
    kpis: tuple[Kpi, ...]
    charts: tuple[Chart, ...]
    notes: tuple[str, ...] = ()
    has_country_detail: bool = False


US = Market(
    key='us',
    label='US',
    kpis=(
        Kpi('10Y Yield', 'bondYield10y', 'FRED'),
        Kpi('Unemployment', 'unemployment', 'FRED'),
        Kpi('CPI YoY', 'cpiYoY', 'FRED'),
        Kpi('Real GDP YoY', 'gdpYoY', 'FRED', period='quarter'),
        Kpi('Shiller CAPE', 'shillerPE', 'multpl.com', kind='num1', tick='ratio'),
    ),
    charts=(
        Chart('bondYield10y', 'U.S. 10-Year Treasury Yield', '10Y Treasury yield', 'Percent per annum', '%', 'FRED', 'amber'),
        Chart('shillerPE', 'S&P 500 Shiller CAPE', 'Shiller CAPE', 'Cyclically adjusted P/E (×)', 'ratio', 'multpl.com', 'green'),
        Chart('stockIndex', 'S&P 500', 'S&P 500', 'Index level', 'index', 'Yahoo Finance', 'blue'),
        Chart('cpiYoY', 'U.S. CPI Inflation', 'CPI inflation', 'Year-over-year change', '%', 'FRED', 'red', period='month'),
        Chart('interestToRevenue', 'Federal Interest Payments / Current Receipts', 'Interest / receipts', '% of federal current receipts, quarterly SAAR', '%', 'FRED', 'rose', period='quarter'),
        Chart('moneySupply', 'U.S. M2 Money Stock', 'M2 money stock', 'USD trillions, seasonally adjusted', 'usd_tn', 'FRED', 'cyan', period='month'),
        Chart('spread10y2y', 'U.S. 10Y–2Y Treasury Curve', '10Y–2Y curve', 'Basis points', 'bps', 'FRED', 'violet', zero_line=True),
        Chart('unemployment', 'U.S. Unemployment Rate', 'Unemployment', '% of civilian labor force, SA', '%', 'FRED', 'cyan', period='month'),
        Chart('tradeBalance', 'U.S. Trade Balance', 'Trade balance', 'USD billions, seasonally adjusted, monthly', 'usd_bn', 'FRED', 'blue', period='month', zero_line=True),
        Chart('gdpYoY', 'U.S. Real GDP Growth', 'Real GDP growth', 'Year-over-year change, quarterly', '%', 'FRED', 'green', period='quarter', zero_line=True),
    ),
    notes=(
        'Rates, inflation, labour, money and trade come from FRED; the S&P 500 from Yahoo Finance; the Shiller CAPE from multpl.com.',
        "CPI is shown year over year (the Fed's formal 2% target uses PCE, not CPI).",
    ),
)

NORWAY = Market(
    key='norway',
    label='Norway',
    kpis=(
        Kpi('10Y Yield', 'bondYield10y', 'Norges Bank'),
        Kpi('Policy Rate', 'policyRate', 'Norges Bank'),
        Kpi('CPI YoY', 'cpiYoY', 'SSB'),
        Kpi('GDP YoY', 'gdpYoY', 'SSB'),
        Kpi('Unemployment', 'unemployment', 'SSB'),
    ),
    charts=(
        Chart('stockIndex', 'OSEBX', 'OSEBX', 'Index level', 'index', 'Yahoo Finance', 'blue'),
        Chart('bondYield10y', 'Norway 10Y Government Bond Yield', '10Y government yield', 'Percent per annum', '%', 'Norges Bank', 'amber'),
        Chart('policyRate', 'Norges Bank Policy Rate', 'Policy rate', 'Percent per annum', '%', 'Norges Bank', 'violet', step=True),
        Chart('spread10y3y', 'Norway 10Y–3Y Yield-Curve Slope', '10Y–3Y slope', 'Basis points', 'bps', 'Norges Bank', 'green', zero_line=True),
        Chart('cpiYoY', 'Norway CPI Inflation', 'CPI inflation', 'Year-over-year change', '%', 'SSB', 'red', period='month'),
        Chart('gdpYoY', 'Norway Real GDP Growth', 'Real GDP growth', 'Year-over-year change, monthly', '%', 'SSB', 'green', period='month', zero_line=True),
        Chart('unemployment', 'Norway Unemployment Rate', 'Unemployment', '% of labor force, SA', '%', 'SSB', 'cyan', period='month'),
        Chart('usdFx', 'USD / NOK', 'USD / NOK', 'NOK per USD', 'fx', 'Norges Bank', 'amber'),
        Chart('eurFx', 'EUR / NOK', 'EUR / NOK', 'NOK per EUR', 'fx', 'Norges Bank', 'green'),
    ),
    notes=(
        'Rates and exchange rates come from Norges Bank; inflation, GDP and unemployment from Statistics Norway (SSB); the OSEBX from Yahoo Finance.',
        'GDP growth is a monthly year-over-year figure and can swing sharply from one month to the next.',
    ),
)

EURO_AREA = Market(
    key='eu',
    label='Euro Area',
    kpis=(
        Kpi('AAA 10Y Spot Rate', 'bondYield10y', 'ECB'),
        Kpi('Deposit Facility Rate', 'policyRate', 'ECB'),
        Kpi('HICP YoY', 'cpiYoY', 'Eurostat'),
        Kpi('Real GDP YoY', 'gdpYoY', 'Eurostat', period='quarter'),
        Kpi('Unemployment', 'unemployment', 'Eurostat'),
    ),
    charts=(
        Chart('bondYield10y', 'Euro Area AAA 10Y Zero-Coupon Spot Rate', 'AAA 10Y spot rate', 'Percent per annum', '%', 'ECB', 'amber'),
        Chart('policyRate', 'ECB Deposit Facility Rate', 'Deposit facility rate', 'Percent per annum', '%', 'ECB', 'violet', step=True),
        Chart('cpiYoY', 'Euro Area HICP Inflation', 'HICP inflation', 'Year-over-year change', '%', 'Eurostat · changing composition', 'red', period='month'),
        Chart('gdpYoY', 'Euro Area Real GDP Growth', 'Real GDP growth', 'Year-over-year change, quarterly', '%', 'Eurostat · changing composition', 'green', period='quarter', zero_line=True),
        Chart('stockIndex', 'Euro Stoxx 50', 'Euro Stoxx 50', 'Index level', 'index', 'Yahoo Finance', 'blue'),
        Chart('unemployment', 'Euro Area Unemployment Rate', 'Unemployment', '% of labor force, SA', '%', 'Eurostat EA21', 'cyan', period='month'),
    ),
    notes=(
        'Rates come from the ECB; inflation, GDP and unemployment from Eurostat (the euro-area composition changes over time); the Euro Stoxx 50 from Yahoo Finance.',
        'The country panel uses FRED series for Germany, France, Italy and Spain.',
    ),
    has_country_detail=True,
)

UK = Market(
    key='uk',
    label='UK',
    kpis=(
        Kpi('10Y Gilt Yield', 'bondYield10y', 'Bank of England'),
        Kpi('CPI YoY', 'cpiYoY', 'ONS'),
        Kpi('Real GDP YoY', 'gdpYoY', 'ONS', period='quarter'),
        Kpi('Unemployment', 'unemployment', 'ONS'),
    ),
    charts=(
        Chart('stockIndex', 'FTSE 100', 'FTSE 100', 'Index level', 'index', 'Yahoo Finance', 'blue'),
        Chart('bondYield10y', 'UK 10Y Nominal Par Gilt Yield', '10Y gilt yield', 'Percent per annum', '%', 'Bank of England', 'amber'),
        Chart('cpiYoY', 'UK CPI Inflation', 'CPI inflation', 'Year-over-year change', '%', 'ONS', 'red', period='month'),
        Chart('gdpYoY', 'UK Real GDP Growth', 'Real GDP growth', 'Year-over-year change, quarterly', '%', 'ONS', 'green', period='quarter', zero_line=True),
        Chart('unemployment', 'UK Unemployment Rate', 'Unemployment', '% of labor force, SA', '%', 'ONS', 'cyan', period='month'),
    ),
    notes=(
        'Gilt yields come from the Bank of England; inflation, GDP and unemployment from the ONS; the FTSE 100 from Yahoo Finance.',
    ),
)

MARKETS: dict[str, Market] = {m.key: m for m in (US, NORWAY, EURO_AREA, UK)}

# Euro-area country panel (stats + stock index for one country).
EU_DETAIL_KPIS = (
    Kpi('10Y Government Yield', 'bondYield10y', 'FRED', short='10Y yield'),
    Kpi('HICP YoY', 'cpiYoY', 'FRED'),
    Kpi('Real GDP YoY', 'gdpYoY', 'FRED', period='quarter'),
    Kpi('Unemployment Rate', 'unemployment', 'FRED', short='Unemployment'),
)
EU_DETAIL_CHART_COLOR = 'green'

# Comparison view: four metrics, each compared across the same four economies.
COMPARISON_COUNTRIES = (
    # key, selector label, short code, colour name in theme.LIGHT_THEME
    ('us', 'US', 'US', 'blue'),
    ('eu', 'Euro Area', 'EA', 'green'),
    ('uk', 'UK', 'UK', 'amber'),
    ('norway', 'Norway', 'NO', 'red'),
)


@dataclass(frozen=True)
class ComparisonMetric:
    key: str
    label: str                 # KPI card label
    title: str                 # chart title
    axis: str
    source: str
    periods: dict[str, str | None] | str | None = None


COMPARISON_METRICS = (
    ComparisonMetric(
        'gdpYoY', 'Real GDP YoY', 'Real GDP Growth', 'Year-over-year change', 'FRED, Eurostat, ONS, SSB',
        {'us': 'quarter', 'eu': 'quarter', 'uk': 'quarter', 'norway': 'month'},
    ),
    ComparisonMetric('cpiYoY', 'Inflation YoY', 'Consumer-Price Inflation', 'Year-over-year change', 'FRED, Eurostat, ONS, SSB', 'month'),
    ComparisonMetric('bondYield10y', '10Y Yield', '10Y Sovereign / AAA Benchmark Yield', 'Percent per annum', 'FRED, ECB, Bank of England, Norges Bank'),
    ComparisonMetric('unemployment', 'Unemployment', 'Unemployment Rate', '% of labor force, SA', 'FRED, Eurostat, ONS, SSB', 'month'),
)

COMPARISON_NOTES = (
    'Actual published observations within the selected date window; frequencies and latest dates vary by country.',
    'Euro Area yield is the ECB AAA 10Y spot rate; the others are 10Y government benchmark yields.',
)

# The classic page starts "All available" in 2000.
FIRST_DATE = date(2000, 1, 1)
RANGE_OPTIONS = (('ytd', 'YTD'), ('5y', '5Y'), ('full', 'All available'))


# --------------------------------------------------------------------------
# Windows and series hygiene
# --------------------------------------------------------------------------

def resolve_window(range_key, today=None):
    """Start and end dates for the "YTD" / "5Y" / "All available" selector."""
    today = today or date.today()
    if range_key == 'ytd':
        return date(today.year, 1, 1), today
    if range_key == '5y':
        # DateOffset keeps 29 Feb valid by landing on 28 Feb of the earlier year.
        return (pd.Timestamp(today) - pd.DateOffset(years=5)).date(), today
    return FIRST_DATE, today


def clean_series(frame):
    """A tidy Date/value frame: numeric, de-duplicated, ascending, no gaps."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=['Date', 'value'])
    if 'Date' not in frame.columns or 'value' not in frame.columns:
        return pd.DataFrame(columns=['Date', 'value'])
    tidy = frame[['Date', 'value']].copy()
    tidy['Date'] = pd.to_datetime(tidy['Date'], errors='coerce')
    tidy['value'] = pd.to_numeric(tidy['value'], errors='coerce')
    return (
        tidy.dropna(subset=['Date', 'value'])
        # A stable sort, so "keep the last" below means the last one in the source.
        .sort_values('Date', kind='stable')
        .drop_duplicates('Date', keep='last')
        .reset_index(drop=True)
    )


def clip_series(frame, start, end, carry_in=False):
    """The observations inside [start, end].

    ``carry_in`` is for step series that only list the dates a value changed (policy
    rates): the value in force at ``start`` is then prepended as a point dated
    ``start``, with the date it began in a ``since`` column, so a window opening
    between two changes does not look as if the series began at the first change
    inside it.
    """
    tidy = clean_series(frame)
    if tidy.empty:
        return tidy
    begin = pd.Timestamp(start)
    inside = tidy.loc[(tidy['Date'] >= begin) & (tidy['Date'] <= pd.Timestamp(end))].reset_index(drop=True)
    if carry_in and not inside.empty and inside['Date'].iloc[0] > begin:
        before = tidy.loc[tidy['Date'] < begin]
        if not before.empty:
            held = pd.DataFrame({
                'Date': [begin],
                'value': [before['value'].iloc[-1]],
                'since': [before['Date'].iloc[-1]],
            })
            inside = pd.concat([held, inside], ignore_index=True)
    return inside


def series_state(frame, start, end):
    """Why a chart may have nothing to draw: 'ok', 'unavailable' (the source
    returned no observations at all) or 'out_of_range' (it has some, but none
    inside the selected window)."""
    tidy = clean_series(frame)
    if tidy.empty:
        return 'unavailable'
    if clip_series(tidy, start, end).empty:
        return 'out_of_range'
    return 'ok'


# --------------------------------------------------------------------------
# Formatting (mirrors pages/useconomy.py so the two pages read identically)
# --------------------------------------------------------------------------

MINUS = '−'


def format_observation_date(value, period=None):
    """Format an observation date without implying false day-level precision."""
    timestamp = pd.Timestamp(value)
    if period == 'quarter':
        return f'Q{timestamp.quarter} {timestamp.year}'
    if period == 'month':
        return timestamp.strftime('%b %Y')
    return timestamp.strftime('%d %b %Y')


def format_observation_value(value, tick):
    """A full-precision value for tooltips and tile headers."""
    if tick == '%':
        return f'{value:.2%}'.replace('-', MINUS, 1)
    if tick == 'bps':
        return f'{value:,.0f} bp'.replace('-', MINUS, 1)
    if tick == 'usd_tn':
        sign = MINUS if value < 0 else ''
        return f'{sign}${abs(value):,.2f}tn'
    if tick == 'usd_bn':
        sign = MINUS if value < 0 else ''
        return f'{sign}${abs(value):,.1f}bn'
    if tick == 'ratio':
        return f'{value:,.1f}×'.replace('-', MINUS, 1)
    if tick == 'fx':
        return f'{value:,.4f}'.replace('-', MINUS, 1)
    return f'{value:,.2f}'.replace('-', MINUS, 1)


def fmt_pct(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return '—'
    return f'{value:.2%}'


def fmt_num(value, decimals=2):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return '—'
    return f'{value:.{decimals}f}'


def infer_observation_period(frame):
    """'month' / 'quarter' for first-of-month series, otherwise None (daily)."""
    tidy = clean_series(frame)
    dates = tidy['Date'].drop_duplicates()
    if len(dates) < 2:
        return None
    if (dates.dt.day == 1).all():
        month_numbers = dates.dt.year * 12 + dates.dt.month
        median_step = month_numbers.diff().dropna().median()
        if median_step <= 2:
            return 'month'
        if median_step <= 4:
            return 'quarter'
    return None


def source_as_of(source, frame, period=None):
    """'FRED · Sep 2026': the source with the date of its latest observation."""
    tidy = clean_series(frame)
    if tidy.empty:
        return source
    inferred = period or infer_observation_period(tidy)
    return f"{source} · {format_observation_date(tidy['Date'].iloc[-1], inferred)}"


# A change smaller than this (in the unit shown) is reported as unchanged.
_FLAT_THRESHOLD = {'pp': 0.005, 'bp': 0.5, '×': 0.05, 'tn': 0.005, 'bn': 0.05, '%': 0.005}


def describe_change(latest, previous, tick):
    """The move from the previous to the latest reading, as (text, direction).

    Rates move in percentage points, spreads in basis points, index levels and
    exchange rates in percent.  ``direction`` is 'up', 'down' or 'flat'; it is
    deliberately not coloured good or bad because that depends on the series.
    """
    if latest is None or previous is None or pd.isna(latest) or pd.isna(previous):
        return None, None

    if tick == '%':
        delta, unit, decimals = (latest - previous) * 100, 'pp', 2
    elif tick == 'bps':
        delta, unit, decimals = latest - previous, 'bp', 0
    elif tick == 'ratio':
        delta, unit, decimals = latest - previous, '×', 1
    elif tick == 'usd_tn':
        delta, unit, decimals = latest - previous, 'tn', 2
    elif tick == 'usd_bn':
        delta, unit, decimals = latest - previous, 'bn', 1
    elif tick in ('index', 'fx'):
        if previous == 0:
            return None, None
        delta, unit, decimals = (latest / previous - 1) * 100, '%', 2
    else:
        delta, unit, decimals = latest - previous, '', 2

    if abs(delta) < _FLAT_THRESHOLD.get(unit, 0.005):
        return 'unchanged', 'flat'

    arrow, direction = ('▲', 'up') if delta > 0 else ('▼', 'down')
    magnitude = f'{abs(delta):,.{decimals}f}'
    prefix = '$' if tick in ('usd_tn', 'usd_bn') else ''
    spacer = ' ' if unit in ('pp', 'bp') else ''
    return f'{arrow} {prefix}{magnitude}{spacer}{unit}', direction


@dataclass(frozen=True)
class Snapshot:
    """What a KPI card shows."""

    label: str
    value_text: str
    delta_text: str | None
    delta_direction: str | None
    as_of: str
    has_data: bool


def snapshot(kpi, frame):
    tidy = clean_series(frame)
    if tidy.empty:
        return Snapshot(kpi.label, '—', None, None, kpi.source, False)

    latest = float(tidy['value'].iloc[-1])
    previous = float(tidy['value'].iloc[-2]) if len(tidy) > 1 else None
    value_text = fmt_pct(latest) if kpi.kind == 'pct' else fmt_num(latest, 1)
    delta_text, direction = describe_change(latest, previous, kpi.tick)
    return Snapshot(
        kpi.label,
        value_text,
        delta_text,
        direction,
        source_as_of(kpi.source, tidy, kpi.period),
        True,
    )


def latest_observation(frame):
    """(value, date) of the newest observation, or (None, None)."""
    tidy = clean_series(frame)
    if tidy.empty:
        return None, None
    return float(tidy['value'].iloc[-1]), tidy['Date'].iloc[-1]


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------

_LEGACY_CACHE_PATH = Path(__file__).resolve().parent / 'econW_updated.csv'


def _fallback_series(dataframe, column, scale=1.0):
    if dataframe.empty or column not in dataframe.columns:
        return pd.DataFrame(columns=['Date', 'value'])
    frame = dataframe[['Date', column]].rename(columns={column: 'value'}).copy()
    frame['Date'] = pd.to_datetime(frame['Date'])
    frame['value'] = pd.to_numeric(frame['value'], errors='coerce') * scale
    frame = frame.dropna(subset=['Date', 'value']).sort_values('Date')
    # The legacy cache is daily and forward-filled.  Keep only the change
    # dates so a monthly fallback does not pretend its last observation
    # happened today.
    return frame.loc[frame['value'].ne(frame['value'].shift())].reset_index(drop=True)


@functools.lru_cache(maxsize=2)
def _read_legacy_cache(path, modified):
    return pd.read_csv(path, parse_dates=['Date'])


def cached_us_fallback(path=None):
    """US series rebuilt from the bundled CSV, for when a live source is empty."""
    path = Path(path or _LEGACY_CACHE_PATH)
    try:
        cached = _read_legacy_cache(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return {}
    return {
        'bondYield10y': _fallback_series(cached, 'TenYield', 0.01),
        'stockIndex': _fallback_series(cached, 'Close'),
        'cpiYoY': _fallback_series(cached, 'CPI YoY'),
        'moneySupply': _fallback_series(cached, 'm2', 0.001),
        'spread10y2y': _fallback_series(cached, 'T10Y2Y', 100.0),
        'unemployment': _fallback_series(cached, 'unemp_rate', 0.01),
        'tradeBalance': _fallback_series(cached, 'Trade Balance', 0.001),
        'shillerPE': _fallback_series(cached, 'Shiller_PE'),
    }


def load_market(market, force=False):
    """Frames for one market; the US view backfills empty series from the CSV."""
    loaded = ds.get_market_data(market, force=force) or {}
    if market != 'us':
        return loaded

    fallback = cached_us_fallback()
    merged = {}
    for key in set(loaded) | set(fallback):
        frame = loaded.get(key)
        if frame is None or (isinstance(frame, pd.DataFrame) and frame.empty):
            frame = fallback.get(key, pd.DataFrame(columns=['Date', 'value']))
        merged[key] = frame
    return merged


def load_comparison(force=False):
    """Comparison series.  A country whose comparison fetch came back empty
    borrows the same indicator from its own market data -- only when that is
    already cached, so this never starts another round of downloads."""
    loaded = ds.get_comparison_data(force=force) or {}
    countries = [key for key, *_ in COMPARISON_COUNTRIES]
    merged = {}
    for metric_key, by_country in loaded.items():
        series = dict(by_country or {})
        for country in countries:
            if not clean_series(series.get(country)).empty:
                continue
            borrowed = (ds.peek_market_data(country) or {}).get(metric_key)
            if not clean_series(borrowed).empty:
                series[country] = borrowed
        merged[metric_key] = series
    return merged


REFRESH_COOLDOWN_SECONDS = 45
_last_forced = {}
_forced_lock = threading.Lock()


def refresh_market(market):
    """Force a re-fetch of one view and return its data.

    A second request inside the cooldown is a plain cached read: the app runs on a
    single worker, so every extra fetch (a comparison reload takes about ten
    seconds) would make every other visitor wait behind it.
    """
    now = time.monotonic()
    with _forced_lock:
        recent = now - _last_forced.get(market, -math.inf) < REFRESH_COOLDOWN_SECONDS
        if not recent:
            _last_forced[market] = now
    if market == 'comparison':
        return load_comparison(force=not recent)
    return load_market(market, force=not recent)
