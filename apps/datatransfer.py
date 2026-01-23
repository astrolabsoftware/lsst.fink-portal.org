# Copyright 2025 AstroLab Software
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
import textwrap

import numpy as np
import pandas as pd
import requests
import yaml
import base64
import io

from dash import Input, Output, State, html, dcc, ctx, callback, no_update, MATCH, ALL
from dash_iconify import DashIconify
from dash_autocomplete_input import AutocompleteInput

from fink_utils.xmatch.simbad import get_simbad_labels

from app import app
from apps.mining.utils import (
    estimate_alert_number_lsst,
    estimate_size_gb_lsst,
    submit_spark_job,
    upload_file_hdfs,
)
from apps.configuration import extract_configuration
from apps.utils import format_field_for_data_transfer
from apps.utils import create_datatransfer_schema_table
from apps.utils import query_and_order_statistics
from apps.api import request_api
from apps.dataclasses import fink_tags, fink_blocks


# from apps.utils import create_datatransfer_livestream_table
from apps.plotting import DEFAULT_FINK_COLORS

import datetime


args = extract_configuration("config.yml")
APIURL = args["APIURL"]

simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

tns_types = pd.read_csv("assets/tns_types.csv", header=None)[0].to_numpy()
tns_types = sorted(tns_types, key=lambda s: s.lower())

min_step = 0
max_step = 5


def date_config():
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
        id="date_config",
    )
    return tab


def date_tab():
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
            minDate="2025-09-06",
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
        if len(fields) > 1 and "Light packet" in fields:
            return "Light packet cannot be combined with other fields."
    return ""


def switch_button(nclicks, label):
    """TBD"""
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
    """TBD"""
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
    """TBD"""
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


