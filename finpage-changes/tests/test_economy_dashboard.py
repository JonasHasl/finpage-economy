"""The /economy-dashboard page: layout wiring, rendering and the CSS contract.

The indicator definitions and formatting are covered in
``test_economy_dashboard_model.py``; these tests cover everything that turns them
into components, plus the places where Python and the stylesheet have to agree.
"""

import importlib
import importlib.util
import inspect
import json
import re
import shutil
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dash
import pandas as pd
from dash import _callback
from dash.development.base_component import Component


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import data_sources as ds  # noqa: E402
import economy_dashboard_model as model  # noqa: E402

ASSETS = SRC / "assets"
CSS = (ASSETS / "economy-dashboard.css").read_text()
JS_PATH = ASSETS / "economy-dashboard.js"
JS = JS_PATH.read_text()

REGISTERED = {}


def import_page():
    """Import the page without registering a Dash page or making live calls."""
    sys.modules.pop("pages.economy_dashboard", None)
    register = MagicMock()
    with patch.object(dash, "register_page", register):
        module = importlib.import_module("pages.economy_dashboard")
    REGISTERED.update(register.call_args.kwargs)
    return module


page = import_page()

WINDOW = (date(2024, 1, 1), date(2026, 12, 31))
COUNTRIES = [key for key, *_ in model.COMPARISON_COUNTRIES]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def walk(node):
    """Every Dash component in a tree, parents first."""
    if isinstance(node, Component):
        yield node
        yield from walk(getattr(node, "children", None))
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from walk(child)


def by_id(root, component_id):
    return next(c for c in walk(root) if getattr(c, "id", None) == component_id)


def classes(node):
    return (getattr(node, "className", None) or "").split()


def with_class(root, name):
    return [c for c in walk(root) if name in classes(c)]


def text_of(node):
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (list, tuple)):
        return "".join(text_of(child) for child in node)
    return text_of(getattr(node, "children", None))


def figure_of(tile):
    return next(c for c in walk(tile) if isinstance(c, page.dcc.Graph)).figure


def note_on(figure):
    return " ".join(a.text for a in figure.layout.annotations)


def monthly(values, start="2024-01-01"):
    dates = pd.date_range(start, periods=len(values), freq="MS")
    return pd.DataFrame({"Date": dates, "value": list(values)})


def ramp(count=30, base=0.02):
    return monthly([base + 0.001 * n for n in range(count)])


def distinct(index, count=30):
    """A ramp whose start, step and last value differ for every ``index``, so a
    card wired to the wrong series shows the wrong number."""
    return monthly([0.02 + 0.007 * index + (0.001 + 0.0002 * index) * n for n in range(count)])


def daily(values, start="2026-01-05"):
    return pd.DataFrame({"Date": pd.bdate_range(start, periods=len(values)), "value": list(values)})


def last(frame):
    return float(frame["value"].iloc[-1])


def market_data(key):
    market = model.MARKETS[key]
    names = sorted({kpi.key for kpi in market.kpis} | {chart.key for chart in market.charts})
    data = {name: distinct(index) for index, name in enumerate(names)}
    if market.has_country_detail:
        detail = sorted({kpi.key for kpi in model.EU_DETAIL_KPIS} | {"stockIndex"})
        data["countries"] = {
            country: {name: distinct(10 * (c + 1) + n) for n, name in enumerate(detail)}
            for c, country in enumerate(ds.EU_COUNTRIES)
        }
    return data


def comparison_data(skip=()):
    return {
        metric.key: {
            country: distinct(10 * m + n)
            for n, country in enumerate(COUNTRIES)
            if (metric.key, country) not in skip
        }
        for m, metric in enumerate(model.COMPARISON_METRICS)
    }


def callback_entry(output_fragment):
    return next(e for e in _callback.GLOBAL_CALLBACK_LIST if output_fragment in str(e["output"]))


