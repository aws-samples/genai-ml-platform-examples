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
import sys
import subprocess

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# Dependencies are installed via requirements.txt (mlflow, sagemaker-mlflow, boto3)

import numpy as np
import pandas as pd
import xgboost
import mlflow
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from time import gmtime, strftime

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
    
    # MLflow setup
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME")
    parent_run_id = os.environ.get("MLFLOW_PARENT_RUN_ID")
    
    # Try to read parent run ID from preprocessing output if not in env
    if not parent_run_id or parent_run_id == "":
        try:
            mlflow_file = '/opt/ml/processing/mlflow/parent_run_id.txt'
            if os.path.exists(mlflow_file):
                with open(mlflow_file, 'r') as f:
                    parent_run_id = f.read().strip()
                logger.info(f"Read parent run ID from preprocessing output: {parent_run_id}")
        except Exception as e:
            logger.warning(f"Could not read parent run ID from file: {e}")
    
    if tracking_uri:
        suffix = strftime('%d-%H-%M-%S', gmtime())
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.set_experiment(experiment_name=experiment_name if experiment_name else f"evaluation-{suffix}")
        if parent_run_id:
            run = mlflow.start_run(run_name=f"evaluate-{suffix}", parent_run_id=parent_run_id)
        else:
            run = mlflow.start_run(run_name=f"evaluate-{suffix}")
    
    try:
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
        X_test = xgboost.DMatrix(df, feature_names=[str(i) for i in range(df.shape[1])])

        logger.info("Performing predictions against test data.")
        predictions_prob = model.predict(X_test)
        predictions = (predictions_prob > 0.5).astype(int)

        logger.debug("Calculating classification metrics.")
        accuracy = accuracy_score(y_test, predictions)
        precision = precision_score(y_test, predictions)
        recall = recall_score(y_test, predictions)
        f1 = f1_score(y_test, predictions)
        auc = roc_auc_score(y_test, predictions_prob)
        
        # Log metrics to MLflow
        if tracking_uri:
            mlflow.log_metrics({
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "auc": auc
            })
        
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
            
        if tracking_uri:
            mlflow.log_artifact(evaluation_path)
    
    finally:
        if tracking_uri:
            mlflow.end_run()
