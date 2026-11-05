import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from drawdown_chart import create_drawdown_figure  # noqa: E402


class DrawdownChartTests(unittest.TestCase):
    def figure(self, daily_returns):
        dates = pd.bdate_range('2026-01-02', periods=len(daily_returns))
        return create_drawdown_figure(pd.Series(daily_returns, index=dates))

    def test_current_loss_and_maximum_are_distinct_after_partial_recovery(self):
        fig = self.figure([0.10, -0.20, 0.10])
        self.assertAlmostEqual(fig.data[0].y[-1], -0.12)
        self.assertAlmostEqual(fig.layout.shapes[0].y0, -0.20)
        self.assertEqual(fig.layout.shapes[0].line.dash, 'dash')
        self.assertIn('Current: -12.00%', fig.layout.annotations[0].text)
        self.assertIn('Window max: -20.00%', fig.layout.annotations[1].text)
        current = next(trace for trace in fig.data if trace.name == 'Current drawdown')
        self.assertAlmostEqual(current.y[0], -0.12)

    def test_first_day_loss_counts_against_opening_capital(self):
        fig = self.figure([-0.10, -0.10])
        self.assertAlmostEqual(fig.data[0].y[0], -0.10)
        self.assertAlmostEqual(fig.data[0].y[-1], -0.19)
        self.assertIn('opening capital', fig.layout.annotations[0].text)

    def test_recovery_to_new_peak_resets_current_drawdown(self):
        fig = self.figure([0.10, -0.20, 0.30])
        self.assertEqual(fig.data[0].y[-1], 0.0)
        self.assertAlmostEqual(fig.layout.shapes[0].y0, -0.20)
        self.assertIn('Current: 0.00%', fig.layout.annotations[0].text)
        self.assertNotIn('Current drawdown episode', [trace.name for trace in fig.data])

    def test_flat_single_observation_and_empty_windows_are_readable(self):
        for returns in ([0.0], [-0.1], []):
            with self.subTest(returns=returns):
                fig = self.figure(returns)
                self.assertTrue(fig.layout.xaxis.fixedrange)
                self.assertTrue(fig.layout.yaxis.fixedrange)
                if returns:
                    self.assertEqual(fig.data[0].mode, 'lines+markers')
                    low, high = fig.layout.yaxis.range
                    self.assertLess(low, high)
                else:
                    self.assertIn('No drawdown data', fig.layout.annotations[0].text)


if __name__ == '__main__':
    unittest.main()
