import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import data_sources as ds


def frame(dates, values):
    return pd.DataFrame({"Date": pd.to_datetime(dates), "value": values})


class EconomyCacheTests(unittest.TestCase):
    def test_force_refresh_preserves_last_good_frames_from_partial_result(self):
        cache = ds.TTLCache(ttl=3600)
        original_yield = frame(["2026-01-01"], [0.04])
        original_gdp = frame(["2026-01-01"], [0.02])
        initial = {
            "bondYield10y": original_yield,
            "gdpYoY": original_gdp,
            "countries": {
                "germany": {
                    "gdpYoY": frame(["2026-01-01"], [0.01]),
                    "stockIndex": frame(["2026-01-02"], [20_000]),
                }
            },
        }
        cache.get_or_load("eu", lambda: initial)

        refreshed_yield = frame(["2026-02-01"], [0.041])
        partial = {
            "bondYield10y": refreshed_yield,
            "gdpYoY": ds._empty(),
            "countries": {
                "germany": {
                    "gdpYoY": ds._empty(),
                    "stockIndex": frame(["2026-02-02"], [21_000]),
                }
            },
        }
        result = cache.get_or_load("eu", lambda: partial, force=True)

        pd.testing.assert_frame_equal(result["bondYield10y"], refreshed_yield)
        pd.testing.assert_frame_equal(result["gdpYoY"], original_gdp)
        pd.testing.assert_frame_equal(
            result["countries"]["germany"]["gdpYoY"],
            initial["countries"]["germany"]["gdpYoY"],
        )
        pd.testing.assert_frame_equal(
            result["countries"]["germany"]["stockIndex"],
            partial["countries"]["germany"]["stockIndex"],
        )

    def test_force_bypasses_a_fresh_cache_entry(self):
        cache = ds.TTLCache(ttl=3600)
        loader = Mock(
            side_effect=[
                {"value": frame(["2026-01-01"], [1.0])},
                {"value": frame(["2026-02-01"], [2.0])},
            ]
        )

        first = cache.get_or_load("market", loader)
        cached = cache.get_or_load("market", loader)
        forced = cache.get_or_load("market", loader, force=True)

        self.assertEqual(loader.call_count, 2)
        pd.testing.assert_frame_equal(cached["value"], first["value"])
        self.assertEqual(forced["value"]["value"].iloc[-1], 2.0)


if __name__ == "__main__":
    unittest.main()
