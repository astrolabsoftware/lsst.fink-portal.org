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
import base64
import datetime
import io
import textwrap

import dash_mantine_components as dmc
import pandas as pd
import numpy as np
import requests
import yaml
from dash import ALL, MATCH, Input, Output, State, callback, ctx, dcc, html, no_update, dash_table
from dash_autocomplete_input import AutocompleteInput
from dash_iconify import DashIconify
from dash.exceptions import PreventUpdate

from app import app
from apps.configuration import extract_configuration
from apps.dataclasses import fink_blocks, fink_tags
from apps.mining.utils import (
    estimate_alert_number_lsst,
    estimate_size_gb_lsst,
    submit_spark_job,
    upload_file_hdfs,
)
from apps.plotting import DEFAULT_FINK_COLORS
from apps.schema import fields_for_data_transfer, predefined_fields_for_data_transfer, lsst_nested_fields_for_data_transfer
from apps.utils import query_and_order_statistics

args = extract_configuration("config.yml")
APIURL = args["APIURL"]

min_step = 0
max_step = 5

MAX_ROW = 100000

ALL_LSST_FIELDS, ALL_FINK_FIELDS = fields_for_data_transfer()


def config_tab():
    """Tab for the configuration"""
    tab = html.Div(
        [
            dmc.Space(h=50),
            dmc.Text("Re-use configuration file", size="sm"),
            dmc.Text(
                "If you downloaded the configuration file (YAML) of a previous job, you can upload it here. Fields will be automatically populated, and you can re-submit the job or further modify options. Otherwise click on Next Step to start selecting options for your job.",
                size="xs",
                c="gray",
            ),
            dmc.Space(h=10),
            dcc.Upload(
                id="upload_yaml_file",
                children=html.Div([
                    "Drag and Drop or ",
                    html.A("Select Configuration YAML Files "),
                ]),
                style={
                    "width": "100%",
                    "height": "60px",
                    "lineHeight": "60px",
                    "borderWidth": "1px",
                    "borderStyle": "dashed",
                    "borderRadius": "5px",
                    "textAlign": "center",
                    "margin": "0px",
                },
            ),
        ],
        id="config_tab",
    )
    return tab


def date_tab():
    """Tab to choose the date"""
    options = html.Div([
        dmc.DatePickerInput(
            type="range",
            id="date-range-picker",
            label="Date Range",
            description="Pick up start and stop dates (included).",
            hideOutsideDates=True,
            numberOfColumns=2,
            dropdownType="modal",
            modalProps={"centered": True},
            minDate="2025-10-25",
            maxDate=datetime.datetime.now().date(),
            allowSingleDateInRange=True,
            required=True,
            clearable=True,
        ),
    ])
    tab = html.Div(
        [
            dmc.Space(h=50),
            options,
        ],
        id="date_tab",
    )
    return tab


@app.callback(
    Output("field_select", "error"),
    [
        Input("field_select", "value"),
    ],
    prevent_initial_call=True,
)
def check_field(fields):
    """Check that alert field selector is correct.

    Parameters
    ----------
    fields: list
        List of selected alert fields

    Returns
    -------
    out: str
        Error message
    """
    if fields is not None:
        if len(fields) > 1 and "Full packet" in fields:
            return "Full packet cannot be combined with other fields."
        if len(fields) > 1 and "Light static packet" in fields:
            return "Light static packet cannot be combined with other fields."
        if len(fields) > 1 and "Light SSO packet" in fields:
            return "Light SSO packet cannot be combined with other fields."
        if len(fields) > 1 and "Medium packet" in fields:
            return "Medium packet cannot be combined with other fields."
    return ""


def switch_button(nclicks, label):
    """Change the layout of buttons depending on the number of clicks"""
    # button_clicked = ctx.triggered_id
    if nclicks is None:
        return no_update

    if isinstance(nclicks, int):
        if nclicks == 0:
            return no_update

        cycle_value = nclicks % 3
        if cycle_value == 0:
            # back to unchecked
            return label.split("NOT")[-1].strip(), "light", "grey"
        if cycle_value == 1:
            # odd clicks
            return label, "filled", DEFAULT_FINK_COLORS[-1]
        elif cycle_value == 2:
            # even clicks: 2, 4, 6, ...
            return "NOT " + label, "filled", DEFAULT_FINK_COLORS[0]


@app.callback(
    [
        Output({"type": "button_filter_transfer", "index": MATCH}, "children"),
        Output({"type": "button_filter_transfer", "index": MATCH}, "variant"),
        Output({"type": "button_filter_transfer", "index": MATCH}, "color"),
    ],
    [
        Input({"type": "button_filter_transfer", "index": MATCH}, "n_clicks"),
    ],
    State({"type": "button_filter_transfer", "index": MATCH}, "children"),
)
def switch_filter_button(nclicks, label):
    """Change the layout of buttons depending on the number of clicks"""
    return switch_button(nclicks, label)


@app.callback(
    [
        Output({"type": "button_blocks_transfer", "index": MATCH}, "children"),
        Output({"type": "button_blocks_transfer", "index": MATCH}, "variant"),
        Output({"type": "button_blocks_transfer", "index": MATCH}, "color"),
    ],
    [
        Input({"type": "button_blocks_transfer", "index": MATCH}, "n_clicks"),
    ],
    State({"type": "button_blocks_transfer", "index": MATCH}, "children"),
)
def switch_block_button(nclicks, label):
    """Change the layout of buttons depending on the number of clicks"""
    return switch_button(nclicks, label)


def store_tags_blocks(tags, variants, n_clicks):
    """Return a list of active tags/blocks"""
    active_tags = [tag for tag, variant in zip(tags, variants) if variant == "filled"]
    return active_tags


