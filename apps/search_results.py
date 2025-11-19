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
"""All functionalities for displaying results on the search page"""

import io
import dash
from dash import (
    html,
    dcc,
    Input,
    Output,
    State,
    no_update,
    clientside_callback,
    dash_table,
    ALL,
    MATCH,
)
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc

import urllib
import numpy as np
import pandas as pd
from dash_iconify import DashIconify

from apps.configuration import extract_configuration
from apps.helpers import help_popover, msg_info
from apps.parse import parse_query
from apps.dataclasses import simbad_types
from apps.api import request_api
from apps.utils import markdownify_objectid
from apps.utils import class_colors
from apps.utils import isoify_time
from apps.utils import is_row_static_or_moving
from apps.cards import card_search_result
from apps.plotting import draw_cutouts_quickview
from apps.plotting import draw_lightcurve_preview
from apps.plotting import CONFIG_PLOT

from app import app


def display_table_results(table, endpoint):
    """Display explorer results in the form of a table with a dropdown menu on top to insert more data columns.

    The dropdown menu options are taken from the client schema (Rubin & Fink). It also
    contains other derived fields from the portal (fink_additional_fields).

    Parameters
    ----------
    table: dash_table.DataTable
        Dash DataTable containing the results. Can be empty.
    endpoint: str
        Endpoint name

    Returns
    -------
    out: list of objects
        The list of objects contain:
          1. A dropdown menu to add new columns in the table
          2. Table of results
        The dropdown is shown only if the table is non-empty.
    """
    data = request_api(
        "/api/v1/schema", method="POST", json={"endpoint": endpoint}, output="json"
    )

    fink_fields = ["f:" + i for i in data["Fink science module outputs (f:)"].keys()]
    rubin_fields = ["r:" + i for i in data["Rubin original fields (r:)"].keys()]

    dropdown = dcc.Dropdown(
        id="field-dropdown2",
        options=[
            {"label": "Fink science module outputs", "disabled": True, "value": "None"},
            *[{"label": field, "value": field} for field in fink_fields],
            # {"label": "Fink additional values", "disabled": True, "value": "None"},
            # *[{"label": field, "value": field} for field in fink_additional_fields],
            {
                "label": "Original Rubin fields ({})".format(endpoint),
                "disabled": True,
                "value": "None",
            },
            *[{"label": field, "value": field} for field in rubin_fields],
        ],
        searchable=True,
        clearable=True,
        placeholder="Add more fields to the table",
    )

    switch = dmc.Switch(
        size="xs",
        radius="xl",
        label="Unique objects",
        color="orange",
        checked=False,
        id="alert-object-switch",
    )
    switch_description = "Toggle the switch to list each object only once. Only the latest alert will be displayed."

    switch_sso = dmc.Switch(
        size="xs",
        radius="xl",
        label="Unique SSO",
        color="orange",
        checked=False,
        id="alert-sso-switch",
    )
    switch_sso_description = "Toggle the switch to list each Solar System Object only once. Only the latest alert will be displayed."

    switch_tracklet = dmc.Switch(
        size="xs",
        radius="xl",
        label="Unique tracklets",
        color="orange",
        checked=False,
        id="alert-tracklet-switch",
    )
    switch_tracklet_description = "Toggle the switch to list each Tracklet only once (fast moving objects). Only the latest alert will be displayed."

    results = [
        dbc.Row(
            [
                dbc.Col(dropdown, lg=5, md=6),
                dbc.Col(
                    dmc.Tooltip(
                        children=switch,
                        w=220,
                        multiline=True,
                        withArrow=True,
                        transitionProps={"transition": "fade", "duration": 200},
                        label=switch_description,
                    ),
                    md="auto",
                ),
                dbc.Col(
                    dmc.Tooltip(
                        children=switch_sso,
                        w=220,
                        multiline=True,
                        withArrow=True,
                        transitionProps={"transition": "fade", "duration": 200},
                        label=switch_sso_description,
                    ),
                    md="auto",
                ),
                dbc.Col(
                    dmc.Tooltip(
                        children=switch_tracklet,
                        w=220,
                        multiline=True,
                        withArrow=True,
                        transitionProps={"transition": "fade", "duration": 200},
                        label=switch_tracklet_description,
                    ),
                    md="auto",
                ),
            ],
            align="center",
            justify="start",
            className="mb-2",
        ),
        table,
    ]

    return [
        html.Div(
            results,
            className="results-inner bg-opaque-100 rounded mb-4 p-2 border shadow",
            style={"overflow": "visible"},
        )
    ]


