#!/usr/bin/env python3
"""
XGBoost Training Example with mlp_sdk

This script demonstrates how to train an XGBoost model on SageMaker using
the mlp_sdk training wrapper with synthetic data.

Usage:
    python xgboost_training_script.py [--config PATH] [--wait]

Options:
    --config PATH    Path to admin-config.yaml (default: uses default location)
    --wait          Wait for training job to complete (default: False)
    --deploy        Deploy model to endpoint after training (default: False)
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
    
    # Create DataFrames with target in first column
    train_df = pd.DataFrame(X_train)
    train_df.insert(0, 'target', y_train)
    
    val_df = pd.DataFrame(X_val)
    val_df.insert(0, 'target', y_val)
    
    # Save to CSV
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
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print(f"\n📋 Configuration:")
            print(f"   Training instance: {mlp_config.compute_config.training_instance_type}")
            print(f"   Instance count: {mlp_config.compute_config.training_instance_count}")
            print(f"   VPC: {mlp_config.networking_config.vpc_id}")
        else:
            print(f"\n📋 No configuration loaded (using SageMaker SDK defaults)")
        
        return session
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Generate config: python examples/generate_admin_config.py --interactive")
        raise


def upload_to_s3(session, train_file, val_file):
    """Upload data files to S3"""
    print("\n" + "="*70)
    print("Step 4: Uploading Data to S3")
    print("="*70)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    s3_prefix = f"xgboost-example/{timestamp}"
    
    train_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/train/"
    val_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/validation/"
    output_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/output"
    
    print(f"📤 Uploading to: s3://{session.default_bucket}/{s3_prefix}")
    
    s3_client = session.boto_session.client('s3')
    
    s3_client.upload_file(train_file, session.default_bucket, f"{s3_prefix}/train/train.csv")
    print(f"   ✅ {train_s3_path}")
    
    s3_client.upload_file(val_file, session.default_bucket, f"{s3_prefix}/validation/validation.csv")
    print(f"   ✅ {val_s3_path}")
    
    return train_s3_path, val_s3_path, output_s3_path, timestamp


def start_training_job(session, train_s3_path, val_s3_path, output_s3_path, timestamp):
    """Start XGBoost training job"""
    print("\n" + "="*70)
    print("Step 5: Starting Training Job")
    print("="*70)
    
    # XGBoost hyperparameters
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
    
    # XGBoost container
    region = session.region_name
    xgboost_container = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost:1.5-1"
    
    job_name = f"xgboost-training-{timestamp}"
    
    print(f"🚀 Job name: {job_name}")
    print(f"   Container: {xgboost_container}")
    print(f"   Hyperparameters: {len(hyperparameters)} parameters")
    
    try:
        # SDK v3 ModelTrainer expects inputs as a dict of channel_name: S3 URI
        inputs = {
            'train': train_s3_path,
            'validation': val_s3_path
        }
        
        training_job = session.run_training_job(
            job_name=job_name,
            training_image=xgboost_container,
            inputs=inputs,
            hyperparameters=hyperparameters,
            output_path=output_s3_path,
            max_run_in_seconds=3600
        )
        
        print(f"\n✅ Training job started!")
        print(f"   ModelTrainer object created")
        print(f"\n💡 Monitor in SageMaker console or use --wait flag")
        
        return job_name
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def wait_for_training(session, job_name):
    """Wait for training job to complete"""
    print("\n" + "="*70)
    print("Step 6: Monitoring Training Job")
    print("="*70)
    
    print(f"⏳ Waiting for job to complete: {job_name}\n")
    
    sagemaker_client = session.sagemaker_client
    
    while True:
        response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
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
    
    audit_entries = session.get_audit_trail(operation="run_training_job")
    
    print(f"\n📊 Training job operations: {len(audit_entries)}\n")
    
    for entry in audit_entries[-3:]:
        print(f"   {entry.get('timestamp')}: {entry.get('operation')}")
        print(f"      Status: {entry.get('status')}")
        if 'parameters' in entry:
            print(f"      Job: {entry['parameters'].get('job_name', 'N/A')}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="XGBoost training example with mlp_sdk",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to admin-config.yaml"
    )
    
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for training job to complete"
    )
    
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy model to endpoint after training"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("XGBoost Training with mlp_sdk")
    print("="*70)
    
    try:
        # Generate data
        X_train, X_val, y_train, y_val = generate_synthetic_data()
        
        # Prepare files
        train_file, val_file = prepare_data_files(X_train, X_val, y_train, y_val)
        
        # Initialize session
        session = initialize_session(args.config)
        
        # Upload to S3
        train_s3, val_s3, output_s3, timestamp = upload_to_s3(session, train_file, val_file)
        
        # Start training
        job_name = start_training_job(session, train_s3, val_s3, output_s3, timestamp)
        
        # Wait if requested
        if args.wait:
            model_artifacts = wait_for_training(session, job_name)
            
            if model_artifacts and args.deploy:
                print("\n💡 Model deployment not implemented in this example")
                print("   See the Jupyter notebook for deployment example")
        
        # Show audit trail
        show_audit_trail(session)
        
        print("\n" + "="*70)
        print("✅ Example completed successfully!")
        print("="*70)
        print(f"\n📋 Training job: {job_name}")
        print(f"   Monitor: SageMaker Console > Training jobs > {job_name}")
        print(f"\n💡 Next steps:")
        print(f"   - Monitor training in SageMaker console")
        print(f"   - View logs in CloudWatch")
        print(f"   - Deploy model to endpoint")
        print(f"   - See examples/xgboost_training_example.ipynb for more details")
        print()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
