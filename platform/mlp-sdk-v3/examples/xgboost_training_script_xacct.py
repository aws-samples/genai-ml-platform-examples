#!/usr/bin/env python3
"""
XGBoost Cross-Account Training Example with mlp_sdk

This script demonstrates how to train an XGBoost model on SageMaker in a
different AWS account using the mlp_sdk cross-account training wrapper.

The script assumes a role in the target account via STS, then runs the
training job there. Two roles are involved:
  - target_role_arn: The role assumed via STS (needs trust policy for your account)
  - role_arn: The SageMaker execution role in the target account

These can be the same role if it has both the trust policy and SageMaker permissions.

Usage:
    python xgboost_training_script_xacct.py \
        --target-role-arn arn:aws:iam::<TARGET_ACCOUNT>:role/CrossAccountRole \
        --execution-role-arn arn:aws:iam::<TARGET_ACCOUNT>:role/SageMakerExecRole \
        --target-bucket <TARGET_ACCOUNT_BUCKET> \
        [--config PATH] [--wait] [--external-id ID] [--target-region REGION]

Options:
    --target-role-arn       IAM role ARN in target account to assume via STS
    --execution-role-arn    SageMaker execution role ARN in target account
    --target-bucket         S3 bucket in target account for data and output
    --config PATH           Path to admin-config.yaml (default: uses default location)
    --wait                  Wait for training job to complete (default: False)
    --external-id           External ID for the STS assume-role call
    --target-region         AWS region for the target account (default: same as source)
"""

import argparse
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

from mlp_sdk import MLP_Session
from mlp_sdk.exceptions import MLPSDKError


def generate_synthetic_data(n_samples=10000, n_features=20, test_size=0.2):
    """Generate synthetic binary classification data"""
    print("\n" + "="*70)
    print("Step 1: Generating Synthetic Data")
    print("="*70)

    np.random.seed(42)

    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=15,
        n_redundant=5,
        n_classes=2,
        weights=[0.7, 0.3],
        flip_y=0.05,
        random_state=42
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    print(f"✅ Data generated:")
    print(f"   Training samples: {len(X_train)}")
    print(f"   Validation samples: {len(X_val)}")
    print(f"   Features: {X_train.shape[1]}")
    print(f"   Class distribution: {np.bincount(y_train)}")

    return X_train, X_val, y_train, y_val


def prepare_data_files(X_train, X_val, y_train, y_val):
    """Prepare CSV files for XGBoost"""
    print("\n" + "="*70)
    print("Step 2: Preparing Data Files")
    print("="*70)

    train_df = pd.DataFrame(X_train)
    train_df.insert(0, 'target', y_train)

    val_df = pd.DataFrame(X_val)
    val_df.insert(0, 'target', y_val)

    os.makedirs('data', exist_ok=True)
    train_df.to_csv('data/train.csv', header=False, index=False)
    val_df.to_csv('data/validation.csv', header=False, index=False)

    print(f"✅ Data saved:")
    print(f"   data/train.csv ({os.path.getsize('data/train.csv')} bytes)")
    print(f"   data/validation.csv ({os.path.getsize('data/validation.csv')} bytes)")

    return 'data/train.csv', 'data/validation.csv'


def initialize_session(config_path=None):
    """Initialize mlp_sdk session"""
    print("\n" + "="*70)
    print("Step 3: Initializing mlp_sdk Session")
    print("="*70)

    try:
        session = MLP_Session(config_path=config_path, log_level="INFO")

        print(f"✅ Session initialized:")
        print(f"   Region: {session.region_name}")
        print(f"   Default bucket: {session.default_bucket}")
        print(f"   Execution role: {session.get_execution_role()}")

        return session

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Generate config: python examples/generate_admin_config.py --interactive")
        raise