@app.callback(
    Output("aladin-lite-div-skymap", "run"),
    [
        Input("result_table", "data"),
        Input("result_table", "columns"),
        Input("modal_skymap", "is_open"),
    ],
)
def display_skymap(data, columns, is_open):
    """Display explorer result on a sky map (Aladin lite). Limited to 1000 sources total.

    TODO: image is not displayed correctly the first time

    the default parameters are:
        * PanSTARRS colors
        * FoV = 360 deg
        * Fink alerts overlayed

    Callbacks
    ----------
    Input: takes the validation flag (0: no results, 1: results) and table data
    Output: Display a sky image around the alert position from aladin.
    """
    if not is_open:
        return no_update

    if len(data) == 0:
        return ""

    if len(data) > 1000:
        # Silently limit the size of list we display
        data = data[:1000]

    pdf = pd.DataFrame(data)
    pdf["f:xm_simbad_otype"] = pdf["f:xm_simbad_otype"].replace("*", "Star")

    link = '<a target="_blank" href="{}/{}">{}</a>'
    config_args = extract_configuration("config.yaml")

    # Determine if sso or not
    # FIXME: refactor this piece of code because it appears in multiple places
    row = pdf.head(1).to_dict(orient="records")[0]
    _, is_sso = is_row_static_or_moving(row)

    if is_sso:
        label = "MPC designation"
        # get data for all sso sources and overwrite
        endpoint = "/api/v1/sso"
        columns = "r:ra,r:dec,r:midpointMjdTai,r:diaSourceId,r:mpcDesignation"
        # FIXME: row["r:mpcDesignation"] is not enough if multiple SSOs in pdf
        pdf = request_api(
            endpoint, json={"n_or_d": row["r:mpcDesignation"], "columns": columns}
        )

        titles = [
            link.format(config_args["SITEURL"], i, i)
            for i in pdf["r:mpcDesignation"].to_numpy()
        ]
        classes = ["SSO"] * len(pdf)
        n_alert_per_class = {"SSO": len(pdf)}
    else:
        label = "diaObjectId"
        titles = [
            link.format(
                config_args["SITEURL"],
                i.split("]")[0].split("[")[1],
                i.split("]")[0].split("[")[1],
            )
            for i in pdf["r:diaObjectId"].to_numpy()
        ]
        classes = pdf["f:xm_simbad_otype"].to_numpy()
        n_alert_per_class = (
            pdf.groupby("f:xm_simbad_otype").count().to_dict()["r:diaObjectId"]
        )

    # Coordinate
    ras = pdf["r:ra"].to_numpy()
    decs = pdf["r:dec"].to_numpy()
    times = pdf["r:midpointMjdTai"].to_numpy()

    # Javascript. Note the use {{}} for dictionary
    # Force redraw of the Aladin lite window
    img = """var container = document.getElementById('aladin-lite-div-skymap');var txt = ''; container.innerHTML = txt;"""

    # Aladin lite
    img += """
    var a = A.aladin('#aladin-lite-div-skymap',
    {{
        target: '{} {}',
        survey: 'https://alasky.cds.unistra.fr/Skymapper/DR4/CDS_P_Skymapper_DR4_color/',
        showReticle: true,
        allowFullZoomout: true,
        showContextMenu: true,
        showCooGridControl: true,
        fov: 360
        }}
    );
    """.format(ras[0], decs[0])

    cats = []
    for ra, dec, time_, title, class_ in zip(ras, decs, times, titles, classes):
        if class_ in simbad_types:
            cat = "cat_{}".format(simbad_types.index(class_))
            color = class_colors["Simbad"]
        elif class_ in class_colors.keys():
            cat = "cat_{}".format(class_.replace(" ", "_"))
            color = class_colors[class_]
        else:
            # Sometimes SIMBAD mess up names :-)
            cat = "cat_{}".format(class_)
            color = class_colors["Simbad"]

        if cat not in cats:
            img += """var {} = A.catalog({{name: '{}', sourceSize: 15, shape: 'circle', color: '{}', onClick: 'showPopup', limit: 1000}});""".format(
                cat, class_ + " ({})".format(n_alert_per_class[class_]), color
            )
            cats.append(cat)

        img += """{}.addSources([A.source({}, {}, {{'{}': '{}', 'Last alert': '{}', 'Fink label': '{}'}})]);""".format(
            cat, ra, dec, label, title, time_, class_
        )

    for cat in sorted(cats):
        img += """a.addCatalog({});""".format(cat)

    # img cannot be executed directly because of formatting
    # We split line-by-line and remove comments
    img_to_show = [i for i in img.split("\n") if "// " not in i]

    return " ".join(img_to_show)


