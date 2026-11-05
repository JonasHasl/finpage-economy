// Layout switch for /economy-dashboard.
//
// The "Layout" radio (#ed-view) only changes which class sits on #ed-page; the
// two layouts live in economy-dashboard.css.  Doing it client-side keeps the
// switch instant and means no data is reloaded.
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.economy_dashboard = {
  set_layout: function (view) {
    var mode = view === "scroll" ? "scroll" : "dashboard";

    // The charts change height with the layout; Plotly resizes on window
    // resize, so nudge it once the new class has been applied.
    window.setTimeout(function () {
      window.dispatchEvent(new Event("resize"));
    }, 60);

    return "ed-page ed-page--" + mode;
  },
};