def upload_to_s3_xacct(session, train_file, val_file, target_role_arn,
                       target_bucket, external_id=None, target_region=None):
    """Upload data files to the target account's S3 bucket using assumed-role credentials"""
    print("\n" + "="*70)
    print("Step 4: Uploading Data to Target Account S3")
    print("="*70)

    import boto3

    # Assume role to get access to target account S3
    sts_client = boto3.client('sts')
    assume_params = {
        'RoleArn': target_role_arn,
        'RoleSessionName': 'mlp-xacct-upload',
        'DurationSeconds': 3600,
    }
    if external_id:
        assume_params['ExternalId'] = external_id

    print(f"🔑 Assuming role: {target_role_arn}")
    sts_response = sts_client.assume_role(**assume_params)
    creds = sts_response['Credentials']

    xacct_session = boto3.Session(
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'],
        region_name=target_region or boto3.Session().region_name,
    )
    s3_client = xacct_session.client('s3')

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    s3_prefix = f"xgboost-xacct-example/{timestamp}"

    train_s3_path = f"s3://{target_bucket}/{s3_prefix}/train/"
    val_s3_path = f"s3://{target_bucket}/{s3_prefix}/validation/"
    output_s3_path = f"s3://{target_bucket}/{s3_prefix}/output"

    print(f"📤 Uploading to: s3://{target_bucket}/{s3_prefix}")

    s3_client.upload_file(train_file, target_bucket, f"{s3_prefix}/train/train.csv")
    print(f"   ✅ {train_s3_path}")

    s3_client.upload_file(val_file, target_bucket, f"{s3_prefix}/validation/validation.csv")
    print(f"   ✅ {val_s3_path}")

    return train_s3_path, val_s3_path, output_s3_path, timestamp


def start_training_job_xacct(session, train_s3_path, val_s3_path, output_s3_path,
                             timestamp, target_role_arn, execution_role_arn,
                             external_id=None, target_region=None):
    """Start XGBoost training job in the target account"""
    print("\n" + "="*70)
    print("Step 5: Starting Cross-Account Training Job")
    print("="*70)

    hyperparameters = {
        'objective': 'binary:logistic',
        'num_round': '100',
        'max_depth': '5',
        'eta': '0.2',
        'gamma': '4',
        'min_child_weight': '6',
        'subsample': '0.8',
        'verbosity': '1',
        'eval_metric': 'auc',
        'scale_pos_weight': '2'
    }

    region = target_region or session.region_name
    xgboost_container = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost:1.5-1"

    job_name = f"xgboost-xacct-{timestamp}"

    print(f"🚀 Job name: {job_name}")
    print(f"   Target role: {target_role_arn}")
    print(f"   Execution role: {execution_role_arn}")
    print(f"   Container: {xgboost_container}")
    print(f"   Hyperparameters: {len(hyperparameters)} parameters")

    try:
        inputs = {
            'train': train_s3_path,
            'validation': val_s3_path
        }

        training_job = session.run_training_job_xacct(
            job_name=job_name,
            target_role_arn=target_role_arn,
            training_image=xgboost_container,
            inputs=inputs,
            hyperparameters=hyperparameters,
            output_path=output_s3_path,
            max_run_in_seconds=3600,
            role_arn=execution_role_arn,
            external_id=external_id,
            **({"target_region": target_region} if target_region else {}),
        )

        print(f"\n✅ Cross-account training job started!")
        print(f"   ModelTrainer object created")
        print(f"\n💡 Monitor in the TARGET account's SageMaker console")

        return job_name

    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def wait_for_training_xacct(target_role_arn, job_name, external_id=None, target_region=None):
    """Wait for training job to complete in the target account"""
    print("\n" + "="*70)
    print("Step 6: Monitoring Cross-Account Training Job")
    print("="*70)

    import boto3

    # Assume role again to poll job status in target account
    sts_client = boto3.client('sts')
    assume_params = {
        'RoleArn': target_role_arn,
        'RoleSessionName': 'mlp-xacct-monitor',
        'DurationSeconds': 3600,
    }
    if external_id:
        assume_params['ExternalId'] = external_id

    creds = boto3.client('sts').assume_role(**assume_params)['Credentials']
    sm_client = boto3.Session(
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'],
        region_name=target_region or boto3.Session().region_name,
    ).client('sagemaker')

    print(f"⏳ Waiting for job to complete: {job_name}\n")

    while True:
        response = sm_client.describe_training_job(TrainingJobName=job_name)
        status = response['TrainingJobStatus']

        if status == 'Completed':
            print(f"\n✅ Training completed!")
            print(f"   Training time: {response.get('TrainingTimeInSeconds', 0)} seconds")
            print(f"   Billable time: {response.get('BillableTimeInSeconds', 0)} seconds")

            if 'FinalMetricDataList' in response:
                print(f"\n📈 Final metrics:")
                for metric in response['FinalMetricDataList']:
                    print(f"   {metric['MetricName']}: {metric['Value']:.4f}")

            model_artifacts = response['ModelArtifacts']['S3ModelArtifacts']
            print(f"\n📦 Model artifacts: {model_artifacts}")
            return model_artifacts

        elif status == 'Failed':
            print(f"\n❌ Training failed!")
            print(f"   Reason: {response.get('FailureReason', 'Unknown')}")
            return None

        elif status == 'Stopped':
            print(f"\n⚠️  Training stopped!")
            return None

        else:
            print(f"   Status: {status} | {datetime.now().strftime('%H:%M:%S')}", end='\r')
            time.sleep(30)