def modal_skymap():
    """Modal containing the Sky Map

    Notes
    -----
    It uses visdcc to execute javascript from Aladin Lite

    Returns
    -------
    out: Modal
    """
    import visdcc

    button = dmc.Button(
        "Sky Map",
        id="open_modal_skymap",
        n_clicks=0,
        leftSection=DashIconify(icon="bi:stars"),
        color="gray",
        fullWidth=True,
        variant="default",
        radius="xl",
    )

    modal = html.Div([
        button,
        dbc.Modal(
            [
                # loading(
                dbc.ModalBody(
                    html.Div(
                        [
                            visdcc.Run_js(
                                id="aladin-lite-div-skymap",
                                style={"border": "0"},
                            ),
                        ],
                        style={
                            "width": "100%",
                            "height": "100%",
                        },
                    ),
                    className="p-1",
                    style={"height": "30pc"},
                ),
                # ),
                dbc.ModalFooter(
                    dmc.Button(
                        "Close",
                        id="close_modal_skymap",
                        className="ml-auto",
                        color="gray",
                        # fullWidth=True,
                        variant="default",
                        radius="xl",
                    ),
                ),
            ],
            id="modal_skymap",
            is_open=False,
            size="lg",
        ),
    ])

    return modal


clientside_callback(
    """
    function toggle_modal_skymap(n1, n2, is_open) {
        if (n1 || n2)
            return ~is_open;
        else
            return is_open;
    }
    """,
    Output("modal_skymap", "is_open"),
    [Input("open_modal_skymap", "n_clicks"), Input("close_modal_skymap", "n_clicks")],
    [State("modal_skymap", "is_open")],
    prevent_initial_call=True,
)


def populate_result_table(data, columns):
    """Define options of the results table, and add data and columns"""
    page_size = 100
    markdown_options = {"link_target": "_blank"}

    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id="result_table",
        page_size=page_size,
        # page_action='none',
        style_as_list_view=True,
        sort_action="native",
        filter_action="native",
        markdown_options=markdown_options,
        # fixed_columns={'headers': True, 'data': 1},
        style_data={
            "backgroundColor": "rgb(248, 248, 248, 1.0)",
        },
        style_table={"maxWidth": "100%", "overflowX": "scroll"},
        style_cell={
            "padding": "5px",
            "textAlign": "right",
            "overflow": "hidden",
            "font-family": "sans-serif",
            "fontSize": 14,
        },
        style_data_conditional=[
            {
                "if": {"column_id": "r:diaObjectId"},
                "backgroundColor": "rgb(240, 240, 240, 1.0)",
            }
        ],
        style_header={
            "backgroundColor": "rgb(230, 230, 230)",
            "fontWeight": "bold",
            "textAlign": "center",
        },
        # Align the text in Markdown cells
        css=[dict(selector="p", rule="margin: 0; text-align: left")],
    )
    return table


