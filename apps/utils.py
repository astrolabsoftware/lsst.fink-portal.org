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
    "Unknown": "gray",
    "Simbad": "blue",
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
