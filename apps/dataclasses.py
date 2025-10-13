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
"""Definition of labels from TNS, SIMBAD and Fink"""

from fink_utils.xmatch.simbad import get_simbad_labels

import pandas as pd

# TNS
tns_types = pd.read_csv("assets/tns_types.csv", header=None)[0].to_numpy()
tns_types = sorted(tns_types, key=lambda s: s.lower())

# SIMBAD
simbad_types = get_simbad_labels("old_and_new")
simbad_types = sorted(simbad_types, key=lambda s: s.lower())

# Fink
fink_classes = [
    # "Anomaly",
    "Unknown",
    # Fink derived classes
    # "Early SN Ia candidate",
    # "SN candidate",
    # "Kilonova candidate",
    # "Microlensing candidate",
    # "Solar System MPC",
    # "Solar System candidate",
    # "Tracklet",
    # "Ambiguous",
    # "(CTA) Blazar",
    # TNS classified data
    *["(TNS) " + t for t in tns_types],
    # Simbad crossmatch
    *["(SIMBAD) " + t for t in simbad_types],
]
