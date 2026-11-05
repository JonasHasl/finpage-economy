import importlib
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dash
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import data_sources as ds  # noqa: E402
import economy_dashboard_model as model  # noqa: E402
from theme import LIGHT_THEME  # noqa: E402


def frame(dates, values):
    return pd.DataFrame({"Date": pd.to_datetime(dates), "value": values})


def loader_keys():
    """The keys each loader really returns, found by running it with every fetch stubbed out."""
    with patch.object(ds, "parallel_fetch", side_effect=lambda fns: {key: None for key in fns}):
        return {
            "us": ds.load_us_economy(),
            "norway": ds.load_norway_economy(),
            "eu": ds.load_eu_economy(),
            "uk": ds.load_uk_economy(),
            "comparison": ds.load_comparison_data(),
        }


class IndicatorSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = loader_keys()

    def test_every_market_indicator_exists_in_the_data_layer(self):
        for key, market in model.MARKETS.items():
            available = set(self.loaded[key])
            wanted = {item.key for item in (*market.kpis, *market.charts)}

            self.assertEqual(wanted - available, set(), f"{key}: indicators missing from data_sources")

    def test_euro_area_country_panel_and_comparison_keys_exist_too(self):
        country = next(iter(self.loaded["eu"]["countries"].values()))
        detail_keys = {kpi.key for kpi in model.EU_DETAIL_KPIS} | {"stockIndex"}

        self.assertEqual(detail_keys - set(country), set())
        self.assertEqual(
            {metric.key for metric in model.COMPARISON_METRICS} - set(self.loaded["comparison"]),
            set(),
        )
        for metric in model.COMPARISON_METRICS:
            self.assertEqual(
                {key for key, *_ in model.COMPARISON_COUNTRIES} - set(self.loaded["comparison"][metric.key]),
                set(),
            )

    def test_country_detail_covers_every_country_the_data_layer_loads(self):
        self.assertTrue(model.MARKETS["eu"].has_country_detail)
        self.assertEqual(set(self.loaded["eu"]["countries"]), set(ds.EU_COUNTRIES))

    def test_chart_specs_use_known_ticks_colours_and_periods(self):
        ticks = {"%", "bps", "usd_tn", "usd_bn", "ratio", "fx", "index"}
        for market in model.MARKETS.values():
            for chart in market.charts:
                self.assertIn(chart.tick, ticks, chart.title)
                self.assertIn(chart.color, LIGHT_THEME, chart.title)
                self.assertIn(chart.period, {None, "month", "quarter"}, chart.title)
                self.assertTrue(chart.short and chart.title and chart.axis and chart.source)
            self.assertEqual(len({chart.key for chart in market.charts}), len(market.charts), market.key)

    def test_every_market_fits_a_two_row_grid_with_the_expected_tile_counts(self):
        # The dashboard uses two rows; the column count follows from the tile count.
        self.assertEqual({key: len(m.charts) for key, m in model.MARKETS.items()},
                         {"us": 10, "norway": 9, "eu": 6, "uk": 5})
        self.assertEqual({key: len(m.kpis) for key, m in model.MARKETS.items()},
                         {"us": 5, "norway": 5, "eu": 5, "uk": 4})


