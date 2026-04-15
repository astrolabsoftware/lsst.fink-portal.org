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
import dash_mantine_components as dmc
from dash import Input, Output, html, no_update, dcc
from dash_iconify import DashIconify

from app import app
from apps.api import request_api
from apps.dataclasses import fink_blocks, fink_tags
from apps.plotting import DEFAULT_FINK_COLORS

CONV_NAMES = {
    "LSST original fields (r:)": "LSST",
    "LSST original cutouts (b:)": "LSST",
    "Fink science module outputs (f:)": "Fink",
}

def extract_type(t):
    """Extract field type from json schema

    Parameters
    ----------
    t: str or list
        In the forms 'field' or ['null', 'field']

    Returns
    -------
    out: str
    """
    if isinstance(t, list):
        field = [i for i in t if i != 'null'][0]
        if isinstance(field, dict):
            #  {'logicalType': 'timestamp-micros', 'type': 'long'},
            return field["type"]
        else:
            return field
    else:
        return t


def predefined_fields_for_data_transfer():
    """Predefined fields for data transfer"""
    fields = ["Full packet", "Medium packet", "Light static packet", "Light SSO packet"]

    data = []

    # high level
    packet = {
        "group": "Pre-defined schema",
        "items": fields,
    }
    data.append(packet)

    return data, fields

def lsst_nested_fields_for_data_transfer():
    """LSST nested sections for data transfer"""
    fields = ["diaSource", "diaObject", "prvDiaSources", "prvDiaForcedSources", "mpc_orbits", "ssSource"]

    data = []

    # high level
    packet = {
        "group": "LSST nested sections",
        "items": fields,
    }
    data.append(packet)

    return data, fields


def fields_for_data_transfer():
    """Return field names and types

    Returns
    -------
    out: (dict, dict)
        Dictionary with field names and types, for LSST and Fink.
    """
    schema_lsst = request_api(
        endpoint="/api/v1/schema",
        json={"endpoint": "/datatransfer/lsst"},
        output="json",
    )
    if len(schema_lsst) > 0:
        all_lsst_fields = list(schema_lsst["LSST"].keys())
        all_lsst_fields_types = [extract_type(i['type']) for i in schema_lsst['LSST'].values()]
    else:
        # HTTP error usually
        return {}, {}

    schema_fink = request_api(
        endpoint="/api/v1/schema",
        json={"endpoint": "/datatransfer/fink"},
        output="json",
    )
    if len(schema_fink) > 0:
        all_fink_fields = list(schema_fink["Fink"].keys())
        all_fink_fields_types = [extract_type(i['type']) for i in schema_fink['Fink'].values()]
    else:
        # HTTP error usually
        return {}, {}

    return {k:v for k, v in zip(all_lsst_fields, all_lsst_fields_types)}, {k:v for k, v in zip(all_fink_fields, all_fink_fields_types)}


