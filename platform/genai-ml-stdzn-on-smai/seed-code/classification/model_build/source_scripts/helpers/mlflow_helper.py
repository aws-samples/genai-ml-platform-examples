# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""MLflow helper utilities for SageMaker pipeline integration."""
import os
import mlflow
from time import gmtime, strftime
from typing import Optional


def setup_mlflow(
    step_name: str,
    tracking_uri: Optional[str] = None,
    experiment_name: Optional[str] = None,
    run_id: Optional[str] = None
):
    """
    Setup MLflow tracking for a pipeline step.
    
    Args:
        step_name: Name of the pipeline step
        tracking_uri: MLflow tracking server URI (defaults to env var)
        experiment_name: MLflow experiment name (defaults to env var)
        run_id: Existing run ID to continue (defaults to env var)
    
    Returns:
        tuple: (experiment, run) or (None, None) if tracking not configured
    """
    tracking_uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = experiment_name or os.environ.get("MLFLOW_EXPERIMENT_NAME")
    run_id = run_id or os.environ.get("MLFLOW_RUN_ID")
    
    if not tracking_uri:
        return None, None
    
    suffix = strftime('%d-%H-%M-%S', gmtime())
    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.set_experiment(
        experiment_name=experiment_name if experiment_name else f"{step_name}-{suffix}"
    )
    run = mlflow.start_run(run_id=run_id) if run_id else mlflow.start_run(
        run_name=f"{step_name}-{suffix}", 
        nested=True
    )
    
    return experiment, run
