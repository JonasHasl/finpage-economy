import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from theme import LIGHT_THEME  # noqa: E402


def relative_luminance(hex_color):
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground, background):
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


class LightThemeTests(unittest.TestCase):
    def test_shared_theme_uses_bright_surfaces_and_readable_text(self):
        self.assertEqual(LIGHT_THEME["page"], "#F4F8FC")
        self.assertEqual(LIGHT_THEME["surface"], "#FFFFFF")

        for role in ("text_primary", "text_secondary", "text_muted"):
            self.assertGreaterEqual(
                contrast_ratio(LIGHT_THEME[role], LIGHT_THEME["surface"]), 4.5
            )

    def test_financial_chart_colors_are_visible_on_white(self):
        for role in ("blue", "green", "red", "amber", "violet", "cyan", "rose"):
            self.assertGreaterEqual(
                contrast_ratio(LIGHT_THEME[role], LIGHT_THEME["surface"]), 3.0
            )

    def test_css_has_no_undefined_project_custom_properties(self):
        css = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC / "assets" / "custom.css", SRC / "assets" / "missing.css")
        )
        definitions = set(re.findall(r"(--[\w-]+)\s*:", css))
        references = set(re.findall(r"var\((--[\w-]+)", css))
        runtime_properties = {"--bubble-drift", "--bubble-opacity"}
        framework_properties = {name for name in references if name.startswith("--bs-")}

        self.assertEqual(
            references - definitions - runtime_properties - framework_properties,
            set(),
        )

    def test_home_and_algorithm_shells_use_light_theme_surfaces(self):
        css = (SRC / "assets" / "custom.css").read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"\.home-hero-dark\s*\{[^}]*background-color:\s*var\(--surface-page\)",
        )
        self.assertRegex(
            css,
            r"\.algo-shell\s*\{[^}]*background-color:\s*var\(--surface-page\)",
        )
        self.assertIn(".mobile-nav-toggle .navbar-toggler-icon", css)
        self.assertIn("stroke='%23102a43'", css)
        self.assertNotIn("--background-color: hsl(222", css)

    def test_financial_pages_share_theme_and_drop_dark_surface_literals(self):
        page_sources = [
            (SRC / "pages" / filename).read_text(encoding="utf-8")
            for filename in ("useconomy.py", "algorithm.py", "Bond_Market.py")
        ]
        retired_dark_colors = {
            "#0b0f19",
            "#0d1321",
            "#0f172a",
            "#111726",
            "#18233a",
            "hsl(222, 42%, 9%)",
        }

        for source in page_sources:
            self.assertIn("from theme import LIGHT_THEME", source)
            for retired_color in retired_dark_colors:
                self.assertNotIn(retired_color, source)

    def test_bond_graphs_use_responsive_centered_widths(self):
        source = (SRC / "pages" / "Bond_Market.py").read_text(encoding="utf-8")

        self.assertIn("BOND_GRAPH_STYLE_3D", source)
        self.assertIn("BOND_GRAPH_STYLE_2D", source)
        self.assertGreaterEqual(source.count("'width': 'min(100%, 1000px)'"), 3)
        self.assertIn("'overflowX': 'auto'", source)
        self.assertIn("Yield Curve (1-month to 30-year)\"", source)
        self.assertIn("<br><sup>", source)
        self.assertNotIn("'marginLeft':'10%'", source)
        self.assertNotIn("'marginRight':'10%'", source)


if __name__ == "__main__":
    unittest.main()
