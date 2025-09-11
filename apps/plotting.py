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
from dash import Output, Input, no_update, clientside_callback, State
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

import io
import gzip
from astropy.io import fits
from copy import deepcopy

from app import app

from astropy.visualization import AsymmetricPercentileInterval, simple_norm

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from astropy.time import Time
from dash import (
    dcc, html
)
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

import nifty_ls  # noqa: F401


# from apps import __file__
from apps.api import request_api
from apps.utils import convert_time
from apps.utils import flux_to_mag
from apps.utils import loading

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

default_radio_options = ["Total flux", "Difference flux", "Magnitude"]
all_radio_options = {v: default_radio_options for v in default_radio_options}

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
    pdf_ = pd.read_json(io.StringIO(object_data))

    if time0 is None:
        position = 0
    else:
        pdf_ = pdf_.sort_values("i:midpointMjdTai", ascending=False)
        # Round to avoid numerical precision issues
        mjds = pdf_["i:midpointMjdTai"].apply(lambda x: np.round(x, 3)).to_numpy()
        mjd0 = np.round(Time(time0, format="iso").mjd, 3)
        if mjd0 in mjds:
            position = np.where(mjds == mjd0)[0][0]
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
        paper_bgcolor="#f0f0f0",
        plot_bgcolor="#f0f0f0",
    )

    fig.update_layout(width=shape[1], height=shape[0])
    fig.update_layout(yaxis={"scaleanchor": "x", "scaleratio": 1})

    style = {"display": "block", "aspect-ratio": "1", "margin": "1px"}
    classname = "zoom"
    classname = ""

    pixel_size = 0.2 # arcsec/pixel

    # graph = html.Div(
    #     [
    #         dcc.Graph(
    #             id={"type": id_type, "id": title} if zoom else "undefined",
    #             figure=fig,
    #             style=style,
    #             config={"displayModeBar": False},
    #             className=classname,
    #             responsive=True,
    #         ),
    #         dmc.Center(
    #             # dbc.Badge(
    #             #     "{} pixels / {}''".format(shape[0], shape[0] * pixel_size),
    #             #     color="light",
    #             #     pill=True,
    #             #     text_color="dark",
    #             # ),
    #             dmc.Badge(
    #                 "{} pixels / {}''".format(shape[0], shape[0] * pixel_size),
    #                 color="gray",
    #                 variant="outline",
    #                 size="md",
    #                 # pill=True,
    #                 # text_color="dark",
    #             ),
    #         )
    #     ]
    # )
    graph = dmc.Indicator(
        dcc.Graph(
            id={"type": id_type, "id": title} if zoom else "undefined",
            figure=fig,
            style=style,
            config={"displayModeBar": False},
            className=classname,
            responsive=True,
        ),
        color="blue",
        variant="outline",
	    position="bottom-center",
        size=16,
        label="{}px / {:.1f}''".format(shape[0], shape[0] * pixel_size),
    )

    return graph


@app.callback(
    Output("stamps", "children"),
    [
        Input("lightcurve_object_page", "clickData"),
        Input("object-data", "data"),
    ],
    prevent_initial_call=True,
)
def draw_cutouts(clickData, object_data):
    """Draw cutouts data based on lightcurve data"""
    if clickData is not None:
        jd0 = clickData["points"][0]["x"]
    else:
        jd0 = None

    figs = []
    for kind in ["science", "template", "difference"]:
        try:
            cutout = extract_cutout(object_data, jd0, kind=kind)
            if cutout is None:
                return no_update

            data = draw_cutout(cutout, kind)
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")

        figs.append(
            dbc.Col(
                data,
                xs=4,
                className="p-0",
            ),
        )

    return figs


@app.callback(
    Output("stamps_modal_content", "children"),
    [
        Input("object-data", "data"),
        Input("date_modal_select", "value"),
        Input("stamps_modal", "is_open"),
    ],
    prevent_initial_call=True,
)
def draw_cutouts_modal(object_data, date_modal_select, is_open):
    """Draw cutouts data based on lightcurve data"""
    if not is_open:
        raise PreventUpdate

    figs = []
    for kind in ["science", "template", "difference"]:
        try:
            cutout = extract_cutout(object_data, date_modal_select, kind=kind)
            if cutout is None:
                return no_update
            data = draw_cutout(cutout, kind, id_type="stamp_modal")
        except OSError:
            data = dcc.Markdown("Load fail, refresh the page")

        figs.append(
            dbc.Col(
                [
                    html.Div(kind.capitalize(), className="text-center"),
                    data,
                ],
                xs=4,
                className="p-0",
            ),
        )

    return figs

