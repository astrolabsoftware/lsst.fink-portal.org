#!/usr/bin/env python
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
import argparse
import logging
import sys
from logging import Logger

from time import time

from fink_science.ztf.xmatch.utils import cross_match_astropy
from astropy.coordinates import SkyCoord
from astropy import units as u

import numpy as np
import pandas as pd
import pyspark.sql.functions as F
import requests
from fink_utils.spark import schema_converter
from fink_utils.spark.utils import (
    FinkUDF,
    expand_function_from_string,
)
from pyspark import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.column import Column, _to_java_column
from pyspark.sql.functions import PandasUDFType, lit, pandas_udf, struct
from pyspark.sql.types import BooleanType, StringType


def get_fink_logger(name: str = "test", log_level: str = "INFO") -> Logger:
    """Initialise python logger. Suitable for both driver and executors.

    Parameters
    ----------
    name : str
        Name of the application to be logged. Typically __name__ of a
        function or module.
    log_level : str
        Minimum level of log wanted: DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF

    Returns
    -------
    logger : logging.Logger
        Python Logger

    Examples
    --------
    >>> log = get_fink_logger(__name__, "INFO")
    >>> log.info("Hi!")
    """
    # Format of the log message to be printed
    FORMAT = "%(asctime)-15s "
    FORMAT += "-Livy- "
    FORMAT += "%(message)s"

    # Date format
    DATEFORMAT = "%y/%m/%d %H:%M:%S"

    logging.basicConfig(format=FORMAT, datefmt=DATEFORMAT)
    logger = logging.getLogger(name)

    # Set the minimum log level
    logger.setLevel(log_level)

    return logger


def add_classification(spark, df, path_to_tns):
    """Recompute classification from TNS

    Notes
    -----
    We recompute TNS column because crossmatch has
    probably evolved since the moment we processed the alert

    Parameters
    ----------
    spark:
    df: DataFrame
        Spark DataFrame containing ZTF alert data
    path_to_tns: str
        Path to TNS data (parquet)

    Returns
    -------
    df: DataFrame
        Input DataFrame with 2 new columns `finkclass` and
        `tns_type_recomputed` containing classification tags.
    """
    pdf_tns_filt = pd.read_parquet(path_to_tns)
    pdf_tns_filt_b = spark.sparkContext.broadcast(pdf_tns_filt)

    @pandas_udf(StringType(), PandasUDFType.SCALAR)
    def crossmatch_with_tns(diaobjectid, ra, dec):
        # TNS
        pdf = pdf_tns_filt_b.value
        ra2, dec2, type2 = pdf["ra"], pdf["declination"], pdf["type"]

        # create catalogs
        catalog_lsst = SkyCoord(
            ra=np.array(ra, dtype=float) * u.degree,
            dec=np.array(dec, dtype=float) * u.degree,
        )
        catalog_tns = SkyCoord(
            ra=np.array(ra2, dtype=float) * u.degree,
            dec=np.array(dec2, dtype=float) * u.degree,
        )

        # cross-match
        idx, d2d, d3d = catalog_tns.match_to_catalog_sky(catalog_lsst)  # noqa: RUF059

        sub_pdf = pd.DataFrame({
            "diaobjectId": diaobjectid.to_numpy(),
            "ra": ra.to_numpy(),
            "dec": dec.to_numpy(),
        })

        # cross-match
        idx2, d2d2, _ = catalog_lsst.match_to_catalog_sky(catalog_tns)

        # set separation length
        sep_constraint2 = d2d2.degree < 1.5 / 3600

        sub_pdf["TNS"] = ["Unknown"] * len(sub_pdf)
        sub_pdf["TNS"][sep_constraint2] = type2.to_numpy()[idx2[sep_constraint2]]

        return diaobjectid.apply(
            lambda x: (
                "Unknown"
                if x not in sub_pdf["diaobjectId"].to_numpy()
                else sub_pdf["TNS"][sub_pdf["diaobjectId"] == x].to_numpy()[0]
            )
        )

    return df.withColumn(
        "tns_type_recomputed",
        crossmatch_with_tns(
            df["diaObject.diaObjectId"], df["diaSource.ra"], df["diaSource.dec"]
        ),
    )


