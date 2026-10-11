import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import dash
import numpy as np
import plotly.graph_objects as go


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def import_bond_page():
    """Import callbacks and graph helpers without loading live market data."""
    with patch.object(dash, "register_page"):
        return importlib.import_module("pages.Bond_Market")


bond = import_bond_page()


class BondGraphInteractionTests(unittest.TestCase):
    def test_graph_factory_explicitly_disables_zoom_controls(self):
        graph = bond.bond_graph("test-graph", bond.BOND_GRAPH_STYLE_2D)

        self.assertFalse(graph.config["displayModeBar"])
        self.assertFalse(graph.config["scrollZoom"])
        self.assertFalse(graph.config["doubleClick"])
        self.assertTrue(graph.config["responsive"])
        self.assertTrue(graph.responsive)

    def test_every_bond_graph_uses_the_shared_factory(self):
        source = (SRC / "pages" / "Bond_Market.py").read_text(encoding="utf-8")

        self.assertEqual(source.count("bond_graph('"), 7)
        self.assertEqual(source.count("dcc.Graph("), 1)
        self.assertNotIn("'scrollZoom': True", source)

    def test_two_dimensional_axes_are_locked_and_hover_is_preserved(self):
        figure = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], hoverinfo="x+y"))

        result = bond._lock_graph_navigation(figure)

        self.assertIs(result, figure)
        self.assertTrue(figure.layout.xaxis.fixedrange)
        self.assertTrue(figure.layout.yaxis.fixedrange)
        self.assertFalse(figure.layout.dragmode)
        self.assertEqual(figure.data[0].hoverinfo, "x+y")

    def test_three_dimensional_camera_drag_is_locked_and_hover_is_preserved(self):
        figure = go.Figure(
            go.Surface(z=np.array([[1.0, 2.0], [3.0, 4.0]]), hoverinfo="x+y+z")
        )

        result = bond._lock_graph_navigation(figure, is_3d=True)

        self.assertIs(result, figure)
        self.assertFalse(figure.layout.scene.dragmode)
        self.assertEqual(figure.data[0].hoverinfo, "x+y+z")


if __name__ == "__main__":
    unittest.main()