@app.callback(
    Output("tag_select", "data", allow_duplicate=True),
    [
        Input({"type": "button_filter_transfer", "index": ALL}, "children"),
        Input({"type": "button_filter_transfer", "index": ALL}, "variant"),
        Input({"type": "button_filter_transfer", "index": ALL}, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def store_tags(tags, variants, n_clicks):
    """Return a list of active tags"""
    return store_tags_blocks(tags, variants, n_clicks)


@app.callback(
    Output("blocks_select", "data", allow_duplicate=True),
    [
        Input({"type": "button_blocks_transfer", "index": ALL}, "children"),
        Input({"type": "button_blocks_transfer", "index": ALL}, "variant"),
        Input({"type": "button_blocks_transfer", "index": ALL}, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def store_blocks(tags, variants, n_clicks):
    """Return a list of active blocks"""
    return store_tags_blocks(tags, variants, n_clicks)

def create_tile(icon, heading, description, index, content):
    return html.Div(
        [
            dmc.Card(
                radius="md",
                p="xl",
                withBorder=True,
                m=5,
                #className="homepage-tile",
                children=[
                    dmc.Group([
                        DashIconify(
                            icon=icon,
                            height=40,
                            color= DEFAULT_FINK_COLORS[0],
                        ),
                        dmc.ActionIcon(
                            DashIconify(
                                icon="material-symbols:add-circle-outline",
                                color=DEFAULT_FINK_COLORS[-1],
                                width=40
                            ),
                            color="white",
                            variant="subtle",
                            size="xl",
                            id=f"modal-datatransfer-button-{index}"
                        )
                    ], justify="space-between"),
                    dmc.Text(heading, size="lg", mt="md"),
                    dmc.Text(description, size="sm", c="dimmed", mt="sm"),
                ],
            ),
            dmc.Modal(
                title=dmc.Text(heading, size="xl", mt="md", c="black"),
                children=content,
                id=f"modal-datatransfer-{index}",
                size="70%",
                #fullScreen=True,
            )
        ]
    )

@callback(
    Output("modal-datatransfer-1", "opened"),
    Input("modal-datatransfer-button-1", "n_clicks"),
    State("modal-datatransfer-1", "opened"),
    prevent_initial_call=True,
)
def modal_demo(nc1, opened):
    return not opened

@callback(
    Output("modal-datatransfer-2", "opened"),
    Input("modal-datatransfer-button-2", "n_clicks"),
    State("modal-datatransfer-2", "opened"),
    prevent_initial_call=True,
)
def modal_demo(nc1, opened):
    return not opened

@callback(
    Output("modal-datatransfer-3", "opened"),
    Input("modal-datatransfer-button-3", "n_clicks"),
    State("modal-datatransfer-3", "opened"),
    prevent_initial_call=True,
)
def modal_demo(nc1, opened):
    return not opened

def create_user_filterblocks_description(items):
    """ """
    # header
    rows = []
    for index, (tag, description) in enumerate(items.items()):
        if tag.startswith("b_"):
            classname = "button_blocks_transfer"
            symbol = "target"
            name = "Blocks"
        else:
            classname = "button_filter_transfer"
            symbol = "stream"
            name = "Filters"
        button = dmc.Button(
            children=tag,
            className=classname,
            id={
                "type": classname,
                "index": index,
            },
            radius="xl",
            #size="lg",
            variant="light",
            color="grey",
            style={"margin": "3px"},
            leftSection=DashIconify(icon=f"material-symbols:{symbol}"),
        )
        rows.append(
            dmc.TableTr([
                dmc.TableTd(button),
                dmc.TableTd(description),
            ])
        )

    head = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh(name, w="35%"),
            dmc.TableTh("Description", w="65%"),
        ])
    )
    body = dmc.TableTbody(rows)

    table_candidate = html.Div(
        dmc.Table(
            [head, body, None],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
    )
    return table_candidate

def upload_catalog():
    """ """
    radius = dmc.NumberInput(
        placeholder="type value...",
        label="Crossmatch radius in arcsecond",
        variant="default",
        # size="sm",
        # radius="sm",
        hideControls=True,
        w=250,
        mb=10,
        id="radius_xmatch",
        disabled=True,
    )

    ra = dmc.Select(
        label="Column for Right Ascension (J2000)",
        placeholder="Select one",
        id="ra-column",
        w=250,
        mb=10,
        disabled=True,
    )
    dec = dmc.Select(
        label="Column for Declination (J2000)",
        placeholder="Select one",
        id="dec-column",
        w=250,
        mb=10,
        disabled=True,
    )
    identifier = dmc.Select(
        label="Select column for the identifier",
        placeholder="Select one",
        id="id-column",
        w=250,
        mb=10,
        disabled=True,
    )

    return html.Div(
        children=[
            dcc.Upload(
                id="upload-data",
                children=html.Div(
                    [
                        "Drag and Drop or ",
                        html.A("Select Files "),
                        "(csv, fits, parquet, or votable)",
                    ]
                ),
                style={
                    "width": "100%",
                    "height": "60px",
                    "lineHeight": "60px",
                    "borderWidth": "1px",
                    "borderStyle": "dashed",
                    "borderRadius": "5px",
                    "textAlign": "center",
                    "margin": "10px",
                },
            ),
            html.Div(id="output-data-upload"),
            dmc.Space(h=10),
            dmc.Group([ra, dec, identifier, radius], justify="center"),
            dmc.Space(h=10),
            # dmc.Center(modal_skymap()),
        ]
    )

@callback(
    Output("output-data-upload", "children"),
    Input("object-catalog", "data"),
    State("upload-data", "filename"),
    State("upload-data", "last_modified"),
)
def update_output(catalog, filename, date):
    if catalog is not None:
        children = parse_contents(catalog, filename, date)
        return children


@callback(
    [
        Output("object-catalog", "data"),
        Output("gauge_catalog_number", "sections"),
        Output("gauge_catalog_number", "label"),
        Output("notification-container", "sendNotifications", allow_duplicate=True),
    ],
    [
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
    ],
    prevent_initial_call='initial_duplicate'
)
def store_catalog(content, filename):
    """Store data from user"""
    if filename is None:
        return no_update, no_update, dmc.Text("No catalog", ta="center"), no_update

    content_type, content_string = content.split(",")
    decoded = base64.b64decode(content_string)

    try:
        if ".csv" in filename:
            # Assume that the user uploaded a CSV file
            pdf = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        elif ".parquet" in filename:
            # Assume that the user uploaded a parquet file
            pdf = pd.read_parquet(io.BytesIO(decoded))
        elif ".xml" in filename:
            # Assume that the user uploaded a votable file
            table = votable.parse(io.BytesIO(decoded))
            pdf = table.get_first_table().to_table(use_names_over_ids=True).to_pandas()
        elif ".fits" in filename:
            # Assume that the user uploaded a fits file
            with fits.open(io.BytesIO(decoded)) as hdul:
                for hdu in hdul:
                    if isinstance(hdu, fits.BinTableHDU):
                        pdf = pd.DataFrame(np.array(hdu.data))
                        break
        if ("pdf" not in locals()) or (not isinstance(pdf, pd.DataFrame)):
            msg = "Catalog format not recognised"
            notification = dict(
                title="Error while uploading catalog",
                id="show-notify",
                action="show",
                message=msg,
                color="red",
                autoClose=False,
            )
            return (
                "{}",
                [{"value": 0, "color": "grey", "tooltip": "0%"}],
                dmc.Text(msg, c="red", ta="center"),
                [notification],

            )
    except Exception as e:
        notification = dict(
            title="Error while uploading catalog",
            id="show-notify",
            action="show",
            message=e,
            color="red",
            autoClose=False,
        )
        return (
            "{}",
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text(e, c="red", ta="center"),
            [notification],
        )

    if len(pdf) > MAX_ROW:
        msg = "{:,} > {} rows allowed. Uploading only {} rows.".format(len(pdf), MAX_ROW, MAX_ROW)
        color = "orange"
        notification = dict(
            title="Truncating input catalog",
            id="show-notify",
            action="show",
            message=msg,
            color=color,
            autoClose=False,
        )
        pdf = pdf.head(MAX_ROW)
    else:
        color = "green"
        notification = dict(
            title="Catalog uploaded",
            id="show-notify",
            action="show",
            message="{:,} rows".format(len(pdf)),
            color=color,
        )
    sections = {
        "value": len(pdf) / MAX_ROW * 100,
        "color": color,
        "tooltip": "{:.2f}%".format(len(pdf) / MAX_ROW * 100),
    }
    label = dmc.Text("{:,} rows".format(len(pdf)), c=DEFAULT_FINK_COLORS[0], ta="center")

    return pdf.to_json(), [sections], label, [notification]

def parse_contents(catalog, filename, date):
    pdf = pd.read_json(io.StringIO(catalog))

    # Check header? Or ask the user to provide what is RA, DEC, OID?

    return html.Div(
        [
            html.H5("{}".format(filename)),
            html.H6("Preview of the 10 first rows"),
            dash_table.DataTable(
                pdf.head(10).to_dict("records"),
                [{"name": i, "id": i} for i in pdf.columns],
            ),
        ]
    )

@app.callback(
    [
        Output("ra-column", "disabled"),
        Output("dec-column", "disabled"),
        Output("id-column", "disabled"),
        Output("radius_xmatch", "disabled"),
        Output("ra-column", "data"),
        Output("dec-column", "data"),
        Output("id-column", "data"),
    ],
    Input("object-catalog", "data"),
    prevent_initial_call=True,
)
def select_columns(catalog):
    """ """
    if catalog is None or catalog == {} or catalog == "{}":
        PreventUpdate()

    pdf = pd.read_json(io.StringIO(catalog))
    if pdf.empty:
        PreventUpdate()

    ra_data = [{"value": c, "label": c} for c in pdf.columns]
    dec_data = [{"value": c, "label": c} for c in pdf.columns]
    identifier = [{"value": c, "label": c} for c in pdf.columns]

    return False, False, False, False, ra_data, dec_data, identifier


def enforce_decimal(pdf, ra_label, dec_label):
    """Convert RA and Dec to decimal degree if need be

    Parameters
    ----------
    pdf: pd.DataFrame
        Pandas DataFrame
    ra_label: str
        RA column name
    dec_label: str
        Dec column name

    Returns
    -------
    out: np.array, np.array
        RA, Dec in decimal degrees
    """
    ra = pdf[ra_label].to_numpy()
    dec = pdf[dec_label].to_numpy()

    # conversion if not degree
    if isinstance(ra[0], str) and not ra[0].isnumeric():
        out = []
        for ra_, dec_ in zip(ra, dec):
            string = "{} {}".format(ra_, dec_)
            m = re.search(
                r"^(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}\.?\d*)\s+([+-])?\s*(\d{1,3})\s+(\d{1,2})\s+(\d{1,2}\.?\d*)(\s+(\d+\.?\d*))?$",
                string,
            ) or re.search(
                r"^(\d{1,2})[:h](\d{1,2})[:m](\d{1,2}\.?\d*)[s]?\s+([+-])?\s*(\d{1,3})[d:](\d{1,2})[m:](\d{1,2}\.?\d*)[s]?(\s+(\d+\.?\d*))?$",
                string,
            )
            if m:
                ra_deg = (float(m[1]) + float(m[2]) / 60 + float(m[3]) / 3600) * 15
                dec_deg = float(m[5]) + float(m[6]) / 60 + float(m[7]) / 3600

                if m[4] == "-":
                    dec_deg *= -1

                out.append([ra_deg, dec_deg])
        if len(out) > 0:
            ra, dec = np.transpose(out)

    return ra, dec

def filter_number_tab():
    """Construct the filtering tab for the Data Transfer service

    Returns
    -------
    out: Div
    """
    option1 = html.Div(
        [
            dmc.Space(h=10),
            dmc.Text(
                [
                    "You can apply one or several Fink filters (",
                    DashIconify(icon="material-symbols:stream"),
                    ") used in real-time to select alerts of interest. You can also apply Fink blocks (",
                    DashIconify(icon="material-symbols:target"),
                    "), which are small user-defined functions acting as building blocks for the filters. One click to apply the filter/block ",
                    dmc.Text("(dark orange) ", c="orange", span=True, inherit=True),
                    ", two clicks to apply the negation ",
                    dmc.Text("(dark blue) ", c="blue", span=True, inherit=True),
                    ", three clicks to deselect (gray). See the ",
                    html.A(
                        "schema page",
                        href="https://lsst.fink-portal.org/schemas",
                        target="_blank",
                    ),
                    r" for description of available filters and blocks.",
                ],
                size="lg",
                c="gray",
            ),
            dmc.Space(h=30),
            create_user_filterblocks_description(fink_tags),
            dmc.Space(h=30),
            create_user_filterblocks_description(fink_blocks),
        ]
    )

    option2 = upload_catalog()

    option3 = html.Div(
        [
            dmc.Space(h=20),
            dmc.Text(
                [
                    "Similarly to the blocks above, you can write your own block. You need to specify one condition per line (SQL syntax), ending with semi-colon (see below for examples). Start typing an alert section such as ",
                    dmc.Text("diaSource., ", fw=700, inherit=True, span=True),
                    dmc.Text("diaObject., ", fw=700, inherit=True, span=True),
                    dmc.Text("mpc_orbits., ", fw=700, inherit=True, span=True),
                    dmc.Text("ssSource., ", fw=700, inherit=True, span=True),
                    "for LSST and ",
                    dmc.Text("xm., ", fw=700, inherit=True, span=True),
                    dmc.Text("clf., ", fw=700, inherit=True, span=True),
                    dmc.Text("misc., ", fw=700, inherit=True, span=True),
                    dmc.Text("pred., ", fw=700, inherit=True, span=True),
                    "for Fink added values and a list with available fields will trigger. You can share your block by submitting your YAML configuration file at ",
                    html.A(
                        "fink-filters",
                        href="https://github.com/astrolabsoftware/fink-filters",
                        target="_blank",
                    ),
                    r". See the ",
                    html.A(
                        "schema page",
                        href="https://lsst.fink-portal.org/schemas",
                        target="_blank",
                    ),
                    r" for description of available fields.",
                ],
                size="lg",
                c="gray",
            ),
            dmc.Space(h=10),
            AutocompleteInput(
                offsetX=0,
                offsetY=0,
                id="extra_cond",
                placeholder="One condition per line (SQL syntax), ending with semi-colon.",
                component="textarea",
                trigger=[
                    "diaSource.",
                    "ssSource.",
                    "diaObject.",
                    "mpc_orbits.",
                    "xm.",
                    "clf.",
                    "misc.",
                    "pred.",
                ],
                options={
                    "diaSource.": [
                        k.split("diaSource.")[-1]
                        for k in ALL_LSST_FIELDS.keys()
                        if k.startswith("diaSource.")
                    ],
                    "ssSource.": [
                        k.split("ssSource.")[-1]
                        for k in ALL_LSST_FIELDS.keys()
                        if k.startswith("ssSource.")
                    ],
                    "mpc_orbits.": [
                        k.split("mpc_orbits.")[-1]
                        for k in ALL_LSST_FIELDS.keys()
                        if k.startswith("mpc_orbits.")
                    ],
                    "diaObject.": [
                        k.split("diaObject.")[-1]
                        for k in ALL_LSST_FIELDS.keys()
                        if k.startswith("diaObject.")
                    ],
                    "xm.": [
                        k.split("xm.")[-1]
                        for k in ALL_FINK_FIELDS.keys()
                        if k.startswith("xm.")
                    ],
                    "clf.": [
                        k.split("clf.")[-1]
                        for k in ALL_FINK_FIELDS.keys()
                        if k.startswith("clf.")
                    ],
                    "misc.": [
                        k.split("misc.")[-1]
                        for k in ALL_FINK_FIELDS.keys()
                        if k.startswith("misc.")
                    ],
                    "pred.": [
                        k.split("pred.")[-1]
                        for k in ALL_FINK_FIELDS.keys()
                        if k.startswith("pred.")
                    ],
                },
                maxOptions=0,
                className="inputbar form-control roundcorner",
                quoteWhitespaces=True,
                autoFocus=True,
                ignoreCase=True,
                triggerInsideWord=False,
                matchAny=True,
                style={
                    "height": "15pc",
                    "width": "100%",
                    "position": "relative",
                },
            ),
            dmc.Accordion(
                id="extra_cond_description",
                children=[
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl(
                                "Examples",
                                icon=DashIconify(
                                    icon="tabler:help",
                                    color=dmc.DEFAULT_THEME["colors"]["blue"][6],
                                    width=20,
                                ),
                            ),
                            dmc.AccordionPanel(
                                dcc.Markdown("""You can impose any extra conditions on the alerts you want to retrieve based on their content. Simply specify the name of the parameter with the condition (SQL syntax). See below for the alert schema. If you have several conditions, put one condition per line, ending with semi-colon. Example of valid conditions:

```sql
-- Example block 1
-- Alerts with flux above 13500 nJy (< mag 21) and
-- at least 3 detections
diaSource.psfFlux > 13500;
diaObject.nDiaSources > 3;

-- Example block 2: Filter on magnitude and specific band
diaSource.band = 'g';
31.4 - 2.5 * LOG10(diaSource.scienceFlux) < 21;

-- Example block 3: Using a combination of fields (magnitude difference between difference and template image)
2.5 * LOG10(diaSource.psfFlux / diaSource.templateFlux) > 0.5;

-- Example block 3: Filtering on ML scores
clf.snnSnVsOthers_score > 0.5;

-- Example block 4: Filtering on catalog output
xm.tns_type IN ('SN Ia', 'SN II');

-- Example block 5: Only classified objects in SIMBAD and Gaia DR3
pred.is_cataloged;

-- Example block 6: Only far away Solar System objects
pred.is_sso;
mpc_orbits.a > 10;
```"""),
                            ),
                        ],
                        value="info",
                    ),
                ], value="info"
            ),
        ],
    )
    tabs = dmc.Container(
        size="lg",
        px=0,
        py=0,
        my=40,
        children=[
            dmc.SimpleGrid(
                mt=80,
                cols={"xs": 1, "sm": 2, "xl": 3},
                children=[
                    create_tile(
                        icon="boxicons:filter",
                        heading="Fink filters",
                        description="Select alerts of interest by applying user-defined Fink filters and blocks.",
                        index=1,
                        content=option1
                    ),
                    create_tile(
                        icon="fluent-mdl2:venn-diagram",
                        heading="External catalog",
                        description="Upload your catalog of astronomical sources to find matches with Fink/LSST alerts.",
                        index=2,
                        content=option2
                    ),
                    create_tile(
                        icon="solar:document-add-linear",
                        heading="Custom filtering",
                        description="Select alerts of interest by writing your own filtering.",
                        index=3,
                        content=option3
                    ),
                ]
            )
        ],
    )
    tab = html.Div(
        [
            dmc.Space(h=50),
            dmc.Divider(variant="solid", label="Reduce the number of incoming alerts"),
            tabs,
        ],
        id="filter_number_tab",
    )
    return tab


def filter_content_tab():
    custom_fields, _ = predefined_fields_for_data_transfer()
    nested_fields, _ = lsst_nested_fields_for_data_transfer()
    data = [
        custom_fields[0],
        nested_fields[0],
        {"group": "Fink added values", "items": list(ALL_FINK_FIELDS.keys())},
        {"group": "LSST original fields", "items": list(ALL_LSST_FIELDS.keys())},
    ]
    options = html.Div(
        [
            dmc.MultiSelect(
                label="Alert fields",
                description=dmc.Text(
                    [
                        dmc.Text(
                            "Select all fields you like! Default is all fields. Schema page is at ",
                            span=True,
                            inherit=True,
                        ),
                        html.A(
                            "https://lsst.fink-portal.org/schemas",
                            href="https://lsst.fink-portal.org/schemas",
                            target="_blank",
                        ),
                    ],
                    size="xs",
                    c="gray",
                ),
                placeholder="start typing...",
                id="field_select",
                data=data,
                searchable=True,
                clearable=True,
            ),
            dmc.Space(h=10),
        ],
    )
    tab = html.Div(
        [
            dmc.Space(h=50),
            dmc.Divider(variant="solid", label="Filter alert content"),
            options,
        ],
        id="filter_content_tab",
    )
    return tab


@app.callback(
    [
        Output("download_yaml", "data"),
        Output("notification-container", "sendNotifications", allow_duplicate=True),
    ],
    [
        Input("submit_yaml_file", "n_clicks"),
        Input("date-range-picker", "value"),
        Input("tag_select", "data"),
        Input("blocks_select", "data"),
        Input("field_select", "value"),
        Input("extra_cond", "value"),
        State("upload-data", "filename"),
    ],
    prevent_initial_call=True,
)
def download_yaml(
    nclicks,
    date_range_picker,
    tag_select,
    blocks_select,
    field_select,
    extra_cond,
    catalog_filename,
):
    """Construct a JSON file and export to YAML"""
    if nclicks is None:
        return no_update, no_update

    if (
        date_range_picker is None
        or isinstance(date_range_picker, list)
        and None in date_range_picker
    ):
        return no_update, [
            dict(
                title="Ooops",
                id="show-notify",
                action="show",
                message="You need to specify dates at least!",
                color="red",
            )
        ]

    if extra_cond is not None and isinstance(extra_cond, str):
        extra_cond = extra_cond.split(";")
        extra_cond = [i.strip() for i in extra_cond]
        extra_cond = [i for i in extra_cond if i != ""]
    outfile = {
        "dates": {"startdate": date_range_picker[0], "stopdate": date_range_picker[1]},
        "filters": tag_select,
        "blocks": blocks_select,
        "content": field_select,
        "extra_cond": extra_cond,
        "catalog_filename": catalog_filename
    }

    if field_select is None or field_select == []:
        field_select = ["Full packet"]

    yaml_string = yaml.dump(outfile, default_flow_style=False)

    # Get the current date and time
    now = datetime.datetime.now()

    # Format the date and time
    formatted_date = now.strftime("%Y%m%d_%H%M%S")

    return dict(content=yaml_string, filename=f"datatransfer_{formatted_date}.yml"), [
        dict(
            title="Success",
            id="show-notify",
            action="show",
            message="Configuration downloaded",
            color="green",
        )
    ]


@app.callback(
    [
        Output("date-range-picker", "value", allow_duplicate=True),
        Output("tag_select", "data", allow_duplicate=True),
        Output("blocks_select", "data", allow_duplicate=True),
        Output("field_select", "value", allow_duplicate=True),
        Output("extra_cond", "value", allow_duplicate=True),
        Output("notification-container", "sendNotifications", allow_duplicate=True),
        Output("stepper-basic-usage", "active", allow_duplicate=True),
    ],
    [
        Input("upload_yaml_file", "contents"),
        Input("upload_yaml_file", "filename"),
    ],
    prevent_initial_call=True,
)
def upload_yaml(content, filename):
    """Construct a JSON file and export to YAML"""
    if content is None:
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    content_type, content_string = content.split(",")
    decoded = base64.b64decode(content_string)

    data = yaml.safe_load(io.StringIO(decoded.decode("utf-8")))

    is_valid, catalog_filename, outNotifications = validate_yaml(data)

    if not is_valid:
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            outNotifications,
            no_update,
        )
    elif catalog_filename != "":
        outNotifications = [
            dict(
                title=f"Previous configuration loaded from {filename}",
                message=f"You still need to re-upload your catalog ({catalog_filename})",
                color="orange",
            )
        ]
    else:
        outNotifications = [
            dict(
                title=f"Previous configuration loaded from {filename}",
                color="green",
            )
        ]

    extra_cond = sanitize_extra_cond(data["extra_cond"])

    return (
        [data["dates"]["startdate"], data["dates"]["stopdate"]],
        data["filters"],
        data["blocks"],
        data["content"],
        "\n".join(extra_cond),
        outNotifications,
        max_step - 1,
    )


def sanitize_extra_cond(extra_cond):
    """Sanitize the extra_cond component

    Parameters
    ----------
    extra_cond: list of str
        List of conditions as string

    Returns
    -------
    out: list of str
        Each element of the list has been stripped, and
        a ; has been added if need be.
    """
    if extra_cond is None:
        return []

    if isinstance(extra_cond, list):
        if len(extra_cond) > 0:
            out = []
            for elem in extra_cond:
                # get rid of blank
                elem = elem.strip()

                # add an extra ; at the end if need be
                if not elem.endswith(";"):
                    elem = elem + ";"

                out.append(elem)
            return out

    return []


def validate_yaml(dic):
    """Check input dictionary has correct fields

    Parameters
    ----------
    dic: dict
        Dictionary for the YAML construction

    Returns
    -------
    is_valid: bool
        True if the dictionary is valid. False otherwise.
    catalog_filename: str
        Name of the catalog. No catalog is empty string.
    outNotifications: dict
        Notifications to send to the user in case of unvalid dictionary.
    """
    outNotifications = None
    default_fields = {
        "dates": dict,
        "filters": list,
        "blocks": list,
        "content": list,
        "extra_cond": list,
        "catalog_filename": str,
    }

    # Support legacy format
    dic["catalog_filename"] = dic.get("catalog_filename", "")

    # Check all mandatory fields are here
    for key in default_fields:
        if key not in dic.keys():
            outNotifications = [
                dict(
                    title=f"Missing field {key} in the configuration file",
                    color="red",
                )
            ]
            return False, dic["catalog_filename"], outNotifications

    # Check we have start AND stop dates
    if len(dic["dates"]) != 2:
        outNotifications = [
            dict(
                title="Missing start/stop dates in the configuration file: {}".format(
                    dic["dates"]
                ),
                color="red",
            )
        ]
        return False, dic["catalog_filename"], outNotifications

    # Check their type. None is fine (means value not set)
    for key, value in dic.items():
        if not isinstance(value, default_fields[key]) and (value is not None):
            outNotifications = [
                dict(
                    title=f"{key} should be a {default_fields[key]} or unset. Did you forget a hyphen (-) in your YAML?",
                    color="red",
                )
            ]
            return False, dic["catalog_filename"], outNotifications

    return True, dic["catalog_filename"], outNotifications


@app.callback(
    [
        Output("gauge_alert_number", "sections"),
        Output("gauge_alert_number", "label"),
        Output("gauge_alert_size", "sections"),
        Output("gauge_alert_size", "label"),
    ],
    [
        Input("alert-stats", "data"),
        Input("date-range-picker", "value"),
        Input("tag_select", "data"),
        Input("blocks_select", "data"),
        Input("field_select", "value"),
        Input("extra_cond", "value"),
    ],
)
def gauge_meter(
    alert_stats,
    date_range_picker,
    tags,
    blocks,
    field_select,
    extra_cond,
):
    """ """
    if (
        date_range_picker is None
        or isinstance(date_range_picker, list)
        and None in date_range_picker
    ):
        return (
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
        )
    else:
        if field_select is None or field_select == []:
            field_select = ["Full packet"]

        total, count = estimate_alert_number_lsst(date_range_picker, tags, blocks)
        sizeGb, defaultGb = estimate_size_gb_lsst(field_select, blocks, ALL_LSST_FIELDS, ALL_FINK_FIELDS)

        if count == 0:
            color = "gray"
            # avoid division by 0
            total = 1
        elif count < 250000:
            color = "green"
        elif count > 1000000:
            color = "red"
        else:
            color = "orange"

        if sizeGb * count == 0:
            color_size = "gray"
            # avoid misinterpretation
            sizeGb = 0
        elif sizeGb * count < 10:
            color_size = "green"
        elif sizeGb * count > 100:
            color_size = "red"
        else:
            color_size = "orange"

        label_number = dmc.Stack(
            align="center",
            children=[
                dmc.Text(
                    f"{int(count):,} alerts",
                    c=DEFAULT_FINK_COLORS[0],
                    ta="center",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(
                            icon="fluent:question-16-regular",
                            width=20,
                        ),
                        size=30,
                        radius="xl",
                        variant="light",
                        color="orange",
                    ),
                    position="bottom",
                    multiline=True,
                    w=220,
                    label="Number of alerts received for the selected dates ({} to {}), excluding all Fink filters.".format(
                        *date_range_picker
                    ),
                ),
            ],
        )
        sections_number = [
            {
                "value": count / total * 100,
                "color": color,
                "tooltip": f"{count / total * 100:.2f}%",
            }
        ]

        label_size = dmc.Stack(
            align="center",
            children=[
                dmc.Text(
                    f"{count * sizeGb:.2f}GB",
                    c=DEFAULT_FINK_COLORS[0],
                    ta="center",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(
                            icon="fluent:question-16-regular",
                            width=20,
                        ),
                        size=30,
                        radius="xl",
                        variant="light",
                        color="orange",
                    ),
                    position="bottom",
                    multiline=True,
                    w=220,
                    label="Estimated data volume to transfer based on selected alert fields. The percentage is given with respect to the total for the selected dates ({} to {}), excluding Fink filters.".format(
                        *date_range_picker
                    ),
                ),
            ],
        )
        sections_size = [
            {
                "value": sizeGb / defaultGb * 100,
                "color": color_size,
                "tooltip": f"{sizeGb / defaultGb * 100:.2f}%",
            }
        ]

        return sections_number, label_number, sections_size, label_size


