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
from dash import dcc, html, Output, Input, no_update, clientside_callback, State
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

import plotly.graph_objects as go
import plotly.colors
from plotly.subplots import make_subplots

import io
import gzip
import copy

from astropy.visualization import AsymmetricPercentileInterval, simple_norm
from astropy.coordinates import SkyCoord
from astropy.coordinates import EarthLocation
from astropy.coordinates import Latitude, Longitude
import astropy.units as u
from astropy.time import Time
from astropy.io import fits

import numpy as np
import pandas as pd

import nifty_ls  # noqa: F401


# from apps import __file__
from app import app
from apps.api import request_api
from apps.utils import convert_time
from apps.utils import flux_to_mag
from apps.utils import loading
from apps.utils import hex_to_rgba, rgb_to_rgba
import apps.observability.utils as observability


PIXEL_SIZE = 0.2  # arcsec/pixel

PAPER_BGCOLOR = "#f7f7f7"

CONFIG_PLOT = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "zoomIn2d",
        "zoomOut2d",
        "toggleSpikelines",
        "pan2d",
        "select2d",
        "lasso2d",
        "autoScale2d",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
    "toImageButtonOptions": {
        "format": "png",  # one of png, svg, jpeg, webp
        "filename": "{}",
        # 'height': 500,
        # 'width': 700,
        "scale": 1.5,  # Multiply title/legend/axis/canvas sizes by this factor
    },
}

BANDS = ["u", "g", "r", "i", "z", "y"]

DEFAULT_FINK_COLORS = ["#15284f", "#626d84", "#afb2b9", "#dbbeb2", "#e89070", "#f5622e"]

default_radio_options = ["Total flux", "Difference flux", "Magnitude"]
all_radio_options = {v: default_radio_options for v in default_radio_options}


def generate_rgb_color_sequence(color_scale: str = "Fink", n_colors: int = 6):
    """Return a list of `n_colors` based on color_scale

    Parameters
    ----------
    color_scale: str
        Name of the color scale. Can be anything from
        plotly.colors.sequential or `Fink`. Default is Fink.
    n_colors: int
        The number of colors to generate. Default is 6.
    """
    if color_scale is None or color_scale == "":
        return DEFAULT_FINK_COLORS
    if color_scale == "Fink":
        colors = DEFAULT_FINK_COLORS
    else:
        # Generate the list of colors - discrete
        colors = getattr(plotly.colors.qualitative, color_scale)[:6]

        # Same for continuous
        # colors = plotly.colors.sample_colorscale(
        #     color_scale, [i / (n_colors - 1) for i in range(n_colors)]
        # )

    return colors


