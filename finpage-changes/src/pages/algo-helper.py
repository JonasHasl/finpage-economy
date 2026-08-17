import ast

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback, dcc, html, dash_table
from dash.exceptions import PreventUpdate
from workbook_store import get_workbook_path, replace_workbook_sheet, workbook_store


dash.register_page(__name__, path='/algo-helper')

SECTION_CARD_STYLE = {
    'background': 'linear-gradient(180deg, rgba(255,255,255,0.98), rgba(246,249,252,0.94))',
    'borderRadius': '26px',
    'padding': '1.35rem',
    'border': '1px solid rgba(190,214,235,0.85)',
    'boxShadow': '0 18px 45px rgba(10,33,59,0.09)'
}

INPUT_STYLE = {
    'width': '100%',
    'borderRadius': '14px',
    'border': '1px solid #d7e3ef',
    'padding': '0.9rem 1rem',
    'fontSize': '1rem',
    'backgroundColor': 'white',
    'color': '#27425c'
}

BUTTON_STYLE = {
    'background': 'linear-gradient(135deg, #0a213b, #1e3a5a)',
    'color': 'white',
    'border': 'none',
    'borderRadius': '999px',
    'padding': '0.85rem 1.4rem',
    'fontWeight': '600',
    'boxShadow': '0 12px 30px rgba(10,33,59,0.18)'
}

SECONDARY_BUTTON_STYLE = {
    'background': 'white',
    'color': '#0a213b',
    'border': '1px solid #bed6eb',
    'borderRadius': '999px',
    'padding': '0.85rem 1.4rem',
    'fontWeight': '600',
    'boxShadow': '0 12px 30px rgba(10,33,59,0.08)'
}

MODEL_TO_SHEET = {'2015': '2015', '2020': '2020'}
MODEL_LABELS = {'2015': 'Since 2015 Model', '2020': 'Since 2020 Model'}


def parse_ticker_input(raw_value: str):
    if not raw_value or not raw_value.strip():
        raise ValueError('Please enter a ticker list.')

    text = raw_value.strip()

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, str):
            tickers = [parsed]
        else:
            tickers = list(parsed)
    except Exception:
        tickers = [item.strip() for item in text.split(',') if item.strip()]

    cleaned = []
    for ticker in tickers:
        value = str(ticker).strip().strip("\"'").upper()
        if value:
            cleaned.append(value)

    if len(cleaned) != 7:
        raise ValueError('Please provide exactly 7 tickers.')
    if len(set(cleaned)) != 7:
        raise ValueError('Tickers must be unique.')

    return cleaned


def load_sheet(sheet_name: str):
    df = pd.read_excel(get_workbook_path(), sheet_name=sheet_name)
    for col in ['ValidFrom', 'ValidTo']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def get_sheet_max_valid_to(df: pd.DataFrame):
    max_valid_to = pd.to_datetime(df['ValidTo'], errors='coerce').max()
    if pd.isna(max_valid_to):
        raise ValueError('Could not determine max ValidTo in the selected sheet.')
    return max_valid_to


def normalize_symbol(series: pd.Series):
    return series.astype(str).str.upper().str.strip()


def dataframe_for_display(df: pd.DataFrame):
    display_df = df.copy()
    for col in ['ValidFrom', 'ValidTo']:
        if col in display_df.columns:
            display_df[col] = pd.to_datetime(display_df[col], errors='coerce').dt.strftime('%Y-%m-%d')
    return display_df


