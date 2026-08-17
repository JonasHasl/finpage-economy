import dash
from dash import html

dash.register_page(
    __name__,
    path="/commute-map",
    name="Commute Map",
)

layout = html.Div(
    html.Iframe(src="/assets/commute-map.html"),
    className="commute-page"
)