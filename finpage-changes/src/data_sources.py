"""Shared macro data-source fetchers for the multi-country Economy and
Comparison pages.

Mirrors the FRED / Yahoo Finance / Norges Bank / SSB series used by the
FinPage reference app, scoped to US, Norway, EU, UK (Japan and China are
intentionally excluded for now -- see comparisonData/economyData in the
reference app for how to add them back later).

Every fetcher fails soft -- returns an empty Date/value frame on any error --
so one broken upstream never takes down a whole tab. Assembled per-market
results are cached in-process (the app runs as a single gunicorn worker, see
Procfile) with a TTL, refreshed lazily on next access after expiry.
"""

import io
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import yfinance as yf
from fredapi import Fred

FRED_API_KEY = "29f9bb6865c0b3be320b44a846d539ea"
_fred = Fred(api_key=FRED_API_KEY)

_HEADERS = {"User-Agent": "FinPage/1.0 (web)"}
_TIMEOUT = 20


def _empty():
    return pd.DataFrame(columns=["Date", "value"])


def _g(d, key):
    """Safe dict lookup for values that may be a DataFrame -- `x or default`
    is unsafe here because pandas raises on truthiness checks of a frame."""
    v = d.get(key)
    return v if v is not None else _empty()


def ten_years_ago():
    return (pd.Timestamp.today() - pd.DateOffset(years=10)).strftime("%Y-%m-%d")


def filter_since(df, start):
    if df is None or df.empty:
        return _empty()
    return df[df["Date"] >= pd.to_datetime(start)].reset_index(drop=True)


def last_value(df):
    if df is None or df.empty:
        return None
    return df["value"].iloc[-1]