@app.callback(
    [
        Output("result_table", "data"),
        Output("result_table", "columns"),
    ],
    [
        Input("field-dropdown2", "value"),
        Input("alert-object-switch", "checked"),
        Input("alert-sso-switch", "checked"),
        Input("alert-tracklet-switch", "checked"),
    ],
    [
        State("result_table", "data"),
        State("result_table", "columns"),
    ],
)
def update_table(field_dropdown, groupby1, groupby2, groupby3, data, columns):
    """Update table by adding new columns (no server call)"""
    changed_id = [p["prop_id"] for p in dash.callback_context.triggered][0]
    # Adding new columns (no client call)
    if "field-dropdown2" in changed_id:
        if field_dropdown is None or len(columns) == 0:
            raise PreventUpdate

        incolumns = any(c.get("id") == field_dropdown for c in columns)

        if incolumns is True:
            raise PreventUpdate

        columns.append({
            "name": field_dropdown,
            "id": field_dropdown,
            "type": "numeric",
            "format": dash_table.Format.Format(precision=8),
            "presentation": "markdown"
            if field_dropdown == "r:diaObjectId"
            else "input",
            # 'hideable': True,
        })

        return data, columns
    elif groupby1 is True:
        pdf = pd.DataFrame.from_dict(data)
        pdf = pdf.drop_duplicates(subset="r:diaObjectId", keep="first")
        data = pdf.to_dict("records")
        return data, columns
    elif groupby2 is True:
        pdf = pd.DataFrame.from_dict(data)
        if not np.all(pdf["i:ssnamenr"] == "null"):
            mask = ~pdf.duplicated(subset="i:ssnamenr") | (pdf["i:ssnamenr"] == "null")
            pdf = pdf[mask]
            data = pdf.to_dict("records")
        return data, columns
    elif groupby3 is True:
        pdf = pd.DataFrame.from_dict(data)
        if not np.all(pdf["d:tracklet"] == ""):
            mask = ~pdf.duplicated(subset="d:tracklet") | (pdf["d:tracklet"] == "")
            pdf = pdf[mask]
            data = pdf.to_dict("records")
        return data, columns
    else:
        raise PreventUpdate


