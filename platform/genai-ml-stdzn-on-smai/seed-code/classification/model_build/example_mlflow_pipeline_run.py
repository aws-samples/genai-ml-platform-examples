#!/usr/bin/env python3
"""
Example script demonstrating how to run the pipeline with MLflow tracking enabled.
"""

import boto3
import sagemaker
from ml_pipelines.training.pipeline import get_pipeline

# Configuration
REGION = "us-east-1"
ROLE = "arn:aws:iam::123456789012:role/SageMakerExecutionRole"  # Replace with your role
BUCKET = "my-sagemaker-bucket"  # Replace with your bucket
GLUE_DATABASE = "bank_marketing_db"  # Replace with your Glue database
GLUE_TABLE = "bank_marketing_table"  # Replace with your Glue table

# MLflow Configuration
MLFLOW_TRACKING_URI = "arn:aws:sagemaker:us-east-1:123456789012:mlflow-tracking-server/my-server"  # Replace
MLFLOW_EXPERIMENT_NAME = "BankMarketingExperiment"

def main():
    """Run the pipeline with MLflow tracking."""
    
    # Initialize SageMaker session
    sagemaker_session = sagemaker.Session(
        boto_session=boto3.Session(region_name=REGION),
        default_bucket=BUCKET
    )
    
    # Get pipeline instance
    pipeline = get_pipeline(
        region=REGION,
        role=ROLE,
        default_bucket=BUCKET,
        model_package_group_name="BankMarketingPackageGroup",
        pipeline_name="BankMarketingPipeline",
        base_job_prefix="BankMarketing",
        sagemaker_session=sagemaker_session,
        glue_database_name=GLUE_DATABASE,
        glue_table_name=GLUE_TABLE,
    )
    
    # Upsert pipeline (create or update)
    pipeline.upsert(role_arn=ROLE)
    print(f"Pipeline upserted: {pipeline.name}")
    
    # Start pipeline execution with MLflow parameters
    execution = pipeline.start(
        parameters={
            "ProcessingInstanceType": "ml.m5.xlarge",
            "TrainingInstanceType": "ml.m5.xlarge",
            "ModelApprovalStatus": "PendingManualApproval",
            "GlueDatabase": GLUE_DATABASE,
            "GlueTable": GLUE_TABLE,
            # MLflow parameters
            "MLflowTrackingUri": MLFLOW_TRACKING_URI,
            "MLflowExperimentName": MLFLOW_EXPERIMENT_NAME,
        }
    )
    
    print(f"Pipeline execution started: {execution.arn}")
    print(f"MLflow experiment: {MLFLOW_EXPERIMENT_NAME}")
    print(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")
    
    # Wait for execution to complete (optional)
    # execution.wait()
    # print(f"Pipeline execution status: {execution.describe()['PipelineExecutionStatus']}")


def run_without_mlflow():
    """Run the pipeline without MLflow tracking (backward compatible)."""
    
    sagemaker_session = sagemaker.Session(
        boto_session=boto3.Session(region_name=REGION),
        default_bucket=BUCKET
    )
    
    pipeline = get_pipeline(
        region=REGION,
        role=ROLE,
        default_bucket=BUCKET,
        sagemaker_session=sagemaker_session,
        glue_database_name=GLUE_DATABASE,
        glue_table_name=GLUE_TABLE,
    )
    
    pipeline.upsert(role_arn=ROLE)
    
    # Start without MLflow parameters - tracking will be skipped
    execution = pipeline.start(
        parameters={
            "GlueDatabase": GLUE_DATABASE,
            "GlueTable": GLUE_TABLE,
        }
    )
    
    print(f"Pipeline execution started without MLflow: {execution.arn}")


if __name__ == "__main__":
    # Run with MLflow tracking
    main()
    
    # Or run without MLflow (uncomment to test)
    # run_without_mlflow()
