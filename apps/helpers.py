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
"""Collections of functions and messages to help users"""

import dash_bootstrap_components as dbc
from dash import html

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
The `Card view` shows the cutout from science image, some basic alert info, and its light curve. Its header displays various quality indicators and badges related to tags (e.g. if found in TNS, SIMBAD, etc.).

By default, the `Table view` shows the following fields:

- r:diaObjectId Unique identifier for this object
- r:ra: Right Ascension of candidate; J2000 (deg)
- r:dec: Declination of candidate; J2000 (deg)

You can also add more columns using the dropdown button above the result table. Full documentation of all available fields can be found at {}/api/v1/schema.

The button `Sky Map` will open a popup with embedded Aladin sky map showing the positions of the search results on the sky.
""".format(config_args["APIURL"])

message_help = """
You may search for different kinds of data depending on what you enter. Below you will find the description of syntax rules and some examples.

##### Using the search bar

The search is defined by the set of search terms (object names, coordinates, tag names) and options (e.g. search radius, number of returned entries, etc). The latters may be entered either manually or by using
the `Quick fields` above the search bar. Supported formats for the options are both `name=value` and `name:value`, where `name` is case-insensitive, and `value` may use quotes to represent multi-word sentences. For some of the options, interactive drop-down menu will be shown with possible values.

The search bar has a button (on the left) to show you the list of your latest search queries so that you may re-use them, and a switch (on the right, right above the search field) to choose the format of results - either card-based (default, shows the previews of object latest cutout and light curve), or tabular (allows to see all the fields of objects).

##### Search for specific LSST objects

To search for specific object, just use its name.

Examples:
- `313761043604045880`
- `313699514821640259`
- `313756671442681875`

##### Search around known astronomical objects

You can run a conesearch around a known astronomical name. Examples:
- Extended objects: Cosmos field r=60
- Catalog names: `ESO 250-8 r=60`, `WISE J041028.04-465835.9 r=60`
- TNS names: SN 2022and

By default, the conesearch radius is 10 arcseconds. You can change the radius by specifying `r=<number>` after the name, e.g. `Cosmos field r=2m` (see the section Cone Search below).

##### Cone search

If you specify the position and search radius (using `r` option), all objects inside the given cone will be returned. Position may be specified by either coordinates, in either decimal or sexagesimal form, an exact LSST `diaObjectId`, or an object name resolvable through TNS or Simbad.

The coordinates may be specified as:
- Pair of degrees
- `HH MM SS.S [+-]?DD MM SS.S`
- `HH:MM:SS.S [+-]?DD:MM:SS.S`
- `HHhMMhSS.Ss [+-]?DDhMMhSS.Ss`
- optionally, you may use one more number as a radius, in either arcseconds, minutes (suffixed with `m`) or degrees (`d`). If specified, you do not need to provide the corresponding keyword (`r`) separately

If the radius is not specified, but the coordinates or resolvable object names are given, the default search radius is 10 arcseconds.

You may also restrict the alert variation time by specifying `after` and `before` keywords. They may be given as UTC timestamps in either ISO string format, as Julian date, or MJD. Alternatively, you may use `window` keyword to define the duration of time window in days.

Examples:
- `61.964820 -48.713443 30` - search within 30 arcseconds around `RA=61.964820 deg` `Dec=-48.713443 deg`
- `61.964820 -48.713443 30 after="2023-03-29 13:36:52" window=10` - the same but also within 10 days since specified time moment
- `04 07 51.56 -48 42 48.4` - search within 10 arcseconds around `RA=04 07 51.56` `Dec=-48 42 48.4`
- `Vega r=10m` - search within 600 arcseconds (10 arcminutes) from Vega
- `313761043604045880 r=20` - search within 20 arcseconds around the position of 313761043604045880
- `SN 2022and` or `SN 2022and` - search within 10 arcseconds around the position of SN 2022and

##### Solar System objects

To search for all LSST alerts associated with specific SSO, you may either directly specify `sso` keyword, which can be any name, number or designation. Under the hood we resolve names using [quaero](https://ssp.imcce.fr/webservices/ssodnet/api/quaero/). So you may e.g. search for: `2015 BC557`, `713454`, `J96T28C`, `K15Bt7C`, `Ukyounodaibu`, etc.

##### Tag-based search

To see the list of latest objects of specific tag (as defined in https://lsst.fink-portal.org/schemas), just specify the `tag` keyword. By default it will return 100 latest ones, but you may also directly specify `last` keywords to alter it.

You may also specify the time interval to refine the search, using the keywords `before` and `after`. The limits may be specified with either time string, JD or MJD values. You may either set both limiting values, or just one of them. The results will be sorted in descending order by time, and limited to specified number of entries.

Examples:
- `tag=extragalactic_lt20mag_candidate` - return 100 latest objects with tag `extragalactic_lt20mag_candidate`
- `last=10 tag="extragalactic_lt20mag_candidate"` - return 10 latest candidates from `extragalactic_lt20mag_candidate`
- `tag="in_tns" before="2026-01-31" after="2026-01-01 04:00:00"` - last 100 alerts flagged as reported in TNS between 4am on Jan 01, 2026 and Jan 31, 2026

"""

lc_help = r"""
##### Lightcurve

The figure shows the evolution of brightness as a function of time. Each filter band is shown with a different color, and a different marker. Colors can be changed in the configuration (top right button of the page).

The y axis unit can also be changed in the configuration. We expose several options:

- Difference magnitude/flux: magnitude/flux estimated from the difference image (science image - reference image).
- Total magnitude/flux: magnitude/flux estimated from the science image.

If the flux estimate is negative, corresponding magnitudes will not be computed. Note that we display the flux in micro-Jansky.

##### Adding forced photometry estimates

TBD

##### Adding Fink/ZTF alerts

By clicking on the `Fink/ZTF alerts` button, you will trigger a conesearch in the Fink/ZTF API. If an object is found within 1.5'' of the LSST object's position, measurements from ZTF will be shown. We use the same colors and markers, except the markers are smaller and the legend specifies `<band>-ztf`.

##### Internal conesearch

By clicking on the `Conesearch` button, you will trigger a conesearch in the LSST portal to check if there is any object 10'' of this LSST object's position. This is particularly useful in these early days where mis-association of nearby alerts can happen (different `diaObjectId` for the same underlying object on sky).

##### SkyBot check

By clicking on the `SkyBot` button, you will open a new page a run a conesearch around the position of the object (radius of 10'') at the last date of observation to check if there were any know asteroids nearby. If the page remains blank, good, no asteroids! Otherwise you will have a table with the Solar System object(s) description. The query can take a few seconds.
"""
