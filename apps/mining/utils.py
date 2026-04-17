# Copyright 2025-2026 AstroLab Software
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
import json
import logging
from datetime import date

import requests
import pandas as pd

from apps.utils import query_and_order_statistics


CONV = {
    "float": 4,
    "double": 8,
    "int": 4,
    "long": 8,
    "string": 8,
    "bytes": 3 * 4 * 40 * 40,
    "boolean": 1,
    "long": 8,
}

FILTERS_AND_BLOCKS_YIELD = {item['name']:item['yield'] for item in pd.read_csv("assets/filters_and_blocks_yield.csv").to_dict(orient='records')}


def upload_file_hdfs(code, webhdfs, namenode, user, filename):
    """Upload a file to HDFS

    Parameters
    ----------
    code: str
        Code as string
    webhdfs: str
        Location of the code on webHDFS in the format
        http://<IP>:<PORT>/webhdfs/v1/<path>
    namenode: str
        Namenode and port in the format
        <IP>:<PORT>
    user: str
        User name in HDFS
    filename: str
        Name on the file to be created

    Returns
    -------
    status_code: int
        HTTP status code. 201 is a success.
    text: str
        Additional information on the query (log).
    """
    try:
        response = requests.put(
            f"{webhdfs}/{filename}?op=CREATE&user.name={user}&namenoderpcaddress={namenode}&createflag=&createparent=true&overwrite=true",
            data=code,
        )
        status_code = response.status_code
        text = response.text
    except (requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
        status_code = -1
        text = e

    if status_code != 201:
        logging.warning(f"Status code: {status_code}")
        logging.warning(f"Log: {text}")

    return status_code, text


def submit_spark_job(livyhost, filename, spark_conf, job_args):
    """Submit a job on the Spark cluster via Livy (batch mode)

    Parameters
    ----------
    livyhost: str
        IP:HOST for the Livy service
    filename: str
        Path on HDFS with the file to submit. Format:
        hdfs://<path>/<filename>
    spark_conf: dict
        Dictionary with Spark configuration
    job_args: list of str
        Arguments for the Spark job in the form
        ['-arg1=val1', '-arg2=val2', ...]

    Returns
    -------
    batchid: int
        The number of the submitted batch
    response.status_code: int
        HTTP status code
    response.text: str
        Payload
    """
    headers = {"Content-Type": "application/json"}

    data = {
        "conf": spark_conf,
        "file": filename,
        "args": job_args,
    }
    response = requests.post(
        "http://" + livyhost + "/batches",
        data=json.dumps(data),
        headers=headers,
    )

    batchid = response.json()["id"]

    if response.status_code != 201:
        logging.warning(f"Batch ID {batchid}")
        logging.warning(f"Status code: {response.status_code}")
        logging.warning(f"Log: {response.text}")

    return batchid, response.status_code, response.text


def estimate_size_gb_lsst(content, blocks, all_lsst_fields, all_fink_fields):
    """Estimate the size of the data to download

    Parameters
    ----------
    content: list
        List of selected alert fields
    blocks: list
        List of selected blocks

    Returns
    -------
    sizeGb: int
    max_size: int
    """
    if content is None:
        return 0

    precomputed = {
        "sso": {
            "Full packet": 60.0 / 1024 / 1024,
            "Medium packet": 3.0 / 1024 / 1024,
            "Light SSO packet": 1.7 / 1024 / 1024,
            "history_factor": 1.0,
        },
        "static": {
            "Full packet": 176.0 / 1024 / 1024,
            "Medium packet": 123.0 / 1024 / 1024,
            "Light static packet": 1.7 / 1024 / 1024,
            "history_factor": 100.0
        },
        "mix": {
            "Full packet": 137.0 / 1024 / 1024,
            "Medium packet": 80.0 / 1024 / 1024,
            "Light static packet": 1.7 / 1024 / 1024,
            "Light SSO packet": 1.7 / 1024 / 1024,
            "history_factor": 75.0
        }
    }

    flavor = None
    if "Full packet" in content:
        flavor = "Full packet"
    elif "Medium packet" in content:
        flavor = "Medium packet"
    if "Light SSO packet" in content:
        flavor = "Light SSO packet"
    if "Light static packet" in content:
        flavor = "Light static packet"

    if "b_is_solar_system" in blocks:
        # pure sso sample
        kind = "sso"
    elif "NOT b_is_solar_system" in blocks:
        # pure static sample
        kind = "static"
    else:
        kind = "mix"

    if flavor is not None:
        sizeGb = precomputed.get(kind, {}).get(flavor, 0)
    else:
        # freedom on fields
        sizeB = 0
        for k in content:
            if k in all_lsst_fields:
                if k.startswith("prvDiaSources"):
                    # Account for history length
                    sizeB += precomputed[kind]["history_factor"] * CONV[all_lsst_fields[k]]
                else:
                    sizeB += CONV[all_lsst_fields[k]]
            elif k == "diaSource":
                sizeB += 0.5 * 1024
            elif k == "prvDiaSources" and kind in ["static", "mix"]:
                sizeB += 116 * 1024 * precomputed[kind]["history_factor"] / 100.
            elif k == "prvDiaForcedSources" and kind in ["static", "mix"]:
                sizeB += 1024 * precomputed[kind]["history_factor"] / 100.
            elif k == "diaObject" and kind in ["static", "mix"]:
                sizeB += 0.3 * 1024
            elif k == "mpc_orbits" and kind in ["sso", "mix"]:
                sizeB += 0.3 * 1024
            elif k == "ssSource" and kind in ["sso", "mix"]:
                sizeB += 0.3 * 1024
            elif k in all_fink_fields:
                sizeB += CONV[all_fink_fields[k]]

        sizeGb = sizeB / 1024 / 1024 / 1024

    return sizeGb, precomputed[kind]["Full packet"]


def initialise_classes(class_select):
    """Add classes selected by the user

    Parameters
    ----------
    class_select: list, optional
        List of classes selected by the user.
        None is not class selected.

    Returns
    -------
    columns: str
        Comma-separated names of classes
    column_classes: list
        List of classes. Empty list if no class selected.
    """
    column_names = []
    columns = "f:alerts"
    if (class_select is not None) and (class_select != []):
        for elem in class_select:
            if elem.startswith("(TNS)"):
                continue

            # name correspondance
            if elem.startswith("(SIMBAD)"):
                elem = elem.replace("(SIMBAD) ", "class:")
            else:
                # prepend class:
                elem = "class:" + elem
            columns += f",{elem}"
            column_names.append(elem)

    return columns, column_names


def get_statistics(dstart, dstop):
    """ """
    dic = {"f:alerts": 0}

    # Get total number of alerts for the period
    pdf = query_and_order_statistics(
        drop=False,
    )

    f1 = pdf["f:night"] <= int(dstop.strftime("%Y%m%d"))
    f2 = pdf["f:night"] >= int(dstart.strftime("%Y%m%d"))

    pdf = pdf[f1 & f2]
    dic["f:alerts"] += int(pdf["f:alerts"].sum())

    return dic


# def add_tns_estimation(dic, class_select):
#     """Add estimation for TNS classes

#     TNS statistics is not pushed in /statistics
#     """
#     if "allclasses" not in class_select:
#         for elem in class_select:
#             # name correspondance
#             if elem.startswith("(TNS)"):
#                 filt = coeffs_per_class["fclass"] == elem

#                 if np.sum(filt) == 0:
#                     # Nothing found. This could be because we have
#                     # no alerts from this class, or because it has not
#                     # yet entered the statistics. To be conservative,
#                     # we do not apply any coefficients.
#                     dic[elem] = 0
#                 else:
#                     dic[elem.replace("(TNS) ", "class:")] = int(
#                         dic["basic:sci"] * coeffs_per_class[filt]["coeff"].to_numpy()[0]
#                     )

#     return dic


# def get_tag_statistics(dic, tag_select):
#     """Get stastitics based on a user-defined filter

#     Parameters
#     ----------
#     dic: dict
#         Dictionnary containing counts
#     tag_select: str, optional
#         Filter name
#     """
#     id_ = coeffs_per_filters["filter"] == tag_select
#     if np.sum(id_) == 1:
#         dic[tag_select] = (
#             coeffs_per_filters[id_]["coeff"].to_numpy()[0] * dic["basic:sci"]
#         )

#     return dic


def estimate_alert_number_lsst(date_range_picker, tags, blocks):
    """Callback to estimate the number of alerts to be transfered

    Notes
    -----
    This can be improved by using the REST API directly to get number of
    alerts per class.
    """
    # FIXME: for the moment, not filtering
    dstart = date(*[int(i) for i in date_range_picker[0].split("-")])
    dstop = date(*[int(i) for i in date_range_picker[1].split("-")])

    dic = get_statistics(dstart, dstop)

    total = dic["f:alerts"]
    count = dic["f:alerts"]
    if isinstance(tags, list) and len(tags) > 0:
        for tag in tags:
            # is it negation?
            is_not = "NOT " in tag
            if tag in FILTERS_AND_BLOCKS_YIELD.keys():
                count *= FILTERS_AND_BLOCKS_YIELD[tag]
            elif is_not:
                not_tag = tag.split("NOT ")[1].strip()
                if not_tag in FILTERS_AND_BLOCKS_YIELD.keys():
                    count *= (1 - FILTERS_AND_BLOCKS_YIELD[not_tag])

    if isinstance(blocks, list) and len(blocks) > 0:
        for block in blocks:
            # is it negation?
            is_not = "NOT " in block
            if block in FILTERS_AND_BLOCKS_YIELD.keys():
                count *= FILTERS_AND_BLOCKS_YIELD[block]
            elif is_not:
                not_block = block.split("NOT ")[1].strip()
                if not_block in FILTERS_AND_BLOCKS_YIELD.keys():
                    count *= (1 - FILTERS_AND_BLOCKS_YIELD[not_block])

    return total, count
