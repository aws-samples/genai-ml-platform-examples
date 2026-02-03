# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Evaluation script for measuring classification metrics."""
import json
import logging
import pathlib
import pickle
import tarfile
import os

import numpy as np
import pandas as pd
import xgboost

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

def is_within_directory(directory, target):
    """Check if the target is within the given directory."""
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    prefix = os.path.commonprefix([abs_directory, abs_target])
    return prefix == abs_directory


def safe_extract(tar, path="."):
    """Extract tarfile members safely."""
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not is_within_directory(path, member_path):
            raise Exception("Attempted Path Traversal in Tar File")
    tar.extractall(path)

if __name__ == "__main__":
    logger.debug("Starting evaluation.")
    model_path = "/opt/ml/processing/model/model.tar.gz"
    with tarfile.open(model_path) as tar:
        safe_extract(tar, path=".")

    logger.debug("Loading xgboost model.")
    model = pickle.load(open("xgboost-model", "rb"))

    logger.debug("Reading test data.")
    test_path = "/opt/ml/processing/test/test.csv"
    df = pd.read_csv(test_path, header=None)

    logger.debug("Reading test data.")
    y_test = df.iloc[:, 0].to_numpy()
    df.drop(df.columns[0], axis=1, inplace=True)
    X_test = xgboost.DMatrix(df.values)

    logger.info("Performing predictions against test data.")
    predictions_prob = model.predict(X_test)
    predictions = (predictions_prob > 0.5).astype(int)

    logger.debug("Calculating classification metrics.")
    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    f1 = f1_score(y_test, predictions)
    auc = roc_auc_score(y_test, predictions_prob)
    
    report_dict = {
        "classification_metrics": {
            "accuracy": {"value": accuracy},
            "precision": {"value": precision},
            "recall": {"value": recall},
            "f1_score": {"value": f1},
            "auc": {"value": auc},
        },
    }

    output_dir = "/opt/ml/processing/evaluation"
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Writing out evaluation report with accuracy: %f", accuracy)
    evaluation_path = f"{output_dir}/evaluation.json"
    with open(evaluation_path, "w") as f:
        f.write(json.dumps(report_dict))
