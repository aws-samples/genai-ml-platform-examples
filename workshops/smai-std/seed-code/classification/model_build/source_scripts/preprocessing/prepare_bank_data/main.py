# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Materialize XGBoost training CSVs from the Lab 2 Iceberg tables.

This step reads the tables Lab 2 published (``training_data`` /
``evaluation_data`` in the ``bank_marketing`` Glue database) and writes
target-first, header-less CSVs for the training and evaluation steps.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does no feature engineering. Lab 2 already label-encoded every categorical
column to a DOUBLE, so the 20 features arrive model-ready. An earlier version of
this step downloaded its own copy of the raw UCI CSV and applied one-hot
encoding + standard scaling, which produced a ~60-column feature space that no
other lab in the workshop could serve or monitor. Re-encoding here would
reintroduce exactly that divergence.

THE TWO FORMAT RULES ARE THE XGBOOST CONTAINER'S, NOT OURS
----------------------------------------------------------
* Target first: column 0 is ``subscribed`` cast to 0/1, features follow.
* No header row: which is why feature ORDER is a hard contract. The booster
  will only ever know these columns by position (``f0..f19``).

SNAPSHOT PINNING
----------------
Drift detection asks whether live traffic still resembles the data the model was
trained on, so it needs that data *as it was at training time*. The Lab 2 tables
are overwritten on every re-run, so this step resolves each table's current
Iceberg snapshot and reads through it with ``FOR VERSION AS OF``. Those snapshot
IDs travel to Lab 5 in ``baseline.json``, which makes the recorded ID a true
description of what the model trained on rather than a hopeful annotation.

An unpinned baseline moves under the drift monitor and drives drift toward zero
-- a false negative indistinguishable from a healthy run. So failing to pin is
fatal by default; pass ``--allow-unpinned-snapshots`` to override.

