# Copyright 2019-2026 AstroLab Software
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
from dash import html, Output, Input
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app import app

from apps.dataclasses import fink_tags, fink_blocks
from apps.api import request_api
from apps.plotting import DEFAULT_FINK_COLORS


def predefined_fields_for_data_transfer():
    """Get schema from API, and make it suitable for Data Transfer"""
    fields = ["Full packet", "Medium packet", "Light packet"]

    data = []

    # high level
    packet = {
        "group": "Pre-defined schema",
        "items": [{"value": v, "label": v} for v in fields],
    }
    data.append(packet)

    return data, fields


def create_datatransfer_schema_table(provenance="LSST", caption=""):
    """ """
    rows = []

    if provenance == "custom":
        _, custom_fields = predefined_fields_for_data_transfer()
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[0]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd("All LSST and Fink content"),
            ])
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[1]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd("All LSST and Fink content without cutouts"),
            ])
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[2]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd("Selection of LSST & Fink fields for lightcurve analysis"),
            ])
        )
    elif provenance == "fink":
        # Need a function
        pass
    elif provenance == "lsst":
        msg = dmc.Text([
            "LSST fields can be browsed at ",
            html.A(
                "https://sdm-schemas.lsst.io/apdb.html",
                href="https://sdm-schemas.lsst.io/apdb.html",
                target="_blank",
            ),
            r" or downloaded as Avro schema from ",
            html.A(
                "https://github.com/lsst/alert_packet/tree/main/python/lsst/alert/packet/schema/10/0",
                href="https://github.com/lsst/alert_packet/tree/main/python/lsst/alert/packet/schema/10/0",
                target="_blank",
            ),
        ])
        return msg

    head = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh("Name", w="25%"),
            dmc.TableTh("From", w="15%"),
            dmc.TableTh("Type", w="15%"),
            dmc.TableTh("Documentation"),
        ])
    )
    body = dmc.TableTbody(rows)

    table_candidate = dmc.TableScrollContainer(
        dmc.Table(
            [head, body, dmc.TableCaption(caption)],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
        maxHeight=300,
        minWidth=0,
        type="scrollarea",
    )
    return table_candidate


def create_api_schema_table(endpoint="/api/v1/objects", caption=""):
    """ """
    schema = request_api(
        "/api/v1/schema", json={"endpoint": endpoint}, method="POST", output="json"
    )

    provenances = sorted(list(schema.keys()))

    conv_names = {
        "LSST original fields (r:)": "LSST",
        "LSST original cutouts (b:)": "LSST",
        "Fink science module outputs (f:)": "Fink",
    }

    def format_type(t):
        if isinstance(t, list):
            return t[-1]
        else:
            return t

    rows = []

    for prov in provenances:
        # Table candidates

        labels = [k for k in schema[prov].keys()]
        if conv_names[prov] == "Fink":
            fink_broker_version = [
                v["fink_broker_version"] for k, v in schema[prov].items()
            ]
            fink_science_version = [
                v["fink_science_version"] for k, v in schema[prov].items()
            ]
            msg = " Available from fink_broker_version {} and fink_science_version {}."
            docs = [
                kv[1]["doc"] + msg.format(fb, fs)
                for kv, fb, fs in zip(
                    schema[prov].items(), fink_broker_version, fink_science_version
                )
            ]
        else:
            docs = [v["doc"] for k, v in schema[prov].items()]

        types = [format_type(v["type"]) for k, v in schema[prov].items()]

        [
            rows.append(
                dmc.TableTr([
                    dmc.TableTd(label),
                    dmc.TableTd(conv_names[prov]),
                    dmc.TableTd(type_),
                    dmc.TableTd(doc),
                ])
            )
            for label, type_, doc in zip(labels, types, docs)
        ]

    head = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh("Name", w="25%"),
            dmc.TableTh("From", w="15%"),
            dmc.TableTh("Type", w="15%"),
            dmc.TableTh("Documentation"),
        ])
    )
    body = dmc.TableTbody(rows)

    table_candidate = dmc.TableScrollContainer(
        dmc.Table(
            [head, body, dmc.TableCaption(caption)],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
        maxHeight=300,
        minWidth=800,
        type="scrollarea",
    )
    return table_candidate


def create_user_filterblocks_description(kind="filters"):
    """ """
    # header
    rows = []
    if kind == "filters":
        items = fink_tags
    elif kind == "blocks":
        items = fink_blocks
    for tag, description in items.items():
        rows.append(
            dmc.TableTr([
                dmc.TableTd(tag),
                dmc.TableTd(description),
            ])
        )

    head = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh("Tag", w="35%"),
            dmc.TableTh("Description", w="65%"),
        ])
    )
    body = dmc.TableTbody(rows)

    table_candidate = dmc.TableScrollContainer(
        dmc.Table(
            [head, body, None],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
        maxHeight=300,
        minWidth=0,
        type="scrollarea",
    )
    return table_candidate


def get_all_observing_nights():
    """ """
    out = request_api(
        "/api/v1/statistics",
        json={
            "output-format": "json",
            "date": "",
            "columns": "f:night,f:fink_broker_version,f:fink_science_version,f:lsst_schema_version",
        },
        output="json",
    )
    return [i["f:night"] for i in out]


def make_elem(label, value):
    return html.Div(
        # className="bottom-section",
        children=html.Div(
            className="row row1",
            children=[
                html.Div(
                    className="item",
                    children=[
                        dmc.Text(
                            children=label,
                            className="big-text",
                            fw=700,
                        ),
                        html.Span(
                            children=value,
                            className="regular-text",
                        ),
                    ],
                ),
            ],
        )
    )


@app.callback(
    Output("schema_versions", "children"),
    Input("date-select", "value"),
)
def get_versions(night):
    """ """
    out = request_api(
        "/api/v1/statistics",
        json={
            "output-format": "json",
            "date": str(night),
            "columns": "f:fink_broker_version,f:fink_science_version,f:lsst_schema_version",
        },
        output="json",
    )

    return dmc.Group(
        children=[
            make_elem("f:fink_broker_version", out[0]["f:fink_broker_version"]),
            make_elem("f:fink_science_version", out[0]["f:fink_science_version"]),
            make_elem("f:lsst_schema_version", out[0]["f:lsst_schema_version"]),
        ]
    )


def layout():
    filters_and_blocks = dmc.Accordion(
        id="filters_and_blocks_schema",
        disableChevronRotation=False,
        chevronPosition="left",
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "User-defined Filters",
                    ),
                    dmc.AccordionPanel(
                        create_user_filterblocks_description(kind="filters")
                    ),
                ],
                value="filters",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "User-defined Blocks",
                    ),
                    dmc.AccordionPanel(
                        create_user_filterblocks_description(kind="blocks")
                    ),
                ],
                value="blocks",
            ),
        ],
    )

    datatransfer = dmc.Accordion(
        id="datatransfer_schema",
        disableChevronRotation=False,
        chevronPosition="left",
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "LSST fields",
                    ),
                    dmc.AccordionPanel(
                        create_datatransfer_schema_table(provenance="lsst")
                    ),
                ],
                value="fink",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Fink fields",
                    ),
                    dmc.AccordionPanel(
                        create_datatransfer_schema_table(provenance="fink")
                    ),
                ],
                value="lsst",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Pre-defined packet contents",
                    ),
                    dmc.AccordionPanel(
                        create_datatransfer_schema_table(provenance="custom")
                    ),
                ],
                value="custom",
            ),
        ],
    )

    api = dmc.Accordion(
        id="api_schema",
        disableChevronRotation=False,
        chevronPosition="left",
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "/api/v1/{}".format(i),
                    ),
                    dmc.AccordionPanel(
                        create_api_schema_table(endpoint="/api/v1/{}".format(i))
                    ),
                ],
                value="/api/v1/{}".format(i),
            )
            for i in [
                "sources",
                "objects",
                "sso",
                "conesearch",
                "tags",
                "cutouts",
                "statistics",
            ]
        ],
    )

    observing_nights = sorted(get_all_observing_nights())[::-1]

    layout = dmc.Accordion(
        id="schema_layout",
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "API & Science Portal",
                        icon=DashIconify(
                            icon="material-symbols:stream",
                            color=DEFAULT_FINK_COLORS[0],
                            width=20,
                        ),
                    ),
                    dmc.AccordionPanel(api),
                ],
                value="api",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Data Transfer & Xmatch",
                        icon=DashIconify(
                            icon="material-symbols:stream",
                            color=DEFAULT_FINK_COLORS[3],
                            width=20,
                        ),
                    ),
                    dmc.AccordionPanel(datatransfer),
                ],
                value="datatransfer",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Filters and Blocks",
                        icon=DashIconify(
                            icon="material-symbols:stream",
                            color=DEFAULT_FINK_COLORS[-1],
                            width=20,
                        ),
                    ),
                    dmc.AccordionPanel(filters_and_blocks),
                ],
                value="filters_and_blocks",
            ),
        ],
    )

    version = dmc.Group(
        [
            dmc.Select(
                label="Select a date",
                placeholder="Default is last observing night",
                searchable=True,
                id="date-select",
                value=max(observing_nights),
                data=[{"value": night, "label": night} for night in observing_nights],
                w=200,
                mb=10,
            ),
            html.Div(id="schema_versions"),
        ],
        className="indicator_schema",
        style={"padding": "20px"},
    )

    return dmc.Container(
        size="90%",
        children=[
            dmc.Space(h=50),
            dmc.Center(
                dmc.Title(children="Fink schemas", style={"color": "#15284F"}),
            ),
            dmc.Space(h=50),
            version,
            dmc.Space(h=20),
            layout,
        ],
    )
