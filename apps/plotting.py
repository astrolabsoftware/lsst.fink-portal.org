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
import io
import gzip
from astropy.io import fits
from copy import deepcopy

from astropy.visualization import AsymmetricPercentileInterval, simple_norm

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from astropy.time import Time
from dash import (
    dcc,
)
import nifty_ls  # noqa: F401


# from apps import __file__
from apps.api import request_api
from apps.utils import convert_time

# FIXME
COLORS_LSST = ["#15284F", "#F5622E", "#15284F", "#F5622E", "#15284F", "#F5622E"]
COLORS_LSST_NEGATIVE = [
    "#274667",
    "#F57A2E",
    "#274667",
    "#F57A2E",
    "#274667",
    "#F57A2E",
]

layout_lightcurve_preview = dict(
    automargin=True,
    margin=dict(l=50, r=0, b=0, t=0),
    hovermode="closest",
    hoverlabel={
        "align": "left",
    },
    legend=dict(
        font=dict(size=10),
        orientation="h",
        xanchor="right",
        x=1,
        y=1.2,
        bgcolor="rgba(218, 223, 225, 0.3)",
    ),
    xaxis={
        "title": "Observation date",
        "automargin": True,
    },
    yaxis={
        # "autorange": "reversed",
        "title": "Flux (nJy)",
        "automargin": True,
    },
)


def draw_cutouts_quickview(name, kinds=None):
    """Draw Science cutout data for the preview service"""
    if kinds is None:
        kinds = ["science"]
    figs = []
    for kind in kinds:
        try:  # noqa: PERF203
            # We may manually construct the payload to avoid extra API call
            object_data = f'{{"i:diaObjectId":{{"0": "{name}"}}}}'
            data = extract_cutout(object_data, None, kind=kind)
            figs.append(draw_cutout(data, kind, zoom=False))
        except OSError:  # noqa: PERF203
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
    return figs


def extract_cutout(object_data, time0, kind):
    """Extract cutout data from the alert

    Parameters
    ----------
    object_data: json
        Jsonified pandas DataFrame
    time0: str
        ISO time of the cutout to extract
    kind: str
        science, template, or difference

    Returns
    -------
    data: np.array
        2D array containing cutout data
    """
    pdf_ = pd.read_json(io.StringIO(object_data), dtype=np.int64)

    if time0 is None:
        position = 0
    else:
        pdf_ = pdf_.sort_values("i:midpointMjdTai", ascending=False)
        # Round to avoid numerical precision issues
        jds = pdf_["i:midpointMjdTai"].apply(lambda x: np.round(x, 3)).to_numpy()
        jd0 = np.round(Time(time0, format="iso").jd, 3)
        if jd0 in jds:
            position = np.where(jds == jd0)[0][0]
        else:
            return None

    # Construct the query
    payload = {
        "diaObjectId": str(pdf_["i:diaObjectId"].to_numpy()[0]),
        "kind": kind.capitalize(),
        "output-format": "FITS",
    }

    if position > 0 and "i:diaSourceId" in pdf_.columns:
        payload["diaSourceId"] = str(pdf_["i:diaSourceId"].to_numpy()[position])

    # Extract the cutout data
    print(payload)
    r = request_api(
        "/api/v1/cutouts",
        json=payload,
        output="raw",
    )

    cutout = readstamp(r, gzipped=False)

    # FIXME: not required for Rubin?
    # if (
    #     kind == "difference"
    #     and "i:isdiffpos" in pdf_.columns
    #     and pdf_["i:isdiffpos"].to_numpy()[position] == "f"
    # ):
    #     # Negative event, let's invert the diff cutout
    #     cutout *= -1

    return cutout