@app.callback(
    Output("code_block", "code"),
    Input("topic_name", "children"),
    prevent_initial_call=True,
)
def update_code_block(topic_name):
    if topic_name is not None and topic_name != "":
        # FIXME: introduce partitioning?
        # This is done by time by default
        code_block = f"""
# Requires fink-client>=10.0
fink_datatransfer \\
    -survey lsst \\
    -topic {topic_name} \\
    -outdir {topic_name} \\
    --verbose
        """
        return code_block


@app.callback(
    Output("submit_datatransfer", "disabled"),
    Output("notification-container", "sendNotifications", allow_duplicate=True),
    Output("batch_id", "children"),
    Output("topic_name", "children"),
    [
        Input("submit_datatransfer", "n_clicks"),
    ],
    [
        State("date-range-picker", "value"),
        State("tag_select", "data"),
        State("blocks_select", "data"),
        State("field_select", "value"),
        State("extra_cond", "value"),
        State("object-catalog", "data"),
        State("upload-data", "filename"),
        State("ra-column", "value"),
        State("dec-column", "value"),
        State("radius_xmatch", "value"),
        State("id-column", "value"),
    ],
    prevent_initial_call=True,
)
def submit_job(
    n_clicks,
    date_range_picker,
    tag_select,
    blocks_select,
    field_select,
    extra_cond,
    catalog,
    catalog_filename,
    catalog_ra,
    catalog_dec,
    catalog_radius,
    catalog_identifier,
):
    """Submit a job to the Apache Spark cluster via Livy"""
    if n_clicks:
        # define unique topic name
        d = datetime.datetime.utcnow()

        # FIXME: should be in config
        topic_name = f"ftransfer_lsst_{d.date().isoformat()}_{d.microsecond}"
        fn = "assets/spark_lsst_transfer.py"
        basepath = "hdfs://ccmaster1:8020/user/fink/archive/science"
        filename = f"stream_{topic_name}.py"

        with open(fn) as f:
            data = f.read()
        code = textwrap.dedent(data)

        input_args = yaml.load(open("config_datatransfer.yml"), yaml.Loader)
        status_code, hdfs_log = upload_file_hdfs(
            code,
            input_args["WEBHDFS"],
            input_args["NAMENODE"],
            input_args["USER"],
            filename,
        )

        if status_code != 201:
            text = dmc.Stack(
                children=[
                    "Unable to upload resources on HDFS, with error: ",
                    dmc.CodeHighlight(code=f"{hdfs_log}", language="html"),
                    "Contact an administrator at contact@fink-broker.org.",
                ]
            )
            alert = dict(
                message=text,
                title=f"[Status code {status_code}]",
                color="red",
                action="show",
                autoClose=False,
            )
            return True, [alert], no_update, no_update

        # Send the data to HDFS as parquet file
        catalog_filename_parquet = os.path.splitext(catalog_filename)[0] + ".parquet"

        # Conversion in decimal degree as xmatch expects it
        pdf_catalog = pd.read_json(io.StringIO(catalog))
        pdf_catalog[catalog_ra], pdf[catalog_dec] = enforce_decimal(pdf_catalog, catalog_ra, catalog_dec)

        status_code, hdfs_log = upload_file_hdfs(
            pdf_catalog.to_parquet(),
            input_args["WEBHDFS"],
            input_args["NAMENODE"],
            input_args["USER"],
            catalog_filename_parquet,
        )

        if status_code != 201:
            text = dmc.Stack(
                children=[
                    "Unable to upload {} on HDFS, with error: ".format(
                        catalog_filename_parquet
                    ),
                    dmc.CodeHighlight(code=f"{hdfs_log}", language="html"),
                    "Contact an administrator at contact@fink-broker.org.",
                ]
            )
            alert = dict(
                message=text,
                title=f"[Status code {status_code}]",
                color="red",
                action="show",
                autoClose=False,
            )
            return True, [alert], no_update, no_update

        # get the job args
        job_args = [
            f"-startDate={date_range_picker[0]}",
            f"-stopDate={date_range_picker[1]}",
            f"-basePath={basepath}",
            f"-topic_name={topic_name}",
            f"-ra_col={catalog_ra}",
            f"-dec_col={catalog_dec}",
            f"-radius_arcsec={catalog_radius}",
            f"-id_col={catalog_identifier}",
            "-catalog_filename={}".format(
                "hdfs://{}///user/{}/{}".format(
                    input_args["NAMENODE"], input_args["USER"], catalog_filename_parquet
                )
            ),
            "-kafka_bootstrap_servers={}".format(input_args["KAFKA_BOOTSTRAP_SERVERS"]),
            "-kafka_sasl_username={}".format(input_args["KAFKA_SASL_USERNAME"]),
            "-kafka_sasl_password={}".format(input_args["KAFKA_SASL_PASSWORD"]),
            "-path_to_tns=/data/fink/tns/tns.parquet",
        ]
        if field_select is not None:
            [job_args.append(f"-ffield={elem}") for elem in field_select]
        if isinstance(tag_select, list) and len(tag_select) > 0:
            [job_args.append(f"-ffilter={tag}") for tag in tag_select]
        if isinstance(blocks_select, list) and len(blocks_select) > 0:
            [job_args.append(f"-fblock={block}") for block in blocks_select]

        if extra_cond is not None:
            extra_cond_list = extra_cond.split(";")
            [job_args.append(f"-extraCond={elem.strip()}") for elem in extra_cond_list]

        # submit the job
        filepath = "hdfs://ccmaster1:8020/user/{}/{}".format(
            input_args["USER"], filename
        )
        batchid, status_code, spark_log = submit_spark_job(
            input_args["LIVYHOST"],
            filepath,
            input_args["SPARKCONF"],
            job_args,
        )

        if status_code != 201:
            text = dmc.Stack(
                children=[
                    "Unable to upload resources on HDFS, with error: ",
                    dmc.CodeHighlight(code=f"{spark_log}", language="html"),
                    "Contact an administrator at contact@fink-broker.org.",
                ]
            )
            alert = dict(
                message=text,
                title=f"[Batch ID {batchid}][Status code {status_code}]",
                color="red",
                autoClose=False,
            )
            return True, [alert], no_update, no_update

        alert = dict(
            message=f"Your topic name is: {topic_name}",
            title="Submitted successfully",
            color="green",
            autoClose=False,
        )
        if n_clicks:
            return True, [alert], batchid, topic_name
        else:
            return False, [alert], batchid, topic_name
    else:
        return no_update, no_update, no_update, no_update


