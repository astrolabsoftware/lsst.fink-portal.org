# Copyright 2019-2024 AstroLab Software
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
"""Collection of utilities for the portal"""

from dash import html
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc

import numpy as np
import pandas as pd

from astropy.time import Time
from astroquery.mpc import MPC

from apps.api import request_api

from fink_utils.xmatch.simbad import get_simbad_labels


# Colors for the Sky map & badges
class_colors = {
    "Early SN Ia candidate": "red",
    "SN candidate": "orange",
    "Kilonova candidate": "dark",
    "Microlensing candidate": "lime",
    "Tracklet": "violet",
    "Solar System MPC": "yellow",
    "Solar System candidate": "indigo",
    "Ambiguous": "grape",
    "Simbad": "blue",
    "Unknown": "gray",
    "nan": "gray",
    "Fail": "gray",
}

simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())


def markdownify_objectid(diaObjectid):
    """Make hyperlink for markdown

    Parameters
    ----------
    diaObjectId: str
        DIA object ID

    Returns
    -------
    out: str
    """
    objectid_markdown = f"[{diaObjectid}](/{diaObjectid})"
    return objectid_markdown


def demarkdownify_objectid(name):
    if name[0] == "[":  # Markdownified
        name = name.split("[")[1].split("]")[0]
    return name


def convert_time(time_in, format_in="mjd", format_out="iso", scale_in="tai"):
    """Convert time to another format.

    Parameters
    ----------
    time_in: Any
        Input time
    format_in: str
        Format for `time_in`. Default is mjd.
    format_out: str
        Format for the output. Default is iso.
    scale_in: str
        Scale for the input time.

    Returns
    -------
    out: Any
        Time in format `format_out`
    """
    return Time(time_in, format=format_in, scale=scale_in).to_value(format_out)


def loading(item):
    return html.Div([
        item,
        dmc.LoadingOverlay(
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
            overlayProps={"radius": "sm", "blur": 2},
            zIndex=100000,
        ),
    ])


def flux_to_mag(flux, flux_err):
    """Convert flux to magnitude (and errors)

    Parameters
    ----------
    flux: array-like
        Total flux in nJy
    flux_err: array-like
        Total flux error in nJy

    Returns
    -------
    mag, mag_err: array-like
    """
    mag = 31.4 - 2.5 * np.log10(flux)
    mag_err = 2.5 / np.log(10) * flux_err / flux

    return mag, mag_err


def get_first_value(pdf, colname, default=None):
    """Get first value from given column of a DataFrame, or default value if not exists."""
    if colname in pdf.columns:
        return pdf.loc[0, colname]
    else:
        return default


def hex_to_rgba(hex, alpha, format_out="plotly"):
    """ """
    hex = hex.strip("#")
    triplet = tuple(int(hex[i : i + 2], 16) for i in (0, 2, 4))

    if format_out == "plotly":
        return "rgba({}, {}, {}, {})".format(*triplet, alpha)
    elif format_out == "raw":
        return (*triplet, alpha)


def rgb_to_rgba(rgb_value, alpha):
    """Adds the alpha channel to an RGB Value and returns it as an RGBA Value

    Parameters
    ----------
    rgb_value: str
        Input RGB Value
    alpha: float
        Alpha Value to add  in range [0,1]

    Returns
    -------
    out: str
        RGBA Value
    """
    return f"rgba{rgb_value[3:-1]}, {alpha})"


def isoify_time(t):
    try:
        tt = Time(t)
    except ValueError:
        ft = float(t)
        if ft // 2400000:
            tt = Time(ft, format="jd")
        else:
            tt = Time(ft, format="mjd")
    return tt.iso


def is_row_static_or_moving(row: dict):
    """Check if a row contains static or moving object data

    Parameters
    ----------
    row: dict
        The row of a DataFrame (as dict)

    Returns
    -------
    main_id: str
        diaObjectId or ssObjectId
    is_sso: boolean
        False if static, True if moving
    """
    # Check whether you have diaObject or ssObject
    dianame = demarkdownify_objectid(str(row.get("r:diaObjectId", 0)))
    ssname = demarkdownify_objectid(str(row.get("r:mpcDesignation", 0)))
    if dianame in [0, "0", None]:
        # FIXME: is 0 the normal value?
        main_id = ssname
        is_sso = True
    else:
        main_id = dianame
        is_sso = False

    return main_id, is_sso


def cats_type_converter():
    """Class mapping for CATS

    Returns
    -------
    out: dict
        Mapping int -> name
    """
    mapping_cats_general = {
        11: "SN-like",  # SN-like
        12: "Fast",  # Fast: KN, ulens, Novae, ...
        13: "Long",  # Long: SLSN, TDE, PISN, ...
        21: "Periodic",  # Periodic: RRLyrae, EB, LPV, ...
        22: "Non-periodic",  # Non-periodic: AGN
    }

    return mapping_cats_general