def filter_number_tab():
    """Construct the filtering tab for the Data Transfer service

    Returns
    -------
    out: Div
    """
    schema_sources = request_api(
        endpoint="/api/v1/schema", json={"endpoint": "/api/v1/sources"}, output="json"
    )
    field_sources = list(schema_sources["Rubin original fields (r:)"].keys())

    schema_objects_static = request_api(
        endpoint="/api/v1/schema", json={"endpoint": "/api/v1/objects"}, output="json"
    )
    field_objects_static = list(
        schema_objects_static["Rubin original fields (r:)"].keys()
    )

    schema_objects_sso = request_api(
        endpoint="/api/v1/schema", json={"endpoint": "/api/v1/sso"}, output="json"
    )
    field_objects_sso = list(schema_objects_sso["Rubin original fields (r:)"].keys())

    options = html.Div(
        [
            dmc.Space(h=10),
            dmc.Text("User-defined filters", size="sm"),
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
                size="xs",
                c="gray",
            ),
            dmc.Space(h=10),
            *[
                dmc.Button(
                    children=fink_tag,
                    className="button_filter_transfer",
                    id={
                        "type": "button_filter_transfer",
                        "index": index,
                    },
                    radius="xl",
                    size="xs",
                    variant="light",
                    color="grey",
                    style={"margin": "3px"},
                    leftSection=DashIconify(icon="material-symbols:stream"),
                )
                for index, fink_tag in enumerate(list(fink_tags.keys()))
            ],
            dmc.Space(h=10),
            *[
                dmc.Button(
                    children=fink_block,
                    className="button_blocks_transfer",
                    id={
                        "type": "button_blocks_transfer",
                        "index": index,
                    },
                    radius="xl",
                    size="xs",
                    variant="light",
                    color="grey",
                    style={"margin": "3px"},
                    leftSection=DashIconify(icon="material-symbols:target"),
                )
                for index, fink_block in enumerate(list(fink_blocks.keys()))
            ],
            # dmc.Space(h=10),
            # dmc.Accordion(
            #     id="extra_cond_description",
            #     children=[
            #         dmc.AccordionItem(
            #             [
            #                 dmc.AccordionControl(
            #                     "Filters description",
            #                     icon=DashIconify(
            #                         icon="tabler:help",
            #                         color=dmc.DEFAULT_THEME["colors"]["blue"][6],
            #                         width=20,
            #                     ),
            #                 ),
            #                 dmc.AccordionPanel(create_userfilter_description()),
            #             ],
            #             value="info",
            #         ),
            #     ],
            # ),
            dmc.Space(h=20),
            dmc.Text("Write your own block", size="sm"),
            dmc.Text(
                [
                    "Similarly to the blocks above, you can write your own block. You need to specify one condition per line (SQL syntax), ending with semi-colon (see below for examples). Start typing an alert section such as ",
                    dmc.Text("diaSource., ", fw=700, inherit=True, span=True),
                    dmc.Text("diaObject., ", fw=700, inherit=True, span=True),
                    dmc.Text("mpc_orbits., ", fw=700, inherit=True, span=True),
                    "and a list will available fields will trigger. Note that you can also use the name of existing blocks, and extra function such as `flux2mag`. You can share your block by submitting the JSON file at ",
                    html.A(
                        "fink-filters",
                        href="https://github.com/astrolabsoftware/fink-filters",
                        target="_blank",
                    ),
                ],
                size="xs",
                c="gray",
            ),
            dmc.Space(h=10),
            AutocompleteInput(
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
                    "diaSource.": field_sources,
                    "ssSource.": [],
                    "mpc_orbits.": field_objects_sso,
                    "diaObject.": field_objects_static,
                    "xm.": [],
                    "clf.": [],
                    "misc.": [],
                    "pred.": [],
                },
                maxOptions=0,
                className="inputbar form-control border-0",
                quoteWhitespaces=True,
                autoFocus=True,
                ignoreCase=True,
                triggerInsideWord=False,
                matchAny=True,
                style={
                    "height": "15pc",
                    "width": "100%",
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

-- Example block 2: Using a combination of fields (at least 1 mag difference)
(diaSource.psfFlux - diaSource.templateFlux) > 20000;

-- Example block 3: Filtering on ML scores
clf.snnSnVsOthers_score > 0.5;

-- Example block 4: Only classified objects
pred.is_cataloged;
```"""),
                            ),
                        ],
                        value="info",
                    ),
                ],
            ),
        ],
    )
    tab = html.Div(
        [
            dmc.Space(h=50),
            dmc.Divider(variant="solid", label="Reduce the number of incoming alerts"),
            options,
        ],
        id="filter_number_tab",
    )
    return tab


def filter_content_tab():
    options = html.Div(
        [
            dmc.MultiSelect(
                label="Alert fields",
                description="Select all fields you like! Default is all fields.",
                placeholder="start typing...",
                id="field_select",
                data=format_field_for_data_transfer(),
                searchable=True,
                clearable=True,
            ),
            dmc.Accordion(
                id="accordion-schema",
                children=[
                    dmc.AccordionItem(
                        [
                            dmc.AccordionControl(
                                "Alert schema",
                                icon=DashIconify(
                                    icon="tabler:help",
                                    color=dmc.DEFAULT_THEME["colors"]["blue"][6],
                                    width=20,
                                ),
                            ),
                            dmc.AccordionPanel(create_datatransfer_schema_table()),
                        ],
                        value="info",
                    ),
                ],
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
):
    """Construct a JSON file and export to YAML"""
    if nclicks is None:
        return no_update, no_update

    if date_range_picker is None:
        return no_update, [
            dict(
                title="Ooops",
                id="show-notify",
                action="show",
                message="You need to specify dates at least!",
                color="red",
            )
        ]
    elif isinstance(date_range_picker, list) and None in date_range_picker:
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
    }

    if field_select is None or field_select == []:
        field_select = ["Full packet"]

    yaml_string = yaml.dump(outfile, default_flow_style=False)

    # Get the current date and time
    now = datetime.datetime.now()

    # Format the date and time
    formatted_date = now.strftime("%Y%m%d_%H%M%S")

    return dict(
        content=yaml_string, filename="datatransfer_{}.yml".format(formatted_date)
    ), [
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

    is_valid, outNotifications = validate_yaml(data)

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
    else:
        outNotifications = [
            dict(
                title="Previous configuration loaded from {}".format(filename),
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
    }

    # Check all mandatory fields are here
    for key in default_fields:
        if key not in dic.keys():
            outNotifications = [
                dict(
                    title="Missing field {} in the configuration file".format(key),
                    color="red",
                )
            ]
            return False, outNotifications

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
        return False, outNotifications

    # Check their type. None is fine (means value not set)
    for key, value in dic.items():
        if not isinstance(value, default_fields[key]) and (value is not None):
            outNotifications = [
                dict(
                    title="{} should be a {} or unset. Did you forget a hyphen (-) in your YAML?".format(
                        key, default_fields[key]
                    ),
                    color="red",
                )
            ]
            return False, outNotifications

    return True, outNotifications


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
        Input("field_select", "value"),
        Input("extra_cond", "value"),
    ],
)
def gauge_meter(
    alert_stats,
    date_range_picker,
    tag_select,
    field_select,
    extra_cond,
):
    """ """
    if date_range_picker is None:
        return (
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
        )
    elif isinstance(date_range_picker, list) and None in date_range_picker:
        return (
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
            [{"value": 0, "color": "grey", "tooltip": "0%"}],
            dmc.Text("No dates", ta="center"),
        )
    else:
        if field_select is None or field_select == []:
            field_select = ["Full packet"]

        total, count = estimate_alert_number_lsst(date_range_picker, tag_select)
        sizeGb = estimate_size_gb_lsst(field_select)
        defaultGb = 55 / 1024 / 1024

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
                    "{:,} alerts".format(int(count)),
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
                    label="Estimated number of alerts for the selected dates, including the class filter(s) and the livestream filter (if any), but not the custom filters (if any). The percentage is given with respect to the total for the selected dates ({} to {})".format(
                        *date_range_picker
                    ),
                ),
            ],
        )
        sections_number = [
            {
                "value": count / total * 100,
                "color": color,
                "tooltip": "{:.2f}%".format(count / total * 100),
            }
        ]

        label_size = dmc.Stack(
            align="center",
            children=[
                dmc.Text(
                    "{:.2f}GB".format(count * sizeGb),
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
                    label="Estimated data volume to transfer based on selected alert fields. The percentage is given with respect to the total for the selected dates ({} to {}), with the class filter(s) applied (if any).".format(
                        *date_range_picker
                    ),
                ),
            ],
        )
        sections_size = [
            {
                "value": sizeGb / defaultGb * 100,
                "color": color_size,
                "tooltip": "{:.2f}%".format(sizeGb / defaultGb * 100),
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
fink_datatransfer \\
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
):
    """Submit a job to the Apache Spark cluster via Livy"""
    if n_clicks:
        # define unique topic name
        d = datetime.datetime.utcnow()

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

        # get the job args
        job_args = [
            f"-startDate={date_range_picker[0]}",
            f"-stopDate={date_range_picker[1]}",
            f"-basePath={basepath}",
            f"-topic_name={topic_name}",
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

#### 2. DOwnload your configuration file

Hit the `Download configuration` button to export your configuration as a YAML file. This way you can upload later
to re-submit the same job.

#### 3. Register

To retrieve the data, you need to get an account. See [fink-client](https://github.com/astrolabsoftware/fink-client) and
the [documentation](https://fink-broker.readthedocs.io/en/latest/services/data_transfer) for more information.

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
    We provide access to alert data from ZTF (over 200 million alerts as of 2025), from the DESC/ELASTiCC data
    challenge (over 50 million alerts), and soon from the Rubin Observatory.

    Follow these steps: (1) select observing nights, (2) apply filters to focus on relevant alerts and reduce the
    volume of data, and (3) select only the relevant alert fields for your analysis. Note that we provide estimates on
    the number of alerts to transfer and the data volume.

    Once ready, submit your job on the Fink Apache Spark and Kafka clusters to retrieve your data wherever you like.
    To access the data, you need to create an account. See the [fink-client](https://github.com/astrolabsoftware/fink-client) and
    the [documentation](https://fink-broker.readthedocs.io/en/latest/services/data_transfer) for more information. The data is available
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
                                    dmc.RingProgress(
                                        roundCaps=True,
                                        sections=[{"value": 0, "color": "grey"}],
                                        size=250,
                                        thickness=20,
                                        label="",
                                        id="gauge_alert_number",
                                    ),
                                    dmc.RingProgress(
                                        roundCaps=True,
                                        sections=[{"value": 0, "color": "grey"}],
                                        size=250,
                                        thickness=20,
                                        label="",
                                        id="gauge_alert_size",
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
                                        children=date_config(),
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
                                    dmc.Button("Next step", id="next-basic-usage"),
                                ],
                            ),
                            dcc.Store(data=n_alert_total, id="alert-stats"),
                            dcc.Store(data="", id="log_progress"),
                            dcc.Store(data=[], id="tag_select"),
                            dcc.Store(data=[], id="blocks_select"),
                            html.Div("", id="batch_id", style={"display": "none"}),
                            html.Div("", id="topic_name", style={"display": "none"}),
                        ],
                        span=9,
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
