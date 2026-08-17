import base64
import random

import dash
from dash import html


dash.register_page(__name__, path="/")


_SVG_ATTRS = (
    'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="hsl(199, 89%, 55%)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
)

# Self-contained inline icons (no external icon-font dependency) -- encoded
# as data URIs so they render as plain <img> tags, no HTML sanitizer involved.
_ICON_SVGS = {
    "trend": f'<svg {_SVG_ATTRS}><polyline points="3,17 9,11 13,15 21,5"/><polyline points="15,5 21,5 21,11"/></svg>',
    "landmark": (
        f'<svg {_SVG_ATTRS}><polygon points="12,3 21,9 3,9"/>'
        '<line x1="5" y1="9" x2="5" y2="18"/><line x1="10" y1="9" x2="10" y2="18"/>'
        '<line x1="14" y1="9" x2="14" y2="18"/><line x1="19" y1="9" x2="19" y2="18"/>'
        '<line x1="3" y1="21" x2="21" y2="21"/></svg>'
    ),
    "bars": f'<svg {_SVG_ATTRS}><line x1="6" y1="20" x2="6" y2="14"/><line x1="12" y1="20" x2="12" y2="9"/><line x1="18" y1="20" x2="18" y2="4"/></svg>',
}

_ICONS = {
    name: "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    for name, svg in _ICON_SVGS.items()
}


# Slow-floating translucent circles for the dark hero background.
_BUBBLE_SHADES = [
    "199 89% 48%",  # sky blue
    "210 80% 52%",  # bright blue
    "217 91% 60%",  # royal blue
    "199 89% 42%",  # deeper blue
    "211 96% 68%",  # light blue
]


def _make_bubble(i):
    size = 40 + random.random() * 120
    left = random.random() * 100
    duration = 16 + random.random() * 20  # 16-36s, slow drift
    delay = -random.random() * 30  # negative = mid-float on load
    drift = (random.random() - 0.5) * 140
    opacity = 0.25 + random.random() * 0.2  # 0.25-0.45, clearly visible
    color = _BUBBLE_SHADES[i % len(_BUBBLE_SHADES)]
    return html.Div(
        className="home-bubble",
        style={
            "width": f"{size}px",
            "height": f"{size}px",
            "left": f"{left}%",
            "bottom": f"-{size}px",
            "background": f"radial-gradient(circle at 32% 32%, hsl({color} / {opacity}), hsl({color} / {opacity * 0.15}) 70%)",
            "boxShadow": f"0 0 {size * 0.3}px hsl({color} / {opacity * 0.5})",
            "animationDuration": f"{duration}s",
            "animationDelay": f"{delay}s",
            "--bubble-drift": f"{drift}px",
            "--bubble-opacity": opacity,
        },
    )


def _bubbles(count=14):
    return html.Div(
        [_make_bubble(i) for i in range(count)],
        className="home-bubbles",
        **{"aria-hidden": "true"},
    )


def _quick_link(href, icon, label, hint, delay):
    return html.A(
        [
            html.Img(src=_ICONS[icon], className="home-dark-card-icon"),
            html.Div(
                [
                    html.Div(label, className="home-dark-card-title"),
                    html.Div(hint, className="home-dark-card-text"),
                ]
            ),
        ],
        href=href,
        className="home-dark-card home-fade-in-up",
        style={"animationDelay": delay},
    )


layout = html.Div(
    [
        _bubbles(),
        html.Div(
            [
                html.H1("FinPage", className="home-hero-title home-fade-in-up"),
                html.P(
                    "Markets · Macro · Strategy",
                    className="home-hero-subtitle home-fade-in-up",
                    style={"animationDelay": "0.05s"},
                ),
                html.Div(
                    [
                        _quick_link(
                            "/economy",
                            "trend",
                            "Economy",
                            "Macro indicators for the US, Norway, EU and UK",
                            "0.1s",
                        ),
                        _quick_link(
                            "/yield_curves",
                            "landmark",
                            "Bond Market",
                            "US and Norwegian government bond data",
                            "0.15s",
                        ),
                        _quick_link(
                            "/portfolio-daily",
                            "bars",
                            "Algorithm",
                            "Overview of optimized fundamental stock selection algorithm",
                            "0.2s",
                        ),
                    ],
                    className="home-hero-grid",
                ),
            ],
            className="home-hero-content",
        ),
    ],
    className="home-hero-dark",
)