def base_table_style():
    return {
        'style_cell': {
            'textAlign': 'left',
            'padding': '16px 18px',
            'fontFamily': 'Arial, sans-serif',
            'fontSize': '14px',
            'lineHeight': '1.45',
            'color': '#27425c',
            'backgroundColor': 'rgba(255,255,255,0.96)',
            'border': '1px solid rgba(225,229,233,0.75)',
            'minWidth': '120px',
            'width': '120px',
            'maxWidth': '260px',
            'whiteSpace': 'normal'
        },
        'style_data': {
            'backgroundColor': 'rgba(255,255,255,0.96)',
            'border': '1px solid rgba(225,229,233,0.75)'
        },
        'style_data_conditional': [
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
        ],
        'style_header': {
            'backgroundColor': '#0f2744',
            'color': 'white',
            'fontWeight': 'bold',
            'fontFamily': 'Arial, sans-serif',
            'fontSize': '15px',
            'padding': '16px 18px',
            'border': '1px solid #004172',
            'textAlign': 'center'
        },
        'style_table': {
            'overflowX': 'auto',
            'borderRadius': '14px',
            'boxShadow': '0 6px 18px rgba(0,0,0,0.06)',
            'border': '1px solid #e1e5e9',
            'margin': '0.75rem 0 0 0',
            'maxHeight': '720px',
            'overflowY': 'auto'
        }
    }


def build_columns(df: pd.DataFrame, editable: bool):
    return [{'name': col, 'id': col, 'editable': editable} for col in df.columns]


def build_read_only_table(df: pd.DataFrame, table_id: str):
    display_df = dataframe_for_display(df)
    return dash_table.DataTable(
        id=table_id,
        data=display_df.to_dict('records'),
        columns=build_columns(display_df, editable=False),
        editable=False,
        row_deletable=False,
        sort_action='native',
        filter_action='native',
        page_size=20,
        cell_selectable=False,
        export_format='xlsx',
        export_headers='display',
        **base_table_style()
    )


def saved_sheet_editor_values(sheet_name: str):
    display_df = dataframe_for_display(load_sheet(sheet_name))
    return display_df.to_dict('records'), build_columns(display_df, editable=True)


def build_proposed_sheet(sheet_name: str, from_date_raw: str, tickers):
    if not get_workbook_path().exists():
        raise FileNotFoundError('AlgoComposition.xlsx was not found in the project root.')

    from_date = pd.to_datetime(from_date_raw)
    if pd.isna(from_date):
        raise ValueError('Please provide a valid FromDate.')

    df = load_sheet(sheet_name)
    max_valid_to = get_sheet_max_valid_to(df)
    outgoing_valid_to = from_date - pd.Timedelta(days=1)
    equal_weight = 1 / len(tickers)

    active_mask = (df['ValidFrom'] <= from_date) & (df['ValidTo'] >= from_date)
    active_df = df.loc[active_mask].copy()
    active_symbols = set(normalize_symbol(active_df['Symbol']))
    new_symbols = set(tickers)

    outgoing_symbols = active_symbols - new_symbols
    incoming_symbols = new_symbols - active_symbols
    unchanged_symbols = active_symbols & new_symbols

    proposed_df = df.copy()

    if outgoing_symbols:
        outgoing_mask = active_mask & normalize_symbol(proposed_df['Symbol']).isin(outgoing_symbols)
        proposed_df.loc[outgoing_mask, 'ValidTo'] = outgoing_valid_to

    template_lookup = (
        proposed_df.assign(SymbolKey=normalize_symbol(proposed_df['Symbol']))
        .sort_values(['SymbolKey', 'ValidTo', 'ValidFrom'])
        .drop_duplicates('SymbolKey', keep='last')
        .set_index('SymbolKey')
        .to_dict('index')
    )

    new_rows = []
    for ticker in tickers:
        if ticker in unchanged_symbols:
            continue

        row_data = {col: pd.NA for col in proposed_df.columns}
        template = template_lookup.get(ticker)

        if template:
            for col in proposed_df.columns:
                if col in template:
                    row_data[col] = template[col]

        row_data['Symbol'] = ticker
        row_data['ValidFrom'] = from_date
        row_data['ValidTo'] = max_valid_to

        if 'Weight' in proposed_df.columns:
            row_data['Weight'] = equal_weight

        if 'Company' in proposed_df.columns:
            existing_company = template.get('Company') if template else None
            if pd.isna(existing_company) or existing_company is None or str(existing_company).strip() == '':
                existing_company = ticker
            row_data['Company'] = existing_company

        new_rows.append(row_data)

    if new_rows:
        new_rows_df = pd.DataFrame(new_rows, columns=proposed_df.columns)
        proposed_df = pd.concat([proposed_df, new_rows_df], ignore_index=True)

    return {
        'sheet_name': sheet_name,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'outgoing_symbols': sorted(outgoing_symbols),
        'incoming_symbols': sorted(incoming_symbols),
        'unchanged_symbols': sorted(unchanged_symbols),
        'proposed_df': proposed_df[proposed_df.columns].copy(),
        'sheet_columns': list(proposed_df.columns),
    }


