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
"""Definition of labels from user-defined filters, SIMBAD, and TNS"""

import pandas as pd
from fink_utils.xmatch.simbad import get_simbad_labels

from apps.api import request_api


def unwrap_fink_tags(kind="filters", default_support=True):
    """Method to properly decode fink_tags from an API call

    Notes
    -----
    This is wanted to handle API migration change transparently
    at the level of the portal

    Returns
    -------
    tags: list of str
    descriptions: list of str
    api_support: list of bool
    """
    tags, descriptions, api_support = [], [], []

    if kind == "filters":
        elems = request_api("/api/v1/tags", output="json", method="GET")
    elif kind == "blocks":
        elems = request_api("/api/v1/blocks", output="json", method="GET")

    for tag, payload in elems.items():
        tags.append(tag)
        # Handle API 3.3.0 migration
        if isinstance(payload, dict):
            descriptions.append(payload["description"])
            api_support.append(payload["API support"])
        elif isinstance(payload, str):
            descriptions.append(payload)
            api_support.append(default_support)

    return tags, descriptions, api_support


# TNS
tns_types = pd.read_csv("assets/tns_types.csv", header=None)[0].to_numpy()
tns_types = sorted(tns_types, key=lambda s: s.lower())

# SIMBAD
simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

# Fink
fink_tags, fink_tag_description, fink_tag_api_support = unwrap_fink_tags(
    kind="filters", default_support=True
)
fink_blocks, fink_block_description, fink_block_api_support = unwrap_fink_tags(
    kind="blocks", default_support=False
)
