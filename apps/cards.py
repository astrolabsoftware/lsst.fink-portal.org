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
"""Various cards in the portal"""

import io
from dash import html, dcc, Output, Input, dash_table, no_update

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc


import numpy as np
import pandas as pd

from astropy.coordinates import SkyCoord
from astropy.time import Time


from apps.api import request_api
from apps.utils import class_colors
from apps.utils import convert_time
from apps.utils import loading
from apps.utils import cats_type_converter

from apps.utils import get_first_value, is_row_static_or_moving
from apps.utils import demarkdownify_objectid
from apps.utils import create_button_for_external_conesearch
from apps.plotting import make_modal_stamps
from apps.helpers import help_popover, lc_help
from dash_iconify import DashIconify

# Callbacks
from apps.plotting import draw_lightcurve  # noqa: F401
from apps.plotting import draw_cutouts  # noqa: F401
from apps.plotting import CONFIG_PLOT
from apps.plotting import DEFAULT_FINK_COLORS

from apps.configuration import extract_configuration

from app import app

import rocks

args = extract_configuration("config.yml")
APIURL = args["APIURL"]

BAD_VALUES = [np.nan, None, "Fail", "nan", ""]


def card_search_result(row, i):
    """Display single item for search results"""
    badges = []

    main_id, is_sso = is_row_static_or_moving(row)
    diasourceid = row["r:diaSourceId"]

    cdsxmatch = row.get("f:crossmatches_simbad_otype")
    if cdsxmatch not in BAD_VALUES:
        badges.append(
            make_badge(
                f"SIMBAD: {cdsxmatch}",
                variant="outline",
                color=class_colors["Simbad"],
                tooltip="SIMBAD classification",
            ),
        )

    badges += generate_generic_badges(row, variant="outline")

    coords = SkyCoord(row["r:ra"], row["r:dec"], unit="deg")

    if "v:separation_degree" in row:
        corner_str = "{:.1f}''".format(row["v:separation_degree"] * 3600)
    else:
        corner_str = f"#{i!s}"

    if not is_sso:
        second_card = html.Div(
            className="second-content",
            children=[
                html.Div(
                    className="container",
                    children=[
                        html.Div(
                            className="canvas",
                            children=[
                                html.Div(
                                    id="card2",
                                    children=[
                                        html.Div(
                                            className="card-content",
                                            children=[
                                                html.Div(
                                                    children=[
                                                        dmc.Space(h=10),
                                                        dmc.Text(
                                                            "Last diaSourceId",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            str(diasourceid),
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=2),
                                                        dmc.Text(
                                                            "Equatorial",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            "{} {}".format(
                                                                coords.ra.to_string(
                                                                    pad=True,
                                                                    unit="hour",
                                                                    precision=2,
                                                                    sep=" ",
                                                                ),
                                                                coords.dec.to_string(
                                                                    pad=True,
                                                                    unit="deg",
                                                                    alwayssign=True,
                                                                    precision=1,
                                                                    sep=" ",
                                                                ),
                                                            ),
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=2),
                                                        dmc.Text(
                                                            "Galactic",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            coords.galactic.to_string(
                                                                style="decimal"
                                                            ),
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=2),
                                                    ],
                                                    style={"zIndex": 10000000},
                                                ),
                                                dmc.Space(h=10),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
    else:
        # FIXME: replace with MPCORB values when they will be up
        sso_data = rocks.Rock(row["r:mpcDesignation"], skip_id_check=False)
        semi_major = sso_data.a.value
        eccentricity = sso_data.e.value
        inclination = sso_data.i.value
        inclination_unit = sso_data.i.unit

        ref_epoch_jd = sso_data.parameters.dynamical.orbital_elements.ref_epoch.value
        if ref_epoch_jd is not None:
            ref_epoch = Time(ref_epoch_jd, format="jd").strftime("%Y-%m-%d")
        else:
            ref_epoch = None
        second_card = html.Div(
            className="second-content",
            children=[
                html.Div(
                    className="container",
                    children=[
                        html.Div(
                            className="canvas",
                            children=[
                                html.Div(
                                    id="card2",
                                    children=[
                                        html.Div(
                                            className="card-content",
                                            children=[
                                                html.Div(
                                                    children=[
                                                        dmc.Space(h=10),
                                                        dmc.Text(
                                                            "Name",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            sso_data.name,
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=5),
                                                        dmc.Text(
                                                            "Class",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            sso_data.class_,
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=5),
                                                        dmc.Text(
                                                            "ssObjectId",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            demarkdownify_objectid(
                                                                str(
                                                                    row.get(
                                                                        "r:ssObjectId",
                                                                        0,
                                                                    )
                                                                )
                                                            ),
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=5),
                                                        dmc.Text(
                                                            "Orbital elements",
                                                            className="subtitle3",
                                                        ),
                                                        dmc.Text(
                                                            "a={}, e={}, incl={}{}, t0={}".format(
                                                                semi_major,
                                                                eccentricity,
                                                                inclination,
                                                                inclination_unit,
                                                                ref_epoch,
                                                            ),
                                                            className="subtitle2",
                                                        ),
                                                        dmc.Space(h=5),
                                                    ],
                                                    style={"zIndex": 10000000},
                                                ),
                                                dmc.Space(h=10),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

    item = dbc.Card(
        [
            dbc.CardHeader(
                dmc.Group(
                    [
                        html.A(
                            dmc.Text(
                                f"{main_id}", style={"fontWeight": 700, "fontSize": 20}
                            ),
                            href=f"/{main_id}",
                            target="_blank",
                            className="text-decoration-none",
                        ),
                        # dmc.Space(w="sm"),
                        dmc.Space(w="sm"),
                        dbc.Popover(
                            "Per-band evolution over the last two observation nights. Intra-night measurements are averaged before comparison.",
                            target={
                                "type": "indicator",
                                "main_id": str(main_id),
                                "is_sso": is_sso,
                                "index": i,
                            },
                            body=True,
                            trigger="hover",
                            placement="top",
                        ),
                        html.Div(
                            className="indicator",
                            id={
                                "type": "indicator",
                                "main_id": str(main_id),
                                "is_sso": is_sso,
                                "index": i,
                            },
                        ),
                        dmc.Space(w="sm"),
                        html.Div(
                            className="indicator",
                            id={
                                "type": "flags",
                                "main_id": str(main_id),
                                "is_sso": is_sso,
                                "index": i,
                            },
                        ),
                        dmc.Space(w="sm"),
                        *badges,
                    ],
                    gap=3,
                ),
            ),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            html.Div(
                                className="card-flip",
                                id="card-flip",
                                children=[
                                    html.Div(
                                        className="first-content",
                                        children=[
                                            html.Div(
                                                className="container",
                                                children=[
                                                    html.Div(
                                                        children=[
                                                            html.Div(
                                                                id="card",
                                                                children=[
                                                                    html.Div(
                                                                        className="card-content",
                                                                        children=[
                                                                            dbc.Col(
                                                                                dmc.Skeleton(
                                                                                    style={
                                                                                        "width": "12pc",
                                                                                        "height": "12pc",
                                                                                    },
                                                                                ),
                                                                                id={
                                                                                    "type": "search_results_cutouts",
                                                                                    "diaSourceId": str(
                                                                                        diasourceid
                                                                                    ),
                                                                                    "index": i,
                                                                                },
                                                                                width="auto",
                                                                            ),
                                                                            html.Div(
                                                                                className="subtitle",
                                                                                children=[
                                                                                    html.Span(
                                                                                        id={
                                                                                            "type": "cutout-size",
                                                                                            "diaSourceId": str(
                                                                                                diasourceid
                                                                                            ),
                                                                                            "index": i,
                                                                                        },
                                                                                    ),
                                                                                ],
                                                                            ),
                                                                            html.Div(
                                                                                className="corner-elements",
                                                                                children=[
                                                                                    html.Span(),
                                                                                    html.Span(),
                                                                                ],
                                                                            ),
                                                                        ],
                                                                    ),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    second_card,
                                ],
                            ),
                            dbc.Col(
                                dmc.Skeleton(
                                    style={
                                        "width": "100%",
                                        "height": "15pc",
                                    },
                                ),
                                id={
                                    "type": "search_results_lightcurve",
                                    "main_id": str(main_id),
                                    "is_sso": is_sso,
                                    "index": i,
                                },
                                xs=12,
                                md=True,
                            ),
                        ],
                        justify="start",
                        className="g-2",
                    ),
                    # Upper right corner badge
                    dbc.Badge(
                        corner_str,
                        color="light",
                        pill=True,
                        text_color="dark",
                        className="position-absolute top-0 start-100 translate-middle border",
                    ),
                ],
            ),
            # dbc.CardFooter("This is the footer"),
        ],
        color="light",
        className="mb-2 border-1 rounded-1 box-shadow",
        outline=True,
    )

    return item


def make_badge(text="", color=None, outline=None, tooltip=None, **kwargs):
    """Make badges for card view"""
    style = kwargs.pop("style", {})
    if outline is not None:
        style["border-color"] = outline

    badge = dmc.Badge(
        text,
        color=color,
        variant=kwargs.pop("variant", "dot"),
        style=style,
        size="sm",
        **kwargs,
    )

    if tooltip is not None:
        badge = dmc.Tooltip(
            badge,
            label=tooltip,
            color=outline if outline is not None else color,
            className="d-inline",
            multiline=True,
        )

    return badge


def generate_generic_badges(row, variant="dot"):
    """Operates on first row of a DataFrame, or directly on Series from pdf.iterrow()"""
    if isinstance(row, pd.DataFrame):
        # for VSX, aggregate values
        vsx_label = get_multi_labels(
            row,
            "f:crossmatches_vizier:B/vsx/vsx_Type",
            default=None,
            to_avoid=BAD_VALUES,
        )
        if vsx_label != row.loc[0].get("f:crossmatches_vizier:B/vsx/vsx_Type"):
            row["f:crossmatches_vizier:B/vsx/vsx_Type"] = vsx_label

        # Get first row from DataFrame
        row = row.loc[0]

    badges = []

    extendedness = row.get("r:extendedness", 0.0)
    if extendedness is not None and extendedness > 0.9:
        badges.append(
            make_badge(
                "EXT",
                variant="outline",
                color="grey",
                tooltip="Extendedness of the source above 0.9",
            )
        )

    if row.get("r:glint_trail", False):
        badges.append(
            make_badge(
                "Glint trail",
                variant="outline",
                color="grey",
                tooltip="The last source is part of a glint trail",
            )
        )

    # SSO
    ssnamenr = row.get("f:sso_name")
    if ssnamenr and ssnamenr != "null":
        badges.append(
            make_badge(
                f"SSO: {ssnamenr}",
                variant=variant,
                color="yellow",
                tooltip="Solar System object name by quaero",
            ),
        )

    tracklet = row.get("f:tracklet")
    if tracklet and tracklet != "null":
        badges.append(
            make_badge(
                f"{tracklet}",
                variant=variant,
                color="violet",
                tooltip="Fink detected tracklet",
            ),
        )

    gcvs = row.get("f:crossmatches_gcvs_type")
    if gcvs not in BAD_VALUES:
        if ~np.isnan(gcvs):
            badges.append(
                make_badge(
                    f"GCVS: {gcvs}",
                    variant=variant,
                    color=class_colors["Simbad"],
                    tooltip="General Catalogue of Variable Stars classification",
                ),
            )

    vsx = row.get("f:crossmatches_vizier:B/vsx/vsx_Type")
    if vsx not in BAD_VALUES:
        if ~np.isnan(vsx):
            badges.append(
                make_badge(
                    f"VSX: {vsx}",
                    variant=variant,
                    color=class_colors["Simbad"],
                    tooltip="AAVSO VSX classification",
                ),
            )

    hsp = row.get("f:crossmatches_x3hsp_type")
    if hsp not in BAD_VALUES:
        if ~np.isnan(hsp):
            badges.append(
                make_badge(
                    f"3HSP: {hsp}",
                    variant=variant,
                    color=class_colors["Simbad"],
                    tooltip="High synchrotron peaked blazars",
                ),
            )

    lac = row.get("f:crossmatches_x4lac_type")
    if lac not in BAD_VALUES:
        if ~np.isnan(lac):
            badges.append(
                make_badge(
                    f"4LAC: {lac}",
                    variant=variant,
                    color=class_colors["Simbad"],
                    tooltip="",
                ),
            )

    gaianame = row.get("f:crossmatches_vizier:I/355/gaiadr3_DR3Name")
    if gaianame not in BAD_VALUES and not pd.isnull(gaianame):
        badges.append(
            make_badge(
                gaianame,
                variant=variant,
                color="teal",
                tooltip="Gaia DR3 catalogue",
            ),
        )

    return badges


def get_multi_labels(pdf, colname, default=None, to_avoid=None):
    """Get aggregation of unique labels from given column of a DataFrame, or default value if not exists.

    Parameters
    ----------
    pdf: pd.DataFrame
        Fink Pandas DataFrame
    colname: str
        Column name
    default: NoneType, optional
        Default value to assign if the
        column is not defined in the DataFrame schema
    to_avoid: NoneType or list, optional
        If provided, list of labels to avoid

    Returns
    -------
    out: str

    Examples
    --------
    >>> pdf = pd.DataFrame({"a": ["nan", "AM", "AM", "toto"]})
    >>> get_multi_labels(pdf, "a", to_avoid=["nan"])
    'AM/toto'
    """
    if colname in pdf.columns:
        if to_avoid is None:
            to_avoid = []

        if len(np.unique(pdf[colname])) == 1:
            return pdf.loc[0, colname]

        # Case for multilabels
        out = "/".join([
            i
            for i in np.unique(pdf[colname].values)
            if not i.startswith("Fail") and i not in to_avoid
        ])
        return out
    else:
        return default


def card_lightcurve_summary(diaObjectId):
    """Add a card containing the lightcurve

    Returns
    -------
    card: dbc.Card
        Card with the lightcurve drawn inside
    """
    CONFIG_PLOT["toImageButtonOptions"]["filename"] = str(diaObjectId)

    accordions = dmc.Accordion(
        multiple=True,
        chevronPosition="left",
        # variant="contained",
        disableChevronRotation=False,
        radius="xl",
        chevronSize=20,
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Add other datasets",
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack([
                            dmc.Group(
                                [
                                    dmc.Button(
                                        "Add Fink/ZTF alert photometry",
                                        id={
                                            "type": "lightcurve_request_ztf_fink",
                                            "name": "main",
                                        },
                                        variant="outline",
                                        color="gray",
                                        radius="xl",
                                        size="xs",
                                    ),
                                    dmc.Button(
                                        "ZTF DR photometry",
                                        id={
                                            "type": "lightcurve_request_release",
                                            "name": "main",
                                        },
                                        variant="outline",
                                        color="gray",
                                        radius="xl",
                                        size="xs",
                                    ),
                                ],
                                justify="center",
                                align="center",
                            ),
                        ]),
                    ),
                ],
                value="datasets",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Help",
                    ),
                    dmc.AccordionPanel(
                        dcc.Markdown(
                            lc_help,
                            mathjax=True,
                        ),
                    ),
                ],
                value="help",
            ),
        ],
    )

    # FIXME: a creuser l'idee d'un radar plot
    # data = [
    #     {"label": "SN like", "prob": 0.9},
    #     {"label": "Periodic", "prob": 0.1},
    #     {"label": "Non-periodic", "prob": 0.2},
    #     {"label": "Long", "prob": 0.1},
    #     {"label": "Fast", "prob": 0.3},
    # ]

    # radar = dmc.RadarChart(
    #     # h=300,
    #     data=data,
    #     dataKey="label",
    #     withPolarRadiusAxis=True,
    #     series=[{"name": "prob", "color": "blue.4", "opacity": 0.2}],
    #     style={
    #         "width": "100%",
    #         "height": "100%",
    #     },
    # )

    card = html.Div(
        [
            dmc.Group([
                dbc.Popover(
                    "Per-band evolution over the last two observation nights. Intra-night measurements are averaged before comparison.",
                    target="indicator_lc",
                    body=True,
                    trigger="hover",
                    placement="top",
                ),
                html.Div(id="indicator_lc", className="indicator"),
                html.Div(id="flags_lc", className="indicator"),
            ]),
            dmc.Space(h=15),
            loading(
                dcc.Graph(
                    id="lightcurve_object_page",
                    style={
                        "width": "100%",
                        "height": "35pc",
                    },
                    config=CONFIG_PLOT,
                    className="mb-2 rounded-5",
                ),
            ),
            accordions,
            # dmc.Grid(
            #     children=[
            #         dmc.GridCol(accordions, span=6),
            #         dmc.GridCol(radar, span=6),
            #     ]
            # ),
        ],
    )
    return card


def card_id(pdf):
    """Add a card containing basic alert data"""
    diaObjectid = pdf["r:diaObjectId"].to_numpy()[0]
    ra0 = pdf["r:ra"].to_numpy()[0]
    dec0 = pdf["r:dec"].to_numpy()[0]

    python_download = f"""import requests
import pandas as pd
import io

# get lightcurve data for {diaObjectid}
r = requests.post(
    '{APIURL}/api/v1/sources',
    json={{
        'diaObjectId': '{diaObjectid}',
        'output-format': 'json'
    }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))"""

    curl_download = f"""
curl -H "Content-Type: application/json" -X POST \\
    -d '{{"diaObjectid":"{diaObjectid}", "output-format":"csv"}}' \\
    {APIURL}/api/v1/sources \\
    -o {diaObjectid}.csv
    """

    download_tab = dmc.Tabs(
        [
            dmc.TabsList(
                [
                    dmc.TabsTab("Python", value="Python"),
                    dmc.TabsTab("Curl", value="Curl"),
                ],
            ),
            dmc.TabsPanel(
                dmc.CodeHighlight(code=python_download, language="python"),
                value="Python",
            ),
            dmc.TabsPanel(
                children=dmc.CodeHighlight(code=curl_download, language="bash"),
                value="Curl",
            ),
        ],
        color="red",
        value="Python",
    )

    card = dmc.Accordion(
        multiple=True,
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Alert cutouts",
                        icon=[
                            DashIconify(
                                icon="tabler:flare",
                                color=DEFAULT_FINK_COLORS[0],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            loading(
                                dbc.Row(
                                    dmc.Skeleton(
                                        style={
                                            "width": "100%",
                                            "aspect-ratio": "3/1",
                                        }
                                    ),
                                    id="stamps",
                                    justify="around",
                                    className="g-0",
                                ),
                            ),
                            dmc.Space(h=10),
                            *make_modal_stamps(pdf),
                        ],
                    ),
                ],
                value="stamps",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Alert content",
                        icon=[
                            DashIconify(
                                icon="tabler:file-description",
                                color=DEFAULT_FINK_COLORS[1],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        html.Div([], id="alert_table"),
                    ),
                ],
                value="last_alert",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Coordinates",
                        icon=[
                            DashIconify(
                                icon="tabler:target",
                                color=DEFAULT_FINK_COLORS[2],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            html.Div(id="coordinates"),
                            dmc.Center(
                                dmc.RadioGroup(
                                    id="coordinates_chips",
                                    value="EQU",
                                    size="sm",
                                    children=dmc.Group([
                                        dmc.Radio(k, value=k, color="orange")
                                        for k in ["EQU", "GAL"]
                                    ]),
                                ),
                            ),
                        ],
                    ),
                ],
                value="coordinates",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Download data",
                        icon=[
                            DashIconify(
                                icon="tabler:database-export",
                                color=DEFAULT_FINK_COLORS[3],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        html.Div(
                            [
                                dmc.Group(
                                    [
                                        dmc.Button(
                                            "JSON",
                                            id="download_json",
                                            variant="outline",
                                            color="indigo",
                                            size="compact-sm",
                                            leftSection=DashIconify(
                                                icon="mdi:code-json"
                                            ),
                                        ),
                                        dmc.Button(
                                            "CSV",
                                            id="download_csv",
                                            variant="outline",
                                            color="indigo",
                                            size="compact-sm",
                                            leftSection=DashIconify(
                                                icon="mdi:file-csv-outline"
                                            ),
                                        ),
                                        dmc.Button(
                                            "VOTable",
                                            id="download_votable",
                                            variant="outline",
                                            color="indigo",
                                            size="compact-sm",
                                            leftSection=DashIconify(icon="mdi:xml"),
                                        ),
                                        help_popover(
                                            [
                                                dcc.Markdown(
                                                    "You may also download the data programmatically."
                                                ),
                                                download_tab,
                                                dcc.Markdown(
                                                    f"See {APIURL} for more options"
                                                ),
                                            ],
                                            "help_download",
                                            trigger=dmc.Button(
                                                "Code",
                                                id="help_download",
                                                variant="outline",
                                                color="indigo",
                                                size="compact-sm",
                                                leftSection=DashIconify(icon="mdi:api"),
                                            ),
                                        ),
                                        html.Div(
                                            str(diaObjectid),
                                            id="download_objectid",
                                            className="d-none",
                                        ),
                                        html.Div(
                                            APIURL,
                                            id="download_apiurl",
                                            className="d-none",
                                        ),
                                    ],
                                    align="center",
                                    justify="center",
                                    gap="xs",
                                ),
                            ],
                        ),
                    ),
                ],
                value="api",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Neighbourhood",
                        icon=[
                            DashIconify(
                                icon="tabler:external-link",
                                color=DEFAULT_FINK_COLORS[4],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(
                            [
                                # card_neighbourhood(pdf),
                                *create_external_conesearches(ra0, dec0),
                            ],
                            align="center",
                        ),
                    ),
                ],
                value="external",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Other brokers",
                        icon=[
                            DashIconify(
                                icon="tabler:atom-2",
                                color=DEFAULT_FINK_COLORS[5],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(
                            [
                                create_external_links_brokers(diaObjectid),
                            ],
                            align="center",
                        ),
                    ),
                ],
                value="external_brokers",
            ),
            # dmc.AccordionItem(
            #     [
            #         dmc.AccordionControl(
            #             "Share",
            #             icon=[
            #                 DashIconify(
            #                     icon="tabler:share",
            #                     color=dmc.DEFAULT_THEME["colors"]["gray"][6],
            #                     width=20,
            #                 ),
            #             ],
            #         ),
            #         dmc.AccordionPanel(
            #             [
            #                 dmc.Center(
            #                     html.Div(id="qrcode"),
            #                     style={"width": "100%", "height": "200"},
            #                 ),
            #             ],
            #         ),
            #     ],
            #     value="qr",
            # ),
        ],
        value=["stamps"],
        styles={"content": {"padding": "5px"}},
    )

    return card


@app.callback(
    Output("alert_table", "children"),
    [
        Input("object-data", "data"),
        Input("lightcurve_object_page", "clickData"),
    ],
    prevent_initial_call=True,
)
def alert_properties(object_data, clickData):
    pdf_ = pd.read_json(io.StringIO(object_data))

    if clickData is not None:
        time0 = clickData["points"][0]["x"]
        # Round to avoid numerical precision issues
        mjds = pdf_["r:midpointMjdTai"].apply(lambda x: np.round(x, 3)).to_numpy()
        mjd0 = np.round(Time(time0, format="iso").mjd, 3)
        if mjd0 in mjds:
            pdf_ = pdf_[mjds == mjd0]
        else:
            return no_update

    pdf = pdf_.head(1)
    print(pdf)
    pdf = pd.DataFrame({"Name": pdf.columns, "Value": pdf.to_numpy()[0]})
    columns = [
        {
            "id": c,
            "name": c,
            # 'hideable': True,
            "presentation": "input",
            "type": "text" if c == "Name" else "numeric",
            "format": dash_table.Format.Format(precision=8),
        }
        for c in pdf.columns
    ]
    data = pdf.to_dict("records")
    table = dash_table.DataTable(
        data=data,
        columns=columns,
        id="result_table_alert",
        # page_size=10,
        page_action="none",
        style_as_list_view=True,
        filter_action="native",
        markdown_options={"link_target": "_blank"},
        # fixed_columns={'headers': True},#, 'data': 1},
        persistence=True,
        persistence_type="memory",
        style_data={
            "backgroundColor": "rgb(248, 248, 248, 1.0)",
        },
        style_table={"maxWidth": "100%", "maxHeight": "300px", "overflow": "auto"},
        style_cell={
            "padding": "5px",
            "textAlign": "left",
            "overflow": "hidden",
            "overflow-wrap": "anywhere",
            "max-width": "100%",
            "font-family": "sans-serif",
            "fontSize": 14,
        },
        style_filter={"backgroundColor": "rgb(238, 238, 238, 1.0)"},
        style_filter_conditional=[
            {
                "if": {"column_id": "Value"},
                "textAlign": "left",
            },
        ],
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgb(248, 248, 248, 1.0)",
            },
            {
                "if": {"column_id": "Name"},
                "backgroundColor": "rgb(240, 240, 240, 1.0)",
                "white-space": "normal",
                "min-width": "8pc",
            },
            {
                "if": {"column_id": "Value"},
                "white-space": "normal",
                "min-width": "8pc",
            },
        ],
        style_header={
            "backgroundColor": "rgb(230, 230, 230, 1.0)",
            "fontWeight": "bold",
            "textAlign": "center",
        },
        # Align the text in Markdown cells
        css=[dict(selector="p", rule="margin: 0; text-align: left")],
    )
    return table


@app.callback(
    Output("card_id_left", "children"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def card_id_left(object_data):
    """Add a card containing basic alert data"""
    pdf = pd.read_json(
        io.StringIO(object_data),
        dtype={"r:diaObjectId": np.int64, "r:diaSourceId": np.int64},
    )

    diaObjectid = pdf["r:diaObjectId"].to_numpy()[0]

    # FIXME
    date_end = convert_time(
        pdf["r:midpointMjdTai"].to_numpy()[0], format_in="mjd", format_out="iso"
    )
    discovery_date = convert_time(
        pdf["r:midpointMjdTai"].to_numpy()[-1], format_in="mjd", format_out="iso"
    )

    # FIXME: what to do with badges?
    # badges = []
    # cdsxmatches = np.unique(pdf["f:crossmatches_simbad_otype"])
    # for cdsxmatch in cdsxmatches:
    #     if cdsxmatch not in BAD_VALUES:
    #         badges.append(
    #             make_badge(
    #                 f"SIMBAD: {cdsxmatch}",
    #                 variant="dot",
    #                 color=class_colors["Simbad"],
    #                 tooltip="SIMBAD classification",
    #             ),
    #         )

    # tns_badge = generate_tns_badge(get_first_value(pdf, "r:diaObjectId"))
    # if tns_badge is not None:
    #     badges.append(tns_badge)

    # badges += generate_generic_badges(pdf, variant="dot")

    coords = SkyCoord(
        get_first_value(pdf, "r:ra"), get_first_value(pdf, "r:dec"), unit="deg"
    )

    cats_mapping = cats_type_converter()
    cats_class = cats_mapping[pdf["f:classifiers_cats_class"].to_numpy()[0]]
    simbad_class = pdf["f:crossmatches_simbad_otype"].to_numpy()[0]
    if pd.isnull(simbad_class) or simbad_class in BAD_VALUES:
        simbad_class = "N/A"

    tns_class = pdf["f:crossmatches_tns_type"].to_numpy()[0]
    if pd.isnull(tns_class) or tns_class in BAD_VALUES:
        tns_class = "N/A"

    card = html.Div(
        className="card_id_left",
        children=[
            # Top section
            html.Div(
                className="top-section",
                children=[
                    html.Div(
                        html.Div(str(diaObjectid), className="title-card_id_left"),
                        className="border2",
                    ),
                    html.Div(
                        className="bottom-section",
                        children=[
                            html.Div(
                                className="row row1",
                                children=[
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=discovery_date[:10],
                                                className="big-text",
                                            ),
                                            html.Span(
                                                children="Discovery",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=date_end[:10],
                                                className="big-text",
                                            ),
                                            html.Span(
                                                children="Last detection",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="row row1",
                                children=[
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=len(pdf), className="big-text"
                                            ),
                                            html.Span(
                                                children="Detections",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children="{:.2f}".format(
                                                    pdf["r:snr"].to_numpy()[0]
                                                ),
                                                className="big-text",
                                            ),
                                            html.Span(
                                                children="Last SNR",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="row row1",
                                children=[
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=simbad_class,
                                                className="big-text",
                                            ),
                                            html.Span(
                                                children="SIMBAD",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=tns_class, className="big-text"
                                            ),
                                            html.Span(
                                                children="TNS",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="row row1",
                                children=[
                                    html.Div(
                                        className="item",
                                        children=[
                                            html.Span(
                                                children=cats_class,
                                                className="big-text",
                                            ),
                                            html.Span(
                                                children="CATS",
                                                className="regular-text",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            # Bottom section
            html.Div(
                className="bottom-section",
                children=[
                    html.Div(
                        className="row",
                        children=[
                            # card_aladin,
                            # dmc.Space(h=20),
                            html.Div(
                                className="item",
                                children=[
                                    html.Span(
                                        children=[
                                            html.Div(
                                                "{} {}".format(
                                                    coords.ra.to_string(
                                                        pad=True,
                                                        unit="hour",
                                                        precision=2,
                                                        sep=" ",
                                                    ),
                                                    coords.dec.to_string(
                                                        pad=True,
                                                        unit="deg",
                                                        alwayssign=True,
                                                        precision=1,
                                                        sep=" ",
                                                    ),
                                                ),
                                                id="coord_card",
                                                className="big-text",
                                                style={"color": "white"},
                                            ),
                                            dcc.Clipboard(
                                                target_id="coord_card",
                                                title="Copy to clipboard",
                                                style={"color": "gray"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            ),
        ],
    )
    return html.Div(card, style={"padding-top": "10px"})


def generate_tns_badge(oid):
    """Generate TNS badge

    Parameters
    ----------
    oid: str
        LSST object ID

    Returns
    -------
    badge: dmc.Badge or None
    """
    r = request_api(
        "/api/v1/resolver",
        json={
            "resolver": "tns",
            "name": str(oid),
            "reverse": True,
        },
        output="json",
    )

    if r != []:
        entries = [i["d:fullname"] for i in r]
        if len(entries) > 1:
            types = [i.get("type", "") for i in r]
            # Check if object is classified
            try:
                index = [~i.startswith("AT") for i in types].index(True)
            except ValueError:
                # no classification in list -- take the last one (most recent)
                index = -1
        else:
            index = 0

        payload = r[index]

        if payload["d:type"] != "nan":
            msg = "TNS: {} ({})".format(payload["d:fullname"], payload["d:type"])
        else:
            msg = "TNS: {}".format(payload["d:fullname"])
        badge = make_badge(
            msg,
            color="red",
            tooltip="Transient Name Server classification",
        )
    else:
        badge = None

    return badge


def generate_metadata_name(oid):
    """Generate name from metadata

    Parameters
    ----------
    oid: str
        LSST object ID

    Returns
    -------
    name: str
    """
    r = request_api(
        "/api/v1/metadata",
        json={
            "diaObjectId": str(oid),
        },
        method="GET",
        output="json",
    )

    if r != []:
        name = r[0]["d:internal_name"]
    else:
        name = None

    return name


# def card_explanation_xmatch():
#     """Explain how xmatch works"""
#     msg = """
#     The Fink Xmatch service allows you to cross-match your catalog data with
#     all Fink alert data processed so far (more than 60 million alerts, from ZTF). Just drag and drop
#     a csv file containing at least position columns named `RA` and `Dec`, and a
#     column containing ids named `ID` (could be string, integer, ... anything to identify your objects). Required column names are case insensitive. The catalog can also contained
#     other columns that will be displayed.

#     The xmatch service will perform a conesearch around the positions with a fix radius of 1.5 arcseconds.
#     The initializer for RA/Dec is very flexible and supports inputs provided in a number of convenient formats.
#     The following ways of declaring positions are all equivalent:

#     * 271.3914265, 45.2545134
#     * 271d23m29.1354s, 45d15m16.2482s
#     * 18h05m33.9424s, +45d15m16.2482s
#     * 18 05 33.9424, +45 15 16.2482
#     * 18:05:33.9424, 45:15:16.2482

#     The final table will contain the original columns of your catalog for all rows matching a Fink object, with two new columns:

#     * `objectId`: clickable ZTF objectId.
#     * `classification`: the class of the last alert received for this object, inferred by Fink.

#     This service is still experimental, and your feedback is welcome. Note that the system will limit to the first 1000 rows of your file (or 5MB max) for the moment.
#     Contact us by opening an [issue](https://github.com/astrolabsoftware/fink-science-portal/issues) if you need other file formats or encounter problems.
#     """
#     card = dbc.Card(
#         dbc.CardBody(
#             dcc.Markdown(msg),
#         ),
#     )
#     return card


def create_external_conesearches(ra0, dec0):
    """Create two rows of buttons to trigger external conesearch

    Parameters
    ----------
    ra0: float
        RA for the conesearch center
    dec0: float
        DEC for the conesearch center
    """
    width = 3
    buttons = [
        dbc.Row(
            [
                create_button_for_external_conesearch(
                    kind="tns", ra0=ra0, dec0=dec0, radius=5, width=width
                ),
                create_button_for_external_conesearch(
                    kind="simbad", ra0=ra0, dec0=dec0, radius=0.08, width=width
                ),
                create_button_for_external_conesearch(
                    kind="snad", ra0=ra0, dec0=dec0, radius=5, width=width
                ),
                create_button_for_external_conesearch(
                    kind="datacentral", ra0=ra0, dec0=dec0, radius=2.0, width=width
                ),
            ],
            justify="around",
        ),
        dbc.Row(
            [
                create_button_for_external_conesearch(
                    kind="ned", ra0=ra0, dec0=dec0, radius=1.0, width=width
                ),
                create_button_for_external_conesearch(
                    kind="sdss", ra0=ra0, dec0=dec0, width=width
                ),
                create_button_for_external_conesearch(
                    kind="asas-sn", ra0=ra0, dec0=dec0, radius=0.5, width=width
                ),
                create_button_for_external_conesearch(
                    kind="vsx", ra0=ra0, dec0=dec0, radius=0.1, width=width
                ),
            ],
            justify="around",
        ),
    ]
    return buttons


def create_external_links_brokers(objectId):
    """ """
    buttons = dbc.Row(
        [
            dbc.Col(
                dbc.Button(
                    className="btn btn-default btn-circle btn-lg zoom btn-image",
                    style={"background-image": "url(/assets/buttons/logo_alerce.png)"},
                    color="dark",
                    outline=True,
                    id="alerce",
                    title="ALeRCE",
                    target="_blank",
                    href=f"https://alerce.online/object/{objectId}",
                ),
            ),
            # dbc.Col(
            #     dbc.Button(
            #         className="btn btn-default btn-circle btn-lg zoom btn-image",
            #         style={"background-image": "url(/assets/buttons/logo_antares.png)"},
            #         color="dark",
            #         outline=True,
            #         id="antares",
            #         title="ANTARES",
            #         target="_blank",
            #         href=f"https://antares.noirlab.edu/loci?query=%7B%22currentPage%22%3A1,%22filters%22%3A%5B%7B%22type%22%3A%22query_string%22,%22field%22%3A%7B%22query%22%3A%22%2a{objectId}%2a%22,%22fields%22%3A%5B%22properties.ztf_object_id%22,%22locus_id%22%5D%7D,%22value%22%3Anull,%22text%22%3A%22ID%20Lookup%3A%20ZTF21abfmbix%22%7D%5D,%22sortBy%22%3A%22properties.newest_alert_observation_time%22,%22sortDesc%22%3Atrue,%22perPage%22%3A25%7D",
            #     ),
            # ),
            dbc.Col(
                dbc.Button(
                    className="btn btn-default btn-circle btn-lg zoom btn-image",
                    style={"background-image": "url(/assets/buttons/logo_lasair.png)"},
                    color="dark",
                    outline=True,
                    id="lasair",
                    title="Lasair",
                    target="_blank",
                    href=f"https://lasair-lsst.lsst.ac.uk/objects/{objectId}",
                ),
            ),
        ],
        justify="around",
    )
    return buttons


# Downloads handling. Requires CORS to be enabled on the server.
# TODO: We are mostly using it like this until GET requests properly initiate
# downloads instead of just opening the file (so, Content-Disposition etc)
download_js = """
function(n_clicks, name, apiurl){
    if(n_clicks > 0){
        fetch(apiurl + '/api/v1/sources', {
            method: 'POST',
            body: JSON.stringify({
                 'diaObjectId': name,
                 'output-format': '$FORMAT'
            }),
            headers: {
                'Content-type': 'application/json'
            }
        }).then(function(response) {
            return response.blob();
        }).then(function(data) {
            window.saveAs(data, name + '.$EXTENSION');
        }).catch(error => console.error('Error:', error));
    };
    return true;
}
"""
app.clientside_callback(
    download_js.replace("$FORMAT", "json").replace("$EXTENSION", "json"),
    Output("download_json", "n_clicks"),
    [
        Input("download_json", "n_clicks"),
        Input("download_objectid", "children"),
        Input("download_apiurl", "children"),
    ],
)
app.clientside_callback(
    download_js.replace("$FORMAT", "csv").replace("$EXTENSION", "csv"),
    Output("download_csv", "n_clicks"),
    [
        Input("download_csv", "n_clicks"),
        Input("download_objectid", "children"),
        Input("download_apiurl", "children"),
    ],
)
app.clientside_callback(
    download_js.replace("$FORMAT", "votable").replace("$EXTENSION", "vot"),
    Output("download_votable", "n_clicks"),
    [
        Input("download_votable", "n_clicks"),
        Input("download_objectid", "children"),
        Input("download_apiurl", "children"),
    ],
)