def validate_review_table(df: pd.DataFrame, sheet_columns):
    missing_columns = [col for col in sheet_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f'Missing columns in review table: {missing_columns}')

    validated_df = df[sheet_columns].copy()
    validated_df['Symbol'] = validated_df['Symbol'].astype(str).str.strip().str.upper()

    if validated_df['Symbol'].eq('').any():
        raise ValueError('Symbol cannot be blank in the review table.')

    if 'ValidFrom' in validated_df.columns:
        validated_df['ValidFrom'] = pd.to_datetime(validated_df['ValidFrom'], errors='coerce')
        if validated_df['ValidFrom'].isna().any():
            raise ValueError('All ValidFrom values must be valid dates.')

    if 'ValidTo' in validated_df.columns:
        validated_df['ValidTo'] = pd.to_datetime(validated_df['ValidTo'], errors='coerce')
        if validated_df['ValidTo'].isna().any():
            raise ValueError('All ValidTo values must be valid dates.')

    if 'Weight' in validated_df.columns:
        validated_df['Weight'] = pd.to_numeric(validated_df['Weight'], errors='coerce')
        if validated_df['Weight'].isna().any():
            raise ValueError('All Weight values must be numeric.')

    if 'Company' in validated_df.columns:
        validated_df['Company'] = validated_df['Company'].astype(str).str.strip()

    if 'ValidFrom' in validated_df.columns and 'ValidTo' in validated_df.columns:
        if (validated_df['ValidFrom'] > validated_df['ValidTo']).any():
            raise ValueError('Each row must have ValidFrom less than or equal to ValidTo.')

    return validated_df


def save_reviewed_sheet(sheet_name: str, reviewed_df: pd.DataFrame):
    replace_workbook_sheet(sheet_name, reviewed_df)


review_table_styles = base_table_style()

