import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from portfolio_history import (
    build_combined_performance,
    calculate_max_drawdown,
    calculate_strategy_max_drawdown,
    convert_cumulative_returns_to_nok,
    get_training_dates,
    load_training_returns,
)


class PortfolioHistoryTests(unittest.TestCase):
    def test_attached_history_has_expected_boundaries_and_values(self):
        history_2015 = load_training_returns("2015")
        history_2020 = load_training_returns("2020")

        self.assertEqual(get_training_dates("2015"), (pd.Timestamp("2014-12-31"), pd.Timestamp("2024-12-31")))
        self.assertEqual(get_training_dates("2020"), (pd.Timestamp("2019-12-31"), pd.Timestamp("2024-12-31")))
        self.assertAlmostEqual(history_2015.iloc[-1, 0], 16.2202)
        self.assertAlmostEqual(history_2020.iloc[-1, 0], 3.45)

    def test_testing_is_spliced_after_training_without_resetting_growth(self):
        testing = pd.DataFrame(
            {
                "Portfolio_Return": [0.50, 0.10, -0.20],
                "ACWI_Return": [0.50, 0.05, -0.10],
            },
            index=pd.to_datetime(["2024-12-31", "2025-01-02", "2025-01-03"]),
        )

        combined, training_end = build_combined_performance("2020", testing)

        self.assertEqual(training_end, pd.Timestamp("2024-12-31"))
        self.assertNotIn(pd.Timestamp("2024-12-31"), combined[combined["Phase"] == "Testing"].index)
        self.assertAlmostEqual(
            combined.loc[pd.Timestamp("2025-01-02"), "Portfolio_Cumulative_Period"],
            (1 + 3.45) * 1.10 - 1,
        )
        self.assertAlmostEqual(
            combined.loc[pd.Timestamp("2025-01-03"), "Portfolio_Cumulative_Period"],
            (1 + 3.45) * 1.10 * 0.80 - 1,
        )

    def test_max_drawdown_uses_authoritative_training_floor(self):
        testing = pd.DataFrame(
            {"Portfolio_Return": [0.10], "ACWI_Return": [0.10]},
            index=pd.to_datetime(["2025-01-02"]),
        )
        combined, _ = build_combined_performance("2020", testing)
        self.assertAlmostEqual(calculate_strategy_max_drawdown("2020", combined), 0.3486)

    def test_larger_testing_drawdown_overrides_training_floor(self):
        testing = pd.DataFrame(
            {
                "Portfolio_Return": [0.10, -0.40],
                "ACWI_Return": [0.10, -0.10],
            },
            index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
        )
        combined, _ = build_combined_performance("2020", testing)
        self.assertAlmostEqual(calculate_strategy_max_drawdown("2020", combined), 0.40)

    def test_drawdown_includes_initial_capital_peak(self):
        self.assertAlmostEqual(calculate_max_drawdown(pd.Series([-0.10, 0.05])), 0.10)

    def test_nok_conversion_compounds_usd_return_and_fx_change(self):
        cumulative = pd.Series(
            [0.10, 0.21],
            index=pd.to_datetime(["2020-01-31", "2020-02-29"]),
        )
        fx = pd.Series(
            [10.0, 11.0, 12.0],
            index=pd.to_datetime(["2019-12-31", "2020-01-31", "2020-02-28"]),
        )

        converted = convert_cumulative_returns_to_nok(cumulative, fx)

        self.assertAlmostEqual(converted.iloc[0], 1.10 * 1.10 - 1)
        self.assertAlmostEqual(converted.iloc[1], 1.21 * 1.20 - 1)


if __name__ == "__main__":
    unittest.main()