def make_modal_stamps(pdf):
    dates = convert_time(pdf["i:midpointMjdTai"].to_numpy(), format_in="mjd", format_out="iso")
    return [
        dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:chevron-left"),
                            id="stamps_prev",
                            # title="Next alert",
                            n_clicks=0,
                            variant="default",
                            size=36,
                            color="gray",
                            className="me-1",
                        ),
                        dmc.Select(
                            label="",
                            placeholder="Select a date",
                            searchable=True,
                            nothingFoundMessage="No options found",
                            id="date_modal_select",
                            value=dates[0],
                            data=[
                                {"value": i, "label": i}
                                for i in dates
                            ],
                            style={"z-index": 10000000},
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:chevron-right"),
                            id="stamps_next",
                            # title="Previous alert",
                            n_clicks=0,
                            variant="default",
                            size=36,
                            color="gray",
                            className="ms-1",
                        ),
                    ],
                    close_button=True,
                    className="p-2 pe-4",
                ),
                loading(
                    dbc.ModalBody(
                        [
                            dbc.Row(
                                id="stamps_modal_content",
                                justify="around",
                                className="g-0 mx-auto",
                            ),
                        ],
                    )
                ),
            ],
            id="stamps_modal",
            scrollable=True,
            centered=True,
            size="xl",
            # style={'max-width': '800px'}
        ),
        dmc.Center(
            dmc.ActionIcon(
                DashIconify(icon="tabler:arrows-maximize"),
                id="maximise_stamps",
                n_clicks=0,
                variant="default",
                radius=30,
                size=36,
                color="gray",
            ),
        ),
    ]


# Toggle stamps modal
clientside_callback(
    """
    function toggle_stamps_modal(n_clicks, is_open) {
        return !is_open;
    }
    """,
    Output("stamps_modal", "is_open"),
    Input("maximise_stamps", "n_clicks"),
    State("stamps_modal", "is_open"),
    prevent_initial_call=True,
)