def template_button_for_external_conesearch(
    className="btn btn-default zoom btn-circle btn-lg btn-image",
    style=None,
    color="dark",
    outline=True,
    title="",
    target="_blank",
    href="",
):
    """Template button for external conesearch

    Parameters
    ----------
    className: str, optional
        Styling options. Default is `btn btn-default zoom btn-circle btn-lg btn-image`
    style: dict, optional
        Extra styling options. Default is {}
    color: str, optional
        Color of the button (default is `dark`)
    outline: bool, optional
    title: str, optional
        Title of the object. Default is ''
    target: str, optional
        Open in the same window or in a new tab (default).
    href: str, optional
        targeted URL
    """
    if style is None:
        style = {}

    button = dbc.Button(
        className=className,
        style=style,
        color=color,
        outline=outline,
        title=title,
        target=target,
        href=href,
    )

    return button


def create_button_for_external_conesearch(
    kind: str, ra0: float, dec0: float, radius=None, width=4
):
    """Create a button that triggers an external conesearch

    The button is wrapped within a dbc.Col object.

    Parameters
    ----------
    kind: str
        External resource name. Currently available:
        - asas-sn, snad, vsx, tns, simbad, datacentral, ned, sdss
    ra0: float
        RA for the conesearch center
    dec0: float
        DEC for the conesearch center
    radius: int or float, optional
        Radius for the conesearch. Each external resource has its
        own default value (default), as well as its own units.
    width: int, optional
        dbc.Col width parameter. Default is 4.
    """
    if kind == "asas-sn-variable":
        if radius is None:
            radius = 0.5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/assassin_logo.png)",
                    "background-color": "black",
                },
                title="ASAS-SN",
                href=f"https://asas-sn.osu.edu/variables?ra={ra0}&dec={dec0}&radius={radius}&vmag_min=&vmag_max=&amplitude_min=&amplitude_max=&period_min=&period_max=&lksl_min=&lksl_max=&class_prob_min=&class_prob_max=&parallax_over_err_min=&parallax_over_err_max=&name=&references[]=I&references[]=II&references[]=III&references[]=IV&references[]=V&references[]=VI&sort_by=raj2000&sort_order=asc&show_non_periodic=true&show_without_class=true&asassn_discov_only=false&",
            ),
            width=width,
        )
    elif kind == "asas-sn":
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/assassin_logo.png)",
                    "background-color": "black",
                },
                title="ASAS-SN",
                href=f"https://asas-sn.osu.edu/?ra={ra0}&dec={dec0}",
            ),
            width=width,
        )
    elif kind == "snad":
        if radius is None:
            radius = 5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/snad.svg)"},
                title="SNAD",
                href=f"https://ztf.snad.space/search/{ra0} {dec0}/{radius}",
            ),
            width=width,
        )
    elif kind == "vsx":
        if radius is None:
            radius = 0.1
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/vsx.png)"},
                title="AAVSO VSX",
                href=f"https://www.aavso.org/vsx/index.php?view=results.get&coords={ra0}+{dec0}&format=d&size={radius}",
            ),
            width=width,
        )
    elif kind == "tns":
        if radius is None:
            radius = 5
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/tns_logo.png)",
                    "background-size": "auto 100%",
                    "background-position-x": "left",
                },
                title="TNS",
                href=f"https://www.wis-tns.org/search?ra={ra0}&decl={dec0}&radius={radius}&coords_unit=arcsec",
            ),
            width=width,
        )
    elif kind == "simbad":
        if radius is None:
            radius = 0.08
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/simbad.png)"},
                title="SIMBAD",
                href=f"http://simbad.u-strasbg.fr/simbad/sim-coo?Coord={ra0}%20{dec0}&Radius={radius}",
            ),
            width=width,
        )
    elif kind == "datacentral":
        if radius is None:
            radius = 2.0
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/dclogo_small.png)"},
                title="DataCentral Data Aggregation Service",
                href=f"https://das.datacentral.org.au/open?RA={ra0}&DEC={dec0}&FOV={0.5}&ERR={radius}",
            ),
            width=width,
        )
    elif kind == "ned":
        if radius is None:
            radius = 1.0
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={
                    "background-image": "url(/assets/buttons/NEDVectorLogo_WebBanner_100pxTall_2NoStars.png)",
                    "background-color": "black",
                },
                title="NED",
                href=f"http://ned.ipac.caltech.edu/cgi-bin/objsearch?search_type=Near+Position+Search&in_csys=Equatorial&in_equinox=J2000.0&ra={ra0}&dec={dec0}&radius={radius}&obj_sort=Distance+to+search+center&img_stamp=Yes",
            ),
            width=width,
        )
    elif kind == "sdss":
        button = dbc.Col(
            template_button_for_external_conesearch(
                style={"background-image": "url(/assets/buttons/sdssIVlogo.png)"},
                title="SDSS",
                href=f"http://skyserver.sdss.org/dr13/en/tools/chart/navi.aspx?ra={ra0}&dec={dec0}",
            ),
            width=width,
        )

    return button


def query_mpc(number, kind="asteroid"):
    """Query MPC for information about object 'designation'.

    Parameters
    ----------
    designation: str
        A name for the object that the MPC will understand.
        This can be a number, proper name, or the packed designation.
    kind: str
        asteroid or comet

    Returns
    -------
    pd.Series
        Series containing orbit and select physical information.
    """
    try:
        mpc = MPC.query_object(target_type=kind, number=number)
        mpc = mpc[0]
    except IndexError:
        try:
            mpc = MPC.query_object(target_type=kind, designation=number)
            mpc = mpc[0]
        except IndexError:
            return pd.Series({})
    except RuntimeError:
        return pd.Series({})
    orbit = pd.Series(mpc)
    return orbit


def convert_mpc_type(index):
    dic = {
        0: "Unclassified (mostly Main Belters)",
        1: "Atiras",
        2: "Atens",
        3: "Apollos",
        4: "Amors",
        5: "Mars Crossers",
        6: "Hungarias",
        7: "Phocaeas",
        8: "Hildas",
        9: "Jupiter Trojans",
        10: "Distant Objects",
    }
    return dic[index]


def help_popover(text, id, trigger=None, className=None):
    """Make clickable help icon with popover at the bottom right corner of current element"""
    if trigger is None:
        trigger = html.I(
            className="fa fa-question-circle fa-1x",
            id=id,
        )
        if className is None:
            className = "d-flex align-items-end justify-content-end"

    return html.Div(
        [
            trigger,
            dbc.Popover(
                dbc.PopoverBody(
                    text,
                    style={
                        "overflow-y": "auto",
                        "white-space": "pre-wrap",
                        "max-height": "80vh",
                    },
                ),
                target=id,
                trigger="legacy",
                placement="auto",
                style={"width": "80vw", "max-width": "800px"},
                className="shadow-lg",
            ),
        ],
        className=className,
    )


def extract_parameter_value_from_url(param_dic, key, default):
    """ """
    if key in param_dic:
        val = param_dic[key]
    else:
        val = default
    return val


def is_float(s: str) -> bool:
    """Check if s can be transformed as a float"""
    try:
        float(s)
        return True
    except ValueError:
        return False


def extract_bayestar_query_url(search: str):
    """Try to infer the query from an URL (GW search)

    Parameters
    ----------
    search: str
        String returned by `dcc.Location.search` property.
        Typically starts with ?

    Returns
    -------
    credible_level: float
        The credible level (0-1)
    event_name: str
        Event name (O3 or O4)
    """
    # remove trailing ?
    search = search[1:]

    # split parameters
    parameters = search.split("&")

    # Make a dictionary with the parameter keys and values
    param_dic = {s.split("=")[0]: s.split("=")[1] for s in parameters}

    credible_level = extract_parameter_value_from_url(param_dic, "credible_level", "")
    event_name = extract_parameter_value_from_url(param_dic, "event_name", "")
    if is_float(credible_level):
        credible_level = float(credible_level)

    return credible_level, event_name


def format_field_for_data_transfer(with_predefined_options=True, cutouts_allowed=True):
    """Get schema from API, and make it suitable for Data Transfer"""
    data = []

    # schema = request_api("/api/v1/schema", method="GET", output="json")

    if with_predefined_options:
        # high level
        packet = {
            "group": "Pre-defined schema",
            "items": [
                {"value": "Full packet", "label": "Full packet"},
                {
                    "value": "Medium packet",
                    "label": "Medium packet (all but cutouts)",
                },
                {
                    "value": "Light packet",
                    "label": "Light packet (all but cutouts and history)",
                },
            ],
        }
        data.append(packet)

    # # classification
    # objectid = {
    #     "group": "Fink derived classification",
    #     "items": [{"value": "finkclass", "label": "finkclass"}],
    # }
    # data.append(objectid)

    # Fink added values
    # labels = [
    #     "{}".format(select_struct(k))
    #     for k in schema["Fink science module outputs (f:)"].keys()
    #     if k not in ["tag"]
    # ]
    # fink = {
    #     "group": "Fink science module outputs",
    #     "items": [{"value": label, "label": label} for label in labels],
    # }
    # data.append(fink)

    # # candidate
    # labels = [
    #     "{}".format(select_struct(k, "candidate."))
    #     for k in schema["LSST original fields (r:)"].keys()
    # ]
    # candidate = {
    #     "group": "LSST original fields",
    #     "items": [{"value": label, "label": label} for label in labels],
    # }
    # data.append(candidate)

    # if cutouts_allowed:
    #     # Cutouts
    #     labels = [
    #         "{}".format(select_struct(k))
    #         for k in schema["LSST original cutouts (b:)"].keys()
    #     ]
    #     cutout = {
    #         "group": "LSST original cutouts",
    #         "items": [{"value": label, "label": label} for label in labels],
    #     }
    #     data.append(cutout)

    return data


