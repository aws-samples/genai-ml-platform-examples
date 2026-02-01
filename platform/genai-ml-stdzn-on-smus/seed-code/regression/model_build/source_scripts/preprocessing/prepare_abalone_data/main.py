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

"""Feature engineers the abalone dataset using AWS Data Wrangler for Glue integration."""
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

# Install dependencies with specific order to handle version conflicts
logger.info("Installing dependencies with specific order")
try:
    # First install AWS Data Wrangler and PyMySQL
    subprocess.check_call([sys.executable, "-m", "pip", "install", "awswrangler==2.16.1", "pymysql"])
    logger.info("Successfully installed AWS Data Wrangler and PyMySQL")
    
    # Then force reinstall pandas 1.1.3 to ensure compatibility with SageMaker container
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas==1.1.3", "--force-reinstall"])
    logger.info("Successfully downgraded pandas to 1.1.3")
except subprocess.CalledProcessError as e:
    logger.error(f"Error installing dependencies: {e}")
    sys.exit(1)

# Set up region and boto3 session before importing AWS Data Wrangler
region = os.environ.get('AWS_REGION', 'us-east-1')
boto3_session = boto3.Session(region_name=region)
logger.info(f"Created boto3 session with region: {region}")

# Import AWS Data Wrangler after installing dependencies
try:
    import awswrangler as wr
    # Set the region explicitly for AWS Data Wrangler
    wr.config.aws_region = region
    logger.info(f"Successfully imported AWS Data Wrangler version: {wr.__version__}")
    logger.info(f"Using AWS region: {region}")
except ImportError as e:
    logger.error(f"Error importing AWS Data Wrangler: {e}")
    sys.exit(1)

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

# Feature column names
feature_columns_names = [
    "sex",
    "length",
    "diameter",
    "height",
    "whole_weight",
    "shucked_weight",
    "viscera_weight",
    "shell_weight",
]
label_column = "rings"

if __name__ == "__main__":
    logger.info("Starting preprocessing with AWS Data Wrangler")
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-name", type=str, required=True)
    parser.add_argument("--table-name", type=str, required=True)
    args = parser.parse_args()

    base_dir = "/opt/ml/processing"
    pathlib.Path(f"{base_dir}/train").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"{base_dir}/validation").mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"{base_dir}/test").mkdir(parents=True, exist_ok=True)
    
    # Try to read from Glue Data Catalog
    try:
        # Get table location using the correct function with explicit boto3 session
        logger.info(f"Getting table location for {args.database_name}.{args.table_name}")
        s3_location = wr.catalog.get_table_location(
            database=args.database_name,
            table=args.table_name,
            boto3_session=boto3_session
        )
        logger.info(f"Found table S3 location: {s3_location}")
        
        # Read data directly from S3 with explicit boto3 session
        logger.info("Reading data from S3 location")
        df = wr.s3.read_csv(
            path=s3_location,
            boto3_session=boto3_session
        )
        logger.info(f"Successfully read {len(df)} rows from S3 location")
        
        # Check if the data has headers
        if df.columns[0] in ['M', 'F', 'I']:
            # No headers, assign column names
            logger.info("Data has no headers, assigning column names")
            df.columns = feature_columns_names + [label_column]
            
    except Exception as e:
        logger.error(f"Error reading from Glue catalog: {e}")
        sys.exit(1)
    
    # Data preprocessing
    logger.info("Defining transformers")
    numeric_features = list(feature_columns_names)
    numeric_features.remove("sex")
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    categorical_features = ["sex"]
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
    y = df[label_column]
    X = df.drop(columns=[label_column])
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