class FormattingTests(unittest.TestCase):
    def test_observation_dates_do_not_claim_false_precision(self):
        self.assertEqual(model.format_observation_date("2026-07-01", "quarter"), "Q3 2026")
        self.assertEqual(model.format_observation_date("2026-09-01", "month"), "Sep 2026")
        self.assertEqual(model.format_observation_date("2026-10-28"), "28 Oct 2026")

    def test_values_use_the_unit_of_their_series(self):
        self.assertEqual(model.format_observation_value(0.0505, "%"), "5.05%")
        self.assertEqual(model.format_observation_value(-0.0123, "%"), "−1.23%")
        self.assertEqual(model.format_observation_value(37, "bps"), "37 bp")
        self.assertEqual(model.format_observation_value(23.414, "usd_tn"), "$23.41tn")
        self.assertEqual(model.format_observation_value(-105.57, "usd_bn"), "−$105.6bn")
        self.assertEqual(model.format_observation_value(40.88, "ratio"), "40.9×")
        self.assertEqual(model.format_observation_value(9.28264, "fx"), "9.2826")
        self.assertEqual(model.format_observation_value(7626.7, "index"), "7,626.70")

    def test_stat_formatting_matches_the_classic_page(self):
        self.assertEqual(model.fmt_pct(0.037173), "3.72%")
        self.assertEqual(model.fmt_pct(None), "—")
        self.assertEqual(model.fmt_pct(float("nan")), "—")
        self.assertEqual(model.fmt_num(40.88, 1), "40.9")
        self.assertEqual(model.fmt_num(None, 1), "—")

    def test_period_is_inferred_from_the_spacing_of_first_of_month_dates(self):
        monthly = frame(["2026-05-01", "2026-06-01", "2026-07-01"], [1, 2, 3])
        quarterly = frame(["2025-10-01", "2026-01-01", "2026-04-01"], [1, 2, 3])
        daily = frame(["2026-05-04", "2026-05-05", "2026-05-06"], [1, 2, 3])

        self.assertEqual(model.infer_observation_period(monthly), "month")
        self.assertEqual(model.infer_observation_period(quarterly), "quarter")
        self.assertIsNone(model.infer_observation_period(daily))
        self.assertIsNone(model.infer_observation_period(frame(["2026-05-01"], [1])))
        self.assertIsNone(model.infer_observation_period(None))

    def test_source_as_of_names_the_latest_observation(self):
        monthly = frame(["2026-08-01", "2026-09-01"], [1, 2])

        self.assertEqual(model.source_as_of("FRED", monthly), "FRED · Sep 2026")
        self.assertEqual(model.source_as_of("Eurostat", monthly, "quarter"), "Eurostat · Q3 2026")
        self.assertEqual(model.source_as_of("FRED", None), "FRED")


class ChangeDescriptionTests(unittest.TestCase):
    def test_rates_move_in_percentage_points(self):
        self.assertEqual(model.describe_change(0.0505, 0.0499, "%"), ("▲ 0.06 pp", "up"))
        self.assertEqual(model.describe_change(0.0199, 0.0212, "%"), ("▼ 0.13 pp", "down"))

    def test_spreads_move_in_basis_points_and_levels_in_percent(self):
        self.assertEqual(model.describe_change(37, 38, "bps"), ("▼ 1 bp", "down"))
        self.assertEqual(model.describe_change(7626.7, 7720.4, "index"), ("▼ 1.21%", "down"))
        self.assertEqual(model.describe_change(10.332, 10.348, "fx"), ("▼ 0.15%", "down"))

    def test_money_series_show_a_currency_amount(self):
        self.assertEqual(model.describe_change(23.414, 23.301, "usd_tn"), ("▲ $0.11tn", "up"))
        self.assertEqual(model.describe_change(-105.57, -92.826, "usd_bn"), ("▼ $12.7bn", "down"))

    def test_tiny_moves_read_as_unchanged_and_missing_inputs_as_nothing(self):
        self.assertEqual(model.describe_change(0.045, 0.045, "%"), ("unchanged", "flat"))
        self.assertEqual(model.describe_change(40.88, 40.86, "ratio"), ("unchanged", "flat"))
        self.assertEqual(model.describe_change(None, 1.0, "%"), (None, None))
        self.assertEqual(model.describe_change(1.0, float("nan"), "%"), (None, None))
        self.assertEqual(model.describe_change(1.0, 0.0, "index"), (None, None))


