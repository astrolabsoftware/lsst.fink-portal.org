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

import numpy as np

from astropy.time import Time

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
