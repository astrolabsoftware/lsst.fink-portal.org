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
import numpy as np
from dash import (
    html,
    dcc,
    Input,
    Output,
)

import dash_bootstrap_components as dbc

import dash_mantine_components as dmc
from dash_iconify import DashIconify


from app import server
from app import app
from apps import gw
from apps import statistics
from apps import __version__

from apps.configuration import extract_configuration
from apps.searchbar import fink_search_bar
import apps.search_results  # noqa: F401
from apps.plotting import generate_rgb_color_sequence

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


def make_navlink(label, icon, href, target="_self"):
    return dmc.NavLink(
        label=label,
        leftSection=dmc.ThemeIcon(
            DashIconify(
                icon=icon,
                width=22,
            ),
            radius=30,
            size=30,
            variant="outline",
            color="gray",
            id="navbar_button_{}".format(href),
        ),
        variant="subtle",
        active="exact",
        href=href,
        target=target,
        style={
            "color": "gray",
            "padding": "0px",
            "padding-bottom": "5px",
            "background-color": "#15284F",
        },
    )


navbar = html.Div(
    children=[
        # dmc.Space(h=10),
        dmc.Stack(
            # align="stretch",
            justify="space-between",
            children=[
                # Right menu
                dmc.Stack(
                    align="flex-start",
                    justify="flex-start",
                    gap="xs",
                    children=[
                        dmc.Space(h=20),
                        html.Img(
                            src="/assets/Fink_SecondaryLogo_WEB.png",
                            style={
                                "width": 60,
                                "zIndex": 100000,
                            },
                            className="small-logo",
                        ),
                        dmc.Space(h=30),
                        make_navlink("Search", "ion:search-outline", "/"),
                        make_navlink(
                            "Transfer", "ion:cloud-download-outline", "/download"
                        ),
                        make_navlink(
                            "Xmatch", "material-symbols:join-right", "/xmatch"
                        ),
                        make_navlink("MMA", "ion:infinite-outline", "/gw"),
                        make_navlink("Statistics", "ion:stats-chart-outline", "/stats"),
                    ],
                ),
            ],
        ),
        dmc.Stack(
            # align="stretch",
            justify="space-between",
            children=dmc.Stack(
                make_navlink(
                    "v{}".format(__version__),
                    "tabler:tag",
                    "https://github.com/astrolabsoftware/lsst.fink-portal.org",
                    target="_blank",
                ),
                align="flex-start",
                justify="flex-start",
                gap="xs",
                style={
                    "position": "absolute",
                    "bottom": 10,
                },
            ),
        ),
    ],
)


@app.callback(
    [
        Output("navbar_button_/", "color"),
        Output("navbar_button_/download", "color"),
        Output("navbar_button_/xmatch", "color"),
        Output("navbar_button_/gw", "color"),
        Output("navbar_button_/stats", "color"),
    ],
    Input("url", "pathname"),
)
def change_color(pathname):
    buttons = ["/", "/download", "/xmatch", "/gw", "/stats"]
    colors = ["#F5622E" if i == pathname else "gray" for i in buttons]

    if np.all([i == "gray" for i in colors]):
        colors[0] = "#F5622E"
    return colors


@app.callback(Output("color_palette", "children"), Input("color_scale", "value"))
def make_radiocard(color_scale):
    return dmc.Group(
        [
            dmc.ActionIcon(
                color=color,
                variant="filled",
                size="xs",
            )
            for color in generate_rgb_color_sequence(color_scale)
        ],
        visibleFrom="md",
        justify="flex-end",
        wrap="nowrap",
    )


plotly_color_sets = [
    "Fink",
    "Alphabet",
    "Alphabet_r",
    "Antique",
    "Antique_r",
    "Bold",
    "Bold_r",
    "D3",
    "D3_r",
    "Dark2",
    "Dark24",
    "Dark24_r",
    "Dark2_r",
    "G10",
    "G10_r",
    "Light24",
    "Light24_r",
    "Pastel",
    "Pastel1",
    "Pastel1_r",
    "Pastel2",
    "Pastel2_r",
    "Pastel_r",
    "Plotly",
    "Plotly_r",
    "Prism",
    "Prism_r",
    "Safe",
    "Safe_r",
    "Set1",
    "Set1_r",
    "Set2",
    "Set2_r",
    "Set3",
    "Set3_r",
    "T10",
    "T10_r",
    "Vivid",
    "Vivid_r",
]


component = dmc.Box([
    dmc.Group(
        [
            dmc.Select(
                id="color_scale",
                value="Fink",
                data=[{"value": k, "label": k} for k in plotly_color_sets],
                w=110,
                # mb=10,
                persistence=True,
                searchable=True,
                clearable=True,
                radius="xl",
            ),
            html.Div(id="color_palette"),
        ],
        justify="space-around",
    ),
])

