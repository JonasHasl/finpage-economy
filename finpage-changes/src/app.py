from dash import Dash, html, dcc, Input, Output, State, callback_context
import dash
import dash_bootstrap_components as dbc
import os
import socket
from contextlib import closing

os.chdir(os.path.dirname(os.path.abspath(__file__)))

external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "custom.css",
    "missing.css",
    "https://use.fontawesome.com/releases/v5.8.1/css/all.css",
]

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=external_stylesheets,
    meta_tags=[
        {
            "name": "viewport",
            "content": "width=device-width, initial-scale=1, maximum-scale=1",
        }
    ],
    suppress_callback_exceptions=True,
    prevent_initial_callbacks="initial_duplicate",
)

server = app.server

NAV_LINK_STYLE = {
    "border": "none",
    "textTransform": "none",
    "textAlign": "left",
}

'''  
brand = dbc.NavbarBrand(
    [
        html.Span("Fin", className="first-word"),
        html.Span("vest", className="second-word"),
    ],
    href="/",
    className="brand-link",
)
'''

nav_links = dbc.Nav(
    [
        dbc.NavItem(
            dbc.NavLink(
                "Home",
                href="/",
                className="top-nav-link",
                style=NAV_LINK_STYLE,
                active="exact",
            ),
            className="menuitemtop",
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Economy",
                href="/economy",
                className="top-nav-link",
                style=NAV_LINK_STYLE,
                active="exact",
            ),
            className="menuitemtop",
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Bond Market",
                href="/yield_curves",
                className="top-nav-link",
                style=NAV_LINK_STYLE,
                active="exact",
            ),
            className="menuitemtop",
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Algorithm",
                href="/portfolio-daily",
                className="top-nav-link",
                style=NAV_LINK_STYLE,
                active="exact",
            ),
            className="menuitemtop",
        ),
        dbc.NavItem(
            dbc.NavLink(
                "Comparison",
                href="/comparison",
                className="top-nav-link",
                style=NAV_LINK_STYLE,
                active="exact",
            ),
            className="menuitemtop",
        ),
    ],
    id="output_div2",
    className="top-nav ms-auto",
    navbar=True,
)

header_banner = dbc.Navbar(
    dbc.Container(
        [
            dbc.NavbarToggler(
                id="navbar-toggler",
                n_clicks=0,
                className="mobile-nav-toggle",
            ),
            dbc.Collapse(
                nav_links,
                id="navbar-collapse",
                is_open=False,
                navbar=True,
            ),
        ],
        fluid=True,
        className="navbar-shell",
    ),
    sticky="top",
    className="headerbanner",
)

contact = html.Div(
    [
        html.H3("Contact Information"),
        html.A(
            html.Span(
                "jonas_fbh@hotmail.com",
                style={
                    "display": "inline-block",
                    "fontSize": "1rem",
                    "textAlign": "center",
                    "color": "black",
                    "paddingBottom": "2px",
                },
            ),
            href="mailto:jonas_fbh@hotmail.com",
        ),
        html.Br(),
        html.A(
            html.Span(
                "https://www.linkedin.com/in/jonashasl",
                style={
                    "display": "inline-block",
                    "fontSize": "1rem",
                    "textAlign": "center",
                    "color": "black",
                    "paddingBottom": "2px",
                },
            ),
            href="https://www.linkedin.com/in/jonashasl",
            target="_blank",
            rel="noopener noreferrer",
        ),
        html.Br(),
        html.A(
            html.Span(
                "+47 45101329",
                style={
                    "display": "inline-block",
                    "fontSize": "1rem",
                    "textAlign": "center",
                    "color": "black",
                    "paddingBottom": "2px",
                },
            ),
            href="tel:+4745101329",
        ),
    ],
    style={"color": "black", "fontWeight": "normal", "textAlign": "center"},
    className="footer-left",
)

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        html.Div(id="hidden-div", style={"display": "none"}),
        header_banner,
        html.Main(
            dash.page_container,
            className="app-main",
        ),
        # html.Div([contact], className="footer")
    ],
    className="app-shell",
)

@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks"), Input("url", "pathname")],
    State("navbar-collapse", "is_open"),
    prevent_initial_call=True,
)
def handle_navbar_state(n_clicks, pathname, is_open):
    ctx = callback_context

    if not ctx.triggered:
        return is_open

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "url":
        return False

    if trigger_id == "navbar-toggler":
        return not is_open

    return is_open

def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

if __name__ == "__main__":
    app.run(debug=True, port=find_free_port())