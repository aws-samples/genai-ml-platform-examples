# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Score the trained booster on the held-out evaluation split.

Writes TWO artifacts, for two different consumers:

``evaluation.json``
    Read by the pipeline's ConditionStep via a PropertyFile
    (``classification_metrics.accuracy.value``) to gate model registration.

``baseline.json``
    Read by Lab 5's drift monitor. The pipeline attaches it to the registered
    model package as ``ModelMetrics.ModelQuality.Statistics``, and Lab 5 resolves
    it by walking: endpoint -> endpoint config -> model ->
    Containers[].ModelPackageName -> describe_model_package -> that S3 URI.

    The key names in baseline.json are an API. They are consumed by
    ``load_baseline_from_registry()`` in
    ``lab5-monitoring/src/drift_monitoring/baseline.py``, and they match what
    Lab 3A writes so that a model built by this pipeline and a model built by
    the Lab 3A notebook are monitored identically. Renaming a key does not fail
    loudly -- the monitor just silently falls back to live data.

    Snapshot IDs are written as STRINGS: they are 19-digit int64 values that
    lose precision if a JSON reader parses them as floats.

    Three keys Lab 3A writes are deliberately NOT written here, because nothing
    reads them and inventing values would be worse than omitting them:

    ``model_package_arn``
        Not knowable yet -- registration happens after this step. Lab 5 injects
        the ARN itself after loading the file
        (``baseline["model_package_arn"] = arn``), so the stored value is dead
        weight even in Lab 3A.
    ``mlflow_model_id`` / ``mlflow_artifact_location``
        Artifacts of Lab 3A's MLflow-registry flow. Grepped: no consumer
        anywhere in the repo outside the notebook that writes them.
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
import tarfile
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# ---------------------------------------------------------------------------
# MLflow install, before any mlflow import. See the equivalent comment in the
# preprocessing step: mlflow pulls in PyJWT, which collides with the
# Debian-managed copy in this container, so the remediation cannot live in
# requirements.txt (FrameworkProcessor installs that file first).
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

import pandas as pd  # noqa: E402
import xgboost as xgb  # noqa: E402
import mlflow  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

BASE_DIR = "/opt/ml/processing"
THRESHOLD = 0.5

# Mirrors model_fn's candidate list in source_scripts/inference/inference.py, so
# the baseline is scored by the same file the endpoint will load.
MODEL_FILE_CANDIDATES = (
    "xgboost-model.json",
    "xgboost-model",
    "model.xgb",
    "model.ubj",
)


def is_within_directory(directory, target):
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    return os.path.commonprefix([abs_directory, abs_target]) == abs_directory


def safe_extract(tar, path="."):
    """Extract tarfile members, refusing path traversal."""
    for member in tar.getmembers():
        if not is_within_directory(path, os.path.join(path, member.name)):
            raise Exception("Attempted path traversal in tar file")
    tar.extractall(path)


def load_booster(model_dir):
    """Load the booster the same way the inference handler will.

    The training step writes the model with `Booster.save_model()` to an
    extensionless `xgboost-model`. An earlier version of the training step
    pickled it to that same name, which this function would fail to load -- the
    same failure the endpoint would hit at container start.
    """
    for name in MODEL_FILE_CANDIDATES:
        candidate = os.path.join(model_dir, name)
        if os.path.exists(candidate):
            logger.info("Loading booster from %s", candidate)
            booster = xgb.Booster()
            booster.load_model(candidate)
            return booster
    raise FileNotFoundError(
        "No XGBoost model file found in %s (looked for %s). If the training step "
        "pickled the model, switch it to Booster.save_model()."
        % (model_dir, ", ".join(MODEL_FILE_CANDIDATES))
    )


