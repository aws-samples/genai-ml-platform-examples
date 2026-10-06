# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Repack the trained model artifact so it carries its own serving code.

SageMaker script mode looks for the inference handler INSIDE the model tarball,
at ``code/inference.py``. The training job's tarball contains only the booster,
so this step rebuilds it:

    input  model.tar.gz : ./xgboost-model, ./mlflow_run_id.txt
    output model.tar.gz : ./xgboost-model, ./mlflow_run_id.txt,
                          ./feature_names.json, ./code/inference.py

The result is a self-contained artifact -- weights, serving code, and column
order in one object -- which is what makes the registered model package
reproducible and independently deployable.

WHY A SEPARATE STEP RATHER THAN SDK REPACKING
---------------------------------------------
`RegisterModel(estimator=...)` and `Model(entry_point=...)` can repack a
source_dir into ``code/`` for you, but they do it inside a hidden, generated
training job, and they cannot place ``feature_names.json`` at the tarball ROOT
(model_fn reads it from the model directory, not from ``code/``). Doing it
explicitly here keeps the packaging visible in the pipeline graph and mirrors,
step for step, what the Lab 3A notebook does by hand.

WHY feature_names.json
----------------------
The booster knows its inputs only by position (f0..f19). The handler uses this
file to reorder an incoming JSON request into the training column order before
building the DMatrix. Without it the handler falls back to whatever order the
request happened to use, which silently produces wrong predictions rather than
an error.

Standard library only -- no requirements.txt for this step.
"""

import argparse
import json
import logging
import os
import pathlib
import shutil
import sys
import tarfile

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

INPUT_DIR = "/opt/ml/processing/input/model"
OUTPUT_DIR = "/opt/ml/processing/output/model"
WORK_DIR = "/tmp/model_repack"

HERE = os.path.dirname(os.path.abspath(__file__))


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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features", type=str, required=True,
        help="Comma-separated feature columns in positional-contract order. "
             "Written to feature_names.json inside the artifact.")
    return parser.parse_args()


def main():
    args = parse_args()
    features = [f.strip() for f in args.features.split(",") if f.strip()]
    if not features:
        raise ValueError("--features resolved to an empty list")
    logger.info("Feature contract: %d columns", len(features))

    shutil.rmtree(WORK_DIR, ignore_errors=True)
    extracted = os.path.join(WORK_DIR, "extracted")
    pathlib.Path(os.path.join(extracted, "code")).mkdir(parents=True, exist_ok=True)
    pathlib.Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # --- 1. Unpack the training artifact
    source_tar = os.path.join(INPUT_DIR, "model.tar.gz")
    if not os.path.exists(source_tar):
        available = os.listdir(INPUT_DIR) if os.path.isdir(INPUT_DIR) else "<missing dir>"
        raise FileNotFoundError(
            "Expected %s from the training step; found %s" % (source_tar, available))
    with tarfile.open(source_tar, "r:gz") as tar:
        safe_extract(tar, path=extracted)
    logger.info("Unpacked %s -> %s", source_tar, sorted(os.listdir(extracted)))

    # --- 2. Add the serving code
    handler_src = os.path.join(HERE, "inference.py")
    if not os.path.exists(handler_src):
        raise FileNotFoundError(
            "inference.py not found next to this script (looked in %s). The repack "
            "step's source_dir must contain both repack.py and inference.py." % HERE)
    shutil.copy(handler_src, os.path.join(extracted, "code", "inference.py"))

    # --- 3. Add the column order, at the tarball ROOT (model_fn reads it from
    #        the model directory, NOT from code/).
    with open(os.path.join(extracted, "feature_names.json"), "w") as f:
        json.dump({"feature_names": features}, f)

    # --- 4. Re-tar. arcname='.' keeps members relative, so the container sees
    #        /opt/ml/model/xgboost-model rather than a nested directory.
    repacked = os.path.join(OUTPUT_DIR, "model.tar.gz")
    with tarfile.open(repacked, "w:gz") as tar:
        tar.add(extracted, arcname=".")

    # --- 5. Verify, while a failure still costs nothing. Without this, a
    #        packaging mistake surfaces ten minutes later as a 5xx from a
    #        deployed endpoint.
    with tarfile.open(repacked, "r:gz") as tar:
        names = tar.getnames()

    problems = []
    if not any(n.endswith("code/inference.py") for n in names):
        problems.append("code/inference.py missing")
    if not any(os.path.basename(n) == "feature_names.json" for n in names):
        problems.append("feature_names.json missing")
    if not any(os.path.basename(n).startswith("xgboost-model") for n in names):
        problems.append("xgboost-model missing")
    if problems:
        raise RuntimeError(
            "Repacked artifact is invalid (%s). Members: %s"
            % ("; ".join(problems), names))

    logger.info("Repacked artifact -> %s", repacked)
    logger.info("  members: %s", sorted(n for n in names if n not in (".",)))


if __name__ == "__main__":
    main()
