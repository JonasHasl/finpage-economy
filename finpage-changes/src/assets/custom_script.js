document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        if (!e.target.matches('#finvest-dropdown-button') && !e.target.matches('#finvest-menu-container')) {
            window.dash_clientside = window.dash_clientside || {};
            window.dash_clientside.no_update = window.dash_clientside.no_update || function(value) {
                return undefined;
            };
            let event = new Event('change');
            document.getElementById('hidden-div').dispatchEvent(event);
        }
    });
});
