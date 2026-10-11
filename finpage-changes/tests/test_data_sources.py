import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import data_sources as ds


def frame(dates, values):
    return pd.DataFrame({"Date": pd.to_datetime(dates), "value": values})


class EconomyDataSourceTests(unittest.TestCase):
    def test_eurostat_cpi_uses_changing_composition_annual_rate(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "dimension": {
                "time": {"category": {"index": {"2026-07": 0, "2026-08": 1}}}
            },
            "value": {"0": 3.0, "1": 3.2},
        }

        with patch.object(ds.requests, "get", return_value=response) as get:
            result = ds.fetch_eurostat_eu_cpi_yoy("2026-01-01")

        self.assertIn("prc_hicp_minr", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["geo"], "EA")
        self.assertEqual(get.call_args.kwargs["params"]["unit"], "RCH_A")
        self.assertEqual(result["Date"].iloc[-1], pd.Timestamp("2026-08-01"))
        self.assertAlmostEqual(result["value"].iloc[-1], 0.032)

    def test_eurostat_gdp_parses_quarters_and_published_yoy_rate(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "dimension": {
                "time": {"category": {"index": {"2026-Q1": 0, "2026-Q2": 1}}}
            },
            "value": {"0": 0.6, "1": 1.2},
        }

        with patch.object(ds.requests, "get", return_value=response) as get:
            result = ds.fetch_eurostat_eu_gdp_yoy("2026-01-01")

        self.assertIn("namq_10_gdp", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["params"]["geo"], "EA")
        self.assertEqual(get.call_args.kwargs["params"]["unit"], "CLV_PCH_SM")
        self.assertEqual(
            result["Date"].tolist(),
            [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-04-01")],
        )
        self.assertAlmostEqual(result["value"].iloc[-1], 0.012)

    def test_uk_gdp_uses_current_pn2_release_dataset(self):
        expected = frame(["2026-04-01"], [1.2])
        with patch.object(ds, "_ons_series", return_value=expected) as loader:
            result = ds.fetch_ons_uk_gdp_yoy()

        loader.assert_called_once_with(
            "economy/grossdomesticproductgdp", "ihyr", "pn2"
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_boe_daily_gilt_yield_is_normalized_to_fraction(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = "DATE,IUDMNPY\n17 Sep 2026,5.1742\n"

        with patch.object(ds.requests, "get", return_value=response) as get:
            result = ds.fetch_boe_uk_yield10y("2026-01-01")

        self.assertEqual(get.call_args.kwargs["params"]["SeriesCodes"], "IUDMNPY")
        self.assertEqual(result["Date"].iloc[-1], pd.Timestamp("2026-09-17"))
        self.assertAlmostEqual(result["value"].iloc[-1], 0.051742)

    def test_ecb_deposit_rate_keeps_changes_and_latest_as_of_date(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = (
            "TIME_PERIOD,OBS_VALUE\n"
            "2026-01-01,2.75\n"
            "2026-06-01,2.50\n"
            "2026-09-22,2.50\n"
        )

        with patch.object(ds.requests, "get", return_value=response):
            result = ds.fetch_ecb_deposit_rate("2026-01-01")

        self.assertEqual(
            result["Date"].tolist(),
            [
                pd.Timestamp("2026-01-01"),
                pd.Timestamp("2026-06-01"),
                pd.Timestamp("2026-09-22"),
            ],
        )
        self.assertAlmostEqual(result["value"].iloc[-1], 0.025)

    def test_norway_gdp_uses_current_monthly_ssb_yoy_table(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "dimension": {
                "Tid": {"category": {"index": {"2025M03": 0, "2026M03": 1}}}
            },
            "value": [0.5, 1.2],
        }

        with patch.object(ds.requests, "post", return_value=response) as post:
            result = ds.fetch_ssb_gdp()

        self.assertIn("11721", post.call_args.args[0])
        self.assertEqual(
            result["Date"].tolist(),
            [pd.Timestamp("2025-03-01"), pd.Timestamp("2026-03-01")],
        )
        self.assertAlmostEqual(result["value"].iloc[-1], 0.012)

    def test_monthly_yoy_uses_calendar_month_when_an_observation_is_missing(self):
        source = frame(
            [
                "2024-01-01",
                "2024-02-01",
                "2024-04-01",
                "2025-01-01",
                "2025-02-01",
                "2025-04-01",
            ],
            [100, 200, 400, 110, 240, 500],
        )

        result = ds.yoy_change(source, 12).set_index("Date")["value"]

        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-01-01")], 0.10)
        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-02-01")], 0.20)
        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-04-01")], 0.25)

    def test_quarterly_yoy_uses_matching_calendar_quarter(self):
        source = frame(
            [
                "2024-01-01",
                "2024-04-01",
                "2024-10-01",
                "2025-01-01",
                "2025-04-01",
                "2025-10-01",
            ],
            [100, 120, 160, 102, 126, 168],
        )

        result = ds.yoy_change(source, 4).set_index("Date")["value"]

        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-01-01")], 0.02)
        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-04-01")], 0.05)
        self.assertAlmostEqual(result.loc[pd.Timestamp("2025-10-01")], 0.05)

    def test_us_loader_normalizes_financial_display_units(self):
        values = {
            "yield": frame(["2026-08-14"], [4.68]),
            "stock": frame(["2026-08-14"], [7785.76]),
            "cpi": frame(["2025-07-01", "2026-07-01"], [322.132, 332.813]),
            "money": frame(["2026-06-01"], [23155.2]),
            "spread": frame(["2026-08-14"], [0.51]),
            "unemployment": frame(["2026-07-01"], [4.1]),
            "trade": frame(["2026-06-01"], [-73261]),
            "gdp": frame(["2025-04-01", "2026-04-01"], [23770.976, 24270.599]),
            "interest": frame(["2026-04-01"], [1247.033]),
            "revenue": frame(["2026-04-01"], [5872.497]),
            "shiller": frame(["2026-08-14"], [42.56]),
        }

        with patch.object(ds, "parallel_fetch", return_value=values):
            result = ds.load_us_economy()

        self.assertAlmostEqual(ds.last_value(result["bondYield10y"]), 0.0468)
        self.assertAlmostEqual(ds.last_value(result["spread10y2y"]), 51.0)
        self.assertAlmostEqual(ds.last_value(result["unemployment"]), 0.041)
        self.assertAlmostEqual(ds.last_value(result["tradeBalance"]), -73.261)
        self.assertAlmostEqual(ds.last_value(result["moneySupply"]), 23.1552)
        self.assertAlmostEqual(
            ds.last_value(result["cpiYoY"]),
            332.813 / 322.132 - 1,
        )
        self.assertAlmostEqual(
            ds.last_value(result["interestToRevenue"]),
            1247.033 / 5872.497,
        )

    def test_comparison_keeps_normalized_eurostat_rates_at_display_scale(self):
        direct_eu = {
            "gdp": frame(["2026-04-01"], [0.012]),
            "cpi": frame(["2026-08-01"], [0.032]),
            "yield": frame(["2026-09-18"], [3.5]),
            "unemployment": frame(["2026-07-01"], [0.064]),
        }
        empty_market = {
            "gdp": ds._empty(),
            "cpi": ds._empty(),
            "yield": ds._empty(),
            "unemployment": ds._empty(),
        }

        with patch.object(
            ds,
            "parallel_fetch",
            side_effect=[empty_market, direct_eu, empty_market, empty_market],
        ):
            result = ds.load_comparison_data()

        self.assertAlmostEqual(ds.last_value(result["gdpYoY"]["eu"]), 0.012)
        self.assertAlmostEqual(ds.last_value(result["cpiYoY"]["eu"]), 0.032)
        self.assertAlmostEqual(
            ds.last_value(result["unemployment"]["eu"]), 0.064
        )


if __name__ == "__main__":
    unittest.main()