# Prev/Next for stamps modal
clientside_callback(
    """
    function stamps_prev_next(n_clicks_prev, n_clicks_next, clickData, value, data) {
        let id = data.findIndex((x) => x.value === value);
        let step = 1;

        const triggered = dash_clientside.callback_context.triggered.map(t => t.prop_id);

        if (triggered == 'lightcurve_object_page.clickData')
            return clickData.points[0].x;

        if (triggered == 'stamps_prev.n_clicks')
            step = -1;

        id += step;
        if (step > 0 && id >= data.length)
            id = 0;
        if (step < 0 && id < 0)
            id = data.length - 1;

        return data[id].value;
    }
    """,
    Output("date_modal_select", "value"),
    [
        Input("stamps_prev", "n_clicks"),
        Input("stamps_next", "n_clicks"),
        Input("lightcurve_object_page", "clickData"),
    ],
    State("date_modal_select", "value"),
    State("date_modal_select", "data"),
    prevent_initial_call=True,
)

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
        "i:scienceFlux",
        "i:scienceFluxErr",
        "i:band",
    ]
    pdf = request_api(
        "/api/v1/sources",
        json={
            "diaObjectId": str(name),
            "columns": ",".join(cols),
            "output-format": "json",
        },
    )

    # type conversion
    dates = convert_time(pdf["i:midpointMjdTai"], format_in="mjd", format_out="iso")

    # Should we correct DC magnitudes for the nearby source?..
    # is_dc_corrected = is_source_behind(pdf["i:distnr"].to_numpy()[0])

    # shortcuts -- in milliJansky
    flux = pdf["i:scienceFlux"] * 1e-3
    flux_err = pdf["i:scienceFluxErr"] * 1e-3

    # We should never modify global variables!!!
    layout = dict(
        automargin=True,
        margin=dict(l=50, r=0, b=0, t=0),
        hovermode="closest",
        plot_bgcolor="white",
        paper_bgcolor="white",
        hoverlabel={
            "align": "left",
        },
        legend=dict(
            font=dict(size=10),
            orientation="h",
            xanchor="right",
            x=1,
            y=0.95,
            bgcolor="rgba(218, 223, 225, 0.8)",
        ),
        xaxis={
            "title": "Observation date",
            "automargin": True,
        },
        yaxis={
            # "autorange": "reversed",
            "title": "Total flux (milliJansky)",
            "automargin": True,
        },
    )

    layout["showlegend"] = True
    layout["shapes"] = []

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

    sparklines = []
    for fid, fname, color, color_negative in (
        (1, "u", COLORS_LSST[0], COLORS_LSST_NEGATIVE[0]),
        (2, "g", COLORS_LSST[1], COLORS_LSST_NEGATIVE[1]),
        (3, "r", COLORS_LSST[2], COLORS_LSST_NEGATIVE[2]),
        (4, "i", COLORS_LSST[3], COLORS_LSST_NEGATIVE[3]),
        (5, "z", COLORS_LSST[4], COLORS_LSST_NEGATIVE[4]),
        (6, "y", COLORS_LSST[5], COLORS_LSST_NEGATIVE[5]),
    ):
        idx = pdf["i:band"] == fname

        if not np.sum(idx):
            continue

        figure["data"].append(
            {
                "x": dates[idx],
                "y": flux[idx],
                "error_y": {
                    "type": "data",
                    "array": flux_err[idx],
                    "visible": True,
                    "width": 0,
                    "color": color,  # It does not support arrays of colors so let's use positive one for all points
                    "opacity": 0.5,
                },
                "mode": "markers",
                "name": f"{fname}",
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

        # Daily average
        # In [8]: pdf.groupby(pdf["i:midpointMjdTai"].apply(lambda x: Time(x, format="mjd", scale="ta
        # ...: i").datetime).dt.strftime('%b %Y %m'))["i:scienceFlux"].mean().reset_index(name='Daily
        # ...: Average')

        if len(flux[idx]) > 1:
            axis_name = "{} band".format(fname)
            sparklines.append(
                dmc.Stack(
                    [
                        dmc.Text(axis_name),
                        sparklines.append(make_sparkline(flux[idx][::-1]))
                    ],
                    gap="xs",
                )
            )

    return figure, sparklines


def make_sparkline(data):
    return dmc.Sparkline(
        w=100,
        h=30,
        data=data,
        curveType="monotone",
        trendColors={"positive": "teal.6", "negative": "red.6", "neutral": "gray.5"},
        fillOpacity=0.2,
    )


@app.callback(
    Output("lightcurve_object_page", "figure"),
    [
        Input("switch-mag-flux", "value"),
        Input("object-data", "data"),
        Input("lightcurve_show_color", "checked"),
    ],
    prevent_initial_call=True,
)
def draw_lightcurve(
    switch: int,
    object_data,
    show_color,
) -> dict:
    """Draw object lightcurve with errorbars

    Parameters
    ----------
    switch: int
        Choose:
          - 0 to display Total Flux
          - 1 to display Difference Flux
          - 2 to display Magnitude

    Returns
    -------
    figure: dict
    """
    # Primary high-quality data points
    pdf = pd.read_json(io.StringIO(object_data))

    # date type conversion
    dates = convert_time(pdf["i:midpointMjdTai"], format_in="mjd", format_out="iso")

    # We should never modify global variables!!!
    layout = dict(
        autosize=True,
        automargin=True,
        margin=dict(l=50, r=30, b=0, t=0),
        hovermode="closest",
        hoverlabel={
            "align": "left",
        },
        legend=dict(
            font=dict(size=10),
            orientation="h",
            xanchor="right",
            x=1,
            yanchor="bottom",
            y=1.02,
            bgcolor="rgba(218, 223, 225, 0.3)",
        ),
        xaxis={
            "title": "Observation date",
            "automargin": True,
            "zeroline": False,
        },
        yaxis={
            "title": "Total flux (mJy)",
            "automargin": True,
            "zeroline": False,
        },
    )

    if switch == "Magnitude":
        # Using same names as others despite being magnitudes
        flux, flux_err = flux_to_mag(pdf["i:scienceFlux"], pdf["i:scienceFluxErr"])
        layout["yaxis"]["title"] = "Magnitude"
        layout["yaxis"]["autorange"] = "reversed"
        scale = 1.0
    elif switch == "Difference flux":
        # shortcuts
        flux = pdf["i:psfFlux"]
        flux_err = pdf["i:psfFluxErr"]

        layout["yaxis"]["title"] = "Difference flux (milliJansky)"
        layout["yaxis"]["autorange"] = True
        scale = 1e-3
    elif switch == "Total flux":
        # shortcuts
        flux = pdf["i:scienceFlux"]
        flux_err = pdf["i:scienceFluxErr"]

        layout["yaxis"]["title"] = "Total flux (milliJansky)"
        layout["yaxis"]["autorange"] = True
        scale = 1e-3

    layout["showlegend"] = True
    layout["shapes"] = []

    layout["paper_bgcolor"] = "#f0f0f0"
    layout["plot_bgcolor"] = "#f0f0f0"

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
        (6, "y", COLORS_LSST[5], COLORS_LSST_NEGATIVE[5]),
    ):
        # High-quality measurements
        hovertemplate = r"""
        <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata[0]}
        <extra></extra>
        """
        idx = pdf["i:band"] == fname
        figure["data"].append(
            {
                "x": dates[idx],
                "y": flux[idx] * scale,
                "error_y": {
                    "type": "data",
                    "array": flux_err[idx] * scale,
                    "visible": True,
                    "width": 0,
                    "opacity": 0.5,
                    "color": color,
                },
                "mode": "markers",
                "name": f"{fname} band",
                "customdata": np.stack(
                    (
                        pdf["i:midpointMjdTai"][idx],
                    ),
                    axis=-1,
                ),
                "hovertemplate": hovertemplate,
                "legendgroup": f"{fname} band",
                "legendrank": 100 + 10 * fid,
                "marker": {
                    "size": 12,
                    "color": flux[idx].apply(
                        lambda x,
                        color_negative=color_negative,
                        color=color: color_negative if x < 0 else color
                    ),
                    "symbol": "o",
                },
            },
        )

    return figure