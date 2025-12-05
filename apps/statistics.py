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
import io
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import Input, Output, dcc, html, no_update

import numpy as np
import pandas as pd
import datetime
from astropy.time import Time

from app import app
from apps.utils import query_and_order_statistics
from apps.api import request_api
from apps.plotting import CONFIG_PLOT

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

dcc.Location(id="url", refresh=False)

dic_names = {
    "f:night": "Observation date in the form YYYYMMDD",
    "f:alerts": "Number of alerts processed",
    "f:alerts_<band>": "Number of alerts processed per band <band>",
    "f:objects": "Number of objects",
    "f:is_sso": "Number of alerts associated to a Solar System objects",
    "f:is_first": "Number of alerts with first detection",
    "f:is_cataloged": "Number of alerts with a counterpart in SIMBAD or Gaia DR3.",
    "f:visits": "Number of visits",
    "f:simbad_<class>": "Number of alerts with a counterpart <class> in SIMBAD.",
}

stat_doc = """
This page shows various statistics concerning Fink processed data.
These statistics are updated once a day, after the LSST observing night.
Click on the different tabs to explore data.

## Heatmap

The `Heatmap` tab shows the number of alerts processed by Fink for each night
since the beginning of our operations (2025/09/06). The graph is color coded,
dark cells represent a low number of processed alerts, while bright cells represent
a high number of processed alerts.

## Daily statistics

The `Daily statistics` tab shows various statistics for a given observing night. By default,
we show the last observing night. You can change the night by using the dropdown button.

The first row shows histograms for various indicators:
- Quality cuts: difference between number of received alerts versus number of processed alerts. The difference is simmply due to the quality cuts in Fink selecting only the best quality alerts.
- Classification: Number of alerts that receive a tag by Fink, either from the Machine Learning classifiers, or from a crossmatch with catalogs. The rest is "unclassified".
- External catalogs: Number of alerts that have a counterpart either in the MPC catalog or in the SIMBAD database.
- Selected candidates: Number of alerts for a subset of classes: early type Ia supernova (SN Ia), supernovae or core-collapse (SNe), Kilonova, or Solar System candidates.

The second row shows the number of alerts for all labels in Fink (from classifiers or crossmatch).
Since there are many labels available, do not hesitate to zoom in to see more details!

## Timelines

The `Timelines` tab shows the evolution of several parameters over time. By default, we show the number of
processed alerts per night, since the beginning of operations. You can change the parameter to
show by using the dropdown button. Fields starting with `SIMBAD:` are labels from the SIMBAD database.

Note that you can also show the cumulative number of alerts over time by switching the button on the top right :-)

## REST API

If you want to explore more statistics, or create your own dashboard based on Fink data,
you can do all of these yourself using the REST API. Here is an example using Python:

```python
import io
import requests
import pandas as pd

# get stats for all the year 2025
r = requests.post(
  'https://api.lsst.fink-portal.org/api/v1/statistics',
  json={{
    'date': '2025',
    'output-format': 'json'
  }}
)

# Format output in a DataFrame
pdf = pd.read_json(io.BytesIO(r.content))
```

Note `date` can be either a given night (YYYYMMDD), month (YYYYMM), year (YYYY), or eveything (empty string).
The schema of the dataframe is the following:

{}.
""".format(pd.DataFrame([dic_names]).T.rename(columns={0: "description"}).to_markdown())


def make_date_dash(indate):
    """Change int(YYYYMMDD) to YYYY-MM-DD"""
    if not isinstance(indate, str):
        indate = str(indate)
    return indate[0:4] + "-" + indate[4:6] + "-" + indate[6:]


@app.callback(
    Output("object-stats", "data"),
    Input("url", "pathname"),
)
def store_stat_query(name):
    """Cache query results (data and upper limits) for easy re-use

    https://dash.plotly.com/sharing-data-between-callbacks
    """
    pdf = query_and_order_statistics(
        drop=False,
    )

    return pdf.to_json()


@app.callback(
    Output("stat_row", "children"),
    Input("object-stats", "data"),
    prevent_initial_call=True,
)
def create_stat_row(object_stats):
    """Show basic stats. Used in the desktop app."""
    pdf = pd.read_json(io.StringIO(object_stats))
    c0_, c1_, c2_, c3_, c4_, c5_ = create_stat_generic(pdf)

    return [
        dbc.Col(
            dbc.Row(
                [
                    dbc.Col(c0_, md=6),
                    dbc.Col(c1_, md=6),
                ],
                style={
                    "border-left": "3px solid #15284f",
                    "border-bottom": "3px solid #15284f",
                    # "border-right": "3px solid #15284f",
                    "border-radius": "0px 0px 75px 25px",
                    "text-align": "center",
                },
            ),
            md=4,
        ),
        # dmc.Space(h=0),
        dbc.Col(
            dbc.Row(
                [
                    dbc.Col(c2_, md=3),
                    dbc.Col(c3_, md=3),
                    dbc.Col(c4_, md=3),
                    dbc.Col(c5_, md=3),
                ],
                style={
                    # "border-left": "3px solid #15284f",
                    "border-bottom": "3px solid #15284f",
                    "border-right": "3px solid #15284f",
                    "border-radius": "0px 0px 25px 35px",
                    "text-align": "center",
                },
            ),
            md=8,
        ),
    ]