class SnapshotTests(unittest.TestCase):
    def test_snapshot_reports_latest_value_change_and_source_date(self):
        kpi = model.Kpi("CPI YoY", "cpiYoY", "FRED")
        snap = model.snapshot(kpi, frame(["2026-08-01", "2026-09-01"], [0.03353, 0.037173]))

        self.assertEqual(
            (snap.value_text, snap.delta_text, snap.delta_direction, snap.as_of, snap.has_data),
            ("3.72%", "▲ 0.36 pp", "up", "FRED · Sep 2026", True),
        )

    def test_number_kpis_use_one_decimal_and_ratio_changes(self):
        kpi = model.Kpi("Shiller CAPE", "shillerPE", "multpl.com", kind="num1", tick="ratio")
        snap = model.snapshot(kpi, frame(["2026-09-01", "2026-10-01"], [40.2, 40.88]))

        self.assertEqual((snap.value_text, snap.delta_text), ("40.9", "▲ 0.7×"))

    def test_a_single_observation_has_a_value_but_no_change(self):
        snap = model.snapshot(model.Kpi("X", "x", "SSB"), frame(["2026-09-01"], [0.05]))

        self.assertEqual((snap.value_text, snap.delta_text, snap.delta_direction), ("5.00%", None, None))

    def test_missing_data_becomes_an_empty_card_that_still_names_the_source(self):
        for missing in (None, pd.DataFrame(columns=["Date", "value"]), pd.DataFrame({"x": [1]})):
            snap = model.snapshot(model.Kpi("Policy Rate", "policyRate", "Norges Bank"), missing)

            self.assertEqual(
                (snap.value_text, snap.delta_text, snap.as_of, snap.has_data),
                ("—", None, "Norges Bank", False),
            )


