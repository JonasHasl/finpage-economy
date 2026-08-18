from pathlib import Path

import pandas as pd


DATA_DIRECTORY = Path(__file__).resolve().parent
TRAINING_RETURNS_PATH = DATA_DIRECTORY / "strategy_training_returns.csv"
BENCHMARK_RETURNS_PATH = DATA_DIRECTORY / "acwi.csv"

# Authoritative training-period figures supplied with strategy_training_returns.csv.
TRAINING_MAX_DRAWDOWN = {
    "2015": 0.2936,
    "2020": 0.3486,
}


def load_training_returns(model_window, path=TRAINING_RETURNS_PATH):
    model_window = str(model_window)
    if model_window not in TRAINING_MAX_DRAWDOWN:
        raise ValueError(f"Unsupported model window: {model_window}")

    history = pd.read_csv(path, parse_dates=["Date"], usecols=["Date", model_window])
    history = history.rename(columns={model_window: "Portfolio_Cumulative"})
    history["Portfolio_Cumulative"] = pd.to_numeric(
        history["Portfolio_Cumulative"], errors="coerce"
    )
    history = history.dropna(subset=["Portfolio_Cumulative"])
    return history.set_index("Date").sort_index()


def get_training_dates(model_window):
    history = load_training_returns(model_window)
    return history.index.min(), history.index.max()


def _load_training_benchmark(training_dates, path=BENCHMARK_RETURNS_PATH):
    benchmark = pd.read_csv(path, usecols=["Date", "Return"], parse_dates=["Date"])
    benchmark["Return"] = pd.to_numeric(benchmark["Return"], errors="coerce")
    monthly_returns = benchmark.set_index("Date")["Return"].reindex(training_dates)

    if monthly_returns.isna().any():
        missing = monthly_returns[monthly_returns.isna()].index.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"Missing ACWI training returns for: {', '.join(missing)}")

    return (1 + monthly_returns).cumprod() - 1


def _as_naive_datetime_index(values):
    index = pd.DatetimeIndex(pd.to_datetime(values))
    if index.tz is not None:
        index = index.tz_convert(None)
    return index


def _fx_levels_for_dates(fx_close, dates):
    fx = pd.Series(fx_close).copy()
    fx.index = _as_naive_datetime_index(fx.index)
    fx = pd.to_numeric(fx, errors="coerce").dropna().sort_index()
    fx = fx[~fx.index.duplicated(keep="last")]

    dates = _as_naive_datetime_index(dates)
    aligned = fx.reindex(fx.index.union(dates).sort_values()).ffill().reindex(dates)
    if aligned.isna().any():
        raise ValueError("USD/NOK history does not cover the full training period")
    return aligned


def convert_cumulative_returns_to_nok(cumulative_returns, fx_close):
    cumulative = pd.Series(cumulative_returns).dropna().sort_index()
    cumulative.index = _as_naive_datetime_index(cumulative.index)
    baseline_date = cumulative.index.min() - pd.offsets.MonthEnd(1)
    required_dates = pd.DatetimeIndex([baseline_date]).append(cumulative.index)
    fx_levels = _fx_levels_for_dates(fx_close, required_dates)
    fx_ratio = fx_levels.iloc[1:] / fx_levels.iloc[0]
    fx_ratio.index = cumulative.index
    return (1 + cumulative) * fx_ratio - 1


def build_combined_performance(model_window, testing_returns, currency="USD", fx_close=None):
    training = load_training_returns(model_window)
    training["ACWI_Cumulative"] = _load_training_benchmark(training.index)

    if currency == "NOK":
        if fx_close is None:
            raise ValueError("USD/NOK history is required for NOK training returns")
        training["Portfolio_Cumulative"] = convert_cumulative_returns_to_nok(
            training["Portfolio_Cumulative"], fx_close
        )
        training["ACWI_Cumulative"] = convert_cumulative_returns_to_nok(
            training["ACWI_Cumulative"], fx_close
        )

    training_end = training.index.max()
    training_display = training.rename(
        columns={
            "Portfolio_Cumulative": "Portfolio_Cumulative_Period",
            "ACWI_Cumulative": "ACWI_Cumulative_Period",
        }
    )
    training_display["Phase"] = "Training"

    testing = pd.DataFrame(testing_returns).copy()
    testing.index = _as_naive_datetime_index(testing.index)
    testing = testing[testing.index > training_end].sort_index()

    if testing.empty:
        return training_display, training_end

    portfolio_start = 1 + training_display["Portfolio_Cumulative_Period"].iloc[-1]
    benchmark_start = 1 + training_display["ACWI_Cumulative_Period"].iloc[-1]
    testing_display = pd.DataFrame(index=testing.index)
    testing_display["Portfolio_Cumulative_Period"] = (
        portfolio_start * (1 + testing["Portfolio_Return"].fillna(0)).cumprod() - 1
    )
    testing_display["ACWI_Cumulative_Period"] = (
        benchmark_start * (1 + testing["ACWI_Return"].fillna(0)).cumprod() - 1
    )
    testing_display["Phase"] = "Testing"

    return pd.concat([training_display, testing_display]), training_end


def calculate_max_drawdown(cumulative_returns):
    cumulative = pd.to_numeric(pd.Series(cumulative_returns), errors="coerce").dropna()
    if cumulative.empty:
        return 0.0

    wealth = 1 + cumulative
    running_peak = wealth.cummax().clip(lower=1.0)
    drawdown = wealth / running_peak - 1
    return float(max(0.0, -drawdown.min()))


def calculate_strategy_max_drawdown(model_window, combined_performance):
    observed_drawdown = calculate_max_drawdown(
        combined_performance["Portfolio_Cumulative_Period"]
    )
    return max(TRAINING_MAX_DRAWDOWN[str(model_window)], observed_drawdown)
