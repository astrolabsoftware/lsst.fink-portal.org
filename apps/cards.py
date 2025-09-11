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
import textwrap
import io
from dash import html, dcc, Output, Input, State

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

import numpy as np
import pandas as pd

from astropy.coordinates import SkyCoord
from astropy.time import Time

from fink_utils.photometry.utils import is_source_behind

from apps.api import request_api
from apps.dataclasses import simbad_types
from apps.utils import class_colors
from apps.utils import convert_time
from apps.utils import loading

from apps.utils import get_first_value
from apps.plotting import all_radio_options, make_modal_stamps
from apps.helpers import help_popover, lc_help
from dash_iconify import DashIconify

# Callbacks
from apps.plotting import draw_lightcurve  # noqa: F401
from apps.plotting import draw_cutouts  # noqa: F401

from apps.configuration import extract_configuration

from app import app

args = extract_configuration("config.yml")
APIURL = args["APIURL"]


def card_search_result(row, i):
    """Display single item for search results"""
    badges = []

    name = row["i:diaObjectId"]
    if name[0] == "[":  # Markdownified
        name = row["i:diaObjectId"].split("[")[1].split("]")[0]

    # Handle different variants for key names from different API entry points
    classification = None
    for key in ["d:finkclass"]:
        if key in row:
            # Classification
            classification = row.get(key)
            if classification in simbad_types:
                color = class_colors["Simbad"]
            elif classification in class_colors.keys():
                color = class_colors[classification]
            else:
                # Sometimes SIMBAD mess up names :-)
                color = class_colors["Simbad"]

            badges.append(
                make_badge(
                    classification,
                    variant="outline",
                    color=color,
                    tooltip="Fink classification",
                ),
            )

    cdsxmatch = row.get("d:cdsxmatch")
    if cdsxmatch and cdsxmatch != "Unknown" and cdsxmatch != classification:
        badges.append(
            make_badge(
                f"SIMBAD: {cdsxmatch}",
                variant="outline",
                color=class_colors["Simbad"],
                tooltip="SIMBAD classification",
            ),
        )

    badges += generate_generic_badges(row, variant="outline")

    # FIXME
    if "i:ndethist" in row:
        ndethist = row.get("i:ndethist")
    elif "d:nalerthist" in row:
        ndethist = row.get("d:nalerthist")
    else:
        ndethist = "?"

    # FIXME: use first/last
    jdend = 2460928.8554911325 + 3  # row.get("i:jdendhist", row.get("i:jd"))
    jdstart = 2460928.8554911325  # row.get("i:jdstarthist")
    lastdate = row.get("i:lastdate", Time(jdend, format="jd").iso)

    coords = SkyCoord(row["i:ra"], row["i:dec"], unit="deg")

    text = """
    `{}` detection(s) in `{:.1f}` days
    First: `{}`
    Last: `{}`
    Equ: `{} {}`
    Gal: `{}`
    """.format(
        ndethist,
        jdend - jdstart,
        Time(jdstart, format="jd").iso[:19],
        lastdate[:19],
        coords.ra.to_string(pad=True, unit="hour", precision=2, sep=" "),
        coords.dec.to_string(
            pad=True, unit="deg", alwayssign=True, precision=1, sep=" "
        ),
        coords.galactic.to_string(style="decimal"),
    )

    text = textwrap.dedent(text)
    # FIXME: reliability is not in rubin.objects
    if "i:reliability" in row:
        text += "RealBogus: `{:.2f}`\n".format(row["i:reliability"])
    if "d:anomaly_score" in row:
        text += "Anomaly score: `{:.2f}`\n".format(row["d:anomaly_score"])

    if "v:separation_degree" in row:
        corner_str = "{:.1f}''".format(row["v:separation_degree"] * 3600)
    else:
        corner_str = f"#{i!s}"

    item = dbc.Card(
        [
            dbc.CardHeader(
                dmc.Group(
                    [
                        html.A(
                            dmc.Text(f"{name}", style={"fontWeight": 700, "fontSize": 20}),
                            href=f"/{name}",
                            target="_blank",
                            className="text-decoration-none",
                        ),
                        # dmc.Space(w="sm"),
                        dmc.Space(w="sm"),
                        html.Div(
                            id={
                                "type": "sparklines",
                                "diaObjectId": str(name),
                                "index": i,
                            },
                        ),
                    ],
                    gap=3,
                ),
                # html.A(
                #     dmc.Group(
                #         [
                #             dmc.Text(
                #                 f"{name}", style={"fontWeight": 700, "fontSize": 26}
                #             ),
                #             dmc.Space(w="sm"),
                #             *badges,
                #         ],
                #         gap=3,
                #     ),
                #     href=f"/{name}",
                #     target="_blank",
                #     className="text-decoration-none",
                # ),
            ),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dmc.Skeleton(
                                    style={
                                        "width": "12pc",
                                        "height": "12pc",
                                    },
                                ),
                                id={
                                    "type": "search_results_cutouts",
                                    "diaObjectId": str(name),
                                    "index": i,
                                },
                                width="auto",
                            ),
                            dbc.Col(
                                [
                                    dmc.Box(
                                        [
                                            # html.A(
                                            #     dmc.Text(f"{name}", style={"fontWeight": 700, "fontSize": 20}),
                                            #     href=f"/{name}",
                                            #     target="_blank",
                                            #     className="text-decoration-none",
                                            # ),
                                            *badges,
                                            dcc.Markdown(
                                                text,
                                                style={"white-space": "pre-wrap"},
                                            ),
                                        ]
                                    )
                                ],
                                width="auto",
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
                                    "diaObjectId": str(name),
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
        ],
        color="light",
        className="mb-2 shadow border-1 rounded-5",
        outline=True,

    )

    # Test with Mantine
    # FIXME: does not work properly
    # item = dmc.Card(
    #     [
    #         dmc.CardSection(
    #             html.A(
    #                 dmc.Group(
    #                     [
    #                         dmc.Text(
    #                             f"{name}", style={"fontWeight": 700, "fontSize": 26}
    #                         ),
    #                         dmc.Space(w="sm"),
    #                         *badges,
    #                     ],
    #                     gap=3,
    #                 ),
    #                 href=f"/{name}",
    #                 target="_blank",
    #                 className="text-decoration-none",
    #             ),
    #             withBorder=True,
    #             inheritPadding=True,
    #             py="xs",
    #         ),
    #         dbc.Row(
    #             [
    #                 dbc.Col(
    #                     dmc.Skeleton(
    #                         style={
    #                             "width": "12pc",
    #                             "height": "12pc",
    #                         },
    #                     ),
    #                     id={
    #                         "type": "search_results_cutouts",
    #                         "diaObjectId": str(name),
    #                         "index": i,
    #                     },
    #                     width="auto",
    #                 ),
    #                 dbc.Col(
    #                     dcc.Markdown(
    #                         text,
    #                         style={"white-space": "pre-wrap"},
    #                     ),
    #                     width="auto",
    #                 ),
    #                 dbc.Col(
    #                     dmc.Skeleton(
    #                         style={
    #                             "width": "100%",
    #                             "height": "15pc",
    #                         },
    #                     ),
    #                     id={
    #                         "type": "search_results_lightcurve",
    #                         "diaObjectId": str(name),
    #                         "index": i,
    #                     },
    #                     xs=12,
    #                     md=True,
    #                 ),
    #             ],
    #             justify="start",
    #             className="g-2",
    #         ),
    #         # Upper right corner badge
    #         dbc.Badge(
    #             corner_str,
    #             color="light",
    #             pill=True,
    #             text_color="dark",
    #             className="position-absolute top-0 start-100 translate-middle border",
    #         ),
    #     ],
    #     # color="light",
    #     withBorder=True,
    #     shadow="sm",
    #     radius="md",
    #     # className="mb-2 shadow border-1",
    #     # outline=True,
    # )

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
    # FIXME: many ZTF leftover
    if isinstance(row, pd.DataFrame):
        # for VSX, aggregate values
        vsx_label = get_multi_labels(row, "d:vsx", default="Unknown", to_avoid=["nan"])
        if vsx_label != row.loc[0].get("d:vsx"):
            row["d:vsx"] = vsx_label

        # Get first row from DataFrame
        row = row.loc[0]

    badges = []

    # SSO
    ssnamenr = row.get("i:ssnamenr")
    if ssnamenr and ssnamenr != "null":
        badges.append(
            make_badge(
                f"SSO: {ssnamenr}",
                variant=variant,
                color="yellow",
                tooltip="Nearest Solar System object",
            ),
        )

    tracklet = row.get("d:tracklet")
    if tracklet and tracklet != "null":
        badges.append(
            make_badge(
                f"{tracklet}",
                variant=variant,
                color="violet",
                tooltip="Fink detected tracklet",
            ),
        )

    gcvs = row.get("d:gcvs")
    if gcvs and gcvs != "Unknown":
        badges.append(
            make_badge(
                f"GCVS: {gcvs}",
                variant=variant,
                color=class_colors["Simbad"],
                tooltip="General Catalogue of Variable Stars classification",
            ),
        )

    vsx = row.get("d:vsx")
    if (
        vsx
        and vsx != "Unknown"
        and vsx != "nan"
        and vsx == vsx
        and (isinstance(vsx, str) and not vsx.startswith("Fail"))
    ):
        badges.append(
            make_badge(
                f"VSX: {vsx}",
                variant=variant,
                color=class_colors["Simbad"],
                tooltip="AAVSO VSX classification",
            ),
        )

    # Nearby objects
    distnr = row.get("i:distnr")
    if distnr:
        is_source = is_source_behind(distnr)
        badges.append(
            make_badge(
                f'ZTF: {distnr:.1f}"',
                variant=variant,
                color="cyan",
                outline="red" if is_source else None,
                tooltip="""There is a source behind in ZTF reference image.
                You might want to check the DC magnitude plot, and get DR photometry to see its long-term behaviour
                """
                if is_source
                else "Distance to closest object in ZTF reference image",
            ),
        )

    distpsnr = row.get("i:distpsnr1")
    if distpsnr:
        badges.append(
            make_badge(
                f'PS1: {distpsnr:.1f}"',
                variant=variant,
                color="teal",
                tooltip="Distance to closest object in Pan-STARRS DR1 catalogue",
            ),
        )

    distgaia = row.get("i:neargaia")
    if distgaia:
        badges.append(
            make_badge(
                f'Gaia: {distgaia:.1f}"',
                variant=variant,
                color="teal",
                tooltip="Distance to closest object in Gaia DR3 catalogue",
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
        out = "/".join(
            [
                i
                for i in np.unique(pdf[colname].values)
                if not i.startswith("Fail") and i not in to_avoid
            ]
        )
        return out
    else:
        return default


def card_lightcurve_summary():
    """Add a card containing the lightcurve

    Returns
    -------
    card: dbc.Card
        Card with the lightcurve drawn inside
    """
    card = html.Div(
        [
            loading(
                dcc.Graph(
                    id="lightcurve_object_page",
                    style={
                        "width": "100%",
                        "height": "30pc",
                    },
                    config={"displayModeBar": False},
                    className="mb-2 rounded-5",
                ),
            ),
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.RadioGroup(
                                id="switch-mag-flux",
                                children=dmc.Group(
                                    [
                                        dmc.Radio(k, value=k, color="orange")
                                        for k in all_radio_options.keys()
                                    ]
                                ),
                                value="Total flux",
                                size="sm",
                            ),
                        ],
                        justify="center",
                        align="center",
                    ),
                    dmc.Group(
                        [
                            dmc.Switch(
                                "Color",
                                id="lightcurve_show_color",
                                color="gray",
                                radius="xl",
                                size="sm",
                                persistence=True,
                            ),
                            dmc.Button(
                                "Get DR photometry",
                                id={
                                    "type": "lightcurve_request_release",
                                    "name": "main",
                                },
                                variant="outline",
                                color="gray",
                                radius="xl",
                                size="xs",
                            ),
                            help_popover(
                                dcc.Markdown(
                                    lc_help,
                                    mathjax=True,
                                ),
                                "help_lc",
                                trigger=dmc.ActionIcon(
                                    DashIconify(icon="mdi:help"),
                                    id="help_lc",
                                    color="gray",
                                    variant="outline",
                                    radius="xl",
                                    size="md",
                                ),
                            ),
                        ],
                        justify="center",
                        align="center",
                    ),
                ]
            ),
        ],
    )
    return card  # dmc.Paper([comp1, comp2, comp3]) #card