def to_avro(dfcol: Column) -> Column:
    """Serialize the structured data of a DataFrame column into avro data (binary).

    Note:
    Since Pyspark does not have a function to convert a column to and from
    avro data, this is a wrapper around the scala function 'to_avro'.
    Just like the function above, to be able to use this you need to have
    the package org.apache.spark:spark-avro_2.11:2.x.y in the classpath.

    Parameters
    ----------
    dfcol: Column
        A DataFrame Column with Structured data

    Returns
    -------
    out: Column
        DataFrame Column encoded into avro data (binary).
        This is what is required to publish to Kafka Server for distribution.

    Examples
    --------
    >>> from pyspark.sql.functions import col, struct
    >>> avro_example_schema = '''
    ... {
    ...     "type" : "record",
    ...     "name" : "struct",
    ...     "fields" : [
    ...             {"name" : "col1", "type" : "long"},
    ...             {"name" : "col2", "type" : "string"}
    ...     ]
    ... }'''
    >>> df = spark.range(5)
    >>> df = df.select(struct("id",\
                 col("id").cast("string").alias("id2"))\
                 .alias("struct"))
    >>> avro_df = df.select(to_avro(col("struct")).alias("avro"))
    """
    sc = SparkContext._active_spark_context
    avro = sc._jvm.org.apache.spark.sql.avro
    f = getattr(getattr(avro, "package$"), "MODULE$").to_avro
    return Column(f(_to_java_column(dfcol)))


def write_to_kafka(
    sdf,
    key,
    kafka_bootstrap_servers,
    kafka_sasl_username,
    kafka_sasl_password,
    topic_name,
    npart=10,
):
    """Send data to a Kafka cluster using Apache Spark

    Parameters
    ----------
    sdf: Spark DataFrame
        DataFrame
    key: str
        key for each Avro message
    kafka_bootstrap_servers: str
        Comma-separated list of ip:port of the Kafka machines
    kafka_sasl_username: str
        Username for writing into the Kafka cluster
    kafka_sasl_password: str
        Password for writing into the Kafka cluster
    topic_name: str
        Kafka topic (does not need to exist)
    npart: int, optional
        Number of Kafka partitions. Default is 10.
    """
    # Create a StructType column in the df for distribution.
    df_struct = sdf.select(struct(sdf.columns).alias("struct"))
    df_kafka = df_struct.select(to_avro("struct").alias("value"))
    df_kafka = df_kafka.withColumn("key", key)
    df_kafka = df_kafka.withColumn("partition", (F.rand(seed=0) * npart).astype("int"))

    # Send schema
    _ = (
        df_kafka.write
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("kafka.sasl.username", kafka_sasl_username)
        .option("kafka.sasl.password", kafka_sasl_password)
        .option("topic", topic_name)
        .save()
    )


def check_path_exist(dateToCheck):
    """Check we have data for the given night

    Parameters
    ----------
    dateToCheck: str
        YYYY-MM-DD

    Returns
    -------
    out: bool
    """
    r = requests.post(
        "https://api.lsst.fink-portal.org/api/v1/statistics",
        json={
            "date": "{}{}{}".format(*dateToCheck.split("-")),
            "columns": "f:alerts",
            "output-format": "json",
        },
    )
    return r.json() != []


def generate_spark_paths(startDate, stopDate, basePath):
    """Generate individual data paths

    Parameters
    ----------
    startDate: str
        YYYY-MM-DD
    stopDate: str
        YYYY-MM-DD
    basePath: str
        HDFS basepath for the data

    Returns
    -------
    paths: list of str
        List of paths
    """
    endPath = "/year={}/month={}/day={}"

    if startDate == stopDate:
        # easy case -- one night
        if check_path_exist(startDate):
            paths = [basePath + endPath.format(*startDate.split("-"))]
        else:
            paths = []
    else:
        # more than one night
        dateRange = (
            pd.date_range(start=startDate, end=stopDate).astype("str").to_numpy()
        )

        paths = []
        for aDate in dateRange:
            if check_path_exist(aDate):
                paths.append(basePath + endPath.format(*aDate.split("-")))

    return paths