class SeriesHygieneTests(unittest.TestCase):
    def test_clean_series_sorts_dedupes_and_drops_non_numeric_rows(self):
        messy = pd.DataFrame({
            "Date": ["2026-03-01", "2026-01-01", "2026-02-01", "2026-02-01", None],
            "value": [3, 1, "x", 2, 9],
        })

        tidy = model.clean_series(messy)

        self.assertEqual(
            list(tidy["Date"].dt.strftime("%Y-%m-%d")),
            ["2026-01-01", "2026-02-01", "2026-03-01"],
        )
        self.assertEqual(list(tidy["value"]), [1.0, 2.0, 3.0])
        self.assertTrue(tidy["Date"].is_monotonic_increasing)

    def test_clean_series_tolerates_missing_or_malformed_input(self):
        for bad in (None, "text", pd.DataFrame(), pd.DataFrame({"Date": [1]})):
            self.assertTrue(model.clean_series(bad).empty)
            self.assertEqual(list(model.clean_series(bad).columns), ["Date", "value"])

    def test_the_last_value_for_a_repeated_date_wins_even_in_a_long_series(self):
        # Sorting is stable, so "last" means last in the source whatever the length.
        order = np.random.RandomState(0).permutation(260)
        dates = pd.date_range("2025-01-01", periods=200, freq="D")
        rows = pd.DataFrame({
            "Date": list(dates) + list(dates[:60]),
            "value": [float(n) for n in range(260)],
        }).iloc[order].reset_index(drop=True)
        expected = rows.groupby("Date")["value"].last()

        tidy = model.clean_series(rows)

        self.assertEqual(len(tidy), 200)
        self.assertEqual(list(tidy["value"]), list(expected.sort_index()))

    def test_a_daily_series_with_a_first_of_month_date_is_not_mistaken_for_monthly(self):
        daily = frame(["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"], [1, 2, 3, 4])
        monthly_series = frame(["2026-07-01", "2026-08-01", "2026-09-01"], [1, 2, 3])
        quarterly = frame(["2026-01-01", "2026-04-01", "2026-07-01"], [1, 2, 3])

        self.assertIsNone(model.infer_observation_period(daily))
        self.assertEqual(model.infer_observation_period(monthly_series), "month")
        self.assertEqual(model.infer_observation_period(quarterly), "quarter")
        self.assertIsNone(model.infer_observation_period(frame(["2026-09-01"], [1])))

    def test_carry_in_holds_the_rate_in_force_at_the_start_of_the_window(self):
        changes = frame(["2025-06-11", "2026-06-17", "2026-10-30"], [0.02, 0.0225, 0.0225])
        window = (date(2026, 1, 1), date(2026, 10, 30))

        carried = model.clip_series(changes, *window, carry_in=True)
        plain = model.clip_series(changes, *window)

        self.assertEqual(list(carried["Date"].dt.strftime("%Y-%m-%d")), ["2026-01-01", "2026-06-17", "2026-10-30"])
        self.assertEqual(list(carried["value"]), [0.02, 0.0225, 0.0225])
        self.assertEqual(carried["since"].iloc[0], pd.Timestamp("2025-06-11"))
        self.assertTrue(carried["since"].iloc[1:].isna().all())
        self.assertEqual(list(plain["Date"].dt.strftime("%Y-%m-%d")), ["2026-06-17", "2026-10-30"])
        self.assertNotIn("since", plain.columns)

    def test_carry_in_adds_nothing_when_there_is_nothing_to_carry(self):
        changes = frame(["2025-06-11", "2026-01-01", "2026-06-17"], [0.02, 0.0225, 0.025])
        window = (date(2026, 1, 1), date(2026, 10, 30))

        on_the_first_day = model.clip_series(changes, *window, carry_in=True)
        self.assertEqual(list(on_the_first_day["value"]), [0.0225, 0.025])  # already starts on 1 January
        self.assertNotIn("since", on_the_first_day.columns)

        no_history = model.clip_series(changes, date(2025, 1, 1), date(2025, 12, 31), carry_in=True)
        self.assertEqual(list(no_history["value"]), [0.02])  # nothing earlier to carry

        nothing_inside = model.clip_series(changes, date(2026, 7, 1), date(2026, 10, 30), carry_in=True)
        self.assertTrue(nothing_inside.empty)  # a stale series must not be drawn as if it were current

    def test_clip_series_keeps_only_the_window(self):
        series = frame(["2025-12-31", "2026-01-01", "2026-06-15", "2026-10-30", "2026-11-02"], [1, 2, 3, 4, 5])

        clipped = model.clip_series(series, date(2026, 1, 1), date(2026, 10, 30))

        self.assertEqual(list(clipped["value"]), [2.0, 3.0, 4.0])

    def test_windows_follow_the_range_selector(self):
        today = date(2026, 10, 30)

        self.assertEqual(model.resolve_window("ytd", today), (date(2026, 1, 1), today))
        self.assertEqual(model.resolve_window("full", today), (date(2000, 1, 1), today))
        self.assertEqual(model.resolve_window(None, today), (date(2000, 1, 1), today))

    def test_range_selector_offers_ytd_five_years_and_everything(self):
        self.assertEqual([key for key, _ in model.RANGE_OPTIONS], ["ytd", "5y", "full"])

    def test_five_year_window_counts_back_from_today(self):
        self.assertEqual(model.resolve_window("5y", date(2026, 10, 30)), (date(2021, 10, 30), date(2026, 10, 30)))
        # 29 February has no counterpart five years earlier, so it lands on the 28th.
        self.assertEqual(model.resolve_window("5y", date(2028, 2, 29))[0], date(2023, 2, 28))

    def test_series_state_tells_a_missing_source_from_an_empty_window(self):
        window = (date(2026, 1, 1), date(2026, 10, 30))

        self.assertEqual(model.series_state(None, *window), "unavailable")
        self.assertEqual(model.series_state(ds._empty(), *window), "unavailable")
        self.assertEqual(model.series_state(frame(["2025-06-01"], [1]), *window), "out_of_range")
        self.assertEqual(model.series_state(frame(["2025-06-01", "2026-03-01"], [1, 2]), *window), "ok")