def create_stat_generic(pdf):
    """Show basic stats. Used in the mobile app."""
    n_ = str(pdf["f:night"].to_numpy()[-1])
    night = n_[0:4] + "-" + n_[4:6] + "-" + n_[6:]

    c0 = [
        html.H3(html.B(night)),
        html.P("Last LSST observing night"),
    ]

    c1 = [
        html.H3(html.B("{:,}".format(pdf["f:alerts"].to_numpy()[-1]))),
        html.P("Alerts processed"),
    ]

    c2 = [
        html.H3(html.B("{:,}".format(np.sum(pdf["f:alerts"].to_numpy())))),
        html.P("Total alerts"),
    ]

    # FIXME: hpw to incorporate candidates from ML?
    # mask = ~np.isnan(pdf["class:Unknown"].to_numpy())
    # n_alert_tot = np.sum(pdf["f:alerts"].to_numpy())
    n_alert_sso = np.sum(pdf["f:is_sso"].to_numpy())
    n_alert_cat = np.sum(pdf["f:is_cataloged"].to_numpy())
    # n_alert_classified = n_alert_sso + n_alert_cat
    # n_alert_unclassified = n_alert_tot - n_alert_classified

    c3 = [
        html.H3(html.B(f"{n_alert_cat:,}")),
        html.P("In catalogs"),
    ]

    c4 = [
        html.H3(html.B(f"{n_alert_sso:,}")),
        html.P("In MPC"),
    ]

    c5 = [
        html.H3(html.B(f"{n_alert_cat:,}")),
        html.P("In TNS"),
    ]

    return c0, c1, c2, c3, c4, c5


def heatmap_content():
    """ """

    # FIXME: this changes the display
    switch = dmc.Switch(label="All years", id="switch_years", style={"display": "none"})

    layout_ = dmc.Card(
        [dmc.Group([generate_year_list(), switch]), html.Div(id="heatmap_stat")],
        className="stat_card",
    )

    return layout_


def timelines():
    """ """
    switch = dmc.Group([
        dmc.Switch("Cumulative", id="switch-cumulative"),
        dmc.Switch("Percentage", id="switch-percentage"),
    ])

    layout_ = dmc.Card(
        [dmc.Group([generate_col_list(), switch]), html.Div(id="timeline_stat")],
        className="stat_card",
    )

    return layout_


@app.callback(
    Output("timeline_stat", "children"),
    [
        Input("object-stats", "data"),
        Input("dropdown_params", "value"),
        Input("switch-cumulative", "checked"),
        Input("switch-percentage", "checked"),
    ],
)
def plot_stat_evolution(data, param_name, switch_cumulative, switch_percentage):
    """Plot evolution of parameters as a function of time"""
    if param_name is None:
        param_name = "f:alerts"
    if param_name == "":
        return no_update

    # pdf = query_and_order_statistics(columns=param_name_)
    pdf = pd.read_json(io.StringIO(data))
    pdf = pdf.fillna(0)

    pdf["date"] = [
        Time(make_date_dash(x)).datetime for x in pdf.index.astype(str).to_numpy()
    ]

    if param_name in dic_names:
        newcol = dic_names[param_name]
    else:
        newcol = param_name.replace("class", "SIMBAD")

    if switch_cumulative:
        pdf[param_name] = pdf[param_name].astype(int).cumsum()
        if param_name != "f:alerts":
            pdf["f:alerts"] = pdf["f:alerts"].astype(int).cumsum()
    if switch_percentage:
        pdf[param_name] = (
            pdf[param_name].astype(int) / pdf["f:alerts"].astype(int) * 100
        )

    pdf = pdf.rename(columns={param_name: newcol})

    fig = px.bar(
        pdf,
        y=newcol,
        x="date",
        text=newcol,
    )
    fig.update_traces(
        textposition="outside",
        marker_color="rgb(21, 40, 79)",
    )
    fig.update_layout(
        uniformtext_minsize=8,
        uniformtext_mode="hide",
        showlegend=True,
    )
    layout = dict(
        autosize=True,
        margin=dict(l=50, r=30, b=0, t=0),
        hovermode="closest",
        showlegend=True,
        shapes=[],
        paper_bgcolor="white",  # PAPER_BGCOLOR,
        plot_bgcolor="white",  # PAPER_BGCOLOR,
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
    fig.update_layout(layout)

    CONFIG_PLOT["toImageButtonOptions"]["filename"] = newcol.replace(" ", "_")
    graph = dcc.Graph(
        figure=fig,
        style={
            "width": "100%",
            "height": "20pc",
        },
        config=CONFIG_PLOT,
    )
    return graph


def generate_year_list():
    """Generate list of years from 2025 to now"""
    year_now = datetime.datetime.today().year
    year_list = range(2025, year_now + 1)
    dropdown = dmc.Select(
        data=[
            *[{"label": str(year), "value": str(year)} for year in year_list],
        ],
        id="dropdown_years",
        clearable=False,
        allowDeselect=False,
        value=str(year_now),
        placeholder="Choose a year",
    )
    return dropdown


def generate_col_list():
    """Generate the list of available columns"""
    pdf = request_api(
        "/api/v1/statistics",
        json={
            "output-format": "json",
            "date": "",
            "schema": True,
        },
    )
    schema_list = list(pdf["schema"])

    labels = [i if i not in dic_names else dic_names[i] for i in schema_list]

    # Sort them for better readability
    idx = np.argsort(labels)
    labels = np.array(labels)[idx]
    schema_list = np.array(schema_list)[idx]

    dropdown = dmc.Select(
        data=[
            *[
                {"label": label, "value": value}
                for label, value in zip(labels, schema_list)
            ],
        ],
        id="dropdown_params",
        searchable=True,
        clearable=False,
        # value="f:alerts",
        w=300,
        placeholder="Choose a columns",
    )

    return dropdown


@app.callback(
    Output("heatmap_stat", "children"),
    [
        Input("object-stats", "data"),
        Input("switch_years", "checked"),
        Input("dropdown_years", "value"),
    ],
    prevent_initial_call=True,
)
def plot_heatmap(object_stats, switch, year):
    """Plot heatmap"""
    pdf = pd.read_json(io.StringIO(object_stats))
    pdf["date"] = [
        Time(make_date_dash(x)).datetime for x in pdf.index.astype(str).to_numpy()
    ]
    if not switch:
        # restrict to one year
        pdf = pdf[pdf["date"].apply(lambda x: str(x.year) == year)]
    years = np.unique(pdf["date"].apply(lambda x: x.year)).tolist()

    idx = pd.date_range(
        Time(f"{np.min(years)}-01-01").datetime,
        Time(f"{np.max(years)}-12-31").datetime,
    )
    pdf.index = pd.DatetimeIndex(pdf.date)
    pdf = pdf.drop(columns="date")
    pdf = pdf.reindex(idx, fill_value=0)
    pdf["date"] = pdf.index.to_numpy()

    fig = display_years(pdf, years)

    graph = dcc.Graph(
        figure=fig,
        config={"displayModeBar": False},
        style={
            "width": "100%",
            "height": "10pc",
        },
    )

    return graph


def display_years(pdf, years):
    """Display all heatmaps stacked

    Parameters
    ----------
    pdf: pd.DataFrame
        DataFrame from the REST API
    years: list or tuple of int
        years to display

    Returns
    -------
    fig: plotly figure object
    """
    fig = make_subplots(rows=len(years), cols=1, subplot_titles=None)
    for i, year in enumerate(years):
        # select the data for the year
        data = pdf[pdf["date"].apply(lambda x, year=year: x.year == year)][
            "f:alerts"
        ].to_numpy()

        # Display year
        display_year(data, year=year, fig=fig, row=i, month_lines=True)

        # Fix the height
        # FIXME: this change the layout when switch is ON
        # fig.update_layout(height=220 * len(years))
    return fig


def display_year(
    data, year: int = None, month_lines: bool = True, fig=None, row: int = None
):
    """Display one year as heatmap

    help from https://community.plotly.com/t/colored-calendar-heatmap-in-dash/10907/17

    Parameters
    ----------
    data: np.array
        Number of alerts per day, for ALL days of the year.
        Should be 0 if no observations
    year: int
        Year to plot
    month_lines: bool
        If true, make lines to mark months
    fig: plotly object
    row: int
        Number of the row (position) in the final plot
    """
    if year is None:
        year = datetime.datetime.now().year

    # First and last day
    d1 = datetime.date(year, 1, 1)
    d2 = datetime.date(year, 12, 31)

    delta = d2 - d1

    # should be put elsewhere as constants?
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    month_days = [
        31,
        28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]

    # annees bisextiles
    if year in [2028, 2032, 2036]:
        month_days[1] = 29

    # black magic
    month_positions = (np.cumsum(month_days) - 15) / 7

    # Gives a list with datetimes for each day a year
    dates_in_year = [d1 + datetime.timedelta(i) for i in range(delta.days + 1)]

    # gives [0,1,2,3,4,5,6,0,1,2,3,4,5,6,…]
    # ticktext in xaxis dict translates this to weekdays
    weekdays_in_year = [i.weekday() for i in dates_in_year]

    # gives [1,1,1,1,1,1,1,2,2,2,2,2,2,2,…]
    weeknumber_of_dates = [
        int(i.strftime("%V"))
        if not (int(i.strftime("%V")) == 1 and i.month == 12)
        else 53
        for i in dates_in_year
    ]

    # Careful, first days of January can belong to week 53...
    # so to avoid messing up, we set them to 1, and shift all
    # other weeks by one
    if weeknumber_of_dates[0] == 53:
        weeknumber_of_dates = [i + 1 for i in weeknumber_of_dates]
        weeknumber_of_dates = [
            1 if (j.month == 1 and i == 54) else i
            for i, j in zip(weeknumber_of_dates, dates_in_year)
        ]

    # Gives something like list of strings like ‘2018-01-25’
    # for each date. Used in data trace to make good hovertext.
    # text = [str(i) for i in dates_in_year]
    text = [f"{int(i):,} alerts processed in {j}" for i, j in zip(data, dates_in_year)]

    # Some examples
    colorscale = [[False, "#eeeeee"], [True, "#76cf63"]]
    colorscale = [[False, "#495a7c"], [True, "#F5622E"]]
    colorscale = [[False, "#15284F"], [True, "#3C8DFF"]]
    colorscale = [[False, "#3C8DFF"], [True, "#15284F"]]
    colorscale = [[False, "#4563a0"], [True, "#F5622E"]]
    colorscale = [[False, "#eeeeee"], [True, "#F5622E"]]

    # handle end of year
    data = [
        go.Heatmap(
            x=weeknumber_of_dates,
            y=weekdays_in_year,
            z=data,
            text=text,
            hoverinfo="text",
            xgap=3,  # this
            ygap=3,  # and this is used to make the grid-like apperance
            showscale=False,
            colorscale=colorscale,
            zmax=100000,  # avoid large peaks
            zmid=10000,
            zmin=0,
        ),
    ]

    if month_lines:
        kwargs = dict(
            mode="lines",
            line=dict(
                color="#9e9e9e",
                width=1,
            ),
            hoverinfo="skip",
        )
        for date, dow, wkn in zip(dates_in_year, weekdays_in_year, weeknumber_of_dates):
            if date.day == 1:
                data += [
                    go.Scatter(
                        x=[wkn - 0.5, wkn - 0.5],
                        y=[dow - 0.5, 6.5],
                        **kwargs,
                    ),
                ]
                if dow:
                    data += [
                        go.Scatter(
                            x=[wkn - 0.5, wkn + 0.5],
                            y=[dow - 0.5, dow - 0.5],
                            **kwargs,
                        ),
                        go.Scatter(
                            x=[wkn + 0.5, wkn + 0.5],
                            y=[dow - 0.5, -0.5],
                            **kwargs,
                        ),
                    ]

    layout = go.Layout(
        # title="Fink activity chart: number of LSST alerts processed per night",
        height=150,
        # paper_bgcolor=PAPER_BGCOLOR,
        # plot_bgcolor=PAPER_BGCOLOR,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            tickmode="array",
            ticktext=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            tickvals=[0, 1, 2, 3, 4, 5, 6],
            autorange="reversed",
        ),
        xaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            tickmode="array",
            ticktext=month_names,
            tickvals=month_positions,
        ),
        font={"size": 10, "color": "#9e9e9e"},
        margin=dict(t=20, b=20),
        showlegend=False,
    )

    if fig is None:
        fig = go.Figure(data=data, layout=layout)
    else:
        fig.add_traces(data, rows=[(row + 1)] * len(data), cols=[1] * len(data))
        fig.update_layout(layout)
        fig.update_xaxes(layout["xaxis"])
        fig.update_yaxes(layout["yaxis"])
        fig.update_layout(
            title={
                "y": 0.995,
                "x": 0.5,
                "xanchor": "center",
                "yanchor": "top",
            },
        )

    return fig


def layout():
    """ """
    inner = dmc.Stack([
        dmc.Space(h=10),
        heatmap_content(),
        dmc.Space(h=10),
        timelines(),
    ])

    layout_ = dbc.Container(
        [
            dmc.Space(h=30),
            dbc.Row(id="stat_row", className="mt-3", justify="center"),
            dbc.Row(
                [
                    dbc.Col(inner),
                ],
                justify="center",
                className="mt-3",
            ),
            dcc.Store(id="object-stats"),
        ],
        fluid="lg",
    )

    return layout_
