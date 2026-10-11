import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dash
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import algorithm_data  # noqa: E402
from portfolio_history import build_combined_performance, get_training_dates  # noqa: E402


def load_page(filename):
    """Execute a page module without an app, capturing its register_page call."""
    path = SRC / "pages" / filename
    spec = importlib.util.spec_from_file_location(f"_test_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(dash, "register_page") as register_page:
        spec.loader.exec_module(module)
    return module, register_page


# Loaded once: executing the module registers its callback on Dash's global list.
dashboard, dashboard_register = load_page("algorithm_dashboard.py")
home, _ = load_page("home.py")


def walk_components(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "to_plotly_json"):
                yield from walk_components(child)
    elif hasattr(children, "to_plotly_json"):
        yield from walk_components(children)


def text_of(component):
    """Concatenate all string children below a component."""
    parts = []
    for node in walk_components(component):
        children = getattr(node, "children", None)
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, (list, tuple)):
            parts.extend(child for child in children if isinstance(child, str))
    return " ".join(parts)


class RoutingTests(unittest.TestCase):
    def test_dashboard_is_registered_at_its_own_path(self):
        self.assertEqual(dashboard_register.call_args.kwargs["path"], "/algorithm-dashboard")

    def test_classic_algorithm_page_keeps_the_portfolio_daily_path(self):
        source = (SRC / "pages" / "algorithm.py").read_text(encoding="utf-8")

        self.assertRegex(
            source, r"register_page\(__name__,\s*path='/portfolio-daily'\)"
        )

    def test_navigation_algorithm_link_opens_the_dashboard(self):
        source = (SRC / "app.py").read_text(encoding="utf-8")

        self.assertRegex(source, r'"Algorithm",\s*href="/algorithm-dashboard"')
        self.assertNotRegex(source, r'"Algorithm",\s*href="/portfolio-daily"')

    def test_home_algorithm_card_opens_the_dashboard(self):
        links = {
            component.href: text_of(component)
            for component in walk_components(home.layout)
            if getattr(component, "href", None)
        }

        self.assertIn("/algorithm-dashboard", links)
        self.assertIn("Algorithm", links["/algorithm-dashboard"])
        self.assertNotIn("/portfolio-daily", links)


class DashboardWiringTests(unittest.TestCase):
    def test_every_callback_id_exists_in_the_layout(self):
        from dash import _callback

        layout_ids = {
            component.id
            for component in walk_components(dashboard.layout)
            if isinstance(getattr(component, "id", None), str)
        }
        entry = next(
            item for item in _callback.GLOBAL_CALLBACK_LIST
            if "ad-kpis.children" in item["output"]
        )
        output_ids = {
            part.rsplit(".", 1)[0]
            for part in entry["output"].strip(".").split("...")
        }
        input_ids = {item["id"] for item in entry["inputs"] + entry["state"]}

        self.assertEqual((output_ids | input_ids) - layout_ids, set())
        self.assertEqual(len(entry["output"].strip(".").split("...")), 11)

    def test_layout_switch_is_wired_client_side_to_the_page_root(self):
        from dash import _callback

        layout_ids = {
            component.id
            for component in walk_components(dashboard.layout)
            if isinstance(getattr(component, "id", None), str)
        }
        entry = next(
            item for item in _callback.GLOBAL_CALLBACK_LIST
            if item["output"] == "ad-page.className"
        )

        self.assertEqual(
            entry["clientside_function"],
            {"namespace": "algorithm_dashboard", "function_name": "set_layout"},
        )
        self.assertEqual([item["id"] for item in entry["inputs"]], ["ad-view"])
        self.assertTrue({"ad-page", "ad-view"} <= layout_ids)

    def test_stylesheet_only_uses_defined_custom_properties(self):
        css = (SRC / "assets" / "algorithm-dashboard.css").read_text(encoding="utf-8")
        shared = (SRC / "assets" / "custom.css").read_text(encoding="utf-8")
        defined = set(re.findall(r"(--[\w-]+)\s*:", css + shared))
        used = set(re.findall(r"var\((--[\w-]+)", css))

        self.assertEqual(used - defined, set())