# Prepare and display the results
@app.callback(
    [
        Output("results", "children"),
        Output("logo", "is_open"),
        Output("search_bar_submit", "children", allow_duplicate=True),
        Output("search_history_store", "data"),
    ],
    [
        Input("search_bar_input", "n_submit"),
        Input("search_bar_submit", "n_clicks"),
        # Next input uses dynamically created source, so has to be pattern-matching
        Input({"type": "search_bar_suggestion", "value": ALL}, "n_clicks"),
        Input("url", "search"),
    ],
    State("search_bar_input", "value"),
    State("search_history_store", "data"),
    State("results_table_switch", "checked"),
    # prevent_initial_call=True
    prevent_initial_call="initial_duplicate",
    # FIXME: Hum, why this one is needed?
    _allow_dynamic_callbacks=True,
)
def results(n_submit, n_clicks, s_n_clicks, searchurl, value, history, show_table):
    """Parse the search string and query the database"""
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if not triggered_id:
        # FIXME: ???
        triggered_id = "url"

    # Safeguards against triggering on initial mount of components
    if (
        (triggered_id == "search_bar_input" and not n_submit)
        or (triggered_id == "search_bar_submit" and not n_clicks)
        or (
            triggered_id == '{"type":"search_bar_suggestion","value":0}'
            and (not s_n_clicks or not s_n_clicks[0])
        )
        or (triggered_id == "url" and not searchurl)
    ):
        raise PreventUpdate

    if not value and not searchurl:
        # TODO: show back the logo?..
        return None, no_update, no_update, no_update

    colnames_to_display = {
        "r:diaObjectId": "diaObjectId",
        "r:ra": "RA (deg)",
        "r:dec": "Dec (deg)",
        # "v:lastdate": "Last alert",
        "f:finkclass": "Classification",
        "r:nDiaSources": "Number of measurements",
        # "v:lapse": "Time variation (day)",
    }

    if searchurl and triggered_id == "url":
        # Parse GET parameters from url
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(searchurl).query))
        # Construct the query from them
        query = {}
        for _ in ["action", "partial", "object"]:
            if _ in params:
                query[_] = params.pop(_)
        query["params"] = params
    else:
        value = value.strip()
        query = parse_query(value)

    if not query or not query["action"]:
        return None, no_update, no_update, no_update

    if query["action"] != "class" and "trend" in query["params"]:
        msg = "trend is experimental and can only be used with class search. Add the keyword `class=` to your search."
        return (
            dbc.Alert(msg, color="warning", className="shadow-sm"),
            no_update,
            no_update,
            history,
        )

    if "last" in query["params"] and query["action"] == "unknown":
        msg = "last must be used with class search. Add the keyword `class=` to your search."
        return (
            dbc.Alert(msg, color="warning", className="shadow-sm"),
            no_update,
            no_update,
            history,
        )

    if query["action"] == "unknown":
        return (
            dbc.Alert(
                "Query not recognized: {}".format(value),
                color="danger",
                className="shadow-sm",
            ),
            no_update,
            no_update,
            no_update,
        )

    elif query["action"] == "diaObjectid":
        # Search objects by diaObjectId
        msg = "ObjectId search with {} name {}".format(
            "partial" if query.get("partial") else "exact", query["object"]
        )
        pdf = request_api(
            "/api/v1/sources",
            json={
                "diaObjectId": str(query["object"]),
            },
        )
        if not pdf.empty:
            pdf = pdf.loc[pdf.groupby("r:diaObjectId")["r:midpointMjdTai"].idxmax()]
        main_id = "r:diaObjectId"

    elif query["action"] == "sso":
        # Solar System Objects
        msg = "Solar System object search with name {}".format(query["params"]["sso"])
        endpoint = "/api/v1/sso"
        pdf = request_api(endpoint, json={"n_or_d": query["params"]["sso"]})
        if not pdf.empty:
            pdf = pdf.loc[pdf.groupby("r:ssObjectId")["r:midpointMjdTai"].idxmax()]
        main_id = "r:ssObjectId"

    elif query["action"] == "tracklet":
        # Tracklet by (partial) name
        msg = "Tracklet search with {} name {}".format(
            "partial" if query.get("partial") else "exact", query["object"]
        )
        payload = {"id": query["object"]}

        endpoint = "/api/v1/tracklet"
        pdf = request_api(endpoint, json=payload)
        main_id = "r:diaObjectId"

    elif query["action"] == "conesearch":
        # Conesearch
        ra = float(query["params"].get("ra"))
        dec = float(query["params"].get("dec"))
        # Default is 10 arcsec, max is 5 degrees
        sr = min(float(query["params"].get("r", 10)), 18000)

        msg = (
            "Cone search with center at {:.4f} {:.3f} and radius {:.1f} arcsec".format(
                ra, dec, sr
            )
        )

        payload = {
            "ra": ra,
            "dec": dec,
            "radius": sr,
        }

        if "after" in query["params"]:
            startdate = isoify_time(query["params"]["after"])

            msg += " after {}".format(startdate)

            payload["startdate"] = startdate

        if "before" in query["params"]:
            stopdate = isoify_time(query["params"]["before"])

            msg += " before {}".format(stopdate)

            payload["stopdate"] = stopdate

        elif "window" in query["params"]:
            window = query["params"]["window"]

            msg += " window {} days".format(window)

            payload["window"] = window

        endpoint = "/api/v1/conesearch"
        pdf = request_api(endpoint, json=payload)
        main_id = "r:diaObjectId"

        colnames_to_display = {
            "r:diaObjectId": "diaObjectId",
            "v:separation_degree": "Separation (degree)",
            "f:finkclass": "Classification",
            "r:nDiaSources": "Number of measurements",
            # "v:lapse": "Time variation (day)",
        }

    elif query["action"] == "class":
        # Class-based search
        alert_class = query["params"].get("class")

        n_last = int(query["params"].get("last", 100))

        msg = "Last {} objects with class '{}'".format(n_last, alert_class)

        payload = {"class": alert_class, "n": n_last}

        if "after" in query["params"]:
            startdate = isoify_time(query["params"]["after"])

            msg += " after {}".format(startdate)

            payload["startdate"] = startdate

        if "before" in query["params"]:
            stopdate = isoify_time(query["params"]["before"])

            msg += " before {}".format(stopdate)

            payload["stopdate"] = stopdate

        if "trend" in query["params"]:
            msg += " and {} trend".format(query["params"]["trend"])
            payload["trend"] = query["params"]["trend"]

        endpoint = "/api/v1/latests"
        pdf = request_api(endpoint, json=payload)
        main_id = "r:diaObjectId"

    elif query["action"] == "anomaly":
        # Anomaly search
        n_last = int(query["params"].get("last", 100))

        msg = "Last {} anomalies".format(n_last)

        payload = {"n": n_last}

        if "after" in query["params"]:
            startdate = isoify_time(query["params"]["after"])

            msg += " after {}".format(startdate)

            payload["start_date"] = startdate

        if "before" in query["params"]:
            stopdate = isoify_time(query["params"]["before"])

            msg += " before {}".format(stopdate)

            payload["stop_date"] = stopdate

        endpoint = "/api/v1/anomaly"
        pdf = request_api("/api/v1/anomaly", json=payload)
        main_id = "r:diaObjectId"

    else:
        return (
            dbc.Alert(
                "Unhandled query: {}".format(query),
                color="danger",
                className="shadow-sm",
            ),
            no_update,
            no_update,
            no_update,
        )

    # Add to history
    if not history:
        history = []
    while value in history:
        history.remove(value)  # Remove duplicates
    history.append(value)
    history = history[-10:]  # Limit it to 10 latest entries

    msg = "{} - {} found".format(
        msg, "nothing" if pdf.empty else str(len(pdf.index)) + " objects"
    )

    if pdf.empty:
        # text, header = text_noresults(query, query_type, dropdown_option, searchurl)
        return (
            dbc.Alert(msg, color="warning", className="shadow-sm"),
            no_update,
            no_update,
            history,
        )
    else:
        # Make clickable objectId
        pdf[main_id] = pdf[main_id].apply(markdownify_objectid)

        # Sort the results
        if query["action"] == "conesearch":
            # FIXME: replace by first/last
            # pdf["v:lapse"] = pdf["r:midpointMjdTai"] - pdf["r:validityStartMjdTai"]
            data = pdf.sort_values("v:separation_degree", ascending=True)
        else:
            data = pdf.sort_values("r:midpointMjdTai", ascending=False)

        if show_table:
            data = data.to_dict("records")

            columns = [
                {
                    "id": c,
                    "name": colnames_to_display[c],
                    "type": "numeric",
                    "format": dash_table.Format.Format(precision=8),
                    # 'hideable': True,
                    "presentation": "markdown" if c == "r:diaObjectId" else "input",
                }
                for c in colnames_to_display.keys()
            ]

            table = populate_result_table(data, columns)
            results_ = display_table_results(table, endpoint)
        else:
            results_ = display_cards_results(pdf)

        results = [
            # Common header for the results
            dbc.Row(
                [
                    dbc.Col(msg, md="auto"),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(modal_skymap(), xs="auto"),
                                dbc.Col(
                                    help_popover(
                                        dcc.Markdown(msg_info),
                                        id="help_msg_info",
                                        trigger=dmc.ActionIcon(
                                            DashIconify(icon="mdi:help"),
                                            id="help_msg_info",
                                            color="gray",
                                            variant="default",
                                            radius="xl",
                                            size="lg",
                                        ),
                                    ),
                                    xs="auto",
                                ),
                            ],
                            justify="end",
                        ),
                        md="auto",
                    ),
                ],
                align="end",
                justify="between",
                className="m-2",
            ),
        ] + results_

        return results, False, no_update, history


