import importlib
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import dash
import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import data_sources as ds  # noqa: E402


def frame(dates, values):
    return pd.DataFrame({"Date": pd.to_datetime(dates), "value": values})


def import_economy_page():
    """Import the page without registering a Dash page or making live calls."""
    seed = {"bondYield10y": frame(["2026-01-02"], [0.04])}
    empty_cache = pd.DataFrame({"Date": pd.Series(dtype="datetime64[ns]")})
    with (
        patch.object(dash, "register_page"),
        patch.object(ds, "get_market_data", return_value=seed),
        patch.object(pd, "read_csv", return_value=empty_cache),
    ):
        return importlib.import_module("pages.useconomy")


economy = import_economy_page()


class EconomyPageFigureTests(unittest.TestCase):
    def test_comparison_filters_every_trace_to_selected_ytd_window(self):
        series = {
            "us": frame(
                ["2025-12-01", "2026-01-01", "2026-04-01", "2026-10-01"],
                [0.01, 0.02, 0.03, 0.04],
            ),
            "uk": frame(
                ["2025-10-01", "2026-01-01", "2026-07-01", "2027-01-01"],
                [0.005, 0.006, 0.007, 0.008],
            ),
        }

        figure = economy.create_comparison_figure(
            "GDP",
            "Year-over-year change",
            series,
            "%",
            ["us", "uk"],
            starts=date(2026, 1, 1),
            ends=date(2026, 9, 30),
        )

        self.assertEqual({trace.name for trace in figure.data}, {"US", "UK"})
        for trace in figure.data:
            plotted = pd.to_datetime(list(trace.x))
            self.assertGreaterEqual(plotted.min(), pd.Timestamp("2026-01-01"))
            self.assertLessEqual(plotted.max(), pd.Timestamp("2026-09-30"))

    def test_comparison_does_not_extend_a_series_to_another_series_endpoint(self):
        series = {
            "us": frame(
                ["2026-01-01", "2026-02-01", "2026-03-01"],
                [0.02, 0.021, 0.022],
            ),
            "uk": frame(
                ["2026-01-01", "2026-02-01"],
                [0.01, 0.011],
            ),
        }

        figure = economy.create_comparison_figure(
            "GDP", "YoY", series, "%", ["us", "uk"]
        )
        traces = {trace.name: trace for trace in figure.data}

        self.assertEqual(pd.to_datetime(traces["US"].x[-1]), pd.Timestamp("2026-03-01"))
        self.assertEqual(pd.to_datetime(traces["UK"].x[-1]), pd.Timestamp("2026-02-01"))
        self.assertEqual(len(traces["UK"].x), 2)

    def test_comparison_discloses_a_selected_country_with_no_data(self):
        series = {
            "us": frame(["2026-01-01", "2026-02-01"], [0.02, 0.021]),
            "uk": frame([], []),
        }

        figure = economy.create_comparison_figure(
            "GDP",
            "YoY",
            series,
            "%",
            ["us", "uk"],
            starts=date(2026, 1, 1),
            ends=date(2026, 12, 31),
        )

        self.assertEqual([trace.name for trace in figure.data], ["US"])
        annotation_text = " ".join(annotation.text for annotation in figure.layout.annotations)
        self.assertIn("Unavailable in selected range", annotation_text)
        self.assertIn("UK", annotation_text)

    def test_single_point_percent_chart_has_sane_bounds_and_visible_zero(self):
        figure = economy.create_graph(
            economy.CHART_COLORS["green"],
            "Year-over-year change",
            "UK Real GDP Growth",
            frame(["2026-01-01"], [0.009]),
            "value",
            "%",
            date(2026, 1, 1),
            date(2026, 12, 31),
            hline0=True,
        )

        lower, upper = figure.layout.yaxis.range
        self.assertLessEqual(lower, 0)
        self.assertGreaterEqual(upper, 0)
        self.assertLess(upper - lower, 0.05)
        self.assertEqual(figure.data[0].mode, "markers")
        self.assertTrue(
            any(shape.y0 == 0 and shape.y1 == 0 for shape in figure.layout.shapes)
        )

    def test_observation_date_helpers_format_monthly_and_daily_sources(self):
        monthly = frame(["2025-12-01", "2026-02-01"], [0.02, 0.025])
        daily = frame(["2026-02-14", "2026-02-15"], [0.03, 0.031])

        self.assertEqual(
            economy.last_observation_date(monthly), pd.Timestamp("2026-02-01")
        )
        self.assertEqual(economy.source_as_of("FRED", monthly), "FRED · Feb 2026")
        self.assertEqual(
            economy.source_as_of("Bank of England", daily),
            "Bank of England · 15 Feb 2026",
        )
        self.assertEqual(economy.source_as_of("SSB", frame([], [])), "SSB")

    def test_quarterly_observations_use_financial_period_labels(self):
        quarterly = frame(["2026-04-01"], [0.012])
        figure = economy.create_graph(
            economy.CHART_COLORS["green"],
            "Year-over-year change, quarterly",
            "UK Real GDP Growth",
            quarterly,
            "value",
            "%",
            date(2026, 1, 1),
            date(2026, 12, 31),
            period="quarter",
        )

        self.assertEqual(figure.data[0].customdata[0], "Q2 2026")
        self.assertIn("Q2 2026", figure.layout.annotations[0].text)
        self.assertEqual(list(figure.layout.xaxis.ticktext), ["Q2 2026"])
        self.assertEqual(
            economy.source_as_of("ONS", quarterly, "quarter"), "ONS · Q2 2026"
        )

    def test_comparison_preserves_each_country_gdp_frequency_label(self):
        figure = economy.create_comparison_figure(
            "Real GDP Growth",
            "Year-over-year change",
            {
                "us": frame(["2026-04-01"], [0.02]),
                "norway": frame(["2026-06-01"], [0.067]),
            },
            "%",
            ["us", "norway"],
            period={
                "us": "quarter",
                "norway": "month",
            },
        )
        traces = {trace.name: trace for trace in figure.data}

        self.assertEqual(traces["US"].customdata[0], "Q2 2026")
        self.assertEqual(traces["Norway"].customdata[0], "Jun 2026")

    def test_manual_refresh_only_reloads_us_when_us_tab_is_active(self):
        self.assertTrue(economy.should_refresh_us("refresh-button", "us"))
        self.assertFalse(economy.should_refresh_us("refresh-button", "uk"))
        self.assertTrue(
            economy.should_refresh_us("interval-component-economy", "uk")
        )


if __name__ == "__main__":
    unittest.main()
