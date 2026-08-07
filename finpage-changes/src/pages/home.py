import dash
from dash import html, dcc


dash.register_page(__name__, path="/")


card_style = {
    "backgroundColor": "#F9F9F9",
    "borderRadius": "8px",
    "padding": "14px 16px",
    "boxShadow": "0px 4px 6px rgba(0, 0, 0, 0.1)",
}


title_link_style = {
    "display": "inline-block",
    "fontSize": "2rem",
    "textAlign": "center",
    "lineHeight": "1.1",
}


wide_title_link_style = {
    "display": "inline-block",
    "fontSize": "2rem",
    "width": "82%",
    "textAlign": "center",
    "lineHeight": "1.1",
}


layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.A(
                                            html.Span("Economy"),
                                            href="/economy",
                                            className="headers home-card-title-link",
                                            style=title_link_style,
                                        )
                                    ],
                                    className="home-card-title-wrap",
                                ),
                                dcc.Markdown(
                                    "Macro indicators for the US, Norway, EU and UK",
                                    className="home-card-text",
                                ),
                            ],
                            className="page-intro home-page-intro",
                            style=card_style,
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.A(
                                            [html.Span("Bond Market")],
                                            href="/yield_curves",
                                            className="headers home-card-title-link",
                                            style=wide_title_link_style,
                                        )
                                    ],
                                    className="home-card-title-wrap",
                                ),
                                dcc.Markdown(
                                    "US and Norwegian Government Bond data",
                                    className="home-card-text",
                                ),
                            ],
                            className="page-intro home-page-intro",
                            style=card_style,
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.A(
                                            [html.Span("Algorithm")],
                                            href="/portfolio-daily",
                                            className="headers home-card-title-link",
                                            style=wide_title_link_style,
                                        )
                                    ],
                                    className="home-card-title-wrap",
                                ),
                                dcc.Markdown(
                                    "Overview of optimized fundamental stock selection algorithm",
                                    className="home-card-text",
                                ),
                            ],
                            className="page-intro home-page-intro",
                            style=card_style,
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.A(
                                            [html.Span("Comparison")],
                                            href="/comparison",
                                            className="headers home-card-title-link",
                                            style=wide_title_link_style,
                                        )
                                    ],
                                    className="home-card-title-wrap",
                                ),
                                dcc.Markdown(
                                    "Cross-country charts for GDP, inflation, yields and jobs",
                                    className="home-card-text",
                                ),
                            ],
                            className="page-intro home-page-intro",
                            style=card_style,
                        ),
                    ],
                    className="page-intros fadeinelement home-intro-grid",
                ),
                html.Br(),
                html.Br(),
            ],
            className="page-intros home-hero-section",
            style={
                "backgroundImage": 'url("/assets/pretty3.JPG")',
                "backgroundSize": "cover",
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "minHeight": "100vh",
                "position": "relative",
            },
        ),
    ]
)