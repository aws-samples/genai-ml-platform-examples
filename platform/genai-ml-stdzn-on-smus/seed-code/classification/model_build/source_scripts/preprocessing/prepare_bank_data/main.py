# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Feature engineers the bank marketing dataset using AWS Data Wrangler for Glue integration."""
import argparse
import logging
import os
import pathlib
import sys
import subprocess
import boto3
import numpy as np
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# Install dependencies
logger.info("Installing dependencies")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "awswrangler==2.16.1", "pymysql"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas==1.1.3", "--force-reinstall"])
except subprocess.CalledProcessError as e:
    logger.error(f"Error installing dependencies: {e}")
    sys.exit(1)

region = os.environ.get('AWS_REGION', 'us-east-1')
boto3_session = boto3.Session(region_name=region)

try:
    import awswrangler as wr
    wr.config.aws_region = region
except ImportError as e:
    logger.error(f"Error importing AWS Data Wrangler: {e}")
    sys.exit(1)

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

# Bank marketing dataset features
numeric_features = ["age", "duration", "campaign", "pdays", "previous", 
                   "emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed"]
categorical_features = ["job", "marital", "education", "default", "housing", "loan", 
                       "contact", "month", "day_of_week", "poutcome"]
label_column = "y"

if __name__ == "__main__":
    logger.info("Starting preprocessing for bank marketing dataset")
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name", type=str, required=True)
    parser.add_argument("--table-name", type=str, required=True)
    args = parser.parse_args()

    base_dir = "/opt/ml/processing"
    pathlib.Path(f"{base_dir}/train").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"{base_dir}/validation").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"{base_dir}/test").mkdir(parents=True, exist_ok=True)
    
    try:
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

    # Write output datasets
    logger.info(f"Writing out datasets to {base_dir}")
    pd.DataFrame(train).to_csv(f"{base_dir}/train/train.csv", header=False, index=False)
    pd.DataFrame(validation).to_csv(f"{base_dir}/validation/validation.csv", header=False, index=False)
    pd.DataFrame(test).to_csv(f"{base_dir}/test/test.csv", header=False, index=False)
    
    logger.info("Data preprocessing completed successfully")