class LayoutSwitchTests(unittest.TestCase):
    SCRIPT = SRC / "assets" / "algorithm-dashboard.js"
    STYLESHEET = SRC / "assets" / "algorithm-dashboard.css"

    @staticmethod
    def find(component_id):
        return next(
            component
            for component in walk_components(dashboard.layout)
            if getattr(component, "id", None) == component_id
        )

    @classmethod
    def stylesheet(cls):
        """The stylesheet without comments, so selectors can be searched safely."""
        css = cls.STYLESHEET.read_text(encoding="utf-8")
        return re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def test_page_starts_in_the_dashboard_layout(self):
        root = dashboard.layout

        self.assertEqual(root.id, "ad-page")
        self.assertEqual(root.className, "ad-page ad-page--dashboard")
        self.assertEqual(dashboard.DEFAULT_VIEW, "dashboard")

    def test_layout_radio_offers_dashboard_and_scroll_and_remembers_the_choice(self):
        radio = self.find("ad-view")

        self.assertEqual(radio.value, "dashboard")
        self.assertEqual([option["value"] for option in radio.options], ["dashboard", "scroll"])
        self.assertTrue(radio.persistence)
        self.assertEqual(radio.persistence_type, "local")

    def test_script_maps_the_choice_to_a_page_class_and_defaults_to_dashboard(self):
        script = self.SCRIPT.read_text(encoding="utf-8")

        self.assertIn("window.dash_clientside.algorithm_dashboard", script)
        self.assertIn("set_layout", script)
        self.assertIn('view === "scroll" ? "scroll" : "dashboard"', script)
        self.assertIn('"ad-page ad-page--" + mode', script)
        self.assertIn('new Event("resize")', script)

    def test_scrolling_layout_follows_the_graph_controls_results_order(self):
        # Only the base rules (before the first @media) define the scrolling order.
        css = self.stylesheet()
        base = css[: css.index("@media")]
        order = {
            name: int(value)
            for name, value in re.findall(r"\.(ad-[\w-]+)\s*\{\s*order:\s*(\d+);", base)
        }
        sequence = [
            "ad-title-block",
            "ad-chart-card--full",
            "ad-controls",
            "ad-chart-card--period",
            "ad-kpis",
            "ad-composition-card",
            "ad-about-card",
        ]

        self.assertEqual([order[name] for name in sequence], sorted(order[name] for name in sequence))
        self.assertEqual(len({order[name] for name in sequence}), len(sequence))

    def test_dashboard_rules_only_apply_on_screens_that_can_hold_the_dashboard(self):
        css = self.stylesheet()
        desktop_query = css.index("@media (min-width: 1180px) and (min-height: 601px)")

        # Base rules are the scrolling layout, so narrow/short screens get it.
        self.assertGreater(css.index(".ad-page--dashboard"), desktop_query)
        self.assertGreater(css.index(".ad-view-control {\n    display: block;"), desktop_query)
        self.assertIn(".ad-view-control {\n  display: none;", css[:desktop_query])

    def test_option_pills_hang_off_markup_that_dash_3_and_4_share(self):
        # Production pins Dash 3 (requirements.txt), whose radios are plain
        # <label><input> pairs with no ".selected" class or wrapper spans.
        css = self.stylesheet()

        self.assertRegex(
            css, r"\.ad-seg(?:\.ad-seg)*\s*>\s*label:has\(input:checked\)"
        )
        self.assertNotRegex(css, r"\.dash-options-list-option(?:\.selected|:hover)")
        self.assertNotIn(".ad-seg .dash-options-list-option {", css)

    def test_hero_and_about_both_receive_the_description(self):
        bundle = UpdateDashboardTests.synthetic_bundle()
        with patch.object(dashboard, "get_dashboard_data", return_value=bundle):
            ok = dashboard.update_dashboard("2015", "testing", "USD")
        with patch.object(dashboard, "get_dashboard_data", side_effect=RuntimeError("down")):
            failed = dashboard.update_dashboard("2015", "testing", "USD")

        for outputs in (ok, failed):
            self.assertEqual(len(outputs), 11)
            self.assertEqual(outputs[10], outputs[8])
            self.assertIn("2015-2024", outputs[10])

    def test_kpi_cards_carry_their_explanation_for_the_scrolling_layout(self):
        card = dashboard._kpi_card("Max drawdown", "34.9%", "Training + testing", tip="Worst loss.")
        classes = [getattr(child, "className", "") for child in card.children]

        self.assertIn("ad-kpi-note", classes)
        self.assertEqual(card.children[-1].children, "Worst loss.")
        self.assertEqual(card.title, "Worst loss.")
        self.assertNotIn(
            "ad-kpi-note",
            [getattr(child, "className", "") for child in dashboard._kpi_card("X").children],
        )


