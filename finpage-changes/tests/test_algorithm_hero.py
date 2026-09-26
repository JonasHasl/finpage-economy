import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import dash
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CSS_PATH = SRC / "assets" / "custom.css"
SCRIPT_PATH = SRC / "assets" / "algorithm-hero.js"
sys.path.insert(0, str(SRC))


def import_algorithm_page():
    """Import the page layout without requiring an instantiated Dash app."""
    with patch.object(dash, "register_page"):
        return importlib.import_module("pages.algorithm")


def walk_components(component):
    """Yield a Dash component tree without depending on concrete tag types."""
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


def class_tokens(component):
    value = getattr(component, "className", None)
    return set(value.split()) if isinstance(value, str) else set()


algorithm = import_algorithm_page()


class AlgorithmHeroTests(unittest.TestCase):
    def test_decorative_line_chart_is_an_accessibility_hidden_canvas(self):
        chart = algorithm._algo_trend_chart()
        components = list(walk_components(chart))
        classes = set().union(*(class_tokens(component) for component in components))
        canvases = [
            component
            for component in components
            if component.to_plotly_json().get("type") == "Canvas"
        ]

        self.assertEqual(len(canvases), 1)
        props = canvases[0].to_plotly_json()["props"]
        self.assertEqual(props.get("id"), "algo-trend-canvas")
        self.assertIn("algo-trend", class_tokens(canvases[0]))
        self.assertEqual(props.get("aria-hidden"), "true")
        self.assertNotIn("algo-trend__bar", classes)

    def test_old_bar_chart_and_hero_shine_css_are_removed(self):
        css = CSS_PATH.read_text(encoding="utf-8")

        self.assertNotIn(".algo-trend__bar", css)
        self.assertNotIn("algo-hero::after", css)
        self.assertNotIn("algo-sheen", css)

    def test_canvas_script_animates_a_line_and_area_with_reduced_motion_support(self):
        self.assertTrue(SCRIPT_PATH.exists(), "Missing Algorithm hero canvas script")
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("algo-trend-canvas", script)
        self.assertIn("getContext", script)
        self.assertIn("requestAnimationFrame", script)
        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertIn("matchMedia", script)
        self.assertIn("beginPath", script)
        self.assertIn("lineTo", script)
        self.assertIn("stroke", script)
        self.assertIn("fill", script)


class AlgorithmGraphInteractionTests(unittest.TestCase):
    def test_graph_components_explicitly_disable_zoom_controls(self):
        graphs = [
            component
            for component in walk_components(algorithm.layout)
            if component.to_plotly_json().get("type") == "Graph"
        ]

        self.assertEqual(len(graphs), 2)
        for graph in graphs:
            config = graph.to_plotly_json()["props"]["config"]
            self.assertFalse(config["displayModeBar"])
            self.assertFalse(config["scrollZoom"])
            self.assertFalse(config["doubleClick"])
            self.assertTrue(config["responsive"])

    def test_portfolio_figure_locks_both_axes_without_disabling_hover(self):
        dates = pd.date_range("2026-01-02", periods=3, freq="D")
        frame = pd.DataFrame({
            "Date": dates,
            "Portfolio_Cumulative_Period": [0.0, 0.01, 0.02],
            "ACWI_Cumulative_Period": [0.0, 0.005, 0.01],
        })

        figure = algorithm.create_portfolio_graph(
            title="Test",
            dataframe=frame,
            y_column="Portfolio_Cumulative_Period",
            start_date=dates.min(),
            end_date=dates.max(),
            currency="USD",
        )

        self.assertTrue(figure.layout.xaxis.fixedrange)
        self.assertTrue(figure.layout.yaxis.fixedrange)
        self.assertFalse(figure.layout.dragmode)
        self.assertEqual(figure.layout.hovermode, "x unified")

    def test_empty_portfolio_figure_is_also_zoom_locked(self):
        frame = pd.DataFrame({
            "Date": pd.to_datetime([]),
            "Portfolio_Cumulative_Period": [],
            "ACWI_Cumulative_Period": [],
        })

        figure = algorithm.create_portfolio_graph(
            title="Test",
            dataframe=frame,
            y_column="Portfolio_Cumulative_Period",
            start_date="2026-01-01",
            end_date="2026-12-31",
        )

        self.assertTrue(figure.layout.xaxis.fixedrange)
        self.assertTrue(figure.layout.yaxis.fixedrange)
        self.assertFalse(figure.layout.dragmode)


if __name__ == "__main__":
    unittest.main()