def cast_long_to_str(df):
    """Cast long into str"""
    for section in ["diaSource", "diaObject", "ssSource"]:
        for field in ["diaObjectId", "diaSourceId", "parentDiaSourceId", "visit"]:
            if field in df.select(section).columns:
                df = df.withColumn(
                    section,
                    F.col(field).withField(field, df[f"{section}.{field}"].cast("str")),
                )
    return df


def sanitize_fields(cnames):
    """Apply proper serialization before sending to Kafka

    Notes
    -----
    Timestamps are casted to strings

    Parameters
    ----------
    cnames: list
        List of fields

    Returns
    -------
    cnames: list
        List of fields, sanitized.
    """
    for col in [
        "xm",
        "clf",
        "pred",
        "misc",
        "diaSource",
        "diaObject",
        "ssSource",
        "MPCORB",
        "mpc_orbits",
    ]:
        if col in cnames:
            cnames[cnames.index(col)] = f"struct({col}.*) as {col}"

    for ts in [
        "timestamp",
        "brokerEndProcessTimestamp",
        "brokerStartProcessTimestamp",
        "brokerIngestTimestamp",
    ]:
        if ts in cnames:
            cnames[cnames.index(ts)] = f"cast({ts} as string) as {ts}"

    # not needed actually as cnames is changed in-place
    return cnames


def apply_filter_or_block(df, names, is_filter=False, is_block=False, logger=None):
    """Wrapper to apply a function by its name on the flatten dataframe

    Parameters
    ----------
    df: Spark DataFrame
        Flatten Spark DataFrame
    names: list of str
        List of filter or blocks names (function names)
    is_filter: bool
        If True, assumes `names` are filters
    is_blocks: bool
        If True, assumes `names` are blocks

    Returns
    -------
    out: Spark DataFrame
        Filtered Spark DataFrame
    """
    if (not is_filter) and (not is_block):
        if logger is not None:
            logger.warning("You need to set one of is_filter or is_block")

    if is_filter and is_block:
        if logger is not None:
            logger.warning("You need to set at most one of is_filter or is_block")

    if is_block:
        name = "block"
    else:
        name = "filter"

    for userfilter in names:
        if userfilter == "":
            continue
        if logger is not None:
            logger.info(f"Applying user-defined {name} {userfilter}...")
        if userfilter.startswith("NOT"):
            reverse = True
            tag = userfilter.split("NOT")[-1].strip()
        else:
            reverse = False
            tag = userfilter.strip()
        base_module = "fink_filters.rubin"

        if is_filter:
            function_name = f"{base_module}.livestream.filter_{tag}.filter.{tag}"
        elif is_block:
            function_name = f"{base_module}.blocks.{tag}"
        filter_func, colnames = expand_function_from_string(df, function_name)
        fink_filter = FinkUDF(
            filter_func,
            BooleanType(),
            tag,
        )
        if reverse:
            df = df.filter(~fink_filter.for_spark(*colnames))
        else:
            df = df.filter(fink_filter.for_spark(*colnames))

    return df