def display_cards_results(pdf, page_size=10):
    results_ = [
        # Data storage
        dcc.Store(
            id="results_store",
            storage_type="memory",
            data=pdf.to_json(),
        ),
        dcc.Store(
            id="results_page_size_store",
            storage_type="memory",
            data=str(page_size),
        ),
        # For Aladin
        dcc.Store(
            id="result_table",
            storage_type="memory",
            data=pdf.to_dict("records"),
        ),
        # Actual display of results
        html.Div(id="results_paginated"),
    ]

    npages = int(np.ceil(len(pdf.index) / page_size))
    results_ += [
        dmc.Space(h=10),
        dmc.Group(
            dmc.Pagination(
                id="results_pagination",
                value=1,
                total=npages,
                siblings=1,
                withControls=True,
                withEdges=True,
            ),
            align="center",
            justify="center",
            className="d-none" if npages == 1 else "",
        ),
        dmc.Space(h=20),
    ]

    return results_


@app.callback(
    Output("results_paginated", "children"),
    Input("results_pagination", "value"),
    State("results_store", "data"),
    State("results_page_size_store", "data"),
)
def on_paginate(page, data, page_size):
    pdf = pd.read_json(io.StringIO(data))
    page_size = int(page_size)

    if not page:
        page = 1

    results = []

    # Slice to selected page
    pdf_ = pdf.iloc[(page - 1) * page_size : min(page * page_size, len(pdf.index))]

    for i, row in pdf_.iterrows():
        results.append(card_search_result(row, i))

    return results