@app.callback(
    Output("batch_log", "children"),
    [
        Input("batch_id", "children"),
        Input("interval-component", "n_intervals"),
    ],
)
def update_log(batchid, interval):
    """Update log from the Spark cluster"""
    if batchid != "":
        response = requests.get(f"http://ccmaster1:21111/batches/{batchid}/log")

        if "log" in response.json():
            bad_words = ["Error", "Traceback"]
            failure_log = [
                row
                for row in response.json()["log"]
                if np.any([i in row for i in bad_words])
            ]
            if len(failure_log) > 0:
                initial_traceback = failure_log[0]
                log = response.json()["log"]
                index = log.index(initial_traceback)
                failure_msg = [
                    f"Batch ID: {batchid}",
                    "Failed. Please, contact contact@fink-broker.org with your batch ID and the message below.",
                    "------------- Traceback -------------",
                    *log[index:],
                ]
                output = html.Div(
                    "\n".join(failure_msg), style={"whiteSpace": "pre-wrap"}
                )
                return output
            # catch and return tailored error msg if fail (with batchid and contact@fink-broker.org)
            livy_log = [row for row in response.json()["log"] if "-Livy-" in row]
            livy_log = [f"Batch ID: {batchid}", "Starting..."] + livy_log
            output = html.Div("\n".join(livy_log), style={"whiteSpace": "pre-wrap"})
        elif "msg" in response.json():
            output = html.Div(response.text)
        return output
    else:
        return no_update