def draw_cutout(data, title, lower_bound=0, upper_bound=1, zoom=True, id_type="stamp"):
    """Draw a cutout data"""
    # Update graph data for stamps
    data = np.nan_to_num(data)

    # data = sigmoid_normalizer(data, lower_bound, upper_bound)
    data = plain_normalizer(
        data,
        lower_bound,
        upper_bound,
        stretch="linear" if title in ["difference"] else "asinh",
        pmin=0.5,
        pmax=99.95,
    )

    data = data[::-1]
    # data = convolve(data, smooth=1, kernel='gauss')
    shape = data.shape

    zsmooth = False

    fig = go.Figure(
        data=go.Heatmap(
            z=data,
            showscale=False,
            hoverinfo="skip",
            colorscale="Blues_r",
            zsmooth=zsmooth,
        ),
    )
    # Greys_r

    axis_template = dict(
        autorange=True,
        showgrid=False,
        zeroline=False,
        linecolor="black",
        showticklabels=False,
        ticks="",
        range=[0, 60],
    )

    fig.update_layout(
        title=title,
        margin=dict(t=0, r=0, b=0, l=0),
        xaxis=axis_template,
        yaxis=axis_template,
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(width=shape[1], height=shape[0])
    fig.update_layout(yaxis={"scaleanchor": "x", "scaleratio": 1})

    style = {"display": "block", "aspect-ratio": "1", "margin": "1px"}
    classname = "zoom"
    classname = ""

    graph = dcc.Graph(
        id={"type": id_type, "id": title} if zoom else "undefined",
        figure=fig,
        style=style,
        config={"displayModeBar": False},
        className=classname,
        responsive=True,
    )

    return graph


def readstamp(stamp: str, return_type="array", gzipped=True) -> np.array:
    """Read the stamp data inside an alert.

    Parameters
    ----------
    stamp: str
        String containing binary data for the stamp
    return_type: str
        Data block of HDU 0 (`array`) or original FITS uncompressed (`FITS`) as file-object.
        Default is `array`.

    Returns
    -------
    data: np.array
        2D array containing image data (`array`) or FITS file uncompressed as file-object (`FITS`)
    """

    def extract_stamp(fitsdata):
        with fits.open(fitsdata, ignore_missing_simple=True) as hdul:
            if return_type == "array":
                data = hdul[0].data
            elif return_type == "FITS":
                data = io.BytesIO()
                hdul.writeto(data)
                data.seek(0)
        return data

    if not isinstance(stamp, io.BytesIO):
        stamp = io.BytesIO(stamp)

    if gzipped:
        with gzip.open(stamp, "rb") as f:
            return extract_stamp(io.BytesIO(f.read()))
    else:
        return extract_stamp(stamp)


def plain_normalizer(
    img: list, vmin: float, vmax: float, stretch="linear", pmin=0.5, pmax=99.5
) -> list:
    """Image normalisation between vmin and vmax

    Parameters
    ----------
    img: float array
        a float array representing a non-normalized image

    Returns
    -------
    out: float array where data are bounded between vmin and vmax
    """
    limits = np.percentile(img, [pmin, pmax])
    data = _data_stretch(
        img, vmin=limits[0], vmax=limits[1], stretch=stretch, vmid=0.1, exponent=2
    )
    data = (vmax - vmin) * data + vmin

    return data


def _data_stretch(
    image,
    vmin=None,
    vmax=None,
    pmin=0.25,
    pmax=99.75,
    stretch="linear",
    vmid: float = 10,
    exponent=2,
):
    """Hacked from aplpy"""
    if vmin is None or vmax is None:
        interval = AsymmetricPercentileInterval(pmin, pmax, n_samples=10000)
        try:
            vmin_auto, vmax_auto = interval.get_limits(image)
        except IndexError:  # no valid values
            vmin_auto = vmax_auto = 0

    if vmin is None:
        # log.info("vmin = %10.3e (auto)" % vmin_auto)
        vmin = vmin_auto
    else:
        pass
        # log.info("vmin = %10.3e" % vmin)

    if vmax is None:
        # log.info("vmax = %10.3e (auto)" % vmax_auto)
        vmax = vmax_auto
    else:
        pass
        # log.info("vmax = %10.3e" % vmax)

    if stretch == "arcsinh":
        stretch = "asinh"

    normalizer = simple_norm(
        image,
        stretch=stretch,
        power=exponent,
        asinh_a=vmid,
        min_cut=vmin,
        max_cut=vmax,
        clip=False,
    )

    data = normalizer(image, clip=True).filled(0)
    data = np.nan_to_num(data)
    # data = np.clip(data * 255., 0., 255.)

    return data  # .astype(np.uint8)


def draw_lightcurve_preview(name) -> dict:
    """Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Returns
    -------
    figure: dict
    """
    cols = [
        "i:midpointMjdTai",
        "i:psfFlux",
        "i:psfFluxErr",
        "i:band",
        # "i:distnr",
        # "i:magnr",
        # "i:sigmagnr",
        # "d:tag",
    ]
    pdf = request_api(
        "/api/v1/sources",
        json={
            "diaObjectId": str(name),
            # "withupperlim": "True",
            "columns": ",".join(cols),
            "output-format": "json",
        },
    )

    # Mask upper-limits (but keep measurements with bad quality)
    mag_ = pdf["i:psfFlux"]
    mask = ~np.isnan(mag_)
    pdf = pdf[mask]

    # type conversion
    dates = convert_time(pdf["i:midpointMjdTai"], format_in="mjd", format_out="iso")

    # shortcuts
    mag = pdf["i:psfFlux"]
    err = pdf["i:psfFluxErr"]

    # Should we correct DC magnitudes for the nearby source?..
    # is_dc_corrected = is_source_behind(pdf["i:distnr"].to_numpy()[0])

    # We should never modify global variables!!!
    layout = deepcopy(layout_lightcurve_preview)

    # layout["yaxis"]["title"] = "Difference magnitude"
    # layout["yaxis"]["autorange"] = "reversed"
    layout["paper_bgcolor"] = "rgba(0,0,0,0.0)"
    layout["plot_bgcolor"] = "rgba(0,0,0,0.2)"
    layout["showlegend"] = False
    layout["shapes"] = []

    # if is_dc_corrected:
    #     # inplace replacement for DC corrected flux
    #     mag, err = np.transpose(
    #         [
    #             dc_mag(*args)
    #             for args in zip(
    #                 mag.astype(float).to_numpy(),
    #                 err.astype(float).to_numpy(),
    #                 pdf["i:magnr"].astype(float).to_numpy(),
    #                 pdf["i:sigmagnr"].astype(float).to_numpy(),
    #                 pdf["i:isdiffpos"].to_numpy(),
    #             )
    #         ],
    #     )
    #     # Keep only "good" measurements
    #     idx = err < 1
    #     pdf, dates, mag, err = (_[idx] for _ in [pdf, dates, mag, err])

    #     layout["yaxis"]["title"] = "Apparent DC magnitude"

    # hovertemplate = r"""
    # <b>%{yaxis.title.text}%{customdata[2]}</b>: %{customdata[1]}%{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    # <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    # <b>mjd</b>: %{customdata[0]}
    # <extra></extra>
    # """
    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
    <b>mjd</b>: %{customdata[0]}
    <extra></extra>
    """
    figure = {
        "data": [],
        "layout": layout,
    }

    for fid, fname, color, color_negative in (
        (1, "u", COLORS_LSST[0], COLORS_LSST_NEGATIVE[0]),
        (2, "g", COLORS_LSST[1], COLORS_LSST_NEGATIVE[1]),
        (3, "r", COLORS_LSST[2], COLORS_LSST_NEGATIVE[2]),
        (4, "i", COLORS_LSST[3], COLORS_LSST_NEGATIVE[3]),
        (5, "z", COLORS_LSST[4], COLORS_LSST_NEGATIVE[4]),
        (6, "y", COLORS_LSST[5], COLORS_LSST_NEGATIVE[4]),
    ):
        idx = pdf["i:band"] == fname

        if not np.sum(idx):
            continue

        # figure["data"].append(
        #     {
        #         "x": dates[idx],
        #         "y": mag[idx],
        #         "error_y": {
        #             "type": "data",
        #             "array": err[idx],
        #             "visible": True,
        #             "width": 0,
        #             "color": color,  # It does not support arrays of colors so let's use positive one for all points
        #             "opacity": 0.5,
        #         },
        #         "mode": "markers",
        #         "name": f"{fname} band",
        #         "customdata": np.stack(
        #             (
        #                 pdf["i:midpointMjdTai"][idx],
        #                 pdf["i:isdiffpos"].apply(lambda x: "(-) " if x == "f" else "")[
        #                     idx
        #                 ],
        #                 pdf["d:tag"].apply(
        #                     lambda x: "" if x == "valid" else " (low quality)"
        #                 )[idx],
        #             ),
        #             axis=-1,
        #         ),
        #         "hovertemplate": hovertemplate,
        #         "marker": {
        #             "size": pdf["d:tag"].apply(lambda x: 12 if x == "valid" else 6)[
        #                 idx
        #             ],
        #             "color": pdf["i:isdiffpos"].apply(
        #                 lambda x,
        #                 color_negative=color_negative,
        #                 color=color: color_negative if x == "f" else color
        #             )[idx],
        #             "symbol": pdf["d:tag"].apply(
        #                 lambda x: "o" if x == "valid" else "triangle-up"
        #             )[idx],
        #             "line": {"width": 0},
        #             "opacity": 1,
        #         },
        #     },
        # )

        figure["data"].append(
            {
                "x": dates[idx],
                "y": mag[idx],
                "error_y": {
                    "type": "data",
                    "array": err[idx],
                    "visible": True,
                    "width": 0,
                    "color": color,  # It does not support arrays of colors so let's use positive one for all points
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": f"{fname} band",
                "customdata": np.stack(
                    (pdf["i:midpointMjdTai"][idx],),
                    axis=-1,
                ),
                "hovertemplate": hovertemplate,
                "marker": {
                    "size": 12,
                    "color": color,
                    "symbol": "o",
                    "line": {"width": 0},
                    "opacity": 1,
                },
            },
        )

        # if is_dc_corrected:
        #     # Overplot the levels of nearby source magnitudes
        #     ref = np.mean(pdf["i:magnr"][idx])

        #     figure["layout"]["shapes"].append(
        #         {
        #             "type": "line",
        #             "yref": "y",
        #             "y0": ref,
        #             "y1": ref,  # adding a horizontal line
        #             "xref": "paper",
        #             "x0": 0,
        #             "x1": 1,
        #             "line": {"color": color, "dash": "dash", "width": 1},
        #             "legendgroup": f"{fname} band",
        #             "opacity": 0.3,
        #         },
        #     )

    return figure
