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
"""Collections of functions and messages to help users"""
from dash import html
import dash_bootstrap_components as dbc
from apps.configuration import extract_configuration


config_args = extract_configuration("config.yml")


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


msg_info = """
The `Card view` shows the cutout from science image, some basic alert info, and its light curve. Its header also displays the badges for alert classification and the distances from several reference catalogs, as listed in the alert.

By default, the `Table view` shows the following fields:

- i:objectId: Unique identifier for this object
- i:ra: Right Ascension of candidate; J2000 (deg)
- i:dec: Declination of candidate; J2000 (deg)
- v:lastdate: last date the object has been seen by Fink
- v:classification: Classification inferred by Fink (Supernova candidate, Microlensing candidate, Solar System, SIMBAD class, ...)
- i:ndethist: Number of spatially coincident detections falling within 1.5 arcsec going back to the beginning of the survey; only detections that fell on the same field and readout-channel ID where the input candidate was observed are counted. All raw detections down to a photometric S/N of ~ 3 are included.
- v:lapse: number of days between the first and last spatially coincident detections.

You can also add more columns using the dropdown button above the result table. Full documentation of all available fields can be found at {}/api/v1/schema.

The button `Sky Map` will open a popup with embedded Aladin sky map showing the positions of the search results on the sky.
""".format(config_args["APIURL"])

message_help = """
You may search for different kinds of data depending on what you enter. Below you will find the description of syntax rules and some examples.

The search is defined by the set of search terms (object names or coordinates) and options (e.g. search radius, number of returned entries, etc). The latters may be entered either manually or by using the `Quick fields` above the search bar. Supported formats for the options are both `name=value` and `name:value`, where `name` is case-insensitive, and `value` may use quotes to represent multi-word sentences. For some of the options, interactive drop-down menu will be shown with possible values.

The search bar has a button (on the left) to show you the list of your latest search queries so that you may re-use them, and a switch (on the right, right above the search field) to choose the format of results - either card-based (default, shows the previews of object latest cutout and light curve), or tabular (allows to see all the fields of objects).

##### Search for specific ZTF objects

To search for specific object, just use its name, or just a part of it. In the latter case, all objects with the names starting with this pattern will be returned.

Supported name patterns are as follows:
- `ZTFyyccccccc` for ZTF objects, i.e. ZTF followed with 2 digits for the year, and 7 characters after that
- `TRCK_YYYYMMDD_HHMMSS_NN` for tracklets detected at specific moment of time

Examples:
- `ZTF21abfmbix` - search for exact ZTF object
- `ZTF21abfmb` - search for partially matched ZTF object name
- `TRCK_20231213_133612_00` - search for all objects associated with specific tracklet
- `TRCK_20231213` - search for all tracklet events from the night of Dec 13, 2023

##### Search around known astronomical objects

You can run a conesearch around a known astronomical name. Examples:
- Extended objects: M31
- Catalog names: TXS 0506+056
- TNS names: AT 2019qiz, SN 2024aaj

By default, the conesearch radius is 10 arcseconds. You can change the radius by specifying `r=<number>` after the name, e.g. `Crab Nebula r=10m` (see the section Cone Search below).

##### Cone search

If you specify the position and search radius (using `r` option), all objects inside the given cone will be returned. Position may be specified by either coordinates, in either decimal or sexagesimal form, as exact ZTF object name, or as an object name resolvable through TNS or Simbad.

The coordinates may be specified as:
- Pair of degrees
- `HH MM SS.S [+-]?DD MM SS.S`
- `HH:MM:SS.S [+-]?DD:MM:SS.S`
- `HHhMMhSS.Ss [+-]?DDhMMhSS.Ss`
- optionally, you may use one more number as a radius, in either arcseconds, minutes (suffixed with `m`) or degrees (`d`). If specified, you do not need to provide the corresponding keyword (`r`) separately

If the radius is not specified, but the coordinates or resolvable object names are given, the default search radius is 10 arcseconds.

You may also restrict the alert variation time by specifying `after` and `before` keywords. They may be given as UTC timestamps in either ISO string format, as Julian date, or MJD. Alternatively, you may use `window` keyword to define the duration of time window in days.

Examples:
- `246.0422 25.669 30` - search within 30 arcseconds around `RA=246.0422 deg` `Dec=25.669 deg`
- `246.0422 25.669 30 after="2023-03-29 13:36:52" window=10` - the same but also within 10 days since specified time moment
- `16 24 10.12 +25 40 09.3` - search within 10 arcseconds around `RA=10:22:31` `Dec=+40:50:55.5`
- `Vega r=10m` - search within 600 arcseconds (10 arcminutes) from Vega
- `ZTF21abfmbix r=20` - search within 20 arcseconds around the position of ZTF21abfmbix
- `AT2021co` or `AT 2021co` - search within 10 arcseconds around the position of AT2021co

##### Solar System objects

To search for all ZTF objects associated with specific SSO, you may either directly specify `sso` keyword, which should be equal to contents of `i:ssnamenr` field of ZTF packets, or just enter the number or name of the SSO object that the system will try to resolve.

So you may e.g. search for:
- Asteroids by proper name
  - `Vesta`
- Asteroids by number
  - Asteroids (Main Belt): `8467`, `1922`, `33803`
  - Asteroids (Hungarians): `18582`, `77799`
  - Asteroids (Jupiter Trojans): `4501`, `1583`
  - Asteroids (Mars Crossers): `302530`
- Asteroids by designation
  - `2010JO69`, `2017AD19`, `2012XK111`
- Comets by number
  - `10P`, `249P`, `124P`
- Comets by designation
  - `C/2020V2`, `C/2020R2`

##### Class-based search

To see the list of latest objects of specific class (as listed in `v:classification` alert field), just specify the `class` keyword. By default it will return 100 latest ones, but you may also directly specify `last` keywords to alter it.

You may also specify the time interval to refine the search, using the self-explanatory keywords `before` and `after`. The limits may be specified with either time string, JD or MJD values. You may either set both limiting values, or just one of them. The results will be sorted in descending order by time, and limited to specified number of entries.

Finally, you can specify a trend to your search, such as rising or fading. Use the keyword `trend` to see the list of available trends. This is an experimental feature that is expected to evolve.

Examples:
- `class=Unknown` - return 100 latest objects with class `Unknown`
- `last=10 class="Early SN Ia candidate"` - return 10 latest arly SN Ia candidates
- `class="Early SN Ia candidate" before="2023-12-01" after="2023-11-07 04:00:00"` - objects of the same class between 4am on Nov 15, 2023 and Dec 1, 2023
- `class="Early SN Ia candidate" before="2023-12-01" after="2023-11-07 04:00:00" trend=rising` - objects of the same class between 4am on Nov 15, 2023 and Dec 1, 2023, that were rising (becoming brighter).
- `class="(CTA) Blazar" trend=low_state after=2025-02-01 before=2025-02-13` - Blazars selected by CTA which were in a low state between the 1st February and 13th February 2025.

"""