Athena is queried with boto3 + pandas rather than awswrangler on purpose: the
only thing needed here is "run a query, read the CSV result", and avoiding
awswrangler keeps a heavyweight pinned dependency out of the container.
"""

import argparse
import glob
import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import time
from io import BytesIO
from time import gmtime, strftime

# ---------------------------------------------------------------------------
# MLflow install, before any mlflow import.
#
# These packages are installed HERE rather than via requirements.txt because
# FrameworkProcessor installs requirements.txt BEFORE running this script, and
# mlflow pulls in PyJWT, which collides with the Debian-managed PyJWT in the
# SageMaker sklearn container. The remediation below has to run first, so it
# cannot live in requirements.txt. Everything else this script needs (pandas,
# numpy, scikit-learn, boto3) already ships in the container.
# ---------------------------------------------------------------------------
for _path in glob.glob("/usr/local/lib/python*/dist-packages/PyJWT-*.dist-info"):
    shutil.rmtree(_path, ignore_errors=True)
for _path in glob.glob("/usr/lib/python3/dist-packages/PyJWT-*.dist-info"):
    shutil.rmtree(_path, ignore_errors=True)
for _path in glob.glob("/usr/lib/python3/dist-packages/jwt*"):
    if os.path.isdir(_path):
        shutil.rmtree(_path, ignore_errors=True)
    elif os.path.isfile(_path):
        os.remove(_path)

subprocess.check_call([
    sys.executable, "-m", "pip", "install",
    "--force-reinstall", "--no-deps", "PyJWT>=2.8.0", "-q",
])
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "mlflow==3.4.0", "sagemaker-mlflow", "-q",
])

import boto3  # noqa: E402
import pandas as pd  # noqa: E402
import mlflow  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

BASE_DIR = "/opt/ml/processing"


# ---------------------------------------------------------------------------
# Athena
# ---------------------------------------------------------------------------
def run_athena_query(athena, s3, sql, database, output_location):
    """Run `sql` and return its result as a DataFrame.

    Athena writes every successful query's result to
    ``<output_location>/<query-execution-id>.csv``, so the result is read
    straight from S3 rather than paged through get_query_results (which returns
    everything as strings and caps at 1000 rows per page).
    """
    logger.info("Athena query: %s", " ".join(sql.split()))
    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )["QueryExecutionId"]

    while True:
        execution = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)

    if state != "SUCCEEDED":
        reason = execution["Status"].get("StateChangeReason", "unknown")
        raise RuntimeError("Athena query %s: %s" % (state, reason))

    location = execution["ResultConfiguration"]["OutputLocation"]
    bucket, key = location.replace("s3://", "").split("/", 1)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return pd.read_csv(BytesIO(body))


def current_snapshot_id(athena, s3, database, table, output_location):
    """Current-lineage Iceberg snapshot ID for `table`, or '' if unresolvable.

    Reads ``$history`` rather than ``$snapshots``: ``$snapshots`` lists every
    snapshot ever written, including ones that are no longer ancestors of the
    current state after a rollback. ``is_current_ancestor`` asks the question we
    actually care about.
    """
    sql = (
        'SELECT CAST(snapshot_id AS VARCHAR) AS sid '
        'FROM "%s"."%s$history" '
        'WHERE is_current_ancestor ORDER BY made_current_at DESC LIMIT 1'
        % (database, table)
    )
    try:
        df = run_athena_query(athena, s3, sql, database, output_location)
    except Exception as e:
        logger.warning("%s: could not read $history (%s: %s)", table, type(e).__name__, e)
        return ""
    if df.empty:
        logger.warning("%s: no snapshots yet -- has Lab 2 written this table?", table)
        return ""
    return str(df["sid"].iloc[0])


def read_split(athena, s3, database, table, features, target_column,
               output_location, snapshot_id):
    """Read one Iceberg table as a target-first DataFrame."""
    source = table if not snapshot_id else "%s FOR VERSION AS OF %s" % (table, snapshot_id)
    sql = "SELECT CAST(%s AS integer) AS y, %s FROM %s" % (
        target_column, ", ".join(features), source,
    )
    df = run_athena_query(athena, s3, sql, database, output_location)
    logger.info("  FROM %s -> %d rows, %d cols", source, df.shape[0], df.shape[1])
    return df


def write_csv(df, directory, filename):
    """Write a target-first, header-less CSV for the XGBoost container."""
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
    path = os.path.join(directory, filename)
    df.to_csv(path, index=False, header=False)
    logger.info("  wrote %s (%d rows)", path, len(df))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=str, required=True,
                        help="Glue/Athena database holding the Lab 2 Iceberg tables.")
    parser.add_argument("--training-table", type=str, required=True)
    parser.add_argument("--evaluation-table", type=str, required=True)
    parser.add_argument("--features", type=str, required=True,
                        help="Comma-separated feature columns, in positional-contract order.")
    parser.add_argument("--target-column", type=str, default="subscribed")
    parser.add_argument("--athena-output", type=str, default="",
                        help="S3 location for Athena results. Derived from the Glue "
                             "database location when omitted.")
    parser.add_argument("--validation-fraction", type=float, default=0.1,
                        help="Fraction of training_data held back as the validation "
                             "channel. evaluation_data is never touched by this split.")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--allow-unpinned-snapshots", action="store_true",
                        help="Continue when an Iceberg snapshot cannot be resolved. "
                             "Degrades the Lab 5 baseline -- see module docstring.")
    return parser.parse_args()


def main():
    args = parse_args()
    features = [f.strip() for f in args.features.split(",") if f.strip()]
    logger.info("Feature contract: %d columns", len(features))

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    athena = boto3.client("athena", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    glue = boto3.client("glue", region_name=region)

    # Athena needs somewhere to put results. Default to the bucket that backs the
    # Glue database, which is the workshop data bucket -- the same convention
    # Lab 3A uses, so both labs leave their query results in one place.
    athena_output = args.athena_output
    if not athena_output:
        database = glue.get_database(Name=args.database)["Database"]
        location = (database.get("LocationUri") or "").rstrip("/")
        if not location:
            raise RuntimeError(
                "Glue database %s has no LocationUri, so the Athena results "
                "location cannot be derived. Pass --athena-output explicitly."
                % args.database
            )
        athena_output = "s3://%s/athena-query-results/" % location.split("/")[2]
    logger.info("Athena results -> %s", athena_output)

    # --- MLflow (parent run is created here when the pipeline did not supply one)
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME")
    parent_run_id = os.environ.get("MLFLOW_PARENT_RUN_ID")
    logger.info("MLflow: uri=%s experiment=%s parent_run=%s",
                tracking_uri, experiment_name, parent_run_id)

    created_parent_run_id = None
    if tracking_uri:
        suffix = strftime("%d-%H-%M-%S", gmtime())
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(
            experiment_name=experiment_name if experiment_name else "preprocessing-%s" % suffix
        )
        if not parent_run_id:
            parent_run = mlflow.start_run(run_name="pipeline-%s" % suffix)
            created_parent_run_id = parent_run.info.run_id
            mlflow.end_run()
            parent_run_id = created_parent_run_id
            logger.info("Created parent MLflow run %s", parent_run_id)
        mlflow.start_run(run_name="preprocess-%s" % suffix, parent_run_id=parent_run_id)

    try:
        # --- Pin one snapshot per table BEFORE reading either of them
        training_snapshot_id = current_snapshot_id(
            athena, s3, args.database, args.training_table, athena_output)
        evaluation_snapshot_id = current_snapshot_id(
            athena, s3, args.database, args.evaluation_table, athena_output)

        logger.info("Frozen baseline:")
        logger.info("  %s snapshot %s", args.training_table, training_snapshot_id or "(NONE)")
        logger.info("  %s snapshot %s", args.evaluation_table, evaluation_snapshot_id or "(NONE)")

        if not (training_snapshot_id and evaluation_snapshot_id):
            message = (
                "Could not pin an Iceberg snapshot for both tables, so drift would be "
                "measured against the LIVE table. Confirm Lab 2 has written "
                "%s.%s and %s.%s (run the Lab 2 data-prep notebook AND the Iceberg "
                "registration notebook), and that the pipeline role can query their "
                "$history metadata. To proceed anyway, pass "
                "--allow-unpinned-snapshots." % (
                    args.database, args.training_table,
                    args.database, args.evaluation_table,
                )
            )
            if not args.allow_unpinned_snapshots:
                raise RuntimeError(message)
            logger.warning("WARNING: %s", message)

        # --- Read both splits through their pinned snapshots
        train_full = read_split(
            athena, s3, args.database, args.training_table, features,
            args.target_column, athena_output, training_snapshot_id)
        test_df = read_split(
            athena, s3, args.database, args.evaluation_table, features,
            args.target_column, athena_output, evaluation_snapshot_id)

        # An empty table is the single most likely failure here, and the stack
        # trace it would otherwise cause (in train_test_split, or much later in
        # XGBoost) says nothing useful about the cause.
        for table, df in ((args.training_table, train_full), (args.evaluation_table, test_df)):
            if df.empty:
                raise RuntimeError(
                    "%s.%s returned 0 rows. The Iceberg tables are created empty by "
                    "CloudFormation and populated by Lab 2 -- run the Lab 2 data-prep "
                    "notebook, then the Iceberg registration notebook, then re-run this "
                    "pipeline." % (args.database, table)
                )

        # --- Carve the validation channel out of training_data only.
        # evaluation_data stays whole: it is the pinned, held-out model-drift
        # baseline, and sampling from it would make the baseline metrics
        # describe a different set of rows than evaluation_snapshot_id names.
        train_df, validation_df = train_test_split(
            train_full,
            test_size=args.validation_fraction,
            random_state=args.random_state,
            stratify=train_full["y"],
        )
        logger.info("Split %d training rows -> %d train / %d validation (stratified)",
                    len(train_full), len(train_df), len(validation_df))

        write_csv(train_df, "%s/train" % BASE_DIR, "train.csv")
        write_csv(validation_df, "%s/validation" % BASE_DIR, "validation.csv")
        write_csv(test_df, "%s/test" % BASE_DIR, "test.csv")

        # --- Lineage for the evaluation step's baseline.json
        lineage = {
            "database": args.database,
            "training_table": args.training_table,
            "evaluation_table": args.evaluation_table,
            "training_snapshot_id": str(training_snapshot_id),
            "evaluation_snapshot_id": str(evaluation_snapshot_id),
            "feature_schema": features,
            "target_column": args.target_column,
            "train_rows": int(len(train_df)),
            "validation_rows": int(len(validation_df)),
            "test_rows": int(len(test_df)),
        }
        pathlib.Path("%s/lineage" % BASE_DIR).mkdir(parents=True, exist_ok=True)
        with open("%s/lineage/lineage.json" % BASE_DIR, "w") as f:
            json.dump(lineage, f, indent=2)
        logger.info("Wrote lineage.json: %s", json.dumps(
            {k: lineage[k] for k in (
                "training_table", "training_snapshot_id",
                "evaluation_table", "evaluation_snapshot_id")}))

        # The parent run ID has to reach the training and evaluation steps, which
        # run in separate containers; a file on a pipeline channel is the only
        # path between them.
        pathlib.Path("%s/mlflow" % BASE_DIR).mkdir(parents=True, exist_ok=True)
        if created_parent_run_id:
            with open("%s/mlflow/parent_run_id.txt" % BASE_DIR, "w") as f:
                f.write(created_parent_run_id)

        if tracking_uri:
            mlflow.log_params({
                "database": args.database,
                "training_table": args.training_table,
                "evaluation_table": args.evaluation_table,
                "training_snapshot_id": str(training_snapshot_id),
                "evaluation_snapshot_id": str(evaluation_snapshot_id),
                "feature_count": len(features),
                "train_rows": len(train_df),
                "validation_rows": len(validation_df),
                "test_rows": len(test_df),
            })

        logger.info("Preprocessing complete")

    finally:
        if tracking_uri:
            mlflow.end_run()


if __name__ == "__main__":
    main()