def create_datatransfer_schema_table(cutouts_allowed=True):
    """ """
    # schema = request_api("/api/v1/schema", method="GET", output="json")

    def format_type(t):
        if isinstance(t, list):
            return t[-1]
        else:
            return t

    rows = []
    # rows.append(
    #     dmc.TableTr(
    #         [
    #             dmc.TableTd("objectId"),
    #             dmc.TableTd("ZTF"),
    #             dmc.TableTd("string"),
    #             dmc.TableTd("Unique identifier for an object"),
    #         ]
    #     )
    # )
    # rows.append(
    #     dmc.TableTr(
    #         [
    #             dmc.TableTd("finkclass"),
    #             dmc.TableTd("Fink"),
    #             dmc.TableTd("string"),
    #             dmc.TableTd("Fink derived classification"),
    #         ]
    #     )
    # )

    # provenances = ["Fink science module outputs (d:)", "ZTF original fields (i:)"]
    # prefixes = ["", "candidate."]

    # if cutouts_allowed:
    #     provenances.append("ZTF original cutouts (b:)")
    #     prefixes.append("")
    # for prov, prefix in zip(provenances, prefixes):
    #     # Table candidates
    #     labels = [
    #         select_struct(k, prefix)
    #         for k in schema[prov].keys()
    #         if k not in ["objectId", "tag"]
    #     ]
    #     types = [
    #         format_type(v["type"])
    #         for k, v in schema[prov].items()
    #         if k not in ["objectId", "tag"]
    #     ]
    #     docs = [
    #         v["doc"] for k, v in schema[prov].items() if k not in ["objectId", "tag"]
    #     ]

    #     [
    #         rows.append(
    #             dmc.TableTr(
    #                 [
    #                     dmc.TableTd(label),
    #                     dmc.TableTd(prov.split(" ")[0]),
    #                     dmc.TableTd(type_),
    #                     dmc.TableTd(doc),
    #                 ]
    #             )
    #         )
    #         for label, type_, doc in zip(labels, types, docs)
    #     ]

    head = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh("Name", w="25%"),
            dmc.TableTh("From", w="15%"),
            dmc.TableTh("Type", w="15%"),
            dmc.TableTh("Documentation"),
        ])
    )
    body = dmc.TableTbody(rows)
    caption = dmc.TableCaption("Alert schema")

    table_candidate = dmc.TableScrollContainer(
        dmc.Table(
            [head, body, caption],
            horizontalSpacing="xl",
            highlightOnHover=True,
        ),
        maxHeight=300,
        minWidth=0,
        type="scrollarea",
    )
    return dmc.Stack([
        dmc.Text(
            "Full packet will give you all LSST + Fink content. Medium packet is Full packet without the cutouts. Light packet is necessary fields for lightcurve analysis."
        ),
        table_candidate,
    ])


def query_and_order_statistics(date="20", columns="*", index_by="f:night", drop=True):
    """Query /statistics, and order the resulting dataframe

    Parameters
    ----------
    date: str, optional
        Date (default is '')
    columns: str
        Column names (default is '*')
    index_by: str, optional
        Column name on which to index on (default is key:key)
    drop: bool
        If True, drop original column used to index the dataframe.
        Default is False.

    Returns
    -------
    pdf: Pandas DataFrame
        DataFrame with statistics data, ordered from
        oldest (top) to most recent (bottom)
    """
    pdf = request_api(
        "/api/v1/statistics",
        json={
            "date": date,
            "columns": columns,
            "output-format": "json",
        },
    )

    pdf = pdf.sort_values(index_by)
    pdf = pdf.set_index(index_by, drop=drop)

    # Remove hbase specific fields
    if "key:time" in pdf.columns:
        pdf = pdf.drop(columns=["key:time"])

    return pdf