def perform_xmatch(spark, df, catalog_filename, ra_col, dec_col, id_col, radius_arcsec):
    """Crossmatch a DataFrame to a catalog with Spark"""
    df_other = spark.read.format("parquet").load(catalog_filename)
    pdf_other = df_other.toPandas()
    pdf_b = spark.sparkContext.broadcast(pdf_other)

    @pandas_udf(StringType(), PandasUDFType.SCALAR)
    def crossmatch(ra, dec):
        """Spark UDF for simple crossmatch"""
        pdf_cat = pdf_b.value
        ra2, dec2, id2 = pdf_cat[ra_col], pdf_cat[dec_col], pdf_cat[id_col]

        pdf = pd.DataFrame({
            "ra": ra.to_numpy(),
            "dec": dec.to_numpy(),
            "candid": range(len(ra)),
        })

        # FIXME: Assumes degrees. Need to generalize for any coordinates type
        if ra2.dtype == float:
            # Limit the catalog to Rubin declinations
            dec_min, dec_max = dec.min(), dec.max()

            # extend the box for safety
            pad = 2 * radius_arcsec / 3600
            mask = (dec2 >= dec_min - pad) & (dec2 <= dec_max + pad)
            if mask.sum() == 0:
                # No overlap, return only Unknowns
                return pd.Series(["Unknown"] * len(ra))

            ra2 = ra2[mask]
            dec2 = dec2[mask]
            id2 = id2[mask]

        # create catalogs
        catalog_ztf = SkyCoord(
            ra=np.array(ra, dtype=float) * u.degree,
            dec=np.array(dec, dtype=float) * u.degree,
        )
        catalog_other = SkyCoord(
            ra=np.array(ra2, dtype=float) * u.degree,
            dec=np.array(dec2, dtype=float) * u.degree,
        )

        pdf_merge, mask, idx2 = cross_match_astropy(
            pdf, catalog_ztf, catalog_other, radius_arcsec=pd.Series([radius_arcsec])
        )

        pdf_merge["Type"] = "Unknown"
        pdf_merge.loc[mask, "Type"] = [
            str(i).strip() for i in id2.astype(str).to_numpy()[idx2]
        ]

        return pdf_merge["Type"]

    # Keep only matches
    df = df.withColumn(
        id_col,
        crossmatch(df["diaSource.ra"], df["diaSource.dec"]),
    ).filter(F.col(id_col) != "Unknown")

    return df