class DashboardCacheTests(unittest.TestCase):
    def setUp(self):
        algorithm_data._cache.clear()
        self.addCleanup(algorithm_data._cache.clear)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workbook = Path(directory.name) / "AlgoComposition.xlsx"
        self.workbook.write_bytes(b"version-1")
        patcher = patch.object(
            algorithm_data, "get_workbook_path", return_value=self.workbook
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def fresh_bundle(*args, **kwargs):
        return {"complete": True, "token": object()}

    def test_repeated_calls_reuse_the_cached_bundle(self):
        with patch.object(
            algorithm_data, "_build_bundle", side_effect=self.fresh_bundle
        ) as build:
            first = algorithm_data.get_dashboard_data("2020", "USD")
            second = algorithm_data.get_dashboard_data("2020", "USD")

        self.assertIs(first, second)
        build.assert_called_once()

    def test_currencies_and_windows_are_cached_separately(self):
        with patch.object(
            algorithm_data, "_build_bundle", side_effect=self.fresh_bundle
        ) as build:
            usd = algorithm_data.get_dashboard_data("2020", "USD")
            nok = algorithm_data.get_dashboard_data("2020", "NOK")
            other_window = algorithm_data.get_dashboard_data("2015", "USD")

        self.assertEqual(build.call_count, 3)
        self.assertIsNot(usd, nok)
        self.assertIsNot(usd, other_window)

    def test_a_changed_workbook_is_reloaded_instead_of_served_stale(self):
        with patch.object(
            algorithm_data, "_build_bundle", side_effect=self.fresh_bundle
        ) as build:
            before = algorithm_data.get_dashboard_data("2020", "USD")

            # What an algo-helper save does: a new file replaces the cached one.
            self.workbook.write_bytes(b"version-2, with a different size")
            stat = self.workbook.stat()
            os.utime(self.workbook, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))

            after = algorithm_data.get_dashboard_data("2020", "USD")

        self.assertEqual(build.call_count, 2)
        self.assertIsNot(before, after)
        self.assertEqual(len(algorithm_data._cache), 1)

    def test_incomplete_downloads_are_returned_but_never_cached(self):
        bundles = [
            {"complete": False, "token": "partial"},
            {"complete": True, "token": "full"},
        ]
        with patch.object(algorithm_data, "_build_bundle", side_effect=bundles):
            partial = algorithm_data.get_dashboard_data("2020", "USD")
            full = algorithm_data.get_dashboard_data("2020", "USD")

        self.assertEqual(partial["token"], "partial")
        self.assertEqual(full["token"], "full")

    def test_loader_errors_are_not_cached(self):
        outcomes = [RuntimeError("yahoo down"), {"complete": True, "token": "ok"}]
        with patch.object(algorithm_data, "_build_bundle", side_effect=outcomes):
            with self.assertRaises(RuntimeError):
                algorithm_data.get_dashboard_data("2020", "USD")
            recovered = algorithm_data.get_dashboard_data("2020", "USD")

        self.assertEqual(recovered["token"], "ok")