def css_blocks(css):
    """Top-level (prelude, body) pairs of a stylesheet, comments removed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks, depth, start, prelude = [], 0, 0, ""
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                prelude, start = css[start:index].strip(), index + 1
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                blocks.append((prelude, css[start:index]))
                start = index + 1
    return blocks


# --------------------------------------------------------------------------
# Layout and callback wiring
# --------------------------------------------------------------------------

class LayoutWiringTests(unittest.TestCase):
    def test_component_ids_are_unique(self):
        ids = [c.id for c in walk(page.layout) if getattr(c, "id", None)]
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_page_starts_in_the_dashboard_layout_on_the_us_market(self):
        props = page.layout.to_plotly_json()["props"]
        self.assertEqual(props["className"], "ed-page ed-page--dashboard")
        self.assertEqual(props["data-market"], "us")

    def test_layout_switch_defaults_to_dashboard_and_is_remembered(self):
        view = by_id(page.layout, "ed-view")
        self.assertEqual([o["value"] for o in view.options], ["dashboard", "scroll"])
        self.assertEqual(view.value, "dashboard")
        self.assertIs(view.persistence, True)
        self.assertEqual(view.persistence_type, "local")

    def test_the_switch_says_why_dashboard_is_unavailable_on_a_small_window(self):
        control = with_class(page.layout, "ed-view-control")[0]
        hint = text_of(with_class(control, "ed-view-hint"))
        self.assertEqual(hint, page.VIEW_HINT)
        self.assertIn(str(page.DASHBOARD_MIN_WIDTH), hint)
        self.assertIn(str(page.DASHBOARD_MIN_HEIGHT), hint)
        # The radio and its hint live in the same block, so they move together.
        self.assertEqual(len([c for c in walk(control) if getattr(c, "id", None) == "ed-view"]), 1)

    def test_market_and_range_selectors(self):
        market = by_id(page.layout, "ed-market")
        self.assertEqual([o["value"] for o in market.options], ["us", "norway", "eu", "uk", "comparison"])
        self.assertEqual(market.value, "us")
        range_control = by_id(page.layout, "ed-range")
        self.assertEqual([o["value"] for o in range_control.options], ["ytd", "5y", "full"])
        self.assertEqual(range_control.value, "full")

    def test_comparison_starts_with_every_economy_selected(self):
        countries = by_id(page.layout, "ed-countries")
        self.assertEqual(countries.value, COUNTRIES)
        self.assertEqual([o["value"] for o in countries.options], COUNTRIES)

    def test_render_callback_controls_are_never_replaced_by_it(self):
        entry = callback_entry("ed-kpis.children")
        inputs = {item["id"] for item in entry["inputs"]}
        self.assertEqual(
            inputs,
            {"ed-market", "ed-range", "ed-refresh", "ed-interval", "ed-countries", "ed-eu-country"},
        )
        in_layout = {c.id for c in walk(page.layout) if getattr(c, "id", None)}
        self.assertTrue(inputs <= in_layout)

        replaced = set()
        for container in ("ed-kpis", "ed-grid", "ed-footnote"):
            replaced |= {c.id for c in walk(by_id(page.layout, container)) if getattr(c, "id", None)}
        self.assertEqual(inputs & replaced, set())

    def test_render_callback_outputs(self):
        entry = callback_entry("ed-kpis.children")
        self.assertEqual(
            entry["output"],
            "..ed-kpis.children...ed-grid.children...ed-footnote.children...ed-asof.children...ed-page.data-market..",
        )

    def test_layout_switch_runs_in_the_browser(self):
        entry = callback_entry("ed-page.className")
        self.assertEqual(entry["inputs"], [{"id": "ed-view", "property": "value"}])
        self.assertEqual(
            entry["clientside_function"],
            {"namespace": "economy_dashboard", "function_name": "set_layout"},
        )
        self.assertIn("window.dash_clientside.economy_dashboard", JS)
        self.assertIn("set_layout", JS)
        self.assertIn("ed-page ed-page--", JS)

    def test_javascript_only_accepts_the_two_layouts(self):
        self.assertIn('view === "scroll" ? "scroll" : "dashboard"', JS)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_layout_switch_script_parses_and_returns_the_right_class(self):
        script = """
            const fs = require('fs'), vm = require('vm');
            const timers = [];
            const window = { setTimeout: (fn, ms) => timers.push(ms), dispatchEvent() {} };
            vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), { window, Event: function () {} });
            const set = window.dash_clientside.economy_dashboard.set_layout;
            console.log(JSON.stringify([set('scroll'), set('dashboard'), set('junk'), set(null), set(undefined), timers]));
        """
        done = subprocess.run(["node", "-e", script, str(JS_PATH)], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        scroll, dashboard, junk, null, undefined, timers = json.loads(done.stdout)
        self.assertEqual(scroll, "ed-page ed-page--scroll")
        self.assertEqual({dashboard, junk, null, undefined}, {"ed-page ed-page--dashboard"})
        self.assertEqual(len(timers), 5)  # the resize nudge is scheduled on every switch

    def test_inputs_match_the_function_parameters_in_order(self):
        ids = [item["id"] for item in callback_entry("ed-kpis.children")["inputs"]]
        self.assertEqual(ids, ["ed-market", "ed-range", "ed-refresh", "ed-interval", "ed-countries", "ed-eu-country"])
        self.assertEqual(
            list(inspect.signature(page.update_dashboard).parameters),
            ["market", "range_key", "n_clicks", "n_intervals", "countries", "eu_country"],
        )

    def test_route_title_and_refresh_interval(self):
        self.assertEqual(REGISTERED["path"], "/economy-dashboard")
        self.assertEqual(REGISTERED["title"], "Economy Dashboard")
        six_hours = 6 * 3600 * 1000
        self.assertEqual(page.REFRESH_INTERVAL_MS, six_hours)
        self.assertEqual(by_id(page.layout, "ed-interval").interval, six_hours)

    def test_refresh_button_is_disabled_while_a_fetch_is_running(self):
        running = callback_entry("ed-kpis.children")["running"]
        self.assertEqual(running["running"], {"ed-refresh.disabled": True})
        self.assertEqual(running["runningOff"], {"ed-refresh.disabled": False})


# --------------------------------------------------------------------------
# Routing: "Economy" opens the dashboard, the classic page stays reachable
# --------------------------------------------------------------------------

def load_home():
    """The home page module, executed without an app."""
    path = SRC / "pages" / "home.py"
    spec = importlib.util.spec_from_file_location("_test_economy_routing_home", path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(dash, "register_page"):
        spec.loader.exec_module(module)
    return module


class RoutingTests(unittest.TestCase):
    def test_navigation_economy_link_opens_the_dashboard(self):
        source = (SRC / "app.py").read_text(encoding="utf-8")

        self.assertRegex(source, r'"Economy",\s*href="/economy-dashboard"')
        self.assertNotRegex(source, r'"Economy",\s*href="/economy"')

    def test_home_economy_card_opens_the_dashboard(self):
        links = {
            component.href: text_of(component)
            for component in walk(load_home().layout)
            if getattr(component, "href", None)
        }

        self.assertIn("/economy-dashboard", links)
        self.assertIn("Economy", links["/economy-dashboard"])
        self.assertNotIn("/economy", links)

    def test_classic_economy_page_keeps_its_path(self):
        source = (SRC / "pages" / "useconomy.py").read_text(encoding="utf-8")

        self.assertRegex(source, r'register_page\(__name__,\s*path="/economy"\)')
        self.assertEqual(REGISTERED["path"], "/economy-dashboard")


# --------------------------------------------------------------------------
# Stylesheet contract
# --------------------------------------------------------------------------

class StylesheetContractTests(unittest.TestCase):
    def test_pills_do_not_depend_on_one_dash_version(self):
        # Dash 3 (production) and Dash 4 render radio/checkbox options with
        # different markup; only "label containing a checked input" is shared.
        self.assertIn("> label:has(input:checked)", CSS)
        self.assertNotIn(".dash-options-list-option.selected", CSS)
        self.assertNotIn(".dash-options-list-option:hover", CSS)

    def test_dashboard_rules_live_only_in_the_desktop_media_queries(self):
        for prelude, body in css_blocks(CSS):
            if prelude.startswith("@"):
                if "ed-page--dashboard" in body:
                    self.assertIn("min-width: 1180px", prelude)
                    self.assertIn("min-height: 601px", prelude)
            else:
                self.assertNotIn("ed-page--dashboard", prelude, prelude)

    def test_the_layout_switch_is_never_hidden(self):
        # It used to disappear below the dashboard's minimum size, so on a small
        # window (a laptop pane, a phone) there was no sign the choice existed.
        def flat(css):
            for prelude, body in css_blocks(css):
                if prelude.startswith("@keyframes"):
                    continue
                if prelude.startswith("@"):
                    yield from flat(body)
                else:
                    yield prelude, body

        about_the_switch = [
            body for prelude, body in flat(CSS)
            if any(part.strip().endswith(".ed-view-control") for part in prelude.split(","))
        ]
        self.assertGreaterEqual(len(about_the_switch), 3)  # base, wide scroll layout, dashboard header
        self.assertFalse([body for body in about_the_switch if "display: none" in body])

    def test_small_window_rules_use_the_same_numbers_as_the_dashboard(self):
        dashboard = next(
            prelude for prelude, body in css_blocks(CSS)
            if prelude.startswith("@media") and ".ed-page--dashboard {" in body
        )
        width, height = (int(n) for n in re.findall(r"\d+", dashboard))
        self.assertEqual((width, height), (page.DASHBOARD_MIN_WIDTH, page.DASHBOARD_MIN_HEIGHT))
        preludes = [prelude for prelude, _ in css_blocks(CSS)]
        self.assertIn(f"@media (max-width: {width - 1}px), (max-height: {height - 1}px)", preludes)

    def test_every_custom_property_is_defined_somewhere(self):
        used = set(re.findall(r"var\((--[\w-]+)", CSS))
        defined = set()
        for sheet in ASSETS.glob("*.css"):
            defined |= set(re.findall(r"(--[\w-]+)\s*:", sheet.read_text()))
        self.assertEqual(used - defined, set())

    def test_selectors_are_namespaced_because_dash_serves_every_asset_globally(self):
        foreign = {
            "app-main",
            "js-plotly-plot",
            "plot-container",
            "svg-container",
            "dash-options-list-option-text",
            "dash-options-list-option-wrapper",
        }
        without_declarations = re.sub(r"\{[^{}]*\}", "{}", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S))
        names = set(re.findall(r"\.([A-Za-z_][\w-]*)", without_declarations))
        self.assertEqual({n for n in names if not n.startswith("ed-")} - foreign, set())

    def test_every_rule_is_scoped_to_this_page(self):
        # Dash serves each asset to every page, so a rule with no ".ed-"/"#ed-"
        # compound (`label {...}`, `body {...}`, `.js-plotly-plot {...}`) would
        # restyle the whole site.
        def split(selector_list):
            parts, depth, current = [], 0, ""
            for char in selector_list:
                depth += char == "("
                depth -= char == ")"
                if char == "," and depth == 0:
                    parts.append(current.strip())
                    current = ""
                else:
                    current += char
            return [*parts, current.strip()]

        def selectors(css):
            for prelude, body in css_blocks(css):
                if prelude.startswith(("@keyframes", "@font-face")):
                    continue
                if prelude.startswith("@"):
                    yield from selectors(body)
                else:
                    yield from split(prelude)

        unscoped = [s for s in selectors(CSS) if ".ed-" not in s and "#ed-" not in s]
        self.assertEqual(unscoped, [])

    def test_grid_columns_match_what_each_view_renders(self):
        declared = {
            market: (int(grid), int(kpi))
            for market, grid, kpi in re.findall(
                r'\.ed-page\[data-market="(\w+)"\]\s*\{\s*--ed-grid-cols:\s*(\d+);\s*--ed-kpi-cols:\s*(\d+);',
                CSS,
            )
        }
        self.assertEqual(set(declared), {"us", "norway", "eu", "uk", "comparison"})

        for market in ("us", "norway", "eu", "uk"):
            with self.subTest(market=market):
                kpis, tiles, _ = page.render_market(market, market_data(market), WINDOW, "germany")
                # The dashboard grid has two rows; the country panel spans two columns.
                cells = len(tiles) + len(with_class(tiles, "ed-tile--detail"))
                self.assertEqual((cells, len(kpis)), (declared[market][0] * 2, declared[market][1]))

        with self.subTest(market="comparison"):
            kpis, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, WINDOW)
            self.assertEqual((len(tiles), len(kpis)), (declared["comparison"][0] * 2, declared["comparison"][1]))


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

class MarketRenderingTests(unittest.TestCase):
    def test_each_market_renders_its_cards_and_tiles(self):
        expected_tiles = {"us": 10, "norway": 10, "eu": 7, "uk": 6}
        for key, tile_count in expected_tiles.items():
            with self.subTest(market=key):
                kpis, tiles, notes = page.render_market(key, market_data(key), WINDOW, "germany")
                self.assertEqual(len(kpis), len(model.MARKETS[key].kpis))
                self.assertEqual(len(tiles), tile_count)
                self.assertTrue(all("ed-tile" in classes(t) for t in tiles))
                self.assertTrue(notes)
                self.assertFalse(with_class(kpis, "ed-kpi--empty"))

    def test_free_grid_cells_hold_the_notes_tile(self):
        for key in ("norway", "uk"):
            _, tiles, _ = page.render_market(key, market_data(key), WINDOW)
            self.assertEqual(len(with_class(tiles, "ed-tile--notes")), 1, key)
        for key in ("us", "eu"):
            _, tiles, _ = page.render_market(key, market_data(key), WINDOW, "germany")
            self.assertEqual(with_class(tiles, "ed-tile--notes"), [], key)

    def test_chart_tiles_state_axis_source_and_latest_observation(self):
        _, tiles, _ = page.render_market("uk", market_data("uk"), WINDOW)
        sub = text_of(with_class(tiles[0], "ed-tile-sub"))
        self.assertIn("Index level", sub)
        self.assertIn("Yahoo Finance", sub)
        self.assertIn("Jun 2026", sub)

    def test_every_card_and_tile_shows_its_own_series(self):
        for key in ("us", "norway", "eu", "uk"):
            with self.subTest(market=key):
                market = model.MARKETS[key]
                data = market_data(key)
                kpis, tiles, _ = page.render_market(key, data, WINDOW, "germany")
                for kpi, card in zip(market.kpis, kpis):
                    value = last(data[kpi.key])
                    expected = model.fmt_pct(value) if kpi.kind == "pct" else model.fmt_num(value, 1)
                    self.assertEqual(text_of(with_class(card, "ed-kpi-value")), expected, kpi.label)
                for chart, tile in zip(market.charts, tiles):
                    value = last(data[chart.key])
                    self.assertEqual(
                        text_of(with_class(tile, "ed-tile-chip")),
                        model.format_observation_value(value, chart.tick),
                        chart.title,
                    )
                    self.assertAlmostEqual(figure_of(tile).data[-1].y[0], value, msg=chart.title)

    def test_the_fixture_series_really_differ(self):
        # Guards the test above: identical series would let any wiring mistake pass.
        data = market_data("us")
        self.assertEqual(len({round(last(frame), 6) for frame in data.values()}), len(data))
        # 0.02 + 0.001 * 29 for the first series, written as a percentage.
        kpis, _, _ = page.render_market("us", data, WINDOW)
        self.assertEqual(text_of(with_class(kpis[0], "ed-kpi-value")), "4.90%")

    def test_the_change_compares_the_last_two_readings(self):
        data = market_data("us")
        data["bondYield10y"] = monthly([0.04, 0.06, 0.05])
        kpis, _, _ = page.render_market("us", data, WINDOW)
        self.assertEqual(text_of(with_class(kpis[0], "ed-kpi-delta")), "▼ 1.00 pp")
        self.assertIn("ed-kpi-delta--down", classes(with_class(kpis[0], "ed-kpi-delta")[0]))

    def test_euro_area_panel_shows_the_selected_countrys_own_numbers(self):
        data = market_data("eu")
        chips = set()
        for country in ds.EU_COUNTRIES:
            _, tiles, _ = page.render_market("eu", data, WINDOW, country)
            detail = with_class(tiles, "ed-tile--detail")[0]
            own = data["countries"][country]
            self.assertEqual(
                [text_of(stat) for stat in with_class(detail, "ed-mini-value")],
                [model.snapshot(kpi, own[kpi.key]).value_text for kpi in model.EU_DETAIL_KPIS],
                country,
            )
            chip = text_of(with_class(detail, "ed-tile-chip"))
            self.assertEqual(chip, model.format_observation_value(last(own["stockIndex"]), "index"), country)
            chips.add(chip)
        self.assertEqual(len(chips), len(ds.EU_COUNTRIES))

    def test_euro_area_country_panel_follows_the_selector(self):
        for country, label in (("france", "France"), ("spain", "Spain")):
            _, tiles, _ = page.render_market("eu", market_data("eu"), WINDOW, country)
            self.assertIn(f"Country detail · {label}", text_of(with_class(tiles, "ed-tile--detail")))

    def test_unknown_euro_area_country_falls_back_to_the_first(self):
        _, tiles, _ = page.render_market("eu", market_data("eu"), WINDOW, "atlantis")
        self.assertIn("Country detail · Germany", text_of(with_class(tiles, "ed-tile--detail")))

    def test_missing_data_says_the_source_is_unavailable(self):
        kpis, tiles, _ = page.render_market("us", {}, WINDOW)
        self.assertEqual(len(with_class(kpis, "ed-kpi--empty")), len(kpis))
        self.assertEqual(len(tiles), 10)
        for tile in tiles:
            self.assertIn("Source unavailable", note_on(figure_of(tile)))
            self.assertIn("Press Refresh", note_on(figure_of(tile)))

    def test_data_outside_the_window_is_not_reported_as_unavailable(self):
        window = (date(2027, 1, 1), date(2027, 6, 1))
        _, tiles, _ = page.render_market("uk", market_data("uk"), window)
        for tile in tiles[:-1]:
            note = note_on(figure_of(tile))
            self.assertIn("No observations in this range", note)
            self.assertIn("Latest:", note)
            self.assertNotIn("unavailable", note)
        self.assertIn("Latest: Jun 2026", note_on(figure_of(tiles[0])))

    def test_unavailable_state_keeps_the_card_count_of_the_view(self):
        for key, count in (("us", 5), ("norway", 5), ("eu", 5), ("uk", 4), ("comparison", 4)):
            kpis, tiles, notes = page.render_unavailable(key, "Nothing here")
            self.assertEqual(len(kpis), count, key)
            self.assertEqual(len(tiles), 1)
            self.assertIn("ed-tile--message", classes(tiles[0]))
            self.assertEqual(notes, [])

    def test_footnote_ends_with_the_chart_legend(self):
        lines = page.footnote(("one", "two"))
        self.assertEqual([text_of(line) for line in lines][:2], ["one", "two"])
        self.assertIn("Red dot", text_of(lines[-1]))


class ComparisonRenderingTests(unittest.TestCase):
    def test_every_economy_is_listed_on_each_card(self):
        kpis, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, WINDOW)
        self.assertEqual(len(kpis), 4)
        self.assertEqual(len(tiles), 4)
        for card in kpis:
            self.assertEqual(len(with_class(card, "ed-cmp-row")), 4)
            self.assertEqual(with_class(card, "ed-cmp-row--off"), [])
        for tile in tiles:
            self.assertEqual(len(with_class(tile, "ed-legend-item")), 4)
            self.assertEqual(len(figure_of(tile).data), 4)

    def test_deselected_economies_stay_on_the_card_but_dim(self):
        kpis, tiles, _ = page.render_comparison(comparison_data(), ["us", "uk"], WINDOW)
        for card in kpis:
            rows = with_class(card, "ed-cmp-row")
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(with_class(card, "ed-cmp-row--off")), 2)
            self.assertEqual([text_of(c) for c in with_class(card, "ed-cmp-code")], ["US", "EA", "UK", "NO"])
        for tile in tiles:
            self.assertEqual([text_of(i) for i in with_class(tile, "ed-legend-item")], ["US", "UK"])
            self.assertEqual({trace.name for trace in figure_of(tile).data}, {"US", "UK"})

    def test_selection_is_always_shown_in_the_fixed_country_order(self):
        _, tiles, _ = page.render_comparison(comparison_data(), ["norway", "us"], WINDOW)
        self.assertEqual([text_of(i) for i in with_class(tiles[0], "ed-legend-item")], ["US", "Norway"])

    def test_nothing_selected_asks_for_a_country(self):
        kpis, tiles, _ = page.render_comparison(comparison_data(), [], WINDOW)
        for card in kpis:
            self.assertEqual(len(with_class(card, "ed-cmp-row--off")), 4)
        for tile in tiles:
            self.assertEqual(note_on(figure_of(tile)), page.NO_COUNTRY_TEXT)

    def test_an_economy_without_data_is_marked_in_the_legend_and_card(self):
        data = comparison_data(skip={("gdpYoY", "norway")})
        kpis, tiles, _ = page.render_comparison(data, COUNTRIES, WINDOW)
        legend = [text_of(i) for i in with_class(tiles[0], "ed-legend-item")]
        self.assertEqual(legend, ["US", "Euro Area", "UK", "Norway · no data"])
        self.assertEqual(len(with_class(tiles[0], "ed-legend-item--empty")), 1)
        self.assertEqual(len(with_class(tiles[1], "ed-legend-item--empty")), 0)
        empty_rows = with_class(kpis[0], "ed-cmp-row--empty")
        self.assertEqual([text_of(r) for r in empty_rows], ["NO—"])
        self.assertEqual(len(figure_of(tiles[0]).data), 3)

    def test_no_source_at_all_is_reported_as_unavailable(self):
        _, tiles, _ = page.render_comparison({}, COUNTRIES, WINDOW)
        for tile in tiles:
            self.assertIn("Source unavailable", note_on(figure_of(tile)))

    def test_empty_window_is_reported_as_such(self):
        window = (date(2027, 1, 1), date(2027, 6, 1))
        _, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, window)
        for tile in tiles:
            self.assertIn("No published observations in this range", note_on(figure_of(tile)))

    def test_gdp_gets_a_zero_line(self):
        _, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, WINDOW)
        shapes = [len(figure_of(tile).layout.shapes) for tile in tiles]
        self.assertEqual(shapes, [1, 0, 0, 0])

    def test_every_row_and_line_belongs_to_its_own_economy_and_indicator(self):
        data = comparison_data()
        kpis, tiles, _ = page.render_comparison(data, COUNTRIES, WINDOW)
        names = {page.COUNTRY_LABELS[key]: key for key in COUNTRIES}
        for metric, card, tile in zip(model.COMPARISON_METRICS, kpis, tiles):
            shown = [text_of(value) for value in with_class(card, "ed-cmp-value")]
            self.assertEqual(shown, [model.fmt_pct(last(data[metric.key][c])) for c in COUNTRIES], metric.key)
            for trace in figure_of(tile).data:
                own = data[metric.key][names[trace.name]]
                self.assertAlmostEqual(trace.y[-1], last(own), places=7, msg=f"{metric.key} {trace.name}")

    def test_cards_state_the_date_of_the_latest_readings(self):
        def frame(dates):
            return pd.DataFrame({"Date": pd.to_datetime(dates), "value": [0.02] * len(dates)})

        gdp = model.COMPARISON_METRICS[0]
        series = {
            "us": frame(["2026-04-01", "2026-07-01"]),
            "eu": frame(["2026-04-01", "2026-07-01"]),
            "uk": frame(["2026-01-01", "2026-04-01"]),
            "norway": frame(["2026-05-01", "2026-06-01"]),
        }
        self.assertEqual(page.comparison_as_of(gdp, series), "As of Q3 2026 · UK Q2 2026 · NO Jun 2026")

        cpi = model.COMPARISON_METRICS[1]
        same = {key: frame(["2026-08-01", "2026-09-01"]) for key in COUNTRIES}
        self.assertEqual(page.comparison_as_of(cpi, same), "As of Sep 2026")
        self.assertEqual(page.comparison_as_of(cpi, {}), "No data")

        kpis, _, _ = page.render_comparison({"gdpYoY": series}, COUNTRIES, WINDOW)
        self.assertEqual(text_of(with_class(kpis[0], "ed-kpi-meta")), "As of Q3 2026 · UK Q2 2026 · NO Jun 2026")

    def test_the_footnote_does_not_describe_a_red_dot_the_comparison_never_draws(self):
        _, _, comparison_notes = page.render_comparison(comparison_data(), COUNTRIES, WINDOW)
        _, _, market_notes = page.render_market("uk", market_data("uk"), WINDOW)
        self.assertNotIn("Red dot", text_of(comparison_notes))
        self.assertIn("Red dot", text_of(market_notes))

    def test_a_single_reading_in_the_window_is_drawn_as_a_marker(self):
        window = (date(2026, 3, 1), date(2026, 3, 31))  # one monthly reading per series
        _, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, window)
        for tile in tiles[1:3]:
            traces = figure_of(tile).data
            self.assertEqual(len(traces), 4)
            self.assertEqual({trace.mode for trace in traces}, {"markers"})
            self.assertEqual({len(trace.x) for trace in traces}, {1})
            self.assertEqual({trace.cliponaxis for trace in traces}, {False})

    def test_hover_is_one_line_per_economy_with_its_own_date(self):
        _, tiles, _ = page.render_comparison(comparison_data(), COUNTRIES, WINDOW)
        gdp = figure_of(tiles[0])
        self.assertEqual(gdp.layout.hovermode, "x unified")
        self.assertEqual(gdp.layout.xaxis.hoverformat, "%b %Y")
        trace = next(t for t in gdp.data if t.name == "Norway")  # monthly; the others are quarterly
        self.assertEqual(trace.hovertemplate, "%{text}<extra></extra>")
        self.assertNotIn("<br>", trace.text[-1])
        self.assertRegex(trace.text[-1], r"^Norway: \d+\.\d\d%  ·  Jun 2026$")
        quarterly = next(t for t in gdp.data if t.name == "US")
        self.assertRegex(quarterly.text[-1], r"^US: \d+\.\d\d%  ·  Q2 2026$")

    def test_daily_series_are_formatted_by_the_browser_under_a_dated_header(self):
        data = comparison_data()
        data["bondYield10y"] = {key: daily([0.041 + 0.001 * n for n in range(60)]) for key in COUNTRIES}
        _, tiles, _ = page.render_comparison(data, COUNTRIES, (date(2026, 1, 1), date(2026, 12, 31)))
        figure = figure_of(tiles[2])
        self.assertEqual(figure.layout.xaxis.hoverformat, "%d %b %Y")
        self.assertEqual({t.hovertemplate for t in figure.data}, {"%{fullData.name}: %{y:.2%}<extra></extra>"})

    def test_values_sent_for_daily_hover_keep_enough_digits_to_format_like_the_cards(self):
        # 0.0412499 is 4.12% on the cards; rounding it to 6 decimals first
        # (0.04125) would let the browser show 4.13%.
        data = comparison_data()
        data["bondYield10y"] = {key: daily([0.0412499, 0.0412499]) for key in COUNTRIES}
        _, tiles, _ = page.render_comparison(data, COUNTRIES, (date(2026, 1, 1), date(2026, 12, 31)))
        for trace in figure_of(tiles[2]).data:
            self.assertEqual(list(trace.y), [0.0412499, 0.0412499])
        self.assertEqual(model.format_observation_value(0.0412499, "%"), "4.12%")


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

class TileFigureTests(unittest.TestCase):
    CHART = model.Chart("k", "Title", "Short", "Axis", "%", "FRED", "blue")

    def figure(self, values, chart=None, **chart_overrides):
        chart = chart or model.Chart(**{**self.CHART.__dict__, **chart_overrides})
        return page.tile_figure(monthly(values), chart, *WINDOW)

    def test_points_are_sent_as_short_date_strings_and_rounded_values(self):
        figure = self.figure([0.123456789, 0.125, 0.1301234567])
        line = figure.data[0]
        self.assertEqual(list(line.x), ["2024-01-01", "2024-02-01", "2024-03-01"])
        self.assertEqual(list(line.y), [0.12345679, 0.125, 0.13012346])

    def test_each_unit_is_rounded_to_its_own_precision(self):
        samples = {
            "%": (0.123456789, 0.12345679),
            "bps": (37.456, 37.46),
            "ratio": (40.8766, 40.877),
            "usd_tn": (23.41396, 23.414),
            "usd_bn": (-105.5724, -105.572),
            "fx": (9.282649, 9.28265),
            "index": (7545.1149, 7545.11),
        }
        for tick, (value, expected) in samples.items():
            with self.subTest(tick=tick):
                chart = model.Chart("k", "T", "T", "Axis", tick, "src", "blue")
                figure = page.tile_figure(monthly([value, value]), chart, *WINDOW)
                # The line is the second-to-last trace (the last is the latest-observation dot).
                self.assertEqual(list(figure.data[-2].y), [expected, expected])

    def test_each_unit_has_its_own_axis_format(self):
        expected = {
            "%": ({"tickformat": ".2%"}, 0.04),
            "bps": ({"tickformat": ",.0f", "ticksuffix": " bp"}, 37.0),
            "ratio": ({"tickformat": ",.0f", "ticksuffix": "×"}, 40.0),
            "fx": ({"tickformat": ",.2f"}, 9.28),
            "index": ({"tickformat": ",~s"}, 7545.0),
        }
        for tick, (axis, value) in expected.items():
            with self.subTest(tick=tick):
                chart = model.Chart("k", "T", "T", "Axis", tick, "src", "blue")
                figure = page.tile_figure(monthly([value, value]), chart, *WINDOW)
                for name, wanted in axis.items():
                    self.assertEqual(getattr(figure.layout.yaxis, name), wanted, name)

    def test_charts_cannot_be_zoomed_or_dragged(self):
        figure = self.figure([0.01, 0.02, 0.03])
        self.assertIs(figure.layout.dragmode, False)
        self.assertIs(figure.layout.xaxis.fixedrange, True)
        self.assertIs(figure.layout.yaxis.fixedrange, True)
        self.assertIs(page.GRAPH_CONFIG["scrollZoom"], False)
        self.assertIs(page.GRAPH_CONFIG["doubleClick"], False)
        self.assertIs(page.GRAPH_CONFIG["displayModeBar"], False)
        comparison = page.comparison_figure(comparison_data()["cpiYoY"], model.COMPARISON_METRICS[1], COUNTRIES, *WINDOW)
        self.assertIs(comparison.layout.dragmode, False)
        self.assertIs(comparison.layout.xaxis.fixedrange, True)

    def test_a_window_between_two_rate_changes_starts_at_the_rate_then_in_force(self):
        changes = pd.DataFrame({
            "Date": pd.to_datetime(["2025-06-11", "2026-06-17", "2026-10-30"]),
            "value": [0.02, 0.0225, 0.0225],
        })
        chart = model.Chart("policyRate", "Rate", "Rate", "Percent", "%", "ECB", "violet", step=True)
        figure = page.tile_figure(changes, chart, date(2026, 1, 1), date(2026, 10, 30))
        line = figure.data[0]

        self.assertEqual(list(line.x), ["2026-01-01", "2026-06-17", "2026-10-30"])
        self.assertEqual(list(line.y), [0.02, 0.0225, 0.0225])
        self.assertEqual(line.text[0], "In force since 11 Jun 2025<br>2.00%")
        self.assertEqual(list(line.marker.size), [0, 5, 5])  # no marker for a point that is not a reading
        self.assertEqual(figure.layout.xaxis.range[0], pd.Timestamp("2026-01-01"))
        self.assertLess(figure.layout.yaxis.range[0], 0.02)  # the axis includes the rate in force

    def test_other_series_do_not_borrow_a_value_from_before_the_window(self):
        changes = pd.DataFrame({
            "Date": pd.to_datetime(["2025-06-11", "2026-06-17"]),
            "value": [0.02, 0.0225],
        })
        chart = model.Chart("k", "T", "T", "Axis", "%", "src", "blue")  # not a step series
        figure = page.tile_figure(changes, chart, date(2026, 1, 1), date(2026, 10, 30))
        self.assertEqual(list(figure.data[0].x), ["2026-06-17"])
        self.assertEqual(figure.data[0].marker.size, 5)

    def test_a_short_window_still_knows_a_monthly_series_is_monthly(self):
        # One reading in the window gives nothing to infer the period from.
        figure = page.tile_figure(monthly([0.01, 0.02, 0.03]), self.CHART, date(2024, 3, 1), date(2024, 3, 31))
        self.assertEqual(figure.data[0].text[0], "Mar 2024<br>3.00%")

    def test_hover_text_uses_the_unrounded_values(self):
        figure = self.figure([0.04126, 0.04127])
        self.assertEqual(figure.data[0].text[0], "Jan 2024<br>4.13%")

    def test_positive_series_fill_to_the_bottom_without_a_helper_trace(self):
        figure = self.figure([0.04, 0.045, 0.05])
        self.assertEqual(len(figure.data), 2)  # the line and the latest-observation dot
        self.assertEqual(figure.data[0].fill, "tozeroy")
        self.assertGreater(figure.layout.yaxis.range[0], 0)

    def test_series_crossing_zero_fill_towards_zero(self):
        figure = self.figure([-0.01, 0.0, 0.02])
        self.assertEqual(len(figure.data), 2)
        self.assertEqual(figure.data[0].fill, "tozeroy")

    def test_an_entirely_negative_range_fills_to_the_bottom_edge(self):
        figure = self.figure([-0.05, -0.04, -0.03])
        self.assertEqual(len(figure.data), 3)
        self.assertEqual(figure.data[0].hoverinfo, "skip")
        self.assertEqual(figure.data[1].fill, "tonexty")

    def test_zero_line_is_drawn_only_when_asked_for(self):
        self.assertEqual(len(self.figure([0.01, 0.02]).layout.shapes), 0)
        self.assertEqual(len(self.figure([0.01, 0.02], zero_line=True).layout.shapes), 1)

    def test_step_series_are_drawn_as_steps(self):
        self.assertEqual(self.figure([0.01, 0.02], step=True).data[0].line.shape, "hv")
        self.assertEqual(self.figure([0.01, 0.02]).data[0].line.shape, "linear")

    def test_latest_observation_is_marked_and_not_clipped(self):
        figure = self.figure([0.01, 0.02, 0.03])
        dot = figure.data[-1]
        self.assertEqual(list(dot.x), ["2024-03-01"])
        self.assertEqual(list(dot.y), [0.03])
        self.assertIs(dot.cliponaxis, False)

    def test_a_flat_series_does_not_look_dramatic(self):
        figure = self.figure([0.04, 0.04, 0.04])
        low, high = figure.layout.yaxis.range
        self.assertGreaterEqual(high - low, page.MIN_AXIS_SPAN["%"])
        self.assertLess(low, 0.04)  # the flat line sits inside the axis
        self.assertGreater(high, 0.04)

    def test_x_axis_leaves_room_for_the_latest_dot(self):
        figure = page.tile_figure(monthly([0.01, 0.02, 0.03]), self.CHART, date(2024, 1, 1), date(2026, 10, 15))
        right = pd.Timestamp(figure.layout.xaxis.range[1])
        self.assertGreater(right, pd.Timestamp("2026-10-15"))
        self.assertLess(right, pd.Timestamp("2026-11-01"))

    def test_x_axis_labels_follow_the_length_of_the_window(self):
        self.assertEqual(page._x_axis_format("2000-01-01", "2026-10-30"), "%Y")
        self.assertEqual(page._x_axis_format("2024-01-01", "2026-10-30"), "%b '%y")
        self.assertEqual(page._x_axis_format("2026-01-01", "2026-10-30"), "%b")
        # Under about three months ticks fall every few days; a bare month would repeat.
        self.assertEqual(page._x_axis_format("2026-01-01", "2026-03-15"), "%d %b")

    def test_padding_never_reaches_a_tick_beyond_today(self):
        self.assertEqual(page._right_limit("2026-10-30", 300, "%b"), pd.Timestamp("2026-10-31"))
        self.assertEqual(page._right_limit("2026-12-31", 4000, "%Y"), pd.Timestamp("2026-12-31"))
        self.assertEqual(page._right_limit("2026-12-30", 900, "%b '%y"), pd.Timestamp("2026-12-31"))
        mid = page._right_limit("2026-10-15", 300, "%b")
        self.assertTrue(pd.Timestamp("2026-10-15") < mid < pd.Timestamp("2026-11-01"))
        # Day-level labels have no month boundary to respect.
        self.assertGreaterEqual((page._right_limit("2026-03-15", 70, "%d %b") - pd.Timestamp("2026-03-15")).days, 1)

    def test_money_axes_use_a_proper_minus_sign_and_exact_labels(self):
        self.assertEqual(page.money_tick_text(-50, "bn", 0), "−$50bn")
        self.assertEqual(page.money_tick_text(23.4, "tn", 1), "$23.4tn")
        chart = model.Chart("k", "Trade", "Trade", "USD billions", "usd_bn", "FRED", "blue", zero_line=True)
        figure = page.tile_figure(monthly([-120.0, -90.0, -100.0]), chart, *WINDOW)
        self.assertTrue(all(text.startswith("−$") or text == "$0bn" for text in figure.layout.yaxis.ticktext))

    def test_money_tick_labels_are_never_rounded_to_a_different_number(self):
        for tick, unit in (("usd_tn", "tn"), ("usd_bn", "bn")):
            for values in ([20.5, 21.0, 21.9], [17.5, 22.5, 27.5], [-110.0, -60.0, -25.0], [4.6, 23.4]):
                with self.subTest(tick=tick, values=values):
                    chart = model.Chart("k", "T", "T", "Axis", tick, "src", "blue")
                    figure = page.tile_figure(monthly(values), chart, *WINDOW)
                    shown = [
                        float(text.replace("−", "-").replace("$", "").replace(unit, ""))
                        for text in figure.layout.yaxis.ticktext
                    ]
                    self.assertEqual(shown, [round(v, 6) for v in figure.layout.yaxis.tickvals])

    def test_nice_ticks_are_round_and_inside_the_range(self):
        self.assertEqual(page.nice_ticks(0, 30), [0, 10, 20, 30])
        self.assertEqual(page.nice_ticks(-50, 100), [-50, 0, 50, 100])
        self.assertEqual(page.nice_ticks(3.2, 41.0), [10, 20, 30, 40])
        self.assertEqual(page.nice_ticks(1.0, 1.0), [1.0])
        self.assertEqual(page.nice_ticks(21.0, 23.6), [21, 22, 23])
        self.assertGreaterEqual(len(page.nice_ticks(21.1, 23.6)), 2)  # never a lone tick

    def test_every_axis_gets_at_least_two_ticks_and_not_too_many(self):
        for low, high in ((21.0, 23.6), (0.2, 0.9), (-3.1, 4.7), (0, 100), (4.6, 23.4), (-132.0, -24.0)):
            with self.subTest(low=low, high=high):
                ticks = page.nice_ticks(low, high)
                self.assertTrue(2 <= len(ticks) <= 5, ticks)
                self.assertTrue(all(low <= t <= high for t in ticks), ticks)

    def test_tick_decimals_are_the_fewest_that_are_exact(self):
        self.assertEqual(page._tick_decimals([20, 40]), 0)
        self.assertEqual(page._tick_decimals([17.5, 20.0]), 1)
        self.assertEqual(page._tick_decimals([20.75, 21.0, 21.25]), 2)

    def test_empty_frames_become_a_message_not_an_error(self):
        figure = page.tile_figure(pd.DataFrame(columns=["Date", "value"]), self.CHART, *WINDOW)
        self.assertEqual(len(figure.data), 0)
        self.assertIn("Source unavailable", note_on(figure))


class EmptyReasonTests(unittest.TestCase):
    def test_reason_depends_on_why_nothing_can_be_drawn(self):
        self.assertIn("Source unavailable", page.empty_reason(None, *WINDOW))
        self.assertIn("Source unavailable", page.empty_reason(pd.DataFrame(), *WINDOW))
        later = (date(2027, 1, 1), date(2027, 3, 1))
        reason = page.empty_reason(monthly([0.01, 0.02]), *later)
        self.assertEqual(reason, "No observations in this range<br>Latest: Feb 2024")

    def test_quarterly_series_name_their_quarter(self):
        later = (date(2027, 1, 1), date(2027, 3, 1))
        frame = pd.DataFrame({"Date": pd.to_datetime(["2026-01-01", "2026-04-01"]), "value": [0.01, 0.02]})
        self.assertTrue(page.empty_reason(frame, *later, period="quarter").endswith("Latest: Q2 2026"))


# --------------------------------------------------------------------------
# The render callback
# --------------------------------------------------------------------------

class RenderCallbackTests(unittest.TestCase):
    def call(self, market="us", range_key="full", countries=None, eu="germany", trigger=None):
        context = SimpleNamespace(triggered_id=trigger)
        with patch.object(page, "callback_context", context):
            return page.update_dashboard(market, range_key, 0, 0, countries or COUNTRIES, eu)

    def test_returns_content_stamp_and_the_market_it_rendered(self):
        with patch.object(model, "load_market", return_value=market_data("uk")) as load:
            kpis, tiles, notes, stamp, market = self.call("uk")
        load.assert_called_once_with("uk")
        self.assertEqual((len(kpis), len(tiles), market), (4, 6, "uk"))
        self.assertTrue(notes)
        self.assertTrue(stamp.startswith("Data checked "))
        self.assertTrue(stamp.endswith("each card and chart shows its observation date"))

    def test_the_comparison_stamp_only_promises_what_the_comparison_shows(self):
        with patch.object(model, "load_comparison", return_value=comparison_data()):
            *_, stamp, market = self.call("comparison")
        self.assertEqual(market, "comparison")
        self.assertTrue(stamp.endswith("each card shows the date of its latest observation"))

    def test_refresh_button_forces_a_fetch_and_nothing_else_does(self):
        with patch.object(model, "load_market", return_value=market_data("us")) as load, \
                patch.object(model, "refresh_market", return_value=market_data("us")) as refresh:
            self.call("us", trigger="ed-refresh")
            refresh.assert_called_once_with("us")
            load.assert_not_called()
            self.call("us", trigger="ed-interval")
            self.call("us", trigger=None)
            self.assertEqual(refresh.call_count, 1)
            self.assertEqual(load.call_count, 2)

    def test_comparison_uses_the_comparison_loader(self):
        with patch.object(model, "load_comparison", return_value=comparison_data()) as load:
            kpis, tiles, _, _, market = self.call("comparison", countries=["us"])
        load.assert_called_once_with()
        self.assertEqual((len(kpis), len(tiles), market), (4, 4, "comparison"))
        self.assertEqual(len(with_class(kpis[0], "ed-cmp-row--off")), 3)

    def test_comparison_refresh_is_forced_too(self):
        with patch.object(model, "refresh_market", return_value=comparison_data()) as refresh:
            self.call("comparison", trigger="ed-refresh")
        refresh.assert_called_once_with("comparison")

    def test_unknown_market_falls_back_to_the_default(self):
        with patch.object(model, "load_market", return_value=market_data("us")) as load:
            *_, market = self.call("mars")
        load.assert_called_once_with("us")
        self.assertEqual(market, "us")

    def test_year_to_date_window_is_applied(self):
        seen = {}

        def render(market_key, data, window, eu_country=None):
            seen["window"] = window
            return [], [], []

        with patch.object(model, "load_market", return_value={}), patch.object(page, "render_market", render):
            self.call("us", range_key="ytd")
        self.assertEqual(seen["window"][0], date(date.today().year, 1, 1))

    def test_a_failing_source_shows_a_message_instead_of_an_error(self):
        with patch.object(model, "load_market", side_effect=RuntimeError("boom")), \
                self.assertLogs(page.logger, level="ERROR"):
            kpis, tiles, notes, stamp, market = self.call("norway")
        self.assertEqual(market, "norway")
        self.assertEqual(len(kpis), 5)
        self.assertEqual(len(tiles), 1)
        self.assertIn("unavailable", text_of(tiles[0]))
        self.assertEqual(notes, [])
        self.assertTrue(stamp)

    def test_nothing_selected_in_the_comparison_still_renders(self):
        with patch.object(model, "load_comparison", return_value=comparison_data()):
            kpis, tiles, *_ = self.call("comparison", countries=[])
        self.assertEqual((len(kpis), len(tiles)), (4, 4))


if __name__ == "__main__":
    unittest.main()
