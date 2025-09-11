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

from dash import (
    html,
    dcc,
    Input,
    Output,
    clientside_callback,
)

import dash_bootstrap_components as dbc

import dash_mantine_components as dmc
from dash_iconify import DashIconify


from app import server
from app import app

from apps.configuration import extract_configuration
from apps.searchbar import fink_search_bar
import apps.search_results  # noqa: F401

from apps import summary

# from apps import summary, about, statistics, query_cluster, gw, xmatch

# from apps.utils import markdownify_objectid, class_colors, simbad_types
# from apps.utils import isoify_time
# from apps.utils import convert_jd
# from apps.utils import retrieve_oid_from_metaname
# from apps.utils import help_popover
# from apps.utils import request_api
# from apps.utils import extract_configuration
# from apps.plotting import draw_cutouts_quickview, draw_lightcurve_preview
# from apps.cards import card_search_result


clientside_callback(
    """
    function drawer_switch(n_clicks, pathname) {
        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);

        /* Change the page title based on its path */
        if (triggered == 'url.pathname') {
            let title = 'Fink/Rubin Science Portal';

            if (pathname.startsWith('/ZTF'))
                title = pathname.substring(1, 13) + ' : ' + title;
            else if (pathname.startsWith('/gw'))
                title = 'Gravitational Waves : ' + title;
            else if (pathname.startsWith('/download'))
                title = 'Data Transfer : ' + title;
            else if (pathname.startsWith('/stats'))
                title = 'Statistics : ' + title;
            else if (pathname.startsWith('/api'))
                title = 'API : ' + title;

            document.title = title;
        }

        if (triggered == 'drawer-button.n_clicks')
            return true;
        else
            return false;
    }
    """,
    Output("drawer", "opened"),
    Input("drawer-button", "n_clicks"),
    Input("url", "pathname"),
    prevent_initial_call=True,
)

navbar = dmc.AppShellHeader(
    id="navbar",
    zIndex=1000,
    p=0,
    m=0,
    className="shadow-sm",
    children=[
        dmc.Space(h=10),
        dmc.Container(
            fluid=True,
            children=dmc.Group(
                # align="stretch",
                justify="space-between",
                children=[
                    # Right menu
                    dmc.Group(
                        align="start",
                        justify="flex-start",
                        children=[
                            # Burger
                            dmc.ActionIcon(
                                DashIconify(icon="dashicons:menu", width=30),
                                id="drawer-button",
                                n_clicks=0,
                                variant="transparent",
                                style={"color": "gray"},
                            ),
                            dmc.Anchor(
                                dmc.Group(
                                    [
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon="ion:search-outline",
                                                width=22,
                                            ),
                                            radius=30,
                                            size=32,
                                            variant="outline",
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Search",
                                            visibleFrom="md",
                                            style={"color": "gray"},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                href="/",
                                variant="text",
                                style={
                                    "textTransform": "capitalize",
                                    "textDecoration": "none",
                                },
                            ),
                            dmc.Anchor(
                                dmc.Group(
                                    [
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon="ion:cloud-download-outline",
                                                width=22,
                                            ),
                                            radius=30,
                                            size=32,
                                            variant="outline",
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Data Transfer",
                                            visibleFrom="md",
                                            style={"color": "gray"},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                href="/download",
                                variant="text",
                                style={
                                    "textTransform": "capitalize",
                                    "textDecoration": "none",
                                },
                            ),
                            dmc.Anchor(
                                dmc.Group(
                                    [
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon="material-symbols:join-right",
                                                width=22,
                                            ),
                                            radius=30,
                                            size=32,
                                            variant="outline",
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Xmatch",
                                            visibleFrom="md",
                                            style={"color": "gray"},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                href="/xmatch",
                                variant="text",
                                style={
                                    "textTransform": "capitalize",
                                    "textDecoration": "none",
                                },
                            ),
                            dmc.Anchor(
                                dmc.Group(
                                    [
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon="ion:infinite-outline",
                                                width=22,
                                            ),
                                            radius=30,
                                            size=32,
                                            variant="outline",
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Gravitational Waves",
                                            visibleFrom="md",
                                            style={"color": "gray"},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                href="/gw",
                                variant="text",
                                style={
                                    "textTransform": "capitalize",
                                    "textDecoration": "none",
                                },
                            ),
                        ],
                    ),
                    # Left menu
                    dmc.Group(
                        align="end",
                        justify="flex-end",
                        children=[
                            dmc.Anchor(
                                dmc.Group(
                                    [
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon="ion:stats-chart-outline",
                                                width=22,
                                            ),
                                            radius=30,
                                            size=32,
                                            variant="outline",
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Statistics",
                                            visibleFrom="md",
                                            style={"color": "gray"},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                href="/stats",
                                variant="text",
                                style={
                                    "textTransform": "capitalize",
                                    "textDecoration": "none",
                                },
                            ),
                        ],
                    ),
                    # Sidebar
                    dmc.Drawer(
                        children=[
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon="tabler:search",
                                        width=15,
                                        style={"marginRight": 10},
                                    ),
                                    "Explore",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        "Search",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="/",
                                        size="sm",
                                    ),
                                    dmc.Anchor(
                                        "Data Transfer",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="/download",
                                        size="sm",
                                    ),
                                    dmc.Anchor(
                                        "Gravitational Waves",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="/gw",
                                        size="sm",
                                    ),
                                    dmc.Anchor(
                                        "Statistics",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="/stats",
                                        size="sm",
                                    ),
                                ],
                                align="left",
                                gap="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon="carbon:api",
                                        width=15,
                                        style={"marginRight": 10},
                                    ),
                                    "Learn",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        "{ API }",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="https://fink-broker.readthedocs.io/en/latest/services/search/getting_started/#quick-start-api",
                                        size="sm",
                                    ),
                                    dmc.Anchor(
                                        "Tutorials",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="https://github.com/astrolabsoftware/fink-tutorials",
                                        size="sm",
                                    ),
                                ],
                                align="left",
                                gap="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                            dmc.Divider(
                                labelPosition="left",
                                label=[
                                    DashIconify(
                                        icon="tabler:external-link",
                                        width=15,
                                        style={"marginRight": 10},
                                    ),
                                    "External links",
                                ],
                                style={"marginTop": 20, "marginBottom": 20},
                            ),
                            dmc.Stack(
                                [
                                    dmc.Anchor(
                                        "Fink broker",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="https://fink-broker.org",
                                        size="sm",
                                        # color="gray",
                                    ),
                                    dmc.Anchor(
                                        "Portal bug tracker",
                                        style={
                                            "textTransform": "capitalize",
                                            "textDecoration": "none",
                                            "color": "gray",
                                        },
                                        href="https://github.com/astrolabsoftware/fink-science-portal",
                                        size="sm",
                                    ),
                                ],
                                align="left",
                                gap="sm",
                                style={"paddingLeft": 30, "paddingRight": 20},
                            ),
                        ],
                        title="Fink Science Portal",
                        id="drawer",
                        padding="md",
                        zIndex=1e7,
                        transitionProps={"transition": "pop-top-left"},
                        style={"fontColor": "gray"},
                    ),
                ],
            ),
        ),
    ],
)