# Scroll to top on paginate
clientside_callback(
    """
    function scroll_top(value) {
        document.querySelector('#search_bar').scrollIntoView({behavior: "smooth"})
        return dash_clientside.no_update;
    }
    """,
    Output("results_pagination", "page"),  # Fake output!!!
    Input("results_pagination", "page"),
    prevent_initial_call=True,
)


@app.callback(
    [
        Output(
            {
                "type": "search_results_lightcurve",
                "main_id": MATCH,
                "is_sso": MATCH,
                "index": MATCH,
            },
            "children",
        ),
        Output(
            {"type": "indicator", "main_id": MATCH, "is_sso": MATCH, "index": MATCH},
            "children",
        ),
        Output(
            {"type": "flags", "main_id": MATCH, "is_sso": MATCH, "index": MATCH},
            "children",
        ),
    ],
    [
        Input(
            {
                "type": "search_results_lightcurve",
                "main_id": MATCH,
                "is_sso": MATCH,
                "index": MATCH,
            },
            "id",
        ),
        Input("color_scale", "value"),
        Input("select-units", "value"),
        Input("select-measurement", "value"),
    ],
)
def on_load_lightcurve(lc_id, color_scale, units, measurement):
    """Draw lightcurve on cards"""
    layout = dict(
        margin=dict(l=50, r=0, b=0, t=0),
        hovermode="closest",
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=True,
        shapes=[],
        hoverlabel={
            "align": "left",
        },
        legend=dict(
            font=dict(size=10),
            orientation="h",
            # xanchor="right",
            x=0,
            y=1.2,
            bgcolor="rgba(218, 223, 225, 0.5)",
        ),
        xaxis={
            "title": "Observation date",
            "automargin": True,
        },
        yaxis={
            "automargin": True,
        },
    )
    if lc_id:
        fig, indicator, flags = draw_lightcurve_preview(
            main_id=lc_id["main_id"],
            is_sso=lc_id["is_sso"],
            color_scale=color_scale,
            units=units,
            measurement=measurement,
            layout=layout,
            switch_layout="plain",
        )
        CONFIG_PLOT["toImageButtonOptions"]["filename"] = str(lc_id["main_id"])
        return (
            dcc.Graph(
                figure=fig,
                config=CONFIG_PLOT,
                style={"width": "100%", "height": "15pc"},
                responsive=True,
            ),
            indicator,
            flags,
        )

    return no_update, no_update


@app.callback(
    [
        Output(
            {"type": "search_results_cutouts", "diaSourceId": MATCH, "index": MATCH},
            "children",
        ),
        Output(
            {"type": "cutout-size", "diaSourceId": MATCH, "index": MATCH},
            "children",
        ),
    ],
    [
        Input(
            {"type": "search_results_cutouts", "diaSourceId": MATCH, "index": MATCH},
            "id",
        ),
    ],
)
def on_load_cutouts(lc_id):
    """Display Science cutouts on cards"""
    if lc_id:
        fig, size = draw_cutouts_quickview(lc_id["diaSourceId"])
        return html.Div(
            fig,
            style={"width": "12pc", "height": "12pc"},
        ), size

    return no_update, no_update