instructions = """
#### 1. Review

You are about to submit a job on the Fink Apache Spark & Kafka clusters.
Review your parameters, and take into account the estimated number of
alerts before hitting submission! Note that the estimation takes into account the number
of alerts between the selected dates, but not the effect of the filters and blocks applied (which could reduce the
number of alerts).

#### 2. Download your configuration file

Hit the `Download configuration` button to export your configuration as a YAML file. This way you will be able to upload it later to re-submit the same job.

#### 3. Register

To retrieve the data, you need to get an account. See [fink-client](https://github.com/astrolabsoftware/fink-client) and
the [documentation](https://doc.lsst.fink-broker.org/services/data_transfer/) for more information.

#### 4. Retrieve

Once data has started to flow in the topic, you can easily download your alerts using the [fink-client](https://github.com/astrolabsoftware/fink-client).
Install the latest version and use e.g.
"""


def layout():
    pdf = query_and_order_statistics(
        columns="f:alerts",
        drop=False,
    )
    n_alert_total = np.sum(pdf["f:alerts"].to_numpy())
    active = 0

    helper = """
    The Fink data transfer service allows you to select and transfer Fink-processed alert data at scale.
    We provide access to alert data produced by the Rubin Observatory, and enriched by Fink.

    Follow these steps: (1) upload a previous configuration file if any (2) select observing nights, (3) apply filters and blocks to focus on relevant alerts and reduce the
    volume of data, and (4) select only the relevant alert fields for your analysis. Note that we provide estimates (upper limits) on
    the number of alerts to transfer and the data volume.

    Once ready, submit your job on the Fink Apache Spark and Kafka clusters to retrieve your data wherever you like.
    To access the data, you need to create an account. See the [fink-client](https://github.com/astrolabsoftware/fink-client) and
    the [documentation](https://doc.lsst.fink-broker.org/en/latest/services/data_transfer) for more information. The data is available
    for download for 7 days.
    """

    layout = dmc.Container(
        size="90%",
        children=[
            dmc.Space(h=20),
            dmc.Grid(
                justify="center",
                gutter={"base": 5, "xs": "md", "md": "xl", "xl": 50},
                grow=True,
                children=[
                    dmc.GridCol(
                        children=[
                            dmc.Stack(
                                [
                                    dmc.Space(h=20),
                                    dmc.Center(
                                        dmc.Title(
                                            children="Fink Data Transfer",
                                            style={"color": "#15284F"},
                                        ),
                                    ),
                                    dmc.Space(h=20),
                                    dmc.Stack(
                                        align="center",
                                        justify="center",
                                        children=[
                                            dmc.RingProgress(
                                                roundCaps=True,
                                                sections=[{"value": 0, "color": "grey"}],
                                                size=200,
                                                thickness=10,
                                                label="",
                                                id="gauge_alert_number",
                                            ),
                                            dmc.RingProgress(
                                                roundCaps=True,
                                                sections=[{"value": 0, "color": "grey"}],
                                                size=200,
                                                thickness=10,
                                                label="",
                                                id="gauge_alert_size",
                                            ),
                                            dmc.RingProgress(
                                                roundCaps=True,
                                                sections=[{"value": 0, "color": "grey"}],
                                                size=200,
                                                thickness=10,
                                                label="",
                                                id="gauge_catalog_number",
                                            ),
                                        ]
                                    ),
                                    dmc.Accordion(
                                        variant="separated",
                                        radius="xl",
                                        children=[
                                            dmc.AccordionItem(
                                                [
                                                    dmc.AccordionControl(
                                                        "Help",
                                                        icon=DashIconify(
                                                            icon="material-symbols:info-outline",
                                                            # color=dmc.DEFAULT_THEME["colors"]["blue"][6],
                                                            color="black",
                                                            width=30,
                                                        ),
                                                    ),
                                                    dmc.AccordionPanel(
                                                        dcc.Markdown(
                                                            helper, link_target="_blank"
                                                        ),
                                                    ),
                                                ],
                                                value="description",
                                            ),
                                        ],
                                        value=None,
                                    ),
                                ],
                                align="center",
                            )
                        ],
                        span=2,
                    ),
                    dmc.GridCol(
                        children=[
                            dmc.Space(h=40),
                            dmc.Stepper(
                                color="#15284F",
                                id="stepper-basic-usage",
                                active=active,
                                children=[
                                    dmc.StepperStep(
                                        label="Configuration",
                                        description="Upload",
                                        children=config_tab(),
                                        id="stepper-date",
                                    ),
                                    dmc.StepperStep(
                                        label="Date Range",
                                        description="Choose a date",
                                        children=date_tab(),
                                        id="stepper-date",
                                    ),
                                    dmc.StepperStep(
                                        label="Reduce number",
                                        description="Filter out unwanted alerts",
                                        children=filter_number_tab(),
                                    ),
                                    dmc.StepperStep(
                                        label="Choose content",
                                        description="Pick up only relevant fields",
                                        children=filter_content_tab(),
                                    ),
                                    dmc.StepperStep(
                                        label="Launch transfer!",
                                        description="Get your data",
                                        children=dmc.Grid(
                                            justify="center",
                                            gutter={
                                                "base": 5,
                                                "xs": "md",
                                                "md": "xl",
                                                "xl": 50,
                                            },
                                            grow=True,
                                            children=[
                                                dmc.GridCol(
                                                    children=[
                                                        dmc.Stack(
                                                            children=[
                                                                dmc.Space(h=20),
                                                                dmc.Group(
                                                                    children=[
                                                                        dmc.Button(
                                                                            "Submit job",
                                                                            id="submit_datatransfer",
                                                                            variant="outline",
                                                                            color=DEFAULT_FINK_COLORS[
                                                                                0
                                                                            ],
                                                                            leftSection=DashIconify(
                                                                                icon="fluent:send-16-filled"
                                                                            ),
                                                                        ),
                                                                        dmc.Button(
                                                                            "Download configuration",
                                                                            id="submit_yaml_file",
                                                                            variant="outline",
                                                                            color=DEFAULT_FINK_COLORS[
                                                                                0
                                                                            ],
                                                                            leftSection=DashIconify(
                                                                                icon="fluent:arrow-download-16-filled"
                                                                            ),
                                                                        ),
                                                                        dcc.Download(
                                                                            id="download_yaml"
                                                                        ),
                                                                        # dmc.Button("Upload", id="upload_yaml_file"),
                                                                        # html.A(
                                                                        #     dmc.Button(
                                                                        #         "Clear and restart",
                                                                        #         id="refresh",
                                                                        #         color="red",
                                                                        #     ),
                                                                        #     href="/download",
                                                                        # ),
                                                                    ]
                                                                ),
                                                                dmc.Group(children=[]),
                                                                dcc.Interval(
                                                                    id="interval-component",
                                                                    interval=1 * 3000,
                                                                    n_intervals=0,
                                                                ),
                                                                html.Div(
                                                                    id="batch_log"
                                                                ),
                                                            ],
                                                            align="center",
                                                        )
                                                    ],
                                                    span=6,
                                                ),
                                                dmc.GridCol(
                                                    dmc.Stack(
                                                        children=[
                                                            dmc.Space(h=20),
                                                            dcc.Markdown(instructions),
                                                            dmc.CodeHighlight(
                                                                code="# Submit to see code",
                                                                id="code_block",
                                                                language="bash",
                                                            ),
                                                        ]
                                                    ),
                                                    span=6,
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                            dmc.Space(h=40),
                            dmc.Group(
                                justify="center",
                                mt="xl",
                                children=[
                                    dmc.Button(
                                        "Back", id="back-basic-usage", variant="default"
                                    ),
                                    dmc.Button(
                                        "Next step",
                                        id="next-basic-usage",
                                        color=DEFAULT_FINK_COLORS[0],
                                    ),
                                ],
                            ),
                            dcc.Store(data=n_alert_total, id="alert-stats"),
                            dcc.Store(data="", id="log_progress"),
                            dcc.Store(data=[], id="tag_select"),
                            dcc.Store(data=[], id="blocks_select"),
                            dcc.Store(id="object-catalog"),
                            html.Div("", id="batch_id", style={"display": "none"}),
                            html.Div("", id="topic_name", style={"display": "none"}),
                        ],
                        span=10,
                    ),
                ],
            ),
        ],
    )

    return layout


@callback(
    Output("stepper-basic-usage", "active", allow_duplicate=True),
    Input("back-basic-usage", "n_clicks"),
    Input("next-basic-usage", "n_clicks"),
    State("stepper-basic-usage", "active"),
    prevent_initial_call=True,
)
def update(back, next_, current):
    button_id = ctx.triggered_id
    step = current if current is not None else 0
    if button_id == "back-basic-usage":
        step = step - 1 if step > min_step else step
    else:
        step = step + 1 if step < max_step else step
    return step


@callback(
    Output("next-basic-usage", "style"),
    Input("next-basic-usage", "n_clicks"),
    Input("stepper-basic-usage", "active"),
    prevent_initial_call=True,
)
def last_step(next, current):
    if current == max_step - 1 or current == max_step:
        return {"display": "none"}
    return {}


@callback(
    Output("back-basic-usage", "style"),
    Input("back-basic-usage", "n_clicks"),
    Input("stepper-basic-usage", "active"),
)
def first_step(back, current):
    if current == 0 or current is None:
        return {"display": "none"}
    return {}


@callback(
    Output("stepper-date", "color"),
    Input("date-range-picker", "value"),
    Input("back-basic-usage", "n_clicks"),
    Input("next-basic-usage", "n_clicks"),
)
def update_icon_date(date, back_, next_):
    button_id = ctx.triggered_id
    if button_id in ["back-basic-usage", "next-basic-usage"]:
        if date is None or date == "":
            return "red"
        return "#15284F"
    return "#15284F"
