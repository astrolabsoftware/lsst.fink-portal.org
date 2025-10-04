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
"""Wrapper for the Fink REST API"""

import io
import requests
import urllib
import pandas as pd

from apps.configuration import extract_configuration


def request_api(endpoint, json=None, output="pandas", method="POST", **kwargs):
    """Wrapper to query the Fink REST API

    Parameters
    ----------
    endpoint: str
        Path to an endpoint
    json: dict
        Payload containing input arguments for POST queries.
        Default is None.
    output: str
        Output format among: pandas (default), raw, or json.
    method: str
        POST or GET

    Returns
    -------
    out: Any
        Format depends on `output`: DataFrame, bytes, or dictionary.
    """
    args = extract_configuration("config.yml")
    APIURL = args["APIURL"]
    if method == "POST":
        r = requests.post(
            f"{APIURL}{endpoint}",
            json=json,
        )
    elif method == "GET":
        URL = f"{APIURL}{endpoint}"
        ARGS = ""
        if json is not None and isinstance(json, dict):
            URL += "?"
            for k, v in json.items():
                # encode reserved characters
                ARGS += "{}={}&".format(
                    urllib.parse.quote_plus(k), urllib.parse.quote_plus(v)
                )
        r = requests.get(URL + ARGS)

    if output == "json":
        if r.status_code != 200:
            return []
        return r.json()
    elif output == "raw":
        if r.status_code != 200:
            return io.BytesIO()
        return io.BytesIO(r.content)
    else:
        if r.status_code != 200:
            return pd.DataFrame()
        return pd.read_json(io.BytesIO(r.content), **kwargs)
