# Copyright 2025 AstroLab Software
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


def estimate_size_gb_lsst(content, all_lsst_fields, all_fink_fields):
    """Estimate the size of the data to download

    Parameters
    ----------
    content: list
        List of selected alert fields

    Returns
    -------
    sizeGb:
    """
    if content is None:
        return 0
    # Pre-defined schema
    if "Full packet" in content:
        # all fields
        sizeGb = 55.0 / 1024 / 1024
    elif "Light packet" in content:
        sizeGb = 1.4 / 1024 / 1024
    elif "Medium packet" in content:
        sizeGb = 18.0 / 1024 / 1024
    else:
        # freedom on candidates + added values
        sizeB = 0
        for k in content:
            if k in all_lsst_fields:
                sizeB += CONV[all_lsst_fields[k]]
            elif k in all_fink_fields:
                sizeB += CONV[all_fink_fields[k]]

        sizeGb = sizeB / 1024 / 1024 / 1024

    return sizeGb


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


def estimate_alert_number_lsst(date_range_picker, tag_select):
    """Callback to estimate the number of alerts to be transfered

    This can be improved by using the REST API directly to get number of
    alerts per class.
    """
    # FIXME: rewrite the logic for LSST
    # FIXME: for the moment, not filtering
    dstart = date(*[int(i) for i in date_range_picker[0].split("-")])
    dstop = date(*[int(i) for i in date_range_picker[1].split("-")])

    dic = get_statistics(dstart, dstop)

    # # we check first filter, and then class
    # dic = get_tag_statistics(dic, tag_select)
    # total = dic["f:alerts"]
    # count = np.sum([v for k, v in dic.items() if k != "f:alerts"])

    total = dic["f:alerts"]
    count = dic["f:alerts"]

    return total, count