class DataAccessTests(unittest.TestCase):
    def setUp(self):
        model._last_forced.clear()

    def test_a_refresh_inside_the_cooldown_is_a_cached_read(self):
        clock = SimpleNamespace(monotonic=MagicMock(side_effect=[1000.0, 1010.0, 1044.9, 1045.0]))
        with patch.object(model, "load_market", return_value={}) as load, patch.object(model, "time", clock):
            for _ in range(4):
                model.refresh_market("uk")

        self.assertEqual(
            [call.kwargs for call in load.call_args_list],
            [{"force": True}, {"force": False}, {"force": False}, {"force": True}],
        )

    def test_the_cooldown_is_kept_per_view(self):
        clock = SimpleNamespace(monotonic=MagicMock(side_effect=[1000.0, 1001.0, 1002.0, 1003.0]))
        with patch.object(model, "load_market", return_value={}) as load_market, \
                patch.object(model, "load_comparison", return_value={}) as load_comparison, \
                patch.object(model, "time", clock):
            model.refresh_market("uk")
            model.refresh_market("us")
            model.refresh_market("comparison")
            model.refresh_market("comparison")

        self.assertEqual([call.kwargs for call in load_market.call_args_list], [{"force": True}, {"force": True}])
        self.assertEqual([call.kwargs for call in load_comparison.call_args_list], [{"force": True}, {"force": False}])

    def test_us_view_backfills_only_the_series_a_live_source_left_empty(self):
        live = {
            "bondYield10y": frame(["2026-10-28"], [0.0505]),
            "unemployment": ds._empty(),
            "cpiYoY": None,
        }
        fallback = {
            "bondYield10y": frame(["2020-01-01"], [0.0100]),
            "unemployment": frame(["2026-09-01"], [0.042]),
            "cpiYoY": frame(["2026-09-01"], [0.037]),
            "shillerPE": frame(["2026-10-01"], [40.0]),
        }
        with patch.object(ds, "get_market_data", return_value=live), \
                patch.object(model, "cached_us_fallback", return_value=fallback):
            merged = model.load_market("us")

        self.assertEqual(merged["bondYield10y"]["value"].iloc[-1], 0.0505)   # live wins
        self.assertEqual(merged["unemployment"]["value"].iloc[-1], 0.042)    # empty -> fallback
        self.assertEqual(merged["cpiYoY"]["value"].iloc[-1], 0.037)          # missing -> fallback
        self.assertEqual(merged["shillerPE"]["value"].iloc[-1], 40.0)        # fallback-only key kept

    def test_other_markets_are_passed_through_untouched(self):
        live = {"policyRate": ds._empty()}
        with patch.object(ds, "get_market_data", return_value=live) as getter, \
                patch.object(model, "cached_us_fallback") as fallback:
            self.assertIs(model.load_market("norway", force=True), live)

        getter.assert_called_once_with("norway", force=True)
        fallback.assert_not_called()

    def test_legacy_csv_fallback_keeps_change_dates_and_converts_units(self):
        legacy = pd.DataFrame({
            "Date": ["2026-08-01", "2026-08-02", "2026-09-01", "2026-09-02"],
            "TenYield": [4.0, 4.0, 4.5, 4.5],
            "m2": [22000.0, 22000.0, 23000.0, 23000.0],
            "T10Y2Y": [0.30, 0.30, 0.37, 0.37],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            legacy.to_csv(path, index=False)
            result = model.cached_us_fallback(path=path)

        self.assertEqual(list(result["bondYield10y"]["Date"].dt.strftime("%Y-%m-%d")), ["2026-08-01", "2026-09-01"])
        self.assertAlmostEqual(result["bondYield10y"]["value"].iloc[-1], 0.045)
        self.assertAlmostEqual(result["moneySupply"]["value"].iloc[-1], 23.0)
        self.assertAlmostEqual(result["spread10y2y"]["value"].iloc[-1], 37.0)
        self.assertTrue(result["stockIndex"].empty)  # no Close column in this frame

    def test_every_legacy_column_is_converted_to_the_unit_the_live_series_use(self):
        legacy = pd.DataFrame({
            "Date": ["2026-09-01", "2026-09-02"],
            "TenYield": [4.0, 4.5],        # percent -> fraction
            "Close": [7500.0, 7545.5],     # index points, unchanged
            "CPI YoY": [0.03, 0.037],      # already a fraction
            "m2": [23000.0, 23400.0],      # billions -> trillions
            "T10Y2Y": [0.3, 0.37],         # percentage points -> basis points
            "unemp_rate": [4.1, 4.2],      # percent -> fraction
            "Trade Balance": [-90000.0, -105000.0],  # millions -> billions
            "Shiller_PE": [40.0, 40.9],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            legacy.to_csv(path, index=False)
            result = model.cached_us_fallback(path=path)

        newest = {key: float(frame["value"].iloc[-1]) for key, frame in result.items()}
        self.assertEqual(set(newest), {
            "bondYield10y", "stockIndex", "cpiYoY", "moneySupply", "spread10y2y",
            "unemployment", "tradeBalance", "shillerPE",
        })
        expected = {
            "bondYield10y": 0.045, "stockIndex": 7545.5, "cpiYoY": 0.037, "moneySupply": 23.4,
            "spread10y2y": 37.0, "unemployment": 0.042, "tradeBalance": -105.0, "shillerPE": 40.9,
        }
        for key, value in expected.items():
            self.assertAlmostEqual(newest[key], value, msg=key)

    def test_missing_legacy_csv_means_no_fallback_rather_than_a_crash(self):
        self.assertEqual(model.cached_us_fallback(path=ROOT / "does-not-exist.csv"), {})

    def test_refreshing_comparison_forces_a_reload(self):
        with patch.object(ds, "get_comparison_data", return_value={"gdpYoY": {}}) as getter:
            self.assertEqual(model.refresh_market("comparison"), {"gdpYoY": {}})

        getter.assert_called_once_with(force=True)

    def test_comparison_borrows_a_missing_country_series_from_its_cached_market(self):
        loaded = {
            "bondYield10y": {"us": frame(["2026-10-28"], [0.0505]), "eu": ds._empty(), "uk": None},
            "cpiYoY": {"us": frame(["2026-09-01"], [0.037]), "eu": ds._empty()},
        }
        markets = {
            "eu": {"bondYield10y": frame(["2026-10-29"], [0.0337]), "cpiYoY": frame(["2026-09-01"], [0.038])},
            "uk": {"bondYield10y": frame(["2026-10-28"], [0.0531])},
        }
        with patch.object(ds, "get_comparison_data", return_value=loaded), \
                patch.object(ds, "peek_market_data", side_effect=markets.get):
            merged = model.load_comparison()

        self.assertEqual(merged["bondYield10y"]["eu"]["value"].iloc[-1], 0.0337)  # empty -> borrowed
        self.assertEqual(merged["bondYield10y"]["uk"]["value"].iloc[-1], 0.0531)  # None -> borrowed
        self.assertEqual(merged["bondYield10y"]["us"]["value"].iloc[-1], 0.0505)  # present: left alone
        self.assertEqual(merged["cpiYoY"]["eu"]["value"].iloc[-1], 0.038)
        self.assertNotIn("uk", merged["cpiYoY"])                                   # nothing to borrow
        self.assertTrue(loaded["bondYield10y"]["eu"].empty)                        # cached object untouched

    def test_borrowing_never_starts_a_download(self):
        loaded = {"gdpYoY": {"us": ds._empty()}}
        with patch.object(ds, "get_comparison_data", return_value=loaded), \
                patch.object(ds, "peek_market_data", return_value=None), \
                patch.object(ds, "get_market_data") as fetch:
            merged = model.load_comparison()

        fetch.assert_not_called()
        self.assertTrue(model.clean_series(merged["gdpYoY"]["us"]).empty)

    def test_cache_peek_sees_stale_entries_but_never_loads(self):
        cache = ds.TTLCache(ttl=0)
        self.assertIsNone(cache.peek("uk"))
        cache.get_or_load("uk", lambda: {"x": 1})

        self.assertEqual(cache.peek("uk"), {"x": 1})  # ttl=0: stale, still returned

        with patch.object(ds, "_cache", cache):
            self.assertEqual(ds.peek_market_data("uk"), {"x": 1})
            self.assertIsNone(ds.peek_market_data("eu"))


def import_classic_economy_page():
    """The classic page, imported without registering a page or touching the network."""
    seed = {"bondYield10y": frame(["2026-01-02"], [0.04])}
    empty_cache = pd.DataFrame({"Date": pd.Series(dtype="datetime64[ns]")})
    with (
        patch.object(dash, "register_page"),
        patch.object(ds, "get_market_data", return_value=seed),
        patch.object(pd, "read_csv", return_value=empty_cache),
    ):
        return importlib.import_module("pages.useconomy")


def stat_cards(row):
    """(label, value, source) for each stat card in a classic stat row."""
    cards = []
    for card in row.children:
        label, value, *source = card.children
        cards.append((label.children, value.children, source[0].children if source else None))
    return cards


class ClassicPageAgreementTests(unittest.TestCase):
    """The dashboard must report the same headline numbers as the page it sits beside."""

    @classmethod
    def setUpClass(cls):
        cls.economy = import_classic_economy_page()
        cls.series = {
            "bondYield10y": frame(["2026-10-27", "2026-10-28"], [0.0499, 0.0505]),
            "policyRate": frame(["2025-06-18", "2026-02-04"], [0.0425, 0.045]),
            "unemployment": frame(["2026-08-01", "2026-09-01"], [0.041, 0.042]),
            "cpiYoY": frame(["2026-08-01", "2026-09-01"], [0.03353, 0.037173]),
            "gdpYoY": frame(["2026-04-01", "2026-07-01"], [0.021916, 0.020657]),
            "shillerPE": frame(["2026-09-01", "2026-10-01"], [40.81, 40.88]),
        }

    def dashboard_cards(self, market):
        return [
            (kpi.label, model.snapshot(kpi, self.series.get(kpi.key)))
            for kpi in model.MARKETS[market].kpis
        ]

    def test_norway_headline_cards_match_the_classic_page(self):
        classic = stat_cards(self.economy.render_norway(self.series, date(2026, 1, 1), date(2026, 10, 30)).children[0])
        new = self.dashboard_cards("norway")

        self.assertEqual([c[0] for c in classic], [n[0] for n in new])
        for (_, classic_value, classic_source), (_, snap) in zip(classic, new):
            self.assertEqual(snap.value_text, classic_value)
            self.assertEqual(snap.as_of, classic_source)

    def test_euro_area_uk_and_us_headline_cards_match_the_classic_page(self):
        renderers = {
            "eu": lambda: self.economy.render_eu(self.series, date(2026, 1, 1), date(2026, 10, 30)).children[0],
            "uk": lambda: self.economy.render_uk(self.series, date(2026, 1, 1), date(2026, 10, 30)).children[0],
        }
        for market, render in renderers.items():
            classic = stat_cards(render())
            new = self.dashboard_cards(market)

            self.assertEqual([c[0] for c in classic], [n[0] for n in new], market)
            for (_, classic_value, classic_source), (_, snap) in zip(classic, new):
                self.assertEqual(snap.value_text, classic_value, market)
                self.assertEqual(snap.as_of, classic_source, market)

        # The US cards are built inside the page callback; reproduce its expressions.
        us = self.dashboard_cards("us")
        expected = [
            ("10Y Yield", self.economy.fmt_pct(ds.last_value(self.series["bondYield10y"]))),
            ("Unemployment", self.economy.fmt_pct(ds.last_value(self.series["unemployment"]))),
            ("CPI YoY", self.economy.fmt_pct(ds.last_value(self.series["cpiYoY"]))),
            ("Real GDP YoY", self.economy.fmt_pct(ds.last_value(self.series["gdpYoY"]))),
            ("Shiller CAPE", self.economy.fmt_num(ds.last_value(self.series["shillerPE"]), 1)),
        ]
        self.assertEqual([(label, snap.value_text) for label, snap in us], expected)


if __name__ == "__main__":
    unittest.main()