def card_id(pdf):
    """Add a card containing basic alert data"""
    diaObjectid = pdf["i:diaObjectId"].to_numpy()[0]
    ra0 = pdf["i:ra"].to_numpy()[0]
    dec0 = pdf["i:dec"].to_numpy()[0]

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
                                color=dmc.DEFAULT_THEME["colors"]["dark"][6],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            loading(
                                dmc.Paper(
                                    [
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
                                    ],
                                    radius="sm",
                                    shadow="sm",
                                    withBorder=True,
                                    style={"padding": "0px"},
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
                                color=dmc.DEFAULT_THEME["colors"]["blue"][6],
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
                                color=dmc.DEFAULT_THEME["colors"]["orange"][6],
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
                                    children=dmc.Group(
                                        [
                                            dmc.Radio(k, value=k, color="orange")
                                            for k in ["EQU", "GAL"]
                                        ]
                                    ),
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
                                color=dmc.DEFAULT_THEME["colors"]["red"][6],
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
                                            trigger=dmc.ActionIcon(
                                                DashIconify(icon="mdi:help"),
                                                id="help_download",
                                                variant="outline",
                                                color="indigo",
                                            ),
                                        ),
                                        html.Div(
                                            diaObjectid,
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
            # dmc.AccordionItem(
            #     [
            #         dmc.AccordionControl(
            #             "Neighbourhood",
            #             icon=[
            #                 DashIconify(
            #                     icon="tabler:external-link",
            #                     color="#15284F",
            #                     width=20,
            #                 ),
            #             ],
            #         ),
            #         dmc.AccordionPanel(
            #             dmc.Stack(
            #                 [
            #                     card_neighbourhood(pdf),
            #                     *create_external_conesearches(ra0, dec0),
            #                 ],
            #                 align="center",
            #             ),
            #         ),
            #     ],
            #     value="external",
            # ),
            # dmc.AccordionItem(
            #     [
            #         dmc.AccordionControl(
            #             "Other brokers",
            #             icon=[
            #                 DashIconify(
            #                     icon="tabler:atom-2",
            #                     color=dmc.DEFAULT_THEME["colors"]["green"][6],
            #                     width=20,
            #                 ),
            #             ],
            #         ),
            #         dmc.AccordionPanel(
            #             dmc.Stack(
            #                 [
            #                     create_external_links_brokers(objectid),
            #                 ],
            #                 align="center",
            #             ),
            #         ),
            #     ],
            #     value="external_brokers",
            # ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        "Share",
                        icon=[
                            DashIconify(
                                icon="tabler:share",
                                color=dmc.DEFAULT_THEME["colors"]["gray"][6],
                                width=20,
                            ),
                        ],
                    ),
                    dmc.AccordionPanel(
                        [
                            dmc.Center(
                                html.Div(id="qrcode"),
                                style={"width": "100%", "height": "200"},
                            ),
                        ],
                    ),
                ],
                value="qr",
            ),
        ],
        value=["stamps"],
        styles={"content": {"padding": "5px"}},
    )

    return card