lc_help = r"""
##### Difference magnitude

Circles (&#9679;) with error bars show valid alerts that pass the Fink quality cuts.
In addition, the _Difference magnitude_ view shows:
- upper triangles with errors (&#9650;), representing alert measurements that do not satisfy Fink quality cuts, but are nevetheless contained in the history of valid alerts and used by classifiers.
- lower triangles (&#9661;), representing 5-sigma magnitude limit in difference image based on PSF-fit photometry contained in the history of valid alerts.

If the `Color` switch is turned on, the view also shows the panel with `g - r` color, estimated by combining nearby (closer than 0.3 days) measurements in two filters.

##### DC magnitude
DC magnitude is computed by combining the nearest reference image catalog magnitude (`magnr`),
differential magnitude (`magpsf`), and `isdiffpos` (positive or negative difference image detection) as follows:
$$
m_{DC} = -2.5\log_{10}(10^{-0.4m_{magnr}} + \texttt{sign} 10^{-0.4m_{magpsf}})
$$

where `sign` = 1 if `isdiffpos` = 't' or `sign` = -1 if `isdiffpos` = 'f'.
Before using the nearest reference image source magnitude (`magnr`), you will need
to ensure the source is close enough to be considered an association
(e.g., `distnr` $\leq$ 1.5 arcsec). It is also advised you check the other associated metrics
(`chinr` and/or `sharpnr`) to ensure it is a point source. ZTF recommends
0.5 $\leq$ `chinr` $\leq$ 1.5 and/or -0.5 $\leq$ `sharpnr` $\leq$ 0.5.

The view also shows, with dashed horizontal lines, the levels corresponding to the magnitudes of the nearest reference image catalog entry (`magnr`) used in computing DC magnitudes.

This view may be augmented with the photometric points from [ZTF Data Releases](https://www.ztf.caltech.edu/ztf-public-releases.html) by clicking `Get DR photometry` button. The points will be shown with semi-transparent dots (&#8226;).

##### Difference flux
Difference flux (in Jansky) is constructed from difference magnitude by using the following:
$$
f = 3631 \times \texttt{sign} 10^{-0.4m_{magpsf}}
$$
where `sign` = 1 if `isdiffpos` = 't' or `sign` = -1 if `isdiffpos` = 'f'.

This view also shows the photometry from ZTF Data Releases (see above), which is converted to fluxes using the same formula. Then, the "baseline" flux, which is computed from the nearest reference image catalog magnitude (`magnr`), is subtracted from it, so that the value represent the flux variation w.r.t. the template image, i.e. the difference flux.

Note that we display the flux in milli-Jansky.

##### DC flux
DC flux (in Jansky) is constructed from DC magnitude by using the following:
$$
f_{DC} = 3631 \times 10^{-0.4m_{DC}}
$$

This view also shows the fluxes from ZTF Data Releases, without any baseline correction.

Note that we display the flux in milli-Jansky.
"""