def create_datatransfer_schema_table(provenance="lsst", caption=""):
    """Create a table for datatransfer"""
    rows = []

    # Strict definition in apps/spark_lsst_transfer.py
    light_static_fields = cols = [
        'diaObjectId', 'snr', 'scienceFlux', 'scienceFluxErr', 'templateFlux',
        'templateFluxErr', 'band', 'midpointMjdTai', 'ra', 'dec', 'reliability',
        'diaSourceId', 'observation_reason', 'target_name',
        'brokerIngestMjd', 'lsst_schema_version', 'brokerStartProcessTimestamp',
        'fink_broker_version', 'fink_science_version', 'publisher',
        'lc_features', 'clf', 'xm', 'pred', 'misc', 'brokerEndProcessTimestamp',
        'timestamp', 'tns_type_recomputed'
    ]
    light_sso_fields = cols = [
        'ssObjectId', 'snr', 'scienceFlux', 'scienceFluxErr', 'templateFlux',
        'templateFluxErr', 'band', 'midpointMjdTai', 'ra', 'dec', 'reliability',
        'diaSourceId',
        'phaseAngle', 'diaDistanceRank',
        'packed_primary_provisional_designation',
        'unpacked_primary_provisional_designation',
        'fink_broker_version', 'fink_science_version', 'lsst_schema_version'
    ]

    if provenance == "custom":
        _, custom_fields = predefined_fields_for_data_transfer()
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[0]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd("All LSST original content, and Fink added values"),
            ])
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[1]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd(
                    "All LSST original content and Fink added values without the cutouts."
                ),
            ])
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[2]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd(
                    "Selection of LSST & Fink fields for lightcurve analysis (static objects): {}".format(", ".join(light_static_fields))
                ),
            ])
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(custom_fields[3]),
                dmc.TableTd("LSST & Fink"),
                dmc.TableTd("--"),
                dmc.TableTd(
                    "Selection of LSST & Fink fields for lightcurve analysis (Solar System objects): {}".format(", ".join(light_sso_fields))
                ),
            ])
        )

        head = dmc.TableThead(
            dmc.TableTr([
                dmc.TableTh("Name", w="25%"),
                dmc.TableTh("From", w="15%"),
                dmc.TableTh("Type", w="15%"),
                dmc.TableTh("Documentation"),
            ])
        )
        body = dmc.TableTbody(rows)
    elif provenance == "fink":
        schema = request_api(
            "/api/v1/schema",
            json={"endpoint": "/datatransfer/fink"},
            method="POST",
            output="json",
        )

        head, body = make_table_body_from_schema(schema)
    elif provenance == "lsst":
        schema = request_api(
            "/api/v1/schema",
            json={"endpoint": "/datatransfer/lsst"},
            method="POST",
            output="json",
        )

        head, body = make_table_body_from_schema(schema)

    table_candidate = dmc.TableScrollContainer(
        dmc.Table(
            [head, body, dmc.TableCaption(caption)],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
        maxHeight=500,
        minWidth=1000,
        type="scrollarea",
    )
    return table_candidate


def format_type(t):
    if isinstance(t, list):
        if isinstance(t[-1], dict):
            # e.g. 'type': ['null', {'logicalType': 'timestamp-micros', 'type': 'long'}]}
            return t[-1]["type"]
        return t[-1]
    else:
        return t


def make_table_body_from_schema(schema):
    """ """
    provenances = sorted(list(schema.keys()))
    rows = []
    for prov in provenances:
        # Table candidates

        labels = [k for k in schema[prov].keys()]
        if CONV_NAMES.get(prov, prov) == "Fink":
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
                    dmc.TableTd(CONV_NAMES.get(prov, prov)),
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
    return head, body


def create_schema_table(endpoint="/api/v1/objects", caption=""):
    """ """
    schema = request_api(
        "/api/v1/schema", json={"endpoint": endpoint}, method="POST", output="json"
    )

    head, body = make_table_body_from_schema(schema)

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
        if kind == "filters":
            tag = "fink_" + tag + "_lsst"
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
        minWidth=1000,
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


@app.callback(
    Output("api", "children"),
    Input("url", "pathname"),
    background=True,
    prevent_initial_call=False,
)
def get_api_background(url):
    if url != "/schemas":
        return no_update
    api = dmc.Accordion(
        id="api_schema",
        disableChevronRotation=False,
        chevronPosition="left",
        children=[dcc.Markdown("This panel shows the fields returned by each API endpoint. Available arguments and examples for each endpoint can be found at [https://api.lsst.fink-portal.org](https://api.lsst.fink-portal.org)."),] +
        [
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        f"/api/v1/{i}",
                    ),
                    dmc.AccordionPanel(create_schema_table(endpoint=f"/api/v1/{i}")),
                ],
                value=f"/api/v1/{i}",
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
    return api


def layout():
    filters_and_blocks = dmc.Accordion(
        id="filters_and_blocks_schema",
        disableChevronRotation=False,
        chevronPosition="left",
        children=[
            dcc.Markdown("Filters are used to filter data during the night, and producing substreams for the Livestream and tags for the API. They can also be used in the Data Transfer to filter historical data and replay streams. Blocks are convenient small functions used for example to build larger filters."),
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
            dcc.Markdown("This section details the alert schema (Avro format) as it is sent by LSST, plus the additional fields by Fink. The schema is nested, that is there are several nested levels. The root sections and field names will be separated by a point, as in `diaSource.ra` (`ra` field in the root section `diaSource`)."),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "LSST fields",
                    ),
                    dmc.AccordionPanel(
                        dmc.Group([
                            dmc.Center(
                                dmc.Group([
                                    dmc.Button(
                                        html.A(
                                            "LSST online schemas",
                                            href="https://sdm-schemas.lsst.io/apdb.html",
                                            target="_blank",
                                        ),
                                        variant="outline",
                                        color=DEFAULT_FINK_COLORS[0],
                                    ),
                                    dmc.Button(
                                        html.A(
                                            "LSST AVRO schemas",
                                            href="https://github.com/lsst/alert_packet/tree/main/python/lsst/alert/packet/schema",
                                            target="_blank",
                                        ),
                                        variant="outline",
                                        color=DEFAULT_FINK_COLORS[0],
                                    ),
                                ])
                            ),
                            create_datatransfer_schema_table(provenance="lsst"),
                        ])
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
                        "Pre-defined packet contents (Data Transfer)",
                    ),
                    dmc.AccordionPanel(
                        create_datatransfer_schema_table(provenance="custom")
                    ),
                ],
                value="custom",
            ),
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
                    dmc.AccordionPanel(
                        html.Div(
                            dmc.Skeleton(height="20pc", mb="xl"),
                            id="api",
                        ),
                    ),
                ],
                value="api",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Alert packet, Data Transfer & Livestream",
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