def draw_cutouts_quickview(name, kinds=None):
    """Draw Science cutout data for the preview service"""
    if kinds is None:
        kinds = ["science"]
    figs = []
    sizes = []
    for kind in kinds:
        try:  # noqa: PERF203
            # We may manually construct the payload to avoid extra API call
            object_data = f'{{"r:diaSourceId":{{"0": "{name}"}}}}'
            data = extract_cutout(object_data, None, kind=kind)
            shape = data.shape
            figs.append(draw_cutout(data, kind, zoom=False))
            sizes.append("{}px / {:.1f}''".format(shape[0], shape[0] * PIXEL_SIZE))
        except OSError:  # noqa: PERF203
            data = dcc.Markdown("Load fail, refresh the page")
            figs.append(data)
            sizes.append("")
    return figs, sizes


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
    pdf_ = pd.read_json(io.StringIO(object_data), dtype={"r:diaSourceId": np.int64})

    if time0 is None:
        position = 0
    else:
        pdf_ = pdf_.sort_values("r:midpointMjdTai", ascending=False)
        # Round to avoid numerical precision issues
        mjds = pdf_["r:midpointMjdTai"].apply(lambda x: np.round(x, 3)).to_numpy()
        mjd0 = np.round(Time(time0, format="iso").mjd, 3)
        if mjd0 in mjds:
            position = np.where(mjds == mjd0)[0][0]
        else:
            return None

    # Construct the query
    payload = {
        "kind": kind.capitalize(),
        "diaSourceId": str(pdf_["r:diaSourceId"].to_numpy()[position]),
        "output-format": "FITS",
    }

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

    # Define the size and position for the reticle
    reticle_size = len(data) / 10  # Total size of the cross reticle
    inner_gap = len(data) / 12  # Size of the hole in the middle
    center = len(data) // 2 - 1  # Center index for a square image

    # Create the 'hole' in the middle by adding small squares around the center
    # Add horizontal lines for the top and bottom parts of the reticle
    fig.add_trace(
        go.Scatter(
            # x=[center - inner_gap // 2, center + inner_gap // 2],
            # y=[vertical_top, vertical_top],
            x=[center - reticle_size, center - inner_gap // 2],
            y=[center, center],
            mode="lines",
            line=dict(color="orange", width=2),  # Color matches the background
            showlegend=False,
            hoverinfo="none",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[center + inner_gap // 2, center + reticle_size],
            y=[center, center],
            mode="lines",
            line=dict(color="orange", width=2),  # Color matches the background
            showlegend=False,
            hoverinfo="none",
        )
    )

    # Add vertical lines for the left and right parts of the reticle
    fig.add_trace(
        go.Scatter(
            x=[center, center],
            y=[center - reticle_size, center - inner_gap // 2],
            mode="lines",
            line=dict(color="orange", width=2),  # Color matches the background
            showlegend=False,
            hoverinfo="none",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[center, center],
            y=[center + inner_gap // 2, center + reticle_size],
            mode="lines",
            line=dict(color="orange", width=2),  # Color matches the background
            showlegend=False,
            hoverinfo="none",
        )
    )

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
        paper_bgcolor=PAPER_BGCOLOR,
        plot_bgcolor=PAPER_BGCOLOR,
    )

    fig.update_layout(width=shape[1], height=shape[0])
    fig.update_layout(yaxis={"scaleanchor": "x", "scaleratio": 1})

    style = {"display": "block", "aspect-ratio": "1", "margin": "1px"}
    classname = "zoom"
    classname = ""

    # graph = dmc.Indicator(

    #     color="blue",
    #     variant="outline",
    #     position="bottom-center",
    #     size=16,
    #     label="{}px / {:.1f}''".format(shape[0], shape[0] * pixel_size),
    # )
    graph = dcc.Graph(
        id={"type": id_type, "id": title} if zoom else "undefined",
        figure=fig,
        style=style,
        config={"displayModeBar": False},
        className=classname,
        responsive=True,
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

        shape = cutout.shape

        card = html.Div(
            children=[
                html.Div(
                    className="first-content",
                    children=[
                        html.Div(
                            className="container-small",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div(
                                            id="card",
                                            children=[
                                                html.Div(
                                                    className="card-content",
                                                    children=[
                                                        dbc.Col(data),
                                                        html.Div(
                                                            className="title-small",
                                                            children=[
                                                                html.Span(
                                                                    kind.capitalize()
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            className="subtitle-small",
                                                            children=[
                                                                html.Span(
                                                                    "{}px / {:.1f}''".format(
                                                                        shape[0],
                                                                        shape[0]
                                                                        * PIXEL_SIZE,
                                                                    )
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            className="corner-elements",
                                                            children=[
                                                                html.Span(),
                                                                html.Span(),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        figs.append(card)

    return dmc.Group(figs, justify="space-around")


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
                    dmc.Stack(
                        [
                            dmc.Text(kind.capitalize(), className="text-center"),
                            data,
                        ],
                        gap="xs",
                    ),
                ],
                xs=3,
                className="p-0",
            ),
        )

    return figs


def make_modal_stamps(pdf):
    dates = convert_time(
        pdf["r:midpointMjdTai"].to_numpy(), format_in="mjd", format_out="iso"
    )
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
                            data=[{"value": i, "label": i} for i in dates],
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
            scrollable=False,
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


def draw_lightcurve_preview(
    pdf=None,
    main_id=None,
    is_sso=False,
    color_scale="Fink",
    units="magnitude",
    measurement="total",
    switch_layout="plain",
    layout=None,
) -> dict:
    """Draw object lightcurve with errorbars (SM view - DC mag fixed)

    Returns
    -------
    figure: dict
    """
    # shortcuts -- in milliJansky
    if measurement == "total":
        flux_name = "r:scienceFlux"
        flux_err_name = "r:scienceFluxErr"
        layout["yaxis"]["title"] = "Total flux (milliJansky)"
    elif measurement == "differential":
        flux_name = "r:psfFlux"
        flux_err_name = "r:psfFluxErr"
        layout["yaxis"]["title"] = "Difference flux (milliJansky)"

    # Get data if necessary
    if pdf is None and isinstance(main_id, str):
        cols = [
            "r:midpointMjdTai",
            flux_name,
            flux_err_name,
            "r:band",
            "r:snr",
            "r:reliability",
            "r:pixelFlags_bad",
            "r:pixelFlags_cr",
            "r:pixelFlags_saturatedCenter",
            "r:pixelFlags_streakCenter",
        ]
        if not is_sso:
            pdf = request_api(
                "/api/v1/sources",
                json={
                    "diaObjectId": main_id,
                    "columns": ",".join(cols),
                    "output-format": "json",
                },
            )
        else:
            pdf = request_api(
                "/api/v1/sso",
                json={
                    "n_or_d": main_id,
                    "columns": ",".join(cols),
                    "output-format": "json",
                },
            )

    # date type conversion
    dates = convert_time(pdf["r:midpointMjdTai"], format_in="mjd", format_out="iso")

    flux = pdf[flux_name]
    flux_err = pdf[flux_err_name]

    if units == "magnitude":
        # Using same names as others despite being magnitudes
        flux, flux_err = flux_to_mag(flux, flux_err)
        layout["yaxis"]["autorange"] = "reversed"
        if measurement == "differential":
            layout["yaxis"]["title"] = "Difference magnitude"
        else:
            layout["yaxis"]["title"] = "Magnitude"

    if units == "flux":
        # milli-jansky
        flux = flux * 1e-3
        flux_err = flux_err * 1e-3

    # integer nights
    pdf["id"] = pdf["r:midpointMjdTai"].apply(lambda x: int(x))

    fig = go.Figure(layout=layout)
    if switch_layout == "split":
        fig = make_subplots(
            rows=3, cols=2, figure=fig, shared_xaxes=False, shared_yaxes=False
        )

    colors = generate_rgb_color_sequence(color_scale)
    for fid, fname, color in zip(range(1, 7), BANDS, colors):
        # High-quality measurements
        hovertemplate = r"""
        <b>%{yaxis.title.text}</b>: %{y:.2f} &plusmn; %{error_y.array:.2f}<br>
        <b>%{xaxis.title.text}</b>: %{x|%Y/%m/%d %H:%M:%S.%L}<br>
        <b>mjd</b>: %{customdata[0]}<br>
        <b>SNR</b>: %{customdata[1]:.2f}<br>
        <b>Reliability</b>: %{customdata[2]:.2f}
        <extra></extra>
        """
        idx = pdf["r:band"] == fname

        trace = go.Scatter(
            x=dates[idx],
            y=flux[idx],
            error_y={
                "type": "data",
                "array": flux_err[idx],
                "visible": True,
                "width": 0,
                "color": hex_to_rgba(color, 0.5)
                if color.startswith("#")
                else rgb_to_rgba(color, 0.5),
            },
            mode="markers",
            name=f"{fname}",
            customdata=np.stack(
                (
                    pdf["r:midpointMjdTai"][idx],
                    pdf["r:snr"][idx],
                    pdf["r:reliability"][idx],
                ),
                axis=-1,
            ),
            hovertemplate=hovertemplate,
            legendgroup=f"{fname} band",
            legendrank=100 + 10 * fid,
            marker={
                "size": 12,
                "color": color,
                "symbol": "circle",
            },
            xaxis="x",
            yaxis="y" if switch_layout == "plain" else "y{}".format(fid),
        )

        if switch_layout == "plain":
            fig.add_trace(trace)
        elif switch_layout == "split":
            row = fid - 3 * (fid // 4)
            col = (fid // 4) + 1
            if len(flux[idx]) > 0:
                fig.add_trace(trace, row=row, col=col)
                fig.update_xaxes(
                    row=row,
                    col=col,
                    title="Observation date",
                )
                fig.update_yaxes(
                    row=row,
                    col=col,
                    title=layout["yaxis"]["title"],
                )
                if units == "magnitude":
                    fig.update_yaxes(row=row, col=col, autorange="reversed")

    # indicators
    indicators = []
    colors = generate_rgb_color_sequence(color_scale)
    for fid, fname, color in zip(range(1, 7), BANDS, colors):
        idx = pdf["r:band"] == fname

        # initialise icon
        icon_indicator = DashIconify(
            icon="material-symbols:close-rounded",
            color=dmc.DEFAULT_THEME["colors"]["dark"][6],
            width=20,
        )
        if len(pdf[idx]) > 1:
            # Last 2 measurements in 2 different nights
            mean_values = pdf[idx].groupby("id")[flux_name].mean().reset_index()
            if len(mean_values) > 1:
                arr = (
                    mean_values.sort_values("id", ascending=False)
                    .head(2)[flux_name]
                    .to_numpy()
                )
                diff = arr[0] - arr[1]
                if diff > 0:
                    # going up
                    icon_indicator = DashIconify(
                        icon="tabler:arrow-up-right",
                        color=dmc.DEFAULT_THEME["colors"]["green"][6],
                        width=20,
                    )
                elif diff <= 0:
                    icon_indicator = DashIconify(
                        icon="tabler:arrow-down-right",
                        color=dmc.DEFAULT_THEME["colors"]["red"][6],
                        width=20,
                    )

        indicators.append(
            dmc.Flex(
                children=[
                    "{}".format(fname),
                    icon_indicator,
                ],
                align="center",
                # gap="sm"
            ),
        )

        # if not np.sum(idx):
        #     continue

        # if units == "magnitude":
        #     # Using same names as others despite being magnitudes
        #     # Redefined within the loop each time
        #     # FIXME: rewrite for better efficiency
        #     flux, flux_err = flux_to_mag(pdf[flux_name], pdf[flux_err_name])
        #     layout["yaxis"]["autorange"] = "reversed"
        #     if measurement == "differential":
        #         layout["yaxis"]["title"] = "Difference magnitude"
        #     else:
        #         layout["yaxis"]["title"] = "Magnitude"

        # figure["data"].append(
        #     {
        #         "x": dates[idx],
        #         "y": flux[idx],
        #         "error_y": {
        #             "type": "data",
        #             "array": flux_err[idx],
        #             "visible": True,
        #             "width": 0,
        #             "color": color,  # It does not support arrays of colors so let's use positive one for all points
        #             "opacity": 0.5,
        #         },
        #         "mode": "markers",
        #         "name": f"{fname}",
        #         "customdata": np.stack(
        #             (
        #                 pdf["r:midpointMjdTai"][idx],
        #                 pdf["r:snr"][idx],
        #                 pdf["r:reliability"][idx],
        #             ),
        #             axis=-1,
        #         ),
        #         "hovertemplate": hovertemplate,
        #         "marker": {
        #             "size": 12,
        #             "color": color,
        #             "symbol": "o",
        #             "line": {"width": 0},
        #             "opacity": 1,
        #         },
        #     },
        # )

    flags = []
    cols = [
        "r:pixelFlags_bad",
        "r:pixelFlags_saturatedCenter",
        "r:pixelFlags_cr",
        "r:pixelFlags_streakCenter",
    ]
    docs = [
        "bad pixel in the DiaSource footprint.",
        "saturated pixel in the 3x3 region around the centroid.",
        "cosmic ray in the DiaSource footprint.",
        "streak in the 3x3 region around the centroid.",
    ]
    for col, doc in zip(cols, docs):
        if any(pdf[col]):
            flags.append(
                html.Div([
                    dbc.Popover(
                        "{}".format(doc.capitalize()),
                        target="{}_{}".format(main_id, col),
                        body=True,
                        trigger="hover",
                        placement="top",
                    ),
                    DashIconify(
                        icon="tabler:square-rounded-filled",
                        color=dmc.DEFAULT_THEME["colors"]["red"][6],
                        width=20,
                        id="{}_{}".format(main_id, col),
                    ),
                ])
            )
        else:
            flags.append(
                html.Div([
                    dbc.Popover(
                        "No {}".format(doc),
                        target="{}_{}".format(main_id, col),
                        body=True,
                        trigger="hover",
                        placement="top",
                    ),
                    DashIconify(
                        icon="tabler:square-rounded-filled",
                        color=dmc.DEFAULT_THEME["colors"]["green"][6],
                        width=20,
                        id="{}_{}".format(main_id, col),
                    ),
                ])
            )

    return fig, indicators, flags


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
        Input("select-lc-layout", "value"),
        Input("object-data", "data"),
        Input("color_scale", "value"),
        Input("select-units", "value"),
        Input("select-measurement", "value"),
    ],
    prevent_initial_call=True,
)
def draw_lightcurve(
    switch_layout: str, object_data, color_scale, units, measurement
) -> dict:
    """Draw diaObject lightcurve with errorbars

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
    layout = dict(
        autosize=True,
        margin=dict(l=50, r=30, b=0, t=0),
        hovermode="closest",
        showlegend=True,
        shapes=[],
        paper_bgcolor=PAPER_BGCOLOR,
        plot_bgcolor=PAPER_BGCOLOR,
        hoverlabel={
            "align": "left",
        },
        legend=dict(
            font=dict(size=10),
            orientation="h",
            x=0,
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
            "automargin": True,
            "zeroline": False,
        },
    )
    pdf = pd.read_json(io.StringIO(object_data))
    fig, indicator, flags = draw_lightcurve_preview(
        pdf=pdf,
        is_sso=False,
        color_scale=color_scale,
        units=units,
        measurement=measurement,
        layout=layout,
        switch_layout=switch_layout,
    )

    return fig


@app.callback(
    Output("coordinates", "children"),
    [
        Input("object-data", "data"),
        Input("coordinates_chips", "value"),
        Input("color_scale", "value"),
    ],
    prevent_initial_call=True,
)
def draw_alert_astrometry(object_data, kind, color_scale) -> dict:
    """Draw object astrometry

    This is the difference position of each alert wrt mean position

    Returns
    -------
    figure: dict
    """
    pdf = pd.read_json(io.StringIO(object_data))

    mean_ra = np.mean(pdf["r:ra"])
    mean_dec = np.mean(pdf["r:dec"])

    deltaRAcosDEC = (pdf["r:ra"] - mean_ra) * np.cos(np.radians(pdf["r:dec"])) * 3600
    deltaDEC = (pdf["r:dec"] - mean_dec) * 3600

    hovertemplate = r"""
    <b>%{yaxis.title.text}</b>: %{y:.2f}<br>
    <b>%{xaxis.title.text}</b>: %{x:.2f}<br>
    <b>Observation date</b>: %{customdata}
    <extra></extra>
    """

    data = []

    colors = generate_rgb_color_sequence(color_scale)
    for fid, fname, color in zip(range(1, 7), BANDS, colors):
        data.append({
            "x": deltaRAcosDEC[pdf["r:band"] == fname],
            "y": deltaDEC[pdf["r:band"] == fname],
            "mode": "markers",
            "name": "{} band".format(fname),
            "customdata": Time(
                pdf["r:midpointMjdTai"][pdf["r:midpointMjdTai"] == 1], format="mjd"
            ).iso,
            "hovertemplate": hovertemplate,
            "marker": {"size": 6, "color": color, "symbol": "o"},
        })

    layout = dict(
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
            "title": "&#916;RA cos(Dec) ('')",
            "automargin": True,
        },
        yaxis={
            "title": "&#916;Dec ('')",
            "automargin": True,
            "scaleanchor": "x",
            "scaleratio": 1,
        },
        paper_bgcolor=PAPER_BGCOLOR,
        plot_bgcolor=PAPER_BGCOLOR,
    )

    figure = {
        "data": data,
        "layout": layout,
    }
    # Force equal aspect ratio
    figure["layout"]["yaxis"]["scaleanchor"] = "x"
    layout["showlegend"] = True
    # figure['layout']['yaxis']['scaleratio'] = 1

    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "100%",
            "height": "20pc",
            # Prevent occupying more than 60% of the screen height
            "max-height": "60vh",
            # Force equal aspect
            # 'display':'block',
            # 'aspect-ratio': '1',
            # 'margin': '1px'
        },
        config={"displayModeBar": False},
        responsive=True,
    )
    # card1 = dmc.Paper(
    #     graph, radius="sm", p="xs", shadow="sm", withBorder=True, className="mb-1"
    # )

    coord = SkyCoord(mean_ra, mean_dec, unit="deg")

    # degrees
    if kind == "GAL":
        coords_deg = coord.galactic.to_string("decimal", precision=6)
    else:
        coords_deg = coord.to_string("decimal", precision=6)

    # hmsdms
    if kind == "GAL":
        # Galactic coordinates are in DMS only
        coords_hms = coord.galactic.to_string("dms", precision=2)
        coords_hms2 = coord.galactic.to_string("dms", precision=2, sep=" ")
    else:
        coords_hms = coord.to_string("hmsdms", precision=2)
        coords_hms2 = coord.to_string("hmsdms", precision=2, sep=" ")

    card_coords = html.Div(
        [
            dmc.Group(
                [
                    html.Code(coords_deg, id="alert_coords_deg"),
                    dcc.Clipboard(
                        target_id="alert_coords_deg",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
            dmc.Group(
                [
                    html.Code(coords_hms, id="alert_coords_hms"),
                    dcc.Clipboard(
                        target_id="alert_coords_hms",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
            dmc.Group(
                [
                    html.Code(coords_hms2, id="alert_coords_hms2"),
                    dcc.Clipboard(
                        target_id="alert_coords_hms2",
                        title="Copy to clipboard",
                        style={"color": "gray"},
                    ),
                ],
                justify="space-between",
                style={"width": "100%"},
            ),
        ],
        className="mx-auto",
        style={"max-width": "17em"},
    )

    return html.Div([graph, card_coords])


@app.callback(
    Output("aladin-lite-runner", "run"),
    Input("object-data", "data"),
    prevent_initial_call=True,
)
def integrate_aladin_lite(object_data):
    """Integrate aladin light in the 2nd Tab of the dashboard.

    the default parameters are:
        * PanSTARRS colors
        * FoV = 0.02 deg
        * SIMBAD catalig overlayed.

    Callbacks
    ----------
    Input: takes the alert ID
    Output: Display a sky image around the alert position from aladin.

    Parameters
    ----------
    alert_id: str
        ID of the alert
    """
    pdf = pd.read_json(io.StringIO(object_data))
    pdf = pdf.sort_values("r:midpointMjdTai", ascending=False)

    # Coordinate of the current alert
    ra0 = pdf["r:ra"].to_numpy()[0]
    dec0 = pdf["r:dec"].to_numpy()[0]

    # Javascript. Note the use {{}} for dictionary
    img = f"""
    var aladin = A.aladin('#aladin-lite-div',
              {{
                survey: 'https://alasky.cds.unistra.fr/Skymapper/DR4/CDS_P_Skymapper_DR4_color/',
                fov: 0.025,
                target: '{ra0} {dec0}',
                reticleColor: '#e89070',
                reticleSize: 32,
                showContextMenu: true,
                showCooGridControl: false,
                showShareControl: false,
                showCooGrid: false,
                showProjectionControl: false,
                showFrame: true,
                showFullscreenControl: true,
                showCooGridControl: false,
                showGotoControl: false
    }});
    var cat_simbad = 'https://axel.u-strasbg.fr/HiPSCatService/Simbad';
    var hips_simbad = A.catalogHiPS(cat_simbad, {{onClick: 'showTable', name: 'Simbad', sourceSize: 15}});
    aladin.addCatalog(hips_simbad);

    var cat_gaia = 'https://axel.u-strasbg.fr/HiPSCatService/Gaia';
    var hips_gaia = A.catalogHiPS(cat_gaia, {{onClick: 'showTable', name: 'Gaia EDR3', sourceSize: 15}});
    aladin.addCatalog(hips_gaia);
    """

    # # Unique positions of nearest reference object
    # pdfnr = pdf[["i:ranr", "i:decnr", "i:magnr", "i:sigmagnr", "i:fid"]][
    #     np.isfinite(pdf["i:magnr"])
    # ].drop_duplicates()

    # if len(pdfnr.index):
    #     img += """
    #     var catnr_zg = A.catalog({name: 'ZTF Reference nearest, zg', sourceSize: 6, shape: 'plus', color: 'green', onClick: 'showPopup', limit: 1000});
    #     var catnr_zr = A.catalog({name: 'ZTF Reference nearest, zr', sourceSize: 6, shape: 'plus', color: 'red', onClick: 'showPopup', limit: 1000});
    #     """

    #     for _, row in pdfnr.iterrows():
    #         img += """
    #         catnr_{}.addSources([A.source({}, {}, {{ZTF: 'Reference', mag: {:.2f}, err: {:.2f}, filter: '{}'}})]);
    #         """.format(
    #             {1: "zg", 2: "zr", 3: "zi"}.get(row["i:fid"]),
    #             row["i:ranr"],
    #             row["i:decnr"],
    #             row["i:magnr"],
    #             row["i:sigmagnr"],
    #             {1: "zg", 2: "zr", 3: "zi"}.get(row["i:fid"]),
    #         )

    #     img += """aladin.addCatalog(catnr_zg);"""
    #     img += """aladin.addCatalog(catnr_zr);"""

    # img cannot be executed directly because of formatting
    # We split line-by-line and remove comments
    img_to_show = [i for i in img.split("\n") if "// " not in i]

    return " ".join(img_to_show)


@app.callback(
    Output("observability_plot", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("observatory", "value"),
        State("dateobs", "value"),
        State("moon_elevation", "checked"),
        State("moon_phase", "checked"),
        State("moon_illumination", "checked"),
        State("longitude", "value"),
        State("latitude", "value"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def plot_observability(
    summary_tab,
    nclick,
    object_data,
    observatory_name,
    dateobs,
    moon_elevation,
    moon_phase,
    moon_illumination,
    longitude,
    latitude,
):
    if summary_tab != "Observability":
        raise PreventUpdate

    layout_observability = dict(
        automargin=True,
        margin=dict(l=50, r=30, b=0, t=0),
        hovermode="closest",
        hoverlabel={
            "align": "left",
            "namelength": -1,
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
        yaxis={
            "range": [0, 90],
            "title": "Elevation (&deg;)",
            "automargin": True,
        },
        yaxis2={
            "title": "Relative airmass",
            "overlaying": "y",
            "side": "right",
            "tickvals": 90 - np.degrees(np.arccos(1 / np.array([1, 2, 3]))),
            "ticktext": [1, 2, 3],
            "showgrid": False,
            "showticklabels": True,
            "matches": "y",
            "anchor": "x",
        },
    )

    pdf = pd.read_json(io.StringIO(object_data))
    ra0 = np.mean(pdf["r:ra"].to_numpy())
    dec0 = np.mean(pdf["r:dec"].to_numpy())

    if longitude and latitude:
        lat = Latitude(latitude, unit=u.deg).deg
        lon = Longitude(longitude, unit=u.deg).deg
        observatory = EarthLocation.from_geodetic(lon=lon, lat=lat)
    elif observatory_name in observability.additional_observatories:
        observatory = observability.additional_observatories[observatory_name]
    else:
        observatory = EarthLocation.of_site(observatory_name)

    local_time = observability.observation_time(dateobs, delta_points=1 / 60)
    UTC_time = (
        local_time - observability.observation_time_to_utc_offset(observatory) * u.hour
    )
    UTC_axis = observability.from_time_to_axis(UTC_time)
    local_axis = observability.from_time_to_axis(local_time)
    mask_axis = [
        True if t[-2:] == "00" and int(t[:2]) % 2 == 0 else False for t in UTC_axis
    ]
    idx_axis = np.where(mask_axis)[0]
    target_coordinates = observability.target_coordinates(
        ra0, dec0, observatory, UTC_time
    )
    airmass = observability.from_elevation_to_airmass(target_coordinates.alt.value)
    twilights = observability.utc_night_hours(
        observatory,
        dateobs,
        observability.observation_time_to_utc_offset(observatory),
        UTC=True,
    )
    twilights_list = observability.from_time_to_axis(list(twilights.values()))

    # Initialize figure
    figure = {"data": [], "layout": copy.deepcopy(layout_observability)}

    # Add UTC time in the layout
    figure["layout"]["xaxis"] = {
        "title": "UTC time",
        "automargin": True,
        "tickvals": UTC_axis[idx_axis],
        "showgrid": True,
    }

    # Target plot
    hovertemplate_elevation = r"""
    <b>UTC time</b>:%{x}<br>
    <b>Elevation</b>: %{y:.0f} &deg;<br>
    <b>Azimut</b>: %{customdata[0]:.0f} &deg;<br>
    <b>Relative airmass</b>: %{customdata[1]:.2f}
    <extra></extra>
    """

    figure["data"].append({
        "x": UTC_axis,
        "y": target_coordinates.alt.value,
        "mode": "lines",
        "name": "Target elevation",
        "legendgroup": "Elevation",
        "customdata": np.stack(
            [
                target_coordinates.az.value,
                airmass,
            ],
            axis=-1,
        ),
        "hovertemplate": hovertemplate_elevation,
        "line": {"color": "black"},
    })

    # Moon target
    if moon_elevation:
        moon_coordinates = observability.moon_coordinates(observatory, UTC_time)
        moon_airmass = observability.from_elevation_to_airmass(
            moon_coordinates.alt.value
        )

        hovertemplate_moon = r"""
        <b>UTC time</b>:%{x}<br>
        <b>Elevation</b>: %{y:.0f} &deg;<br>
        <b>Azimut</b>: %{customdata[0]:.0f} &deg;<br>
        <b>Relative airmass</b>: %{customdata[1]:.2f}
        <extra></extra>
        """

        figure["data"].append({
            "x": UTC_axis,
            "y": moon_coordinates.alt.value,
            "mode": "lines",
            "name": "Moon elevation",
            "legendgroup": "Elevation",
            "customdata": np.stack(
                [
                    moon_coordinates.az.value,
                    moon_airmass,
                ],
                axis=-1,
            ),
            "hovertemplate": hovertemplate_moon,
            "line": {"color": observability.moon_color},
        })

    # For relative airmass
    figure["data"].append({
        "x": ["00:00", "00:00", "00:00"],
        "y": list(90 - np.degrees(np.arccos(1 / np.array([1, 2, 3])))),
        "yaxis": "y2",
        "mode": "markers",
        "marker": {"opacity": 0},
        "showlegend": False,
        "hoverinfo": "skip",
    })

    # Layout modification for local time
    figure["layout"]["xaxis2"] = {
        "title": "Local time",
        "overlaying": "x",
        "side": "top",
        "tickvals": UTC_axis[idx_axis],
        "ticktext": local_axis[idx_axis],
        "showgrid": False,
        "showticklabels": True,
        "matches": "x",
        "anchor": "y",
    }

    # For local time
    figure["data"].append({
        "x": local_axis,
        "y": 45 * np.ones(len(local_axis)),
        "xaxis": "x2",
        "mode": "markers",
        "marker": {"opacity": 0},
        "showlegend": False,
        "hoverinfo": "skip",
    })

    # Twilights
    figure["layout"]["shapes"] = []
    for dummy in range(len(twilights_list) - 1):
        figure["layout"]["shapes"].append({
            "type": "rect",
            "xref": "x",
            "yref": "paper",
            "x0": twilights_list[dummy],
            "x1": twilights_list[dummy + 1],
            "y0": 0,
            "y1": 1,
            "fillcolor": observability.night_colors[dummy],
            "layer": "below",
            "line_width": 0,
            "line": dict(width=0),
        })

    # Graphs
    graph = dcc.Graph(
        figure=figure,
        style={
            "width": "90%",
            "height": "25pc",
            "marginLeft": "auto",
            "marginRight": "auto",
        },
        config={"displayModeBar": False},
        responsive=True,
    )

    return graph


@app.callback(
    Output("moon_data", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("dateobs", "value"),
        State("moon_phase", "checked"),
        State("moon_illumination", "checked"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def show_moon_data(
    summary_tab, nclick, object_data, dateobs, moon_phase, moon_illumination
):
    if summary_tab != "Observability":
        raise PreventUpdate

    date_time = Time(dateobs, scale="utc")
    msg = None
    if moon_phase and not moon_illumination:
        msg = f"Moon phase: {observability.get_moon_phase(date_time)}"
    elif not moon_phase and moon_illumination:
        msg = f"Moon illumination: {int(100 * observability.get_moon_illumination(date_time))}%"
    elif moon_phase and moon_illumination:
        msg = f"moon phase: `{observability.get_moon_phase(date_time)}`, moon illumination: `{int(100 * observability.get_moon_illumination(date_time))}%`"
    return msg


@app.callback(
    Output("observability_title", "children"),
    [
        Input("summary_tabs", "value"),
        Input("submit_observability", "n_clicks"),
        Input("object-data", "data"),
    ],
    [
        State("dateobs", "value"),
    ],
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submit_observability", "disabled"), True, False),
        (Output("submit_observability", "loading"), True, False),
    ],
)
def show_observability_title(
    summary_tab,
    nclick,
    object_data,
    dateobs,
):
    if summary_tab != "Observability":
        raise PreventUpdate

    msg = "Observability for the night between "
    msg += (Time(dateobs) - 1 * u.day).to_value("iso", subfmt="date")
    msg += " and "
    msg += Time(dateobs).to_value("iso", subfmt="date")
    return msg


@app.callback(
    Output("latitude", "value"),
    Output("longitude", "value"),
    Input("clear_button", "n_clicks"),
    prevent_initial_call=True,  # So callback only triggers on clicks
)
def clear_input(n_clicks):
    if n_clicks:
        return "", ""  # Clear the input field
    return no_update, no_update