# embedding the navigation bar
app.layout = dmc.MantineProvider(
    [
        dcc.Location(id="url", refresh=False),
        dmc.AppShell(
            children=[
                dmc.AppShellHeader(
                    id="header",
                    children=[
                        dmc.Flex(
                            [
                                dmc.ActionIcon(
                                    DashIconify(icon="clarity:settings-line"),
                                    variant="subtle",
                                    color="dark",
                                    size="lg",
                                    radius="sm",
                                    id="drawer-demo-button",
                                ),
                                dmc.Drawer(
                                    id="drawer-simple",
                                    padding="md",
                                    position="right",
                                    radius="lg",
                                    overlayProps={"opacity": 0.1},
                                    transitionProps={"duration": 350},
                                    size="20%",
                                    children=[
                                        dmc.Title(
                                            "Lightcurve settings",
                                            order=4,
                                            style={"padding-top": "0px"},
                                        ),
                                        dmc.Divider(
                                            labelPosition="left",
                                            style={"marginTop": 20, "marginBottom": 20},
                                        ),
                                        dmc.Group(
                                            [
                                                dmc.Text("Units"),
                                                dmc.Select(
                                                    id="select-units",
                                                    value="magnitude",
                                                    data=[
                                                        {
                                                            "value": "magnitude",
                                                            "label": "magnitude",
                                                        },
                                                        {
                                                            "value": "flux",
                                                            "label": "flux",
                                                        },
                                                    ],
                                                    w=200,
                                                    # size="xs",
                                                    mb=5,
                                                    persistence=True,
                                                    searchable=True,
                                                    clearable=True,
                                                    radius="xl",
                                                ),
                                            ],
                                            justify="space-around",
                                            grow=True,
                                        ),
                                        dmc.Space(h=5),
                                        dmc.Group(
                                            [
                                                dmc.Text("Measurement"),
                                                dmc.Select(
                                                    id="select-measurement",
                                                    value="total",
                                                    data=[
                                                        {
                                                            "value": "total",
                                                            "label": "total",
                                                        },
                                                        {
                                                            "value": "differential",
                                                            "label": "differential",
                                                        },
                                                    ],
                                                    w=200,
                                                    mb=5,
                                                    persistence=True,
                                                    searchable=True,
                                                    clearable=True,
                                                    radius="xl",
                                                ),
                                            ],
                                            justify="space-around",
                                            grow=True,
                                        ),
                                        dmc.Space(h=5),
                                        dmc.Group(
                                            [
                                                dmc.Text("Layout"),
                                                dmc.Select(
                                                    id="select-lc-layout",
                                                    value="plain",
                                                    data=[
                                                        {
                                                            "value": "plain",
                                                            "label": "plain",
                                                        },
                                                        {
                                                            "value": "split",
                                                            "label": "split",
                                                        },
                                                    ],
                                                    w=200,
                                                    mb=5,
                                                    persistence=True,
                                                    searchable=True,
                                                    clearable=True,
                                                    radius="xl",
                                                ),
                                            ],
                                            justify="space-around",
                                            grow=True,
                                        ),
                                        dmc.Space(h=40),
                                        dmc.Title(
                                            "Color scheme",
                                            order=4,
                                            style={"padding-top": "0px"},
                                        ),
                                        dmc.Divider(
                                            labelPosition="left",
                                            style={"marginTop": 20, "marginBottom": 20},
                                        ),
                                        component,
                                    ],
                                ),
                            ],
                            justify="flex-end",
                        ),
                    ],
                    p="md",
                    style={"background-color": "#f7f7f7", "border": "0px"},
                ),
                # navbar,
                dmc.AppShellNavbar(
                    id="navbar",
                    children=navbar,
                    withBorder=False,
                    p="md",
                    style={"background-color": "#15284F"},
                    className="banner",
                ),
                dmc.AppShellMain(
                    children=[],
                    id="page-content",
                    style={"padding-top": "20px"},  # header
                ),
            ],
            # header={"height": 20},
            padding="md",
            navbar={
                "width": {"base": 60, "sm": 60, "lg": 60},
            },
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
    Output("drawer-simple", "opened"),
    Input("drawer-demo-button", "n_clicks"),
    prevent_initial_call=True,
)
def drawer_demo(n_clicks):
    return True


@app.callback(
    [
        Output("page-content", "children"),
        Output("page-content", "className"),
    ],
    [
        Input("url", "pathname"),
    ],
    prevent_initial_call=True,
)
def display_page(pathname):
    layout = html.Div(
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
                    dmc.Space(h=30),  # actionicon
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
        if pathname[1:].isdigit():
            # diaObject
            is_sso = False
        elif pathname[1:].startswith("K"):
            # ssObject
            is_sso = True
        elif pathname == "/gw":
            # GW
            return gw.layout(), "home"
        elif pathname == "/stats":
            # statistics
            return statistics.layout(), "home"
        return summary.layout(pathname, is_sso=is_sso), "home"
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