layout = dbc.Container([
    dcc.Store(id='helper-sheet-columns-store'),
    dcc.Store(id='helper-selected-sheet-store'),

    html.Div(className='beforediv'),

    html.Div([
        html.Div('Algorithm composition helper', style={
            'display': 'inline-block',
            'padding': '0.45rem 1rem',
            'borderRadius': '999px',
            'background': 'linear-gradient(135deg, rgba(0,65,114,0.10), rgba(30,58,90,0.16))',
            'border': '1px solid rgba(0,65,114,0.12)',
            'color': '#004172',
            'fontSize': '0.92rem',
            'letterSpacing': '0.04em',
            'textTransform': 'uppercase',
            'fontWeight': '600',
            'marginBottom': '1rem'
        }),
        html.H1('Update AlgoComposition.xlsx', className='headerfinvest', style={
            'textAlign': 'center',
            'marginBottom': '0.75rem',
            'color': '#0f2744',
            'fontWeight': '500',
            'letterSpacing': '-0.03em',
            'lineHeight': '1.05'
        }),
        html.P(
            'Build a proposed updated sheet from your 7 tickers and FromDate, review or edit it, then save it to the selected sheet.',
            style={
                'textAlign': 'center',
                'fontSize': '1.05rem',
                'margin': '0 auto',
                'maxWidth': '920px',
                'fontWeight': '400',
                'lineHeight': '1.75',
                'color': '#516274'
            }
        )
    ], style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.5rem auto',
        'padding': '2.6rem 2rem 2rem 2rem',
        'borderRadius': '28px',
        'background': 'linear-gradient(180deg, rgba(255,255,255,0.96), rgba(237,243,244,0.92))',
        'boxShadow': '0 24px 70px rgba(10,33,59,0.12)',
        'border': '1px solid rgba(190,214,235,0.85)',
        'position': 'relative',
        'overflow': 'hidden'
    }),

    html.Div([
        dbc.Row([
            dbc.Col([
                html.Div('Model window', style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#5f7488', 'marginBottom': '0.55rem'}),
                dcc.Dropdown(
                    id='helper-model-selector',
                    options=[
                        {'label': MODEL_LABELS['2015'], 'value': '2015'},
                        {'label': MODEL_LABELS['2020'], 'value': '2020'}
                    ],
                    value='2020',
                    clearable=False
                )
            ], xs=12, md=4),
            dbc.Col([
                html.Div('FromDate', style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#5f7488', 'marginBottom': '0.55rem'}),
                dcc.DatePickerSingle(id='helper-from-date', display_format='YYYY-MM-DD')
            ], xs=12, md=3),
            dbc.Col([
                html.Div('Tickers', style={'fontSize': '0.85rem', 'fontWeight': '600', 'color': '#5f7488', 'marginBottom': '0.55rem'}),
                dcc.Textarea(
                    id='helper-ticker-input',
                    value="['AVGO', 'DELL', 'INTU', 'MU', 'NVDA', 'PLTR', 'SNDK']",
                    style={**INPUT_STYLE, 'height': '110px'}
                )
            ], xs=12, md=5)
        ], className='g-3'),

        html.Div([
            html.Button('Build proposed table', id='helper-build-button', n_clicks=0, style=BUTTON_STYLE),
            html.Button('Submit reviewed table to Excel', id='helper-save-button', n_clicks=0, style=SECONDARY_BUTTON_STYLE),
        ], style={'display': 'flex', 'justifyContent': 'center', 'gap': '12px', 'marginTop': '1.25rem'}),

        html.Div(id='helper-build-status-message', style={'marginTop': '1rem'}),
        html.Div(id='helper-save-status-message', style={'marginTop': '0.75rem'})
    ], style={
        'maxWidth': '1120px',
        'margin': '0 auto 1.75rem auto',
        'padding': '1.4rem 1.5rem',
        'backgroundColor': 'rgba(255,255,255,0.88)',
        'border': '1px solid rgba(190,214,235,0.85)',
        'borderRadius': '24px',
        'boxShadow': '0 14px 38px rgba(10,33,59,0.08)'
    }),

    dbc.Row([
        dbc.Col(html.Div([
            html.Div('Reviewed sheet to be saved', style={
                'fontSize': '0.92rem',
                'fontWeight': '700',
                'letterSpacing': '0.03em',
                'textTransform': 'uppercase',
                'color': '#5f7488',
                'marginBottom': '0.8rem'
            }),
            dash_table.DataTable(
                id='helper-review-table',
                data=[],
                columns=[],
                editable=True,
                row_deletable=False,
                sort_action='native',
                filter_action='native',
                page_size=20,
                **review_table_styles
            )
        ], style=SECTION_CARD_STYLE), width=12)
    ], style={'maxWidth': '1120px', 'margin': '0 auto 1.5rem auto'}),

    dbc.Row([
        dbc.Col(html.Div([
            html.Div('Current saved selected sheet', style={
                'fontSize': '0.92rem',
                'fontWeight': '700',
                'letterSpacing': '0.03em',
                'textTransform': 'uppercase',
                'color': '#5f7488',
                'marginBottom': '0.8rem'
            }),
            html.P(
                'Edit cells, add rows, or remove rows here. Nothing is saved until you click Save edits to Excel.',
                style={'margin': '0 0 0.8rem', 'color': '#516274'}
            ),
            html.Div([
                html.Button('Add row', id='helper-current-add-row', n_clicks=0, style=SECONDARY_BUTTON_STYLE),
                html.Button('Save edits to Excel', id='helper-current-save-button', n_clicks=0, style=BUTTON_STYLE),
                html.Button('Discard unsaved edits', id='helper-current-reload-button', n_clicks=0, style=SECONDARY_BUTTON_STYLE),
            ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '12px', 'marginBottom': '0.8rem'}),
            html.Div(id='helper-current-sheet-status-message', style={'marginBottom': '0.5rem'}),
            dash_table.DataTable(
                id='helper-current-sheet-editor',
                data=[],
                columns=[],
                editable=True,
                row_deletable=True,
                sort_action='native',
                filter_action='native',
                page_size=20,
                export_format='xlsx',
                export_headers='display',
                **review_table_styles
            )
        ], style=SECTION_CARD_STYLE), width=12)
    ], style={'maxWidth': '1120px', 'margin': '0 auto 2rem auto'}),
], fluid=True)


@callback(
    Output('helper-build-status-message', 'children'),
    Output('helper-save-status-message', 'children'),
    Output('helper-review-table', 'data'),
    Output('helper-review-table', 'columns'),
    Output('helper-current-sheet-editor', 'data'),
    Output('helper-current-sheet-editor', 'columns'),
    Output('helper-sheet-columns-store', 'data'),
    Output('helper-selected-sheet-store', 'data'),
    Output('helper-current-sheet-status-message', 'children'),
    Input('helper-model-selector', 'value'),
    Input('helper-build-button', 'n_clicks'),
    Input('helper-save-button', 'n_clicks'),
    Input('helper-current-add-row', 'n_clicks'),
    Input('helper-current-save-button', 'n_clicks'),
    Input('helper-current-reload-button', 'n_clicks'),
    State('helper-from-date', 'date'),
    State('helper-ticker-input', 'value'),
    State('helper-review-table', 'data'),
    State('helper-current-sheet-editor', 'data'),
    State('helper-current-sheet-editor', 'columns'),
    State('helper-sheet-columns-store', 'data'),
    State('helper-selected-sheet-store', 'data'),
    prevent_initial_call=False
)
def helper_controller(model_value, build_clicks, save_clicks, add_row_clicks,
                      save_current_clicks, reload_current_clicks, from_date,
                      ticker_text, review_table_data, current_sheet_data,
                      current_sheet_columns, stored_sheet_columns,
                      stored_selected_sheet):
    ctx = dash.callback_context
    triggered = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else 'helper-model-selector'
    current_sheet_data_update = dash.no_update
    current_sheet_columns_update = dash.no_update

    if model_value not in MODEL_TO_SHEET:
        return '', '', dash.no_update, dash.no_update, [], [], dash.no_update, dash.no_update, ''

    selected_sheet = MODEL_TO_SHEET[model_value]

    try:
        if triggered == 'helper-model-selector':
            current_sheet_data_update, current_sheet_columns_update = saved_sheet_editor_values(selected_sheet)
            return '', '', [], [], current_sheet_data_update, current_sheet_columns_update, [], None, ''

        if triggered == 'helper-build-button':
            if not from_date:
                raise ValueError('Please select a FromDate.')

            tickers = parse_ticker_input(ticker_text)
            result = build_proposed_sheet(selected_sheet, from_date, tickers)
            proposed_df = dataframe_for_display(result['proposed_df'])
            review_columns = build_columns(proposed_df, editable=True)

            build_status = dbc.Alert([
                html.Div(
                    f"Proposed sheet ready for review: {result['sheet_name']} | FromDate: {result['from_date']}",
                    style={'fontWeight': '700', 'marginBottom': '0.4rem'}
                ),
                html.Div(f"Incoming tickers: {', '.join(result['incoming_symbols']) if result['incoming_symbols'] else 'None'}"),
                html.Div(f"Outgoing tickers: {', '.join(result['outgoing_symbols']) if result['outgoing_symbols'] else 'None'}"),
                html.Div(f"Unchanged tickers: {', '.join(result['unchanged_symbols']) if result['unchanged_symbols'] else 'None'}"),
                html.Div('Review or edit the proposed table below, then submit it to Excel.', style={'marginTop': '0.5rem'})
            ], color='info', style={'borderRadius': '16px'})

            return (
                build_status,
                '',
                proposed_df.to_dict('records'),
                review_columns,
                dash.no_update,
                dash.no_update,
                result['sheet_columns'],
                result['sheet_name'],
                ''
            )

        if triggered == 'helper-save-button':
            if not review_table_data:
                raise ValueError('Build the proposed table first before saving.')
            if not stored_sheet_columns:
                raise ValueError('Missing sheet metadata. Build the proposed table again.')
            if not stored_selected_sheet:
                raise ValueError('Missing selected sheet. Build the proposed table again.')

            reviewed_df = pd.DataFrame(review_table_data)
            reviewed_df = validate_review_table(reviewed_df, stored_sheet_columns)
            save_reviewed_sheet(stored_selected_sheet, reviewed_df)
            current_sheet_data_update, current_sheet_columns_update = saved_sheet_editor_values(stored_selected_sheet)

            save_status = dbc.Alert(
                (
                    f"Saved reviewed table to sheet {stored_selected_sheet} and synced it to GitHub."
                    if workbook_store.uses_github
                    else f"Saved reviewed table to sheet {stored_selected_sheet} in AlgoComposition.xlsx."
                ),
                color='success',
                style={'borderRadius': '16px'}
            )

            return (
                dash.no_update,
                save_status,
                dash.no_update,
                dash.no_update,
                current_sheet_data_update,
                current_sheet_columns_update,
                dash.no_update,
                dash.no_update,
                ''
            )

        if triggered == 'helper-current-add-row':
            if not current_sheet_columns:
                raise ValueError('The saved sheet is still loading. Please try again in a moment.')

            blank_row = {column['id']: '' for column in current_sheet_columns}
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                list(current_sheet_data or []) + [blank_row],
                dash.no_update,
                dash.no_update,
                dash.no_update,
                ''
            )

        if triggered == 'helper-current-save-button':
            if not current_sheet_data:
                raise ValueError('The saved sheet is empty. Add a valid row before saving.')

            current_sheet_columns = list(load_sheet(selected_sheet).columns)
            edited_df = validate_review_table(pd.DataFrame(current_sheet_data), current_sheet_columns)
            save_reviewed_sheet(selected_sheet, edited_df)
            current_sheet_data_update, current_sheet_columns_update = saved_sheet_editor_values(selected_sheet)

            save_status = dbc.Alert(
                (
                    f"Saved edits to sheet {selected_sheet} and synced them to GitHub."
                    if workbook_store.uses_github
                    else f"Saved edits to sheet {selected_sheet} in AlgoComposition.xlsx."
                ),
                color='success',
                style={'borderRadius': '16px'}
            )

            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                current_sheet_data_update,
                current_sheet_columns_update,
                dash.no_update,
                dash.no_update,
                save_status
            )

        if triggered == 'helper-current-reload-button':
            current_sheet_data_update, current_sheet_columns_update = saved_sheet_editor_values(selected_sheet)
            discard_status = dbc.Alert(
                'Discarded unsaved edits and reloaded the saved sheet.',
                color='secondary',
                style={'borderRadius': '16px'}
            )

            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                current_sheet_data_update,
                current_sheet_columns_update,
                dash.no_update,
                dash.no_update,
                discard_status
            )

        raise PreventUpdate

    except Exception as exc:
        error_alert = dbc.Alert(str(exc), color='danger', style={'borderRadius': '16px'})

        if triggered == 'helper-save-button':
            return dash.no_update, error_alert, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, ''

        if triggered in {'helper-current-add-row', 'helper-current-save-button', 'helper-current-reload-button'}:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, error_alert

        return error_alert, '', dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, ''
