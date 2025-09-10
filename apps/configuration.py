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
"""Utility to load the configuration file"""
import yaml


def extract_configuration(filename):
    """Extract user defined configuration

    Parameters
    ----------
    filename: str
        Full path to the `config.yml` file.

    Returns
    -------
    out: dict
        Dictionary with user defined values.
    """
    config = yaml.load(open("config.yml"), yaml.Loader)
    if config["HOST"].endswith(".org"):
        config["SITEURL"] = "https://" + config["HOST"]
    else:
        config["SITEURL"] = "http://" + config["HOST"] + ":" + str(config["PORT"])
    return config