class BuildBundleTests(unittest.TestCase):
    @staticmethod
    def loaded(symbols):
        returns = pd.DataFrame(columns=["Date", "Symbol", "Return"])
        composition = pd.DataFrame({"Symbol": ["AAA", "BBB"]})
        symbol_frame = pd.DataFrame(
            {"Date": pd.Timestamp("2026-01-02"), "Symbol": symbols, "Return": 0.0}
        )
        # An empty portfolio frame short-circuits before the combined history.
        return returns.set_index("Date"), symbol_frame, composition, None

    def test_a_dropped_ticker_triggers_one_retry(self):
        attempts = [self.loaded(["AAA"]), self.loaded(["AAA", "BBB"])]
        with patch.object(algorithm_data, "load_returns", side_effect=attempts) as load:
            bundle = algorithm_data._build_bundle("2020", "USD")

        self.assertEqual(load.call_count, 2)
        self.assertTrue(bundle["complete"])

    def test_persistently_missing_tickers_are_flagged_incomplete(self):
        with patch.object(
            algorithm_data, "load_returns", side_effect=lambda *a: self.loaded(["AAA"])
        ) as load:
            bundle = algorithm_data._build_bundle("2020", "USD")

        self.assertEqual(load.call_count, 2)
        self.assertFalse(bundle["complete"])


class PerformanceFigureTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2025-01-02", periods=30)
        self.frame = pd.DataFrame({
            "Date": self.dates,
            "Portfolio_Cumulative_Period": np.linspace(0.0, 0.5, 30),
            "ACWI_Cumulative_Period": np.linspace(0.0, 0.1, 30),
        })

    def test_draws_both_series_with_end_labels_and_locked_navigation(self):
        fig = dashboard._performance_figure(self.frame)

        lines = [trace.name for trace in fig.data if trace.mode == "lines"]
        labels = [annotation.text for annotation in fig.layout.annotations]

        self.assertEqual(lines, ["Portfolio", "ACWI"])
        self.assertIn("<b>+50.0%</b>", labels)
        self.assertIn("<b>+10.0%</b>", labels)
        self.assertTrue(fig.layout.xaxis.fixedrange)
        self.assertTrue(fig.layout.yaxis.fixedrange)
        self.assertFalse(fig.layout.dragmode)
        self.assertEqual(pd.Timestamp(fig.layout.xaxis.range[1]), self.dates[-1])

    def test_training_region_is_marked_only_when_the_boundary_is_inside_the_window(self):
        inside = dashboard._performance_figure(self.frame, training_end=self.dates[10])
        before = dashboard._performance_figure(
            self.frame, training_end=self.dates[0] - pd.Timedelta(days=5)
        )
        none = dashboard._performance_figure(self.frame)

        self.assertEqual({shape.type for shape in inside.layout.shapes}, {"rect", "line"})
        self.assertEqual(len(before.layout.shapes), 0)
        self.assertEqual(len(none.layout.shapes), 0)

    def test_empty_window_renders_a_message_instead_of_failing(self):
        fig = dashboard._performance_figure(self.frame.iloc[0:0])

        self.assertEqual(len(fig.data), 0)
        self.assertIn("No data", fig.layout.annotations[0].text)