def show_audit_trail(session):
    """Display audit trail"""
    print("\n" + "="*70)
    print("Audit Trail")
    print("="*70)

    audit_entries = session.get_audit_trail(operation="run_training_job_xacct")

    print(f"\n📊 Cross-account training operations: {len(audit_entries)}\n")

    for entry in audit_entries[-3:]:
        print(f"   {entry.get('timestamp')}: {entry.get('operation')}")
        print(f"      Status: {entry.get('status')}")
        if 'parameters' in entry:
            print(f"      Job: {entry['parameters'].get('job_name', 'N/A')}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="XGBoost cross-account training example with mlp_sdk",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--target-role-arn", type=str, required=True,
                        help="IAM role ARN in target account to assume via STS")
    parser.add_argument("--execution-role-arn", type=str, required=True,
                        help="SageMaker execution role ARN in target account")
    parser.add_argument("--target-bucket", type=str, required=True,
                        help="S3 bucket in target account for data and output")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to admin-config.yaml")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for training job to complete")
    parser.add_argument("--external-id", type=str, default=None,
                        help="External ID for the STS assume-role call")
    parser.add_argument("--target-region", type=str, default=None,
                        help="AWS region for the target account")

    args = parser.parse_args()

    print("\n" + "="*70)
    print("XGBoost Cross-Account Training with mlp_sdk")
    print("="*70)
    print(f"   Target role:      {args.target_role_arn}")
    print(f"   Execution role:   {args.execution_role_arn}")
    print(f"   Target bucket:    {args.target_bucket}")
    if args.target_region:
        print(f"   Target region:    {args.target_region}")

    try:
        # Generate data
        X_train, X_val, y_train, y_val = generate_synthetic_data()

        # Prepare files
        train_file, val_file = prepare_data_files(X_train, X_val, y_train, y_val)

        # Initialize session (local account)
        session = initialize_session(args.config)

        # Upload to target account S3
        train_s3, val_s3, output_s3, timestamp = upload_to_s3_xacct(
            session, train_file, val_file,
            target_role_arn=args.target_role_arn,
            target_bucket=args.target_bucket,
            external_id=args.external_id,
            target_region=args.target_region,
        )

        # Start cross-account training
        job_name = start_training_job_xacct(
            session, train_s3, val_s3, output_s3, timestamp,
            target_role_arn=args.target_role_arn,
            execution_role_arn=args.execution_role_arn,
            external_id=args.external_id,
            target_region=args.target_region,
        )

        # Wait if requested
        if args.wait:
            wait_for_training_xacct(
                target_role_arn=args.target_role_arn,
                job_name=job_name,
                external_id=args.external_id,
                target_region=args.target_region,
            )

        # Show audit trail
        show_audit_trail(session)

        print("\n" + "="*70)
        print("✅ Cross-account example completed successfully!")
        print("="*70)
        print(f"\n📋 Training job: {job_name}")
        print(f"   Monitor in TARGET account: SageMaker Console > Training jobs > {job_name}")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