# embedding the navigation bar
app.layout = dmc.MantineProvider(
    [
        dcc.Location(id="url", refresh=False),
        dmc.AppShell(
            children=[
                navbar,
                dmc.AppShellMain(
                    children=[],
                    id="page-content",
                    style={"padding-top": "55px"},  # header
                ),
            ],
            header={"height": 55},
        ),
    ],
    # theme={
    #     "primaryColor": "teal",
    #     "defaultRadius": "md",
    #     "components": {
    #         "Card": {"defaultProps": {"shadow": "md"}},
    #         "Div": {"defaultProps": {"shadow": "md"}}
    #     },
    # },
    # forceColorScheme="dark",
    # defaultColorScheme="dark"
)


@app.callback(
    [
        Output("page-content", "children"),
        Output("page-content", "className"),
    ],
    [
        Input("url", "pathname"),
        Input("url", "search"),
    ],
)
def display_page(pathname, searchurl):
    layout = dmc.MantineProvider(
        [
            dbc.Container(
                [
                    # Logo shown by default
                    dbc.Collapse(
                        [
                            dmc.Space(h=200),
                            dbc.Row(
                                dbc.Col(
                                    html.Img(
                                        src="/assets/Fink_PrimaryLogo_WEB.png",
                                        style={
                                            "min-width": "200px",
                                            "max-width": "250px",
                                        },
                                    )
                                ),
                                style={"textAlign": "center"},
                                className="mt-3",
                            ),
                        ],
                        is_open=True,
                        id="logo",
                    ),
                    dbc.Row(
                        dbc.Col(
                            fink_search_bar,
                            lg={"size": 6, "offset": 3},
                            # md={"size": 10, "offset": 1},
                        ),
                        className="mt-3 mb-3",
                    ),
                ],
                fluid="lg",
            ),
            dbc.Container(
                # Default content for results part - search history
                dbc.Row(
                    dbc.Col(
                        id="search_history",
                        # Size should match the one of fink_search_bar above
                        lg={"size": 8, "offset": 2},
                        md={"size": 10, "offset": 1},
                    ),
                    className="m-3",
                ),
                id="results",
                fluid="xxl",
            ),
        ],
        # theme={
        #     "primaryColor": "teal",
        #     "defaultRadius": "md",
        #     "components": {
        #         "Card": {"defaultProps": {"shadow": "md"}},
        #         "Div": {"defaultProps": {"shadow": "md"}}
        #     },
        # },
        # forceColorScheme="dark",
        # defaultColorScheme="dark"
    )

    if pathname[1:]:
        # Other pages
        if pathname[1:].isdigit():
            # LSST object name
            return summary.layout(pathname), "home"
    else:
        # Home page
        return layout, "home"

    # if pathname == "/about":
    #     return about.layout, "home"
    # elif pathname == "/stats":
    #     return statistics.layout(), "home"
    # elif pathname == "/download":
    #     return query_cluster.layout(), "home"
    # elif pathname == "/gw":
    #     return gw.layout(), "home"
    # elif pathname == "/xmatch":
    #     return xmatch.layout(), "home"
    # elif pathname.startswith("/ZTF"):
    #     return summary.layout(pathname), "home"
    # else:
    #     if pathname[1:]:
    #         # check this is not a name generated by a user
    #         oid = retrieve_oid_from_metaname(pathname[1:])
    #         if oid is not None:
    #             return summary.layout("/" + oid), "home"
    #     return layout, "home"


server.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
server.config["JSON_SORT_KEYS"] = False

if __name__ == "__main__":
    config_args = extract_configuration("config.yml")
    app.run(config_args["HOST"], debug=True, port=config_args["PORT"])