class UpdateDashboardTests(unittest.TestCase):
    DAILY_PORTFOLIO = 0.001
    DAILY_BENCHMARK = 0.0005

    @classmethod
    def synthetic_bundle(cls, sheet="2020", days=300):
        _, training_end = get_training_dates(sheet)
        dates = pd.bdate_range(training_end + pd.Timedelta(days=1), periods=days)
        portfolio_returns = pd.DataFrame(
            {"Portfolio_Return": cls.DAILY_PORTFOLIO, "ACWI_Return": cls.DAILY_BENCHMARK},
            index=pd.DatetimeIndex(dates, name="Date"),
        )
        combined, training_end = build_combined_performance(sheet, portfolio_returns)

        symbols = {"AAA": 0.002, "BBB": -0.001}
        full_symbol_df = pd.concat([
            pd.DataFrame({"Date": dates, "Symbol": symbol, "Return": daily})
            for symbol, daily in symbols.items()
        ], ignore_index=True)
        composition = pd.DataFrame({
            "Symbol": list(symbols),
            "Company": ["Alpha <Corp> & Co", "Beta Inc"],
            "Weight": 0.5,
            "ValidFrom": dates[0],
            "ValidTo": pd.Timestamp("2050-12-24"),
        })
        return {
            "portfolio_returns": portfolio_returns,
            "full_symbol_df": full_symbol_df,
            "composition": composition,
            "combined_performance": combined,
            "training_end": training_end,
            "today": dates[-1],
            "complete": True,
        }

    @staticmethod
    def kpi_values(outputs):
        return {
            text_of(kpi.children[0]): text_of(kpi.children[1])
            for kpi in outputs[0]
        }

    def test_testing_window_compounds_every_daily_testing_return(self):
        bundle = self.synthetic_bundle()
        with patch.object(dashboard, "get_dashboard_data", return_value=bundle):
            outputs = dashboard.update_dashboard("2020", "testing", "USD")

        days = len(bundle["portfolio_returns"])
        values = self.kpi_values(outputs)
        expected = (1 + self.DAILY_PORTFOLIO) ** days - 1
        benchmark = (1 + self.DAILY_BENCHMARK) ** days - 1

        self.assertEqual(values["Testing period return"], f"{expected:+.1%}")
        self.assertEqual(values["ACWI benchmark"], f"{benchmark:+.1%}")
        self.assertEqual(values["Annualized volatility"], "0.0%")
        self.assertEqual(len(outputs), 11)
        self.assertIn("Testing period performance", outputs[4])
        self.assertIn("2020-2024", outputs[7])

    def test_ytd_window_starts_on_january_first_of_the_latest_data_year(self):
        bundle = self.synthetic_bundle()
        with patch.object(dashboard, "get_dashboard_data", return_value=bundle):
            outputs = dashboard.update_dashboard("2020", "ytd", "NOK")

        index = bundle["portfolio_returns"].index
        days_this_year = int((index.year == index[-1].year).sum())
        values = self.kpi_values(outputs)
        expected = (1 + self.DAILY_PORTFOLIO) ** days_this_year - 1

        self.assertEqual(values["Year to date return"], f"{expected:+.1%}")
        self.assertIn("Year to date performance · NOK", outputs[4])
        self.assertIn("returns in NOK", outputs[9])

    def test_composition_is_sorted_by_ytd_and_links_are_escaped(self):
        bundle = self.synthetic_bundle()
        table, holdings = dashboard._composition_table(bundle, bundle["today"])

        rows = table.data
        self.assertEqual(holdings, 2)
        self.assertEqual([row["Symbol"] for row in rows], ["AAA", "BBB"])
        self.assertTrue(rows[0]["YTD"].startswith("+"))
        self.assertTrue(rows[1]["YTD"].startswith("-"))
        self.assertIn("Alpha &lt;Corp&gt; &amp; Co", rows[0]["Company"])
        self.assertNotIn("<Corp>", rows[0]["Company"])
        self.assertIn("/stock/aaa", rows[0]["Company"])
        self.assertIn('rel="noopener noreferrer"', rows[0]["Company"])
        self.assertEqual(
            [column["id"] for column in table.columns],
            ["Company", "Symbol", "YTD", "SinceInclusion", "ValidFrom"],
        )

    def test_failed_load_shows_a_message_and_keeps_the_page_standing(self):
        with patch.object(
            dashboard, "get_dashboard_data", side_effect=RuntimeError("yahoo down")
        ):
            outputs = dashboard.update_dashboard("2020", "testing", "USD")

        self.assertEqual(len(outputs), 11)
        self.assertEqual(len(outputs[0]), len(dashboard.KPI_LABELS))
        self.assertIn("unavailable", text_of(outputs[5]))
        self.assertEqual(outputs[1].layout.annotations[0].text, text_of(outputs[5]))


if __name__ == "__main__":
    unittest.main()