# ---------------------------------------------------------------- FRED -----
def fetch_fred(series_id, observation_start=None):
    """Raw FRED series as an ascending Date/value frame."""
    try:
        s = _fred.get_series(series_id, observation_start=observation_start)
        df = s.reset_index()
        df.columns = ["Date", "value"]
        df["Date"] = pd.to_datetime(df["Date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


# ------------------------------------------------------------- Yahoo -------
def fetch_yahoo(ticker, period="10y"):
    """Daily close series for an equity index or FX ticker."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if hist is None or hist.empty:
            return _empty()
        df = hist.reset_index()[["Date", "Close"]].rename(columns={"Close": "value"})
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


# -------------------------------------------------------- Norges Bank ------
def _norges_bank_csv(url):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text), sep=";")
    except Exception:
        return pd.DataFrame()


def fetch_norges_yields(tenors, start="2016-01-01"):
    """{tenor: Date/value frame} for Norwegian government bond/bill yields."""
    path = "+".join(tenors)
    url = (
        "https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/"
        f"B.{path}.GBON+TBIL.?format=csv&startPeriod={start}&locale=en"
    )
    raw = _norges_bank_csv(url)
    out = {}
    # The CSV has both "TENOR" (short code, e.g. "3Y") and "Tenor" (label,
    # e.g. "3 years") columns -- group by the short code since that's what
    # callers look up (out.get("10Y"), etc).
    if not raw.empty and "TENOR" in raw.columns:
        for tenor, grp in raw.groupby("TENOR"):
            df = grp[["TIME_PERIOD", "OBS_VALUE"]].rename(
                columns={"TIME_PERIOD": "Date", "OBS_VALUE": "value"}
            )
            df["Date"] = pd.to_datetime(df["Date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            out[tenor] = df.dropna().sort_values("Date").reset_index(drop=True)
    for t in tenors:
        out.setdefault(t, _empty())
    return out


def fetch_norges_policy_rate(start="2016-01-01"):
    url = f"https://data.norges-bank.no/api/data/IR/B.KPRA.SD.?format=csv&startPeriod={start}&locale=en"
    raw = _norges_bank_csv(url)
    if raw.empty:
        return _empty()
    df = raw[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "Date", "OBS_VALUE": "value"})
    df["Date"] = pd.to_datetime(df["Date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("Date").reset_index(drop=True)


def fetch_norges_fx(base, start="2016-01-01"):
    url = f"https://data.norges-bank.no/api/data/EXR/B.{base}.NOK.SP?format=csv&startPeriod={start}&locale=en"
    raw = _norges_bank_csv(url)
    if raw.empty:
        return _empty()
    df = raw[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "Date", "OBS_VALUE": "value"})
    df["Date"] = pd.to_datetime(df["Date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("Date").reset_index(drop=True)


# ------------------------------------------------------------------ SSB ----
def fetch_ssb_cpi():
    """Norway CPI index (2015=100), monthly -- table 14709."""
    try:
        r = requests.get(
            "https://data.ssb.no/api/pxwebapi/v2/tables/14709/data?lang=en&outputFormat=json-stat2",
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        j = r.json()
        dim = j.get("dimension", {})
        m_idx = dim.get("Maaned", {}).get("category", {}).get("index", {})
        y_idx = dim.get("Tid", {}).get("category", {}).get("index", {})
        c_idx = dim.get("ContentsCode", {}).get("category", {}).get("index", {})
        size = j.get("size", [])
        if len(size) < 3:
            return _empty()
        m_size, c_size, t_size = size[0], size[1], size[2]
        cc_pos = c_idx.get("KpiIndMnd", 0)
        values = j.get("value", [])
        rows = []
        for mc, mp in m_idx.items():
            if not re.match(r"^(0[1-9]|1[0-2])$", mc):
                continue  # skip annual-average code "90"
            for yc, yp in y_idx.items():
                flat = mp * c_size * t_size + cc_pos * t_size + yp
                if 0 <= flat < len(values) and values[flat] is not None:
                    rows.append({"Date": f"{yc}-{mc}-01", "value": values[flat]})
        if not rows:
            return _empty()
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


def fetch_ssb_unemployment():
    """Norway seasonally-adjusted unemployment rate, ages 15-74 -- table 13760."""
    try:
        r = requests.post(
            "https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=en&outputFormat=json-stat2",
            headers={**_HEADERS, "Content-Type": "application/json"},
            json={
                "Selection": [
                    {"VariableCode": "Kjonn", "ValueCodes": ["0"]},
                    {"VariableCode": "Alder", "ValueCodes": ["15-74"]},
                    {"VariableCode": "Justering", "ValueCodes": ["S"]},
                    {"VariableCode": "ContentsCode", "ValueCodes": ["ArbledProsArbstyrk"]},
                    {"VariableCode": "Tid", "ValueCodes": ["*"]},
                ]
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        j = r.json()
        t_idx = j.get("dimension", {}).get("Tid", {}).get("category", {}).get("index", {})
        values = j.get("value", [])
        rows = []
        for tc, tp in t_idx.items():
            m = re.match(r"^(\d{4})M(\d{2})$", tc)
            if not m or tp >= len(values) or values[tp] is None:
                continue
            rows.append({"Date": f"{m.group(1)}-{m.group(2)}-01", "value": values[tp]})
        if not rows:
            return _empty()
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        # SSB returns a plain percent number (e.g. 4.2) -- normalize to a fraction.
        df["value"] = pd.to_numeric(df["value"], errors="coerce") / 100.0
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


def fetch_ssb_gdp():
    """Norway real GDP annual growth rate -- table 09189."""
    try:
        r = requests.post(
            "https://data.ssb.no/api/pxwebapi/v2/tables/09189/data?lang=en&outputFormat=json-stat2",
            headers={**_HEADERS, "Content-Type": "application/json"},
            json={
                "Selection": [
                    {"VariableCode": "Makrost", "ValueCodes": ["bnpb.nr23_9"]},
                    {"VariableCode": "ContentsCode", "ValueCodes": ["Volum"]},
                    {"VariableCode": "Tid", "ValueCodes": ["*"]},
                ]
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        j = r.json()
        t_idx = j.get("dimension", {}).get("Tid", {}).get("category", {}).get("index", {})
        values = j.get("value", [])
        rows = []
        for tc, tp in t_idx.items():
            if tp >= len(values) or values[tp] is None:
                continue
            rows.append({"Date": f"{tc}-01-01", "value": values[tp] / 100.0})
        if not rows:
            return _empty()
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


# ------------------------------------------------------------------ ONS ----
def _ons_series(section, series_id, dataset_id):
    """UK Office for National Statistics timeseries API. Returns whatever
    granularity (monthly/quarterly/annual) the series publishes at. These
    are already the rate/level callers want -- no yoy_change() needed."""
    try:
        url = f"https://api.beta.ons.gov.uk/v1/data?uri=/{section}/timeseries/{series_id}/{dataset_id}"
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        points = data.get("months") or data.get("quarters") or data.get("years") or []
        rows = []
        for p in points:
            if p.get("quarter"):
                q = int(p["quarter"].replace("Q", ""))
                date = pd.Timestamp(year=int(p["year"]), month=(q - 1) * 3 + 1, day=1)
            elif p.get("month"):
                date = pd.to_datetime(f"{p['year']} {p['month']}", format="%Y %B")
            else:
                date = pd.Timestamp(year=int(p["year"]), month=1, day=1)
            rows.append({"Date": date, "value": p["value"]})
        if not rows:
            return _empty()
        df = pd.DataFrame(rows)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


def fetch_ons_uk_cpi_yoy():
    """UK CPI 12-month rate, all items (ONS D7G7/MM23) -- the FRED mirror
    (GBRCPIALLMINMEI) stopped updating in March 2025."""
    return _ons_series("economy/inflationandpriceindices", "d7g7", "mm23")


def fetch_ons_uk_unemployment():
    """UK unemployment rate, aged 16+, seasonally adjusted (ONS MGSX/LMS)."""
    return _ons_series("employmentandlabourmarket/peoplenotinwork/unemployment", "mgsx", "lms")


def fetch_ons_uk_gdp_yoy():
    """UK real GDP, quarter vs. same quarter a year ago, CVM SA %
    (ONS IHYR/QNA) -- same reference quarter as the FRED mirror
    (NGDPRSAXDCGBQ) since that's genuinely the latest UK GDP has been
    published anywhere, but sourced directly instead of via a FRED mirror
    that has lagged behind ONS on other series."""
    return _ons_series("economy/grossdomesticproductgdp", "ihyr", "qna")


# ------------------------------------------------------------------ ECB ----
def fetch_ecb_eu_yield10y(start="2016-01-01"):
    """Euro area AAA-rated 10-year yield curve spot rate -- ECB Statistical
    Data Warehouse, updated daily. Replaces the FRED-mirrored "convergence
    purposes" rate (IRLTLT01EZM156N), which only updates monthly and has
    been running several months behind."""
    try:
        url = (
            "https://data-api.ecb.europa.eu/service/data/YC/"
            f"B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=csvdata&startPeriod={start}"
        )
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df = df[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "Date", "OBS_VALUE": "value"})
        df["Date"] = pd.to_datetime(df["Date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


# ------------------------------------------------------------ Eurostat -----
def fetch_eurostat_eu_unemployment(start="2010-01"):
    """Euro area (21 countries) unemployment rate, seasonally adjusted --
    Eurostat. Replaces the FRED-mirrored OECD series (LRHUTTTTEZM156S),
    which stopped updating in 2023."""
    try:
        url = (
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"
            f"?format=JSON&geo=EA21&s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT&sinceTimePeriod={start}"
        )
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        time_idx = j.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
        values = j.get("value", {})
        rows = []
        for period, idx in time_idx.items():
            v = values.get(str(idx))
            if v is None:
                continue
            rows.append({"Date": pd.to_datetime(period + "-01"), "value": v})
        if not rows:
            return _empty()
        df = pd.DataFrame(rows)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)
    except Exception:
        return _empty()


# -------------------------------------------------------------- helpers ----
def yoy_change(df, periods=12):
    """Year-over-year fractional change from an index-level Date/value frame."""
    if df is None or df.empty:
        return _empty()
    out = df.copy().sort_values("Date").reset_index(drop=True)
    out["value"] = out["value"].pct_change(periods=periods)
    out = out.dropna(subset=["value"])
    return out[["Date", "value"]].reset_index(drop=True)


def as_rate(df):
    """Normalize a raw percent series (e.g. FRED yields) into a fraction."""
    if df is None or df.empty:
        return _empty()
    out = df.copy()
    out["value"] = pd.to_numeric(out["value"], errors="coerce") / 100.0
    return out.dropna().reset_index(drop=True)


def series_diff(a, b):
    """a.value - b.value aligned on Date (inner join)."""
    if a is None or a.empty or b is None or b.empty:
        return _empty()
    m = pd.merge(a, b, on="Date", suffixes=("_a", "_b"))
    if m.empty:
        return _empty()
    m["value"] = m["value_a"] - m["value_b"]
    return m[["Date", "value"]].sort_values("Date").reset_index(drop=True)


def parallel_fetch(fn_map):
    """Run independent zero-arg fetchers concurrently; a failure fails soft to None."""
    results = {}
    if not fn_map:
        return results
    with ThreadPoolExecutor(max_workers=max(1, len(fn_map))) as pool:
        futures = {key: pool.submit(fn) for key, fn in fn_map.items()}
        for key, future in futures.items():
            try:
                results[key] = future.result()
            except Exception:
                results[key] = None
    return results


class TTLCache:
    """Tiny process-local cache: one entry per key, refreshed after `ttl` seconds.

    The app runs as a single gunicorn worker (see Procfile), so a module-level
    cache is safe and avoids re-hitting FRED/Yahoo/Norges Bank/SSB on every
    page view.
    """

    def __init__(self, ttl=6 * 3600):
        self.ttl = ttl
        self._store = {}
        self._lock = threading.Lock()

    def get_or_load(self, key, loader):
        with self._lock:
            entry = self._store.get(key)
            fresh = entry and (time.time() - entry[1]) < self.ttl
        if fresh:
            return entry[0]
        value = loader()
        with self._lock:
            self._store[key] = (value, time.time())
        return value

    def invalidate(self, key=None):
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)


# ------------------------------------------------------- market assembly ---
EU_COUNTRIES = {
    "germany": {"code": "DE", "stock": "^GDAXI", "label": "Germany"},
    "france": {"code": "FR", "stock": "^FCHI", "label": "France"},
    "italy": {"code": "IT", "stock": "FTSEMIB.MI", "label": "Italy"},
    "spain": {"code": "ES", "stock": "^IBEX", "label": "Spain"},
}


def load_norway_economy():
    since = "2016-01-01"
    vals = parallel_fetch(
        {
            "yields": lambda: fetch_norges_yields(["3Y", "10Y"], since),
            "policy": lambda: fetch_norges_policy_rate(since),
            "stock": lambda: fetch_yahoo("OSEBX.OL", "10y"),
            "cpi": fetch_ssb_cpi,
            "unemployment": fetch_ssb_unemployment,
            "usd": lambda: fetch_norges_fx("USD", since),
            "eur": lambda: fetch_norges_fx("EUR", since),
            "gdp": fetch_ssb_gdp,
        }
    )
    yields = vals.get("yields") or {}
    y10 = as_rate(yields.get("10Y", _empty()))
    y3 = as_rate(yields.get("3Y", _empty()))
    return {
        "bondYield10y": y10,
        "policyRate": as_rate(_g(vals, "policy")),
        "spread10y3y": series_diff(y10, y3),
        "stockIndex": _g(vals, "stock"),
        "cpiYoY": yoy_change(_g(vals, "cpi"), 12),
        "unemployment": _g(vals, "unemployment"),
        "gdpYoY": filter_since(_g(vals, "gdp"), ten_years_ago()),
        "usdFx": _g(vals, "usd"),
        "eurFx": _g(vals, "eur"),
    }


def load_eu_economy():
    since = ten_years_ago()
    headline = parallel_fetch(
        {
            "yield": lambda: fetch_ecb_eu_yield10y(since),
            "policy": lambda: fetch_fred("ECBDFR", since),
            "cpi": lambda: fetch_fred("CP0000EZ19M086NEST", since),
            "gdp": lambda: fetch_fred("CLVMNACSCAB1GQEA19", since),
            "stock": lambda: fetch_yahoo("^STOXX50E", "10y"),
        }
    )
    countries = {}
    # Fetch countries sequentially (each internally parallel) to avoid
    # hammering FRED with too many simultaneous connections.
    for name, c in EU_COUNTRIES.items():
        vals = parallel_fetch(
            {
                "yield": lambda code=c["code"]: fetch_fred(f"IRLTLT01{code}M156N", since),
                "stock": lambda t=c["stock"]: fetch_yahoo(t, "10y"),
                "cpi": lambda code=c["code"]: fetch_fred(f"CP0000{code}M086NEST", since),
                "unemployment": lambda code=c["code"]: fetch_fred(f"LRHUTTTT{code}M156S", since),
                # NAEXKP01{code}Q189S (OECD) stopped updating in 2023 and
                # doesn't exist at all for Spain -- CLVMNACSCAB1GQ{code}
                # (Eurostat, same series family as the EU-wide headline GDP
                # below) is current for all four countries.
                "gdp": lambda code=c["code"]: fetch_fred(f"CLVMNACSCAB1GQ{code}", since),
            }
        )
        countries[name] = {
            "label": c["label"],
            "bondYield10y": as_rate(_g(vals, "yield")),
            "stockIndex": _g(vals, "stock"),
            "cpiYoY": yoy_change(_g(vals, "cpi"), 12),
            "unemployment": as_rate(_g(vals, "unemployment")),
            "gdpYoY": yoy_change(_g(vals, "gdp"), 4),
        }
    return {
        "bondYield10y": as_rate(_g(headline, "yield")),
        "policyRate": as_rate(_g(headline, "policy")),
        "cpiYoY": yoy_change(_g(headline, "cpi"), 12),
        "gdpYoY": yoy_change(_g(headline, "gdp"), 4),
        "stockIndex": _g(headline, "stock"),
        "countries": countries,
    }


def load_uk_economy():
    since = ten_years_ago()
    vals = parallel_fetch(
        {
            "yield": lambda: fetch_fred("IRLTLT01GBM156N", since),
            "stock": lambda: fetch_yahoo("^FTSE", "10y"),
            # ONS direct -- the FRED mirrors of these three (GBRCPIALLMINMEI,
            # LRHUTTTTGBM156S, NGDPRSAXDCGBQ) lag ONS's own releases, badly
            # so for CPI (17 months stale). ONS already publishes each of
            # these as a YoY rate, so no yoy_change() step needed.
            "cpi": fetch_ons_uk_cpi_yoy,
            "unemployment": fetch_ons_uk_unemployment,
            "gdp": fetch_ons_uk_gdp_yoy,
        }
    )
    return {
        "bondYield10y": as_rate(_g(vals, "yield")),
        "stockIndex": _g(vals, "stock"),
        "cpiYoY": as_rate(_g(vals, "cpi")),
        "unemployment": as_rate(_g(vals, "unemployment")),
        "gdpYoY": as_rate(_g(vals, "gdp")),
    }


def load_comparison_data():
    """Cross-country GDP/CPI/10Y-yield/Unemployment for US, EU, UK, Norway."""
    since = "2010-01-01"
    us = parallel_fetch(
        {
            "gdp": lambda: fetch_fred("GDPC1", since),
            "cpi": lambda: fetch_fred("CPIAUCSL", since),
            "yield": lambda: fetch_fred("DGS10", since),
            "unemployment": lambda: fetch_fred("UNRATE", since),
        }
    )
    eu = parallel_fetch(
        {
            "gdp": lambda: fetch_fred("CLVMNACSCAB1GQEA19", since),
            "cpi": lambda: fetch_fred("CP0000EZ19M086NEST", since),
            # ECB/Eurostat direct -- the FRED mirrors of these two
            # (IRLTLT01EZM156N, LRHUTTTTEZM156S) lag several months to
            # several years behind the source.
            "yield": lambda: fetch_ecb_eu_yield10y(since),
            "unemployment": fetch_eurostat_eu_unemployment,
        }
    )
    uk = parallel_fetch(
        {
            "yield": lambda: fetch_fred("IRLTLT01GBM156N", since),
            # ONS direct -- see load_uk_economy() for why.
            "gdp": fetch_ons_uk_gdp_yoy,
            "cpi": fetch_ons_uk_cpi_yoy,
            "unemployment": fetch_ons_uk_unemployment,
        }
    )
    norway = parallel_fetch(
        {
            "gdp": fetch_ssb_gdp,
            "cpi": fetch_ssb_cpi,
            "yield": lambda: fetch_norges_yields(["10Y"], since).get("10Y", _empty()),
            "unemployment": fetch_ssb_unemployment,
        }
    )
    return {
        "gdpYoY": {
            "us": yoy_change(_g(us, "gdp"), 4),
            "eu": yoy_change(_g(eu, "gdp"), 4),
            "uk": as_rate(_g(uk, "gdp")),
            "norway": filter_since(_g(norway, "gdp"), since),
        },
        "cpiYoY": {
            "us": yoy_change(_g(us, "cpi"), 12),
            "eu": yoy_change(_g(eu, "cpi"), 12),
            "uk": as_rate(_g(uk, "cpi")),
            "norway": yoy_change(_g(norway, "cpi"), 12),
        },
        "bondYield10y": {
            "us": as_rate(_g(us, "yield")),
            "eu": as_rate(_g(eu, "yield")),
            "uk": as_rate(_g(uk, "yield")),
            "norway": as_rate(_g(norway, "yield")),
        },
        "unemployment": {
            "us": as_rate(_g(us, "unemployment")),
            "eu": as_rate(_g(eu, "unemployment")),
            "uk": as_rate(_g(uk, "unemployment")),
            "norway": _g(norway, "unemployment"),
        },
    }


_cache = TTLCache(ttl=6 * 3600)

_MARKET_LOADERS = {
    "norway": load_norway_economy,
    "eu": load_eu_economy,
    "uk": load_uk_economy,
}


def get_market_data(market):
    loader = _MARKET_LOADERS.get(market)
    if not loader:
        return {}
    return _cache.get_or_load(market, loader)


def get_comparison_data():
    return _cache.get_or_load("comparison", load_comparison_data)


def invalidate_market(market):
    _cache.invalidate(market)
