# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Feature engineers the bank marketing dataset using AWS Data Wrangler for Glue integration."""
import argparse
import logging
import os
import pathlib
import sys
import boto3
import numpy as np
import pandas as pd
import mlflow
from time import gmtime, strftime
import awswrangler as wr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# Bank marketing dataset features
numeric_features = ["age", "duration", "campaign", "pdays", "previous",
    "emp_var_rate", "cons_price_idx", "cons_conf_idx", "euribor3m", "nr_employed"]

categorical_features = ["job", "marital", "education", "default", "housing", "loan",
                       "contact", "month", "day_of_week", "poutcome"]
label_column = "y"

if __name__ == "__main__":
    logger.info("Starting preprocessing for bank marketing dataset")
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name", type=str, required=True)
    parser.add_argument("--table-name", type=str, required=True)
    args = parser.parse_args()

    region = os.environ.get('AWS_REGION', 'us-east-1')
    boto3_session = boto3.Session(region_name=region)
    wr.config.aws_region = region

    # MLflow setup
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME")
    parent_run_id = os.environ.get("MLFLOW_PARENT_RUN_ID")
    
    # Log MLflow configuration for debugging
    logger.info(f"MLflow Tracking URI: {tracking_uri}")
    logger.info(f"MLflow Experiment Name: {experiment_name}")
    logger.info(f"MLflow Parent Run ID: {parent_run_id}")

    created_parent_run_id = None
    if tracking_uri:
        suffix = strftime('%d-%H-%M-%S', gmtime())
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name=experiment_name if experiment_name else f"preprocessing-{suffix}")
        
        # Create parent run if not provided
        if not parent_run_id or parent_run_id == "":
            logger.info("Creating new parent MLflow run")
            parent_run = mlflow.start_run(run_name=f"pipeline-{suffix}")
            created_parent_run_id = parent_run.info.run_id
            logger.info(f"Created parent run ID: {created_parent_run_id}")
            mlflow.end_run()
            parent_run_id = created_parent_run_id
        
        # Start preprocessing run as child
        logger.info(f"Starting MLflow run with parent_run_id: {parent_run_id}")
        run = mlflow.start_run(run_name=f"preprocess-{suffix}", parent_run_id=parent_run_id)

    try:
        base_dir = "/opt/ml/processing"
        pathlib.Path(f"{base_dir}/train").mkdir(parents=True, exist_ok=True)
        pathlib.Path(f"{base_dir}/validation").mkdir(parents=True, exist_ok=True)
        pathlib.Path(f"{base_dir}/test").mkdir(parents=True, exist_ok=True)

        try:

        
            """ 
            *** We are subscribing to S3 iceberg table and need to use pyiceberg to read *** 


        
            """ 
            *** We are subscribing to S3 iceberg table and need to use pyiceberg to read *** 

            logger.info(f"Getting table location for {args.database_name}.{args.table_name}")
            s3_location = wr.catalog.get_table_location(
                database=args.database_name,
                table=args.table_name,
                boto3_session=boto3_session
            )
            logger.info(f"Found table S3 location: {s3_location}")

            logger.info("Reading data from S3 location")
            df = wr.s3.read_csv(
                path=s3_location,
                sep=';',
                quotechar='"',
                boto3_session=boto3_session
            )
            logger.info(f"Successfully read {len(df)} rows from S3")
            """

            logger.info(f"Getting table location for {args.database_name}.{args.table_name}")

            import pandas as pd
            from pyiceberg.catalog import load_catalog

            catalog = load_catalog(
                "glue",
                **{
                    "type": "glue",
                    "glue.region": region,
                }
            )
            table_identifier = f"{args.database_name}.{args.table_name}"
            logger.info(f"Loading Iceberg table: {table_identifier}")
            table = catalog.load_table(table_identifier)
            df = table.scan().to_pandas()
            
            logger.info(f"Successfully read {len(df)} rows from S3 iceberg table")

        except Exception as e:
            logger.error(f"Error reading from Glue catalog: {e}")
            sys.exit(1)

        # Data preprocessing
        logger.info("Defining transformers")
        numeric_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler())
        ])

        categorical_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore"))
        ])

        preprocess = ColumnTransformer(transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features)
        ])

        # Apply transformations
        logger.info("Applying transforms")
        y = df[label_column].map({'yes': 1, 'no': 0})
        X = df[numeric_features + categorical_features]
        X_pre = preprocess.fit_transform(X)
        y_pre = y.to_numpy().reshape(len(y), 1)

        X = np.concatenate((y_pre, X_pre), axis=1)

        # Split data
        logger.info(f"Splitting {len(X)} rows into train, validation, test datasets")
        np.random.shuffle(X)
        train, validation, test = np.split(X, [int(0.7 * len(X)), int(0.85 * len(X))])

        # Log to MLflow
        if tracking_uri:
            mlflow.log_params({
                "total_rows": len(X),
                "train_rows": len(train),
                "validation_rows": len(validation),
                "test_rows": len(test),
                "database": args.database_name,
                "table": args.table_name
            })

        # Write output datasets
        logger.info(f"Writing out datasets to {base_dir}")
        pd.DataFrame(train).to_csv(f"{base_dir}/train/train.csv", header=False, index=False)
        pd.DataFrame(validation).to_csv(f"{base_dir}/validation/validation.csv", header=False, index=False)
        pd.DataFrame(test).to_csv(f"{base_dir}/test/test.csv", header=False, index=False)
        
        # Write parent run ID to output for subsequent steps
        if created_parent_run_id:
            pathlib.Path(f"{base_dir}/mlflow").mkdir(parents=True, exist_ok=True)
            with open(f"{base_dir}/mlflow/parent_run_id.txt", "w") as f:
                f.write(created_parent_run_id)
            logger.info(f"Wrote parent run ID to output: {created_parent_run_id}")

        logger.info("Data preprocessing completed successfully")

    finally:
        if tracking_uri:
            mlflow.end_run()
