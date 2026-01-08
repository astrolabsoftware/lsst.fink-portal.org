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


def is_packed_designation(name: str) -> bool:
    """Check if the name is a packed provisional designation

    Notes
    -----
    https://minorplanetcenter.net/iau/info/PackedDes.html

    Parameters
    ----------
    name: str
        SSO name

    Returns
    -------
    out: bool
        True if the name corresponds to a provisional packed
        designation. False otherwise.

    Examples
    --------
    >>> is_packed_designation("K04P97S")
    True

    >>> is_packed_designation("Z04P97S")
    False

    >>> is_packed_designation("2004 PS97")
    False
    """
    assert isinstance(name, str), "SSO name should be a string!"

    c_start = name[0] in ["I", "J", "K"]
    c_length = len(name) == 7
    c_packed = " " not in name

    return c_start & c_length & c_packed