@app.callback(
    Output("card_id_left", "children"),
    [
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def card_id_left(object_data):
    """Add a card containing basic alert data"""
    pdf = pd.read_json(io.StringIO(object_data), dtype={"i:diaObjectId": np.int64, "i:diaSourceId": np.int64})

    diaObjectid = pdf["i:diaObjectId"].to_numpy()[0]

    # FIXME
    date_end = convert_time(pdf["i:midpointMjdTai"].to_numpy()[0], format_in="mjd", format_out="iso")
    discovery_date = convert_time(pdf["i:midpointMjdTai"].to_numpy()[-1], format_in="mjd", format_out="iso")
    mjds = pdf["i:midpointMjdTai"].to_numpy()
    ndet = len(pdf)

    badges = []
    for c in np.unique(pdf["d:finkclass"]):
        if c in simbad_types:
            color = class_colors["Simbad"]
        elif c in class_colors.keys():
            color = class_colors[c]
        else:
            # Sometimes SIMBAD mess up names :-)
            color = class_colors["Simbad"]

        badges.append(
            make_badge(
                c,
                color=color,
                tooltip="Fink classification",
            ),
        )

    tns_badge = generate_tns_badge(get_first_value(pdf, "i:diaObjectId"))
    if tns_badge is not None:
        badges.append(tns_badge)

    badges += generate_generic_badges(pdf, variant="dot")

    meta_name = generate_metadata_name(get_first_value(pdf, "i:diaObjectId"))
    if meta_name is not None:
        extra_div = dbc.Row(
            [
                dbc.Col(
                    dmc.Title(meta_name, order=4, style={"color": "#15284F"}), width=10
                ),
            ],
            justify="start",
            align="center",
        )
    else:
        extra_div = html.Div()

    coords = SkyCoord(
        get_first_value(pdf, "i:ra"), get_first_value(pdf, "i:dec"), unit="deg"
    )

    c1 = dmc.Avatar(src="/assets/Fink_SecondaryLogo_WEB.png", size="lg")
    c2 = dmc.Title(
        str(diaObjectid), order=1, style={"color": "#15284F", "wordWrap": "break-word"}
    )
    card = dmc.Paper(
        [
            dmc.Grid(
                [dmc.GridCol(c1, span="content"), dmc.GridCol(c2, span="auto")],
                gutter="xs",
            ),
            extra_div,
            html.Div(badges),
            dcc.Markdown(
                """
                Discovery date: `{}`
                Last detection: `{}`
                SNR: `{:.2f}`
                Duration: `{:.2f}` days
                Number of detections: `{}`
                RA/Dec: `{} {}`
                """.format(
                    discovery_date[:19],
                    date_end[:19],
                    pdf["i:snr"].to_numpy()[0],
                    mjds[0] - mjds[-1],
                    # get_first_value(pdf, "i:last") # FIXME with first/last
                    # - get_first_value(pdf, "i:first"),
                    ndet,
                    coords.ra.to_string(pad=True, unit="hour", precision=2, sep=" "),
                    coords.dec.to_string(
                        pad=True, unit="deg", alwayssign=True, precision=1, sep=" "
                    ),
                ),
                className="markdown markdown-pre ps-2 pe-2 mt-2",
            ),
        ],
        radius="xl",
        p="md",
        shadow="xl",
        withBorder=True,
    )
    return card

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
            # AT & SN?
            try:
                # Keep SN
                index = [i.startswith("SN") for i in entries].index(True)
            except ValueError:
                # no SN in list -- take the first one (most recent)
                index = 0
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


# def create_external_conesearches(ra0, dec0):
#     """Create two rows of buttons to trigger external conesearch

#     Parameters
#     ----------
#     ra0: float
#         RA for the conesearch center
#     dec0: float
#         DEC for the conesearch center
#     """
#     width = 3
#     buttons = [
#         dbc.Row(
#             [
#                 create_button_for_external_conesearch(
#                     kind="tns", ra0=ra0, dec0=dec0, radius=5, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="simbad", ra0=ra0, dec0=dec0, radius=0.08, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="snad", ra0=ra0, dec0=dec0, radius=5, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="datacentral", ra0=ra0, dec0=dec0, radius=2.0, width=width
#                 ),
#             ],
#             justify="around",
#         ),
#         dbc.Row(
#             [
#                 create_button_for_external_conesearch(
#                     kind="ned", ra0=ra0, dec0=dec0, radius=1.0, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="sdss", ra0=ra0, dec0=dec0, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="asas-sn", ra0=ra0, dec0=dec0, radius=0.5, width=width
#                 ),
#                 create_button_for_external_conesearch(
#                     kind="vsx", ra0=ra0, dec0=dec0, radius=0.1, width=width
#                 ),
#             ],
#             justify="around",
#         ),
#     ]
#     return buttons


# def create_external_links_brokers(objectId):
#     """ """
#     buttons = dbc.Row(
#         [
#             dbc.Col(
#                 dbc.Button(
#                     className="btn btn-default btn-circle btn-lg zoom btn-image",
#                     style={"background-image": "url(/assets/buttons/logo_alerce.png)"},
#                     color="dark",
#                     outline=True,
#                     id="alerce",
#                     title="ALeRCE",
#                     target="_blank",
#                     href=f"https://alerce.online/object/{objectId}",
#                 ),
#             ),
#             dbc.Col(
#                 dbc.Button(
#                     className="btn btn-default btn-circle btn-lg zoom btn-image",
#                     style={"background-image": "url(/assets/buttons/logo_antares.png)"},
#                     color="dark",
#                     outline=True,
#                     id="antares",
#                     title="ANTARES",
#                     target="_blank",
#                     href=f"https://antares.noirlab.edu/loci?query=%7B%22currentPage%22%3A1,%22filters%22%3A%5B%7B%22type%22%3A%22query_string%22,%22field%22%3A%7B%22query%22%3A%22%2a{objectId}%2a%22,%22fields%22%3A%5B%22properties.ztf_object_id%22,%22locus_id%22%5D%7D,%22value%22%3Anull,%22text%22%3A%22ID%20Lookup%3A%20ZTF21abfmbix%22%7D%5D,%22sortBy%22%3A%22properties.newest_alert_observation_time%22,%22sortDesc%22%3Atrue,%22perPage%22%3A25%7D",
#                 ),
#             ),
#             dbc.Col(
#                 dbc.Button(
#                     className="btn btn-default btn-circle btn-lg zoom btn-image",
#                     style={"background-image": "url(/assets/buttons/logo_lasair.png)"},
#                     color="dark",
#                     outline=True,
#                     id="lasair",
#                     title="Lasair",
#                     target="_blank",
#                     href=f"https://lasair-ztf.lsst.ac.uk/objects/{objectId}",
#                 ),
#             ),
#         ],
#         justify="around",
#     )
#     return buttons


# def card_neighbourhood(pdf):
#     distnr = get_first_value(pdf, "i:distnr")
#     ssnamenr = get_first_value(pdf, "i:ssnamenr")
#     distpsnr1 = get_first_value(pdf, "i:distpsnr1")
#     neargaia = get_first_value(pdf, "i:neargaia")
#     constellation = get_first_value(pdf, "v:constellation")
#     gaianame = get_multi_labels(pdf, "d:DR3Name", to_avoid=["nan"])
#     cdsxmatch = get_multi_labels(pdf, "d:cdsxmatch", to_avoid=["nan"])
#     vsx = get_multi_labels(pdf, "d:vsx", to_avoid=["nan"])
#     gcvs = get_multi_labels(pdf, "d:gcvs", to_avoid=["nan"])

#     # Sanitize empty values
#     if ssnamenr == "null":
#         ssnamenr = "N/A"

#     if not vsx or vsx == "nan":
#         vsx = "Unknown"

#     card = dmc.Paper(
#         [
#             dcc.Markdown(
#                 f"""
#                 Constellation: `{constellation}`
#                 Class (SIMBAD): `{cdsxmatch}`
#                 Class (VSX): `{vsx}`
#                 Class (GCVS): `{gcvs}`
#                 Name (MPC): `{ssnamenr}`
#                 Name (Gaia): `{gaianame}`
#                 Distance (Gaia): `{float(neargaia):.2f}` arcsec
#                 Distance (PS1): `{float(distpsnr1):.2f}` arcsec
#                 Distance (ZTF): `{float(distnr):.2f}` arcsec
#                 """,
#                 className="markdown markdown-pre ps-2 pe-2",
#             ),
#         ],
#         radius="sm",
#         p="xs",
#         shadow="sm",
#         withBorder=True,
#         style={"width": "100%"},
#     )

#     return card

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
                 'withupperlim': true,
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