def read_json_if_present(path, default=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    logger.warning("%s not found", path)
    return {} if default is None else default


def read_text_if_present(path, default=""):
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return default


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-job-name", type=str, default="")
    parser.add_argument("--model-package-group", type=str, default="")
    parser.add_argument("--feature-schema-version", type=int, default=1)
    parser.add_argument("--code-commit-sha", type=str, default="",
                        help="Commit that produced this model (GITHUB_SHA in CI).")
    return parser.parse_args()


def main():
    args = parse_args()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME")
    parent_run_id = os.environ.get("MLFLOW_PARENT_RUN_ID") or read_text_if_present(
        "%s/mlflow/parent_run_id.txt" % BASE_DIR)

    if tracking_uri:
        suffix = datetime.utcnow().strftime("%d-%H-%M-%S")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(
            experiment_name=experiment_name if experiment_name else "evaluation-%s" % suffix)
        if parent_run_id:
            mlflow.start_run(run_name="evaluate-%s" % suffix, parent_run_id=parent_run_id)
        else:
            mlflow.start_run(run_name="evaluate-%s" % suffix)

    try:
        # --- Unpack the trained model
        extract_dir = os.path.join(BASE_DIR, "extracted")
        pathlib.Path(extract_dir).mkdir(parents=True, exist_ok=True)
        with tarfile.open("%s/model/model.tar.gz" % BASE_DIR) as tar:
            safe_extract(tar, path=extract_dir)
        booster = load_booster(extract_dir)

        # --- Score the held-out evaluation split.
        # test.csv is the FULL evaluation_data table read through its pinned
        # Iceberg snapshot, so these metrics describe exactly the rows
        # evaluation_snapshot_id names -- which is what makes them a valid
        # reference for Lab 5's model-drift check.
        df = pd.read_csv("%s/test/test.csv" % BASE_DIR, header=None)
        y_true = df.iloc[:, 0].astype(int).to_numpy()
        X = df.iloc[:, 1:]

        # DMatrix from a bare numpy array: the booster was trained on header-less
        # CSV so it carries positional names (f0..f19). A named DataFrame here
        # would raise a feature-name mismatch -- same reason inference.py does it.
        y_proba = booster.predict(xgb.DMatrix(X.values))
        y_pred = (y_proba > THRESHOLD).astype(int)

        metrics = {
            "roc_auc": float(roc_auc_score(y_true, y_proba)),
            "pr_auc": float(average_precision_score(y_true, y_proba)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
            "accuracy": float(accuracy_score(y_true, y_pred)),
        }
        logger.info("Evaluated %d rows (%d positive)", len(y_true), int(y_true.sum()))
        for name, value in metrics.items():
            logger.info("  %-10s %.4f", name, value)

        output_dir = "%s/evaluation" % BASE_DIR
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

        # --- evaluation.json: the ConditionStep's gate.
        # The nested {"value": x} shape is what JsonGet reads via the PropertyFile
        # path classification_metrics.accuracy.value -- do not flatten it.
        report = {
            "classification_metrics": {
                "accuracy": {"value": metrics["accuracy"]},
                "precision": {"value": metrics["precision"]},
                "recall": {"value": metrics["recall"]},
                "f1_score": {"value": metrics["f1_score"]},
                "auc": {"value": metrics["roc_auc"]},
            },
        }
        evaluation_path = os.path.join(output_dir, "evaluation.json")
        with open(evaluation_path, "w") as f:
            json.dump(report, f)
        logger.info("Wrote %s", evaluation_path)

        # --- baseline.json: Lab 5's contract.
        lineage = read_json_if_present("%s/lineage/lineage.json" % BASE_DIR)
        mlflow_run_id = read_text_if_present(
            os.path.join(extract_dir, "mlflow_run_id.txt"), "unresolved") or "unresolved"

        baseline = {
            "schema_version": 2,
            "created_at": datetime.now().isoformat(),
            "model_package_group": args.model_package_group,
            "code_commit_sha": args.code_commit_sha or args.training_job_name,
            "training_table": lineage.get("training_table", ""),
            "evaluation_table": lineage.get("evaluation_table", ""),
            "training_snapshot_id": str(lineage.get("training_snapshot_id", "")),
            "evaluation_snapshot_id": str(lineage.get("evaluation_snapshot_id", "")),
            "feature_schema_version": args.feature_schema_version,
            "feature_schema": lineage.get("feature_schema", []),
            "metrics": metrics,
            "sample_size": int(len(y_true)),
            "positive_samples": int(y_true.sum()),
            "negative_samples": int(len(y_true) - y_true.sum()),
            "threshold": THRESHOLD,
            "training_job_name": args.training_job_name,
            "mlflow_run_id": mlflow_run_id,
        }
        baseline_path = os.path.join(output_dir, "baseline.json")
        with open(baseline_path, "w") as f:
            json.dump(baseline, f, indent=2)
        logger.info("Wrote %s", baseline_path)
        logger.info("Baseline lineage: %s", json.dumps({
            k: baseline[k] for k in (
                "training_table", "training_snapshot_id",
                "evaluation_table", "evaluation_snapshot_id")}))

        if not baseline["training_snapshot_id"] or not baseline["evaluation_snapshot_id"]:
            logger.warning(
                "baseline.json has no pinned Iceberg snapshot, so Lab 5 will measure "
                "drift against the LIVE table. This happens only when the "
                "preprocessing step ran with --allow-unpinned-snapshots.")

        if tracking_uri:
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(evaluation_path)
            mlflow.log_artifact(baseline_path)

    finally:
        if tracking_uri:
            mlflow.end_run()


if __name__ == "__main__":
    main()
