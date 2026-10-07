#!/usr/bin/env python3
"""Run the training pipeline by hand, outside GitHub Actions.

Normally the pipeline is built and started by `.github/workflows/build.yml`,
which reads `config/pipeline_config.json`. This script is the manual equivalent,
useful for iterating on the pipeline definition without pushing a commit.

PREREQUISITE: Lab 2 must have populated the Iceberg tables
(`bank_marketing.training_data` and `.evaluation_data`) -- run the Lab 2
data-prep notebook AND the Iceberg registration notebook first. The preprocessing
step fails with an explicit message if either table is empty.
"""

import boto3
import sagemaker

from ml_pipelines.training.pipeline import get_pipeline

# --- Configuration: replace these with values from your account ---------------
REGION = "us-east-1"
ROLE = "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
ARTIFACT_BUCKET = "my-sagemaker-bucket"          # pipeline-managed outputs
DATA_BUCKET = "my-workshop-data-bucket"          # where baseline.json is written

# The Lab 2 Iceberg tables this pipeline trains on.
ATHENA_DATABASE = "bank_marketing"
TRAINING_TABLE = "training_data"
EVALUATION_TABLE = "evaluation_data"

# --- MLflow ------------------------------------------------------------------
# Keep this experiment distinct from Lab 3A's ("bank-marketing-prediction").
# Lab 3A resolves its MLflow run id with search_runs(order_by=start_time DESC,
# max_results=1) on its own experiment, so sharing one would let a pipeline run
# become the run id Lab 3A records in its baseline.json.
MLFLOW_TRACKING_URI = (
    "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/my-server"
)
MLFLOW_EXPERIMENT_NAME = "bank-classification-experiment"


def build_pipeline(sagemaker_session, mlflow_tracking_uri=None):
    """Construct the pipeline. Pass mlflow_tracking_uri=None to skip tracking."""
    return get_pipeline(
        region=REGION,
        role=ROLE,
        default_bucket=ARTIFACT_BUCKET,
        data_bucket=DATA_BUCKET,
        model_package_group_name="bank-classification-model-group",
        pipeline_name="BankMarketingPipeline",
        base_job_prefix="BankMarketing",
        sagemaker_session=sagemaker_session,
        athena_database=ATHENA_DATABASE,
        training_table=TRAINING_TABLE,
        evaluation_table=EVALUATION_TABLE,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_experiment_name=MLFLOW_EXPERIMENT_NAME,
        code_commit_sha="local-run",
    )


def main():
    """Upsert and start the pipeline with MLflow tracking enabled."""
    sagemaker_session = sagemaker.Session(
        boto_session=boto3.Session(region_name=REGION),
        default_bucket=ARTIFACT_BUCKET,
    )

    pipeline = build_pipeline(sagemaker_session, MLFLOW_TRACKING_URI)
    pipeline.upsert(role_arn=ROLE)
    print(f"Pipeline upserted: {pipeline.name}")

    execution = pipeline.start(
        parameters={
            "ProcessingInstanceType": "ml.m5.xlarge",
            "TrainingInstanceType": "ml.m5.xlarge",
            "ModelApprovalStatus": "PendingManualApproval",
            "AthenaDatabase": ATHENA_DATABASE,
            "TrainingTable": TRAINING_TABLE,
            "EvaluationTable": EVALUATION_TABLE,
            "MLflowTrackingUri": MLFLOW_TRACKING_URI,
            "MLflowExperimentName": MLFLOW_EXPERIMENT_NAME,
        }
    )

    print(f"Pipeline execution started: {execution.arn}")
    print(f"MLflow experiment: {MLFLOW_EXPERIMENT_NAME}")


def run_without_mlflow():
    """Upsert and start the pipeline with MLflow tracking disabled."""
    sagemaker_session = sagemaker.Session(
        boto_session=boto3.Session(region_name=REGION),
        default_bucket=ARTIFACT_BUCKET,
    )

    pipeline = build_pipeline(sagemaker_session, mlflow_tracking_uri=None)
    pipeline.upsert(role_arn=ROLE)

    execution = pipeline.start(
        parameters={
            "AthenaDatabase": ATHENA_DATABASE,
            "TrainingTable": TRAINING_TABLE,
            "EvaluationTable": EVALUATION_TABLE,
        }
    )

    print(f"Pipeline execution started without MLflow: {execution.arn}")


if __name__ == "__main__":
    main()

    # Or run without MLflow (uncomment to test)
    # run_without_mlflow()