def main(args):
    spark = SparkSession.builder.getOrCreate()

    # reduce Java verbosity
    spark.sparkContext.setLogLevel("WARN")

    log = get_fink_logger(__file__)

    log.info("Generating data paths...")
    paths = generate_spark_paths(args.startDate, args.stopDate, args.basePath)
    if paths == []:
        log.info(f"No alert data found in between {args.startDate} and {args.stopDate}")
        spark.stop()
        sys.exit(1)

    df = (
        spark.read
        .format("parquet")
        .option("mergeSchema", "true")
        .option("basePath", args.basePath)
        .load(paths)
    )

    df = add_classification(spark, df, args.path_to_tns)

    if args.catalog_filename is not None:
        # Perform the xmatch
        log.info("Crossmatching with {}".format(args.catalog_filename.split("/")[-1]))
        df = perform_xmatch(
            spark,
            df,
            args.catalog_filename,
            args.ra_col,
            args.dec_col,
            args.id_col,
            float(args.radius_arcsec),
        )

    # direct Spark SQL filtering
    if args.extraCond is not None:
        for cond in args.extraCond:
            if cond == "":
                continue
            df = df.filter(cond)

    # UDF (filters)
    if args.ffilter is not None:
        df = apply_filter_or_block(df, args.ffilter, is_filter=True, logger=log)

    # UDF (blocks)
    if args.fblock is not None:
        df = apply_filter_or_block(df, args.fblock, is_block=True, logger=log)

    # Define content
    if args.ffield is None:
        content = ["Full packet"]
    elif not isinstance(args.ffield, list):
        log.warning(f"Content has not been defined: {args.ffield}")
        log.warning("Exiting.")
        spark.stop()
        sys.exit(1)
    else:
        content = args.ffield

    log.info(f"Selecting content {content}...")

    if "Full packet" in content:
        # Cast fields to ease the distribution
        cnames = df.columns
    elif "Medium packet" in content:
        cnames = [col for col in df.columns if not col.startswith("cutout")]
    elif "Light static packet" in content:
        # Wanted content from diaSource.
        cnames = [
            "diaSource.diaObjectId",
            "diaSource.snr",
            "diaSource.psfFlux",
            "diaSource.psfFluxErr",
            "diaSource.scienceFlux",
            "diaSource.scienceFluxErr",
            "diaSource.templateFlux",
            "diaSource.templateFluxErr",
            "diaSource.band",
            "diaSource.midpointMjdTai",
            "diaSource.ra",
            "diaSource.dec",
            "diaSource.reliability",
        ]

        # add other values from the root level,
        # including fink derived products & tns_type_recomputed
        to_avoid = [
            "cutoutScience",
            "cutoutTemplate",
            "cutoutDifference",
            "diaSource",
            "prvDiaSources",
            "prvDiaForcedSources",
            "diaObject",
            "ssSource",
            "MPCORB",
            "mpc_orbits",
            "day",
            "month",
            "year",
        ]
        [cnames.append(col) for col in df.columns if col not in to_avoid]
    elif "Light SSO packet" in content:
        # Wanted content from diaSource.
        cnames = [
            "diaSourceId",
            "ssSource.ssObjectId",
            "ssSource.phaseAngle",
            "ssSource.diaDistanceRank",
            "diaSource.snr",
            "diaSource.psfFlux",
            "diaSource.psfFluxErr",
            "diaSource.scienceFlux",
            "diaSource.scienceFluxErr",
            "diaSource.templateFlux",
            "diaSource.templateFluxErr",
            "diaSource.band",
            "diaSource.midpointMjdTai",
            "diaSource.ra",
            "diaSource.dec",
            "diaSource.reliability",
            "mpc_orbits.packed_primary_provisional_designation",
            "mpc_orbits.unpacked_primary_provisional_designation",
            "lsst_schema_version",
            "fink_broker_version",
            "fink_science_version",
        ]

    elif isinstance(content, list):
        # other cases
        cnames = content

    # enforce proper serialisation
    cnames = sanitize_fields(cnames)

    # Wrap alert data
    df = df.selectExpr(cnames)

    # extract schema
    log.info("Determining data schema...")
    schema = schema_converter.to_avro(df.coalesce(1).limit(1).schema)

    log.info("Schema OK...")

    # create a fake dataframe with 100 entries
    df_schema = spark.createDataFrame(
        pd.DataFrame({"schema": [f"new_schema_{time()}.avsc"] * 1000})
    )

    log.info("Sending the schema to Kafka...")

    # Send schema
    write_to_kafka(
        df_schema,
        lit(schema),
        args.kafka_bootstrap_servers,
        args.kafka_sasl_username,
        args.kafka_sasl_password,
        args.topic_name + "_schema",
    )

    log.info(f"Starting to send data to topic {args.topic_name}")

    write_to_kafka(
        df,
        lit(args.topic_name),
        args.kafka_bootstrap_servers,
        args.kafka_sasl_username,
        args.kafka_sasl_password,
        args.topic_name,
    )

    log.info(f"Data available at topic: {args.topic_name}")
    log.info("End.")


if __name__ == "__main__":
    """ Execute the test suite """
    parser = argparse.ArgumentParser()

    parser.add_argument("-startDate")
    parser.add_argument("-stopDate")
    parser.add_argument("-ffilter", action="append")
    parser.add_argument("-fblock", action="append")
    parser.add_argument("-extraCond", action="append")
    parser.add_argument("-ffield", action="append")
    parser.add_argument("-ra_col")
    parser.add_argument("-dec_col")
    parser.add_argument("-radius_arcsec")
    parser.add_argument("-id_col")
    parser.add_argument("-catalog_filename")
    parser.add_argument("-basePath")
    parser.add_argument("-topic_name")
    parser.add_argument("-kafka_bootstrap_servers")
    parser.add_argument("-kafka_sasl_username")
    parser.add_argument("-kafka_sasl_password")
    parser.add_argument("-path_to_tns")

    args = parser.parse_args()
    main(args)
