# Copyright 2019-2025 AstroLab Software
# Author: Julien Peloton
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities for managing the Fink search bar"""

import dash
from dash import (
    html,
    dcc,
    Input,
    Output,
    State,
    no_update,
    clientside_callback,
    ALL,
)

from dash_autocomplete_input import AutocompleteInput
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import app


from apps.helpers import help_popover, message_help
from apps.dataclasses import fink_classes
from apps.parse import parse_query

# Smart search field
quick_fields = [
    ["last", "Number of latest alerts to show. Must be used with the `class` keyword."],
    [
        "radius",
        "Radius for cone search\nMay be used as either `r` or `radius`\nIn arcseconds by default, use `r=1m` or `r=2d` for arcminutes or degrees, correspondingly",
    ],
    ["after", "Lower timit on alert time\nISO time, MJD or JD"],
    ["before", "Upper timit on alert time\nISO time, MJD or JD"],
    ["window", "Time window length\nDays"],
]

fink_search_bar = (
    [
        html.Div(
            [
                html.Span("Quick fields:", className="text-secondary"),
            ]
            + [
                html.Span(
                    [
                        html.A(
                            __[0],
                            title=__[1],
                            id={
                                "type": "search_bar_quick_field",
                                "index": _,
                                "text": __[0],
                            },
                            n_clicks=0,
                            className="ms-2 link text-decoration-none",
                        ),
                        " ",
                    ]
                )
                for _, __ in enumerate(quick_fields)
            ]
            + [
                html.Span(
                    dmc.Switch(
                        radius="xl",
                        size="sm",
                        offLabel=DashIconify(icon="radix-icons:id-card", width=15),
                        onLabel=DashIconify(icon="radix-icons:table", width=15),
                        color="orange",
                        checked=False,
                        persistence=True,
                        id="results_table_switch",
                    ),
                    className="float-end",
                    title="Show results as cards or table",
                ),
            ],
            className="ps-4 pe-4 mb-0 mt-1",
        ),
    ]
    + [dmc.Space(h=2)]
    + [
        html.Div(
            # className='p-0 m-0 border shadow-sm rounded-3',
            # className="pt-0 pb-0 ps-1 pe-1 m-0 rcorners2 box-shadow",
            className="pt-0 pb-0 ps-1 pe-1 m-0 search_bar box-shadow rcorners2",
            id="search_bar",
            # className='rcorners2',
            children=[
                dbc.InputGroup(
                    [
                        # History
                        dmc.Menu(
                            [
                                dmc.MenuTarget(
                                    dmc.ActionIcon(
                                        DashIconify(icon="bi:clock-history"),
                                        color="gray",
                                        variant="transparent",
                                        radius="xl",
                                        size="lg",
                                        # title="Search history",
                                    )
                                ),
                                dmc.MenuDropdown(
                                    [
                                        dmc.MenuLabel("Search history is empty"),
                                    ],
                                    className="shadow rounded",
                                    id="search_history_menu",
                                ),
                            ],
                            zIndex=1000000,
                        ),
                        # Main input
                        AutocompleteInput(
                            id="search_bar_input",
                            placeholder="Search, and you will find",
                            component="input",
                            trigger=[
                                "class:",
                                "class=",
                                "last:",
                                "last=",
                                "radius:",
                                "radius=",
                                "r:",
                                "r=",
                                "trend=",
                                "trend:",
                            ],
                            options={
                                "class:": fink_classes,
                                "class=": fink_classes,
                                "last:": ["1", "10", "100", "1000"],
                                "last=": ["1", "10", "100", "1000"],
                                "radius:": ["10", "60", "10m", "30m"],
                                "radius=": ["10", "60", "10m", "30m"],
                                "r:": ["10", "60", "10m", "30m"],
                                "r=": ["10", "60", "10m", "30m"],
                                "trend=": [
                                    "rising",
                                    "fading",
                                    "low_state",
                                    "new_low_state",
                                ],
                            },
                            maxOptions=0,
                            className="inputbar form-control border-0",
                            quoteWhitespaces=True,
                            autoFocus=True,
                            ignoreCase=True,
                            triggerInsideWord=False,
                            matchAny=True,
                        ),
                        # Clear
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:clear-bold"),
                            n_clicks=0,
                            id="search_bar_clear",
                            color="gray",
                            variant="subtle",
                            radius="xl",
                            size="lg",
                            # title="Clear the input",
                        ),
                        # Submit
                        dbc.Spinner(
                            dmc.ActionIcon(
                                DashIconify(icon="tabler:search", width=20),
                                n_clicks=0,
                                id="search_bar_submit",
                                color="gray",
                                variant="transparent",
                                radius="xl",
                                size="lg",
                                # loaderProps={"variant": "dots", "color": "orange"},
                                # title="Search",
                            ),
                            size="sm",
                            color="warning",
                        ),
                        # Help popup
                        help_popover(
                            [dcc.Markdown(message_help)],
                            "help_search",
                            trigger=dmc.ActionIcon(
                                DashIconify(icon="mdi:help"),
                                id="help_search",
                                color="gray",
                                variant="transparent",
                                radius="xl",
                                size="lg",
                                # className="d-none d-sm-flex"
                                # title="Show some help",
                            ),
                        ),
                    ]
                ),
                # Search suggestions
                dbc.Collapse(
                    dbc.ListGroup(
                        id="search_bar_suggestions",
                    ),
                    id="search_bar_suggestions_collapser",
                    is_open=False,
                ),
                # Debounce timer
                dcc.Interval(
                    id="search_bar_timer", interval=2000, max_intervals=1, disabled=True
                ),
                dcc.Store(
                    id="search_history_store",
                    storage_type="local",
                ),
            ],
        )
    ]
)

# Time-based debounce from https://joetatusko.com/2023/07/11/time-based-debouncing-with-plotly-dash/
clientside_callback(
    """
    function start_suggestion_debounce_timer(value, n_submit, n_clicks, n_intervals) {
        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);
        if (triggered == 'search_bar_input.n_submit' || triggered == 'search_bar_submit.n_clicks')
            return [dash_clientside.no_update, true];

        if (n_intervals > 0)
            return [0, false];
        else
            return [dash_clientside.no_update, false];
    }
    """,
    [Output("search_bar_timer", "n_intervals"), Output("search_bar_timer", "disabled")],
    Input("search_bar_input", "value"),
    Input("search_bar_input", "n_submit"),
    Input("search_bar_submit", "n_clicks"),
    State("search_bar_timer", "n_intervals"),
    prevent_initial_call=True,
)


# Search history
@app.callback(
    Output("search_history_menu", "children"),
    Input("search_history_store", "timestamp"),
    Input("search_history_store", "data"),
)
def update_search_history_menu(timestamp, history):
    if history:
        return [
            dmc.MenuLabel("Search history"),
        ] + [
            dmc.MenuItem(
                item,
                id={
                    "type": "search_bar_completion",
                    "index": 1000 + i,
                    "text": str(item),
                },
            )
            for i, item in enumerate(history[::-1])
        ]
    else:
        return no_update


# Update suggestions on (debounced) input
@app.callback(
    Output("search_bar_suggestions", "children"),
    Output("search_bar_submit", "children"),
    Output("search_bar_suggestions_collapser", "is_open"),
    Input("search_bar_timer", "n_intervals"),
    Input("search_bar_input", "n_submit"),
    Input("search_bar_submit", "n_clicks"),
    # Next input uses dynamically created source, so has to be pattern-matching
    Input({"type": "search_bar_suggestion", "value": ALL}, "n_clicks"),
    State("search_bar_input", "value"),
    prevent_initial_call=True,
)
def update_suggestions(n_intervals, n_submit, n_clicks, s_n_clicks, value):
    # Clear the suggestions on submit by various means
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id in [
        "search_bar_input",
        "search_bar_submit",
        '{"type":"search_bar_suggestion","value":0}',
    ]:
        return no_update, no_update, False

    # Did debounce trigger fire?..
    if n_intervals != 1:
        return no_update, no_update, no_update

    if not value.strip():
        return None, no_update, False

    query = parse_query(value, timeout=5)
    suggestions = []

    params = query["params"]

    if not query["action"]:
        return None, no_update, False

    if query["action"] == "unknown":
        content = [html.Div(html.Em("Query not recognized", className="m-0"))]
    else:
        content = []

        if query["completions"]:
            completions = []

            for i, item in enumerate(query["completions"]):
                if isinstance(item, list) or isinstance(item, tuple):
                    # We expect it to be (name, ext)
                    name = item[0]
                    ext = item[1]
                else:
                    name = item
                    ext = item

                completions.append(
                    html.A(
                        ext,
                        id={"type": "search_bar_completion", "index": i, "text": name},
                        title=name,
                        n_clicks=0,
                        className="ms-2 link text-decoration-none",
                    )
                )

            suggestions.append(
                dbc.ListGroupItem(
                    html.Div(
                        [
                            html.Span("Did you mean:", className="text-secondary"),
                        ]
                        + completions
                    ),
                    className="border-bottom p-1 mt-1 small",
                )
            )

        content += [
            dmc.Group(
                [
                    html.Strong(query["object"]) if query["object"] else None,
                    dmc.Badge(query["type"], variant="outline", color="blue")
                    if query["type"]
                    else None,
                    dmc.Badge(query["action"], variant="outline", color="red"),
                ],
                wrap="wrap",
                align="left",
            ),
            html.P(query["hint"], className="m-0"),
        ]

    if len(params):
        content += [
            html.Small(" ".join(["{}={}".format(_, params[_]) for _ in params]))
        ]

    suggestion = dbc.ListGroupItem(
        content,
        action=True,
        n_clicks=0,
        # We make it pattern-matching so that it is possible to catch it in global callbacks
        id={"type": "search_bar_suggestion", "value": 0},
        className="border-0",
    )

    suggestions.append(suggestion)

    return suggestions, no_update, True


# Completion clicked
clientside_callback(
    """
    function on_completion(n_clicks) {
        const ctx = dash_clientside.callback_context;
        let triggered_id = ctx.triggered[0].prop_id;

        if (!ctx.triggered[0].value)
            return dash_clientside.no_update;

        if (triggered_id.search('.n_clicks') > 0) {
            triggered_id = JSON.parse(triggered_id.substr(0, triggered_id.indexOf('.n_clicks')));
            return triggered_id.text + ' ';
        }
        return dash_clientside.no_update;
    }
    """,
    Output("search_bar_input", "value", allow_duplicate=True),
    Input({"type": "search_bar_completion", "index": ALL, "text": ALL}, "n_clicks"),
    prevent_initial_call=True,
)

# Quick field clicked
clientside_callback(
    """
    function on_quickfield(n_clicks, value) {
        const ctx = dash_clientside.callback_context;
        let triggered_id = ctx.triggered[0].prop_id;

        if (!ctx.triggered[0].value)
            return dash_clientside.no_update;

        if (triggered_id.search('.n_clicks') > 0) {
            triggered_id = JSON.parse(triggered_id.substr(0, triggered_id.indexOf('.n_clicks')));
            if (value)
                return value + ' ' + triggered_id.text + '=';
            else
                return triggered_id.text + '=';
        }
        return dash_clientside.no_update;
    }
    """,
    Output("search_bar_input", "value", allow_duplicate=True),
    Input({"type": "search_bar_quick_field", "index": ALL, "text": ALL}, "n_clicks"),
    State("search_bar_input", "value"),
    prevent_initial_call=True,
)

# Clear inpit field
clientside_callback(
    """
    function on_clear(n_clicks) {
        return '';
    }
    """,
    Output("search_bar_input", "value", allow_duplicate=True),
    Input("search_bar_clear", "n_clicks"),
    prevent_initial_call=True,
)
