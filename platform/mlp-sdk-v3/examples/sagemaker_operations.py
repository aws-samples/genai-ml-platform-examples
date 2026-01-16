#!/usr/bin/env python3
"""
SageMaker Operations Examples for mlp_sdk

This script demonstrates how to use mlp_sdk for common SageMaker operations
with configuration-driven defaults.

Prerequisites:
1. Generate and configure admin-config.yaml
2. Ensure AWS credentials are configured
3. Have appropriate IAM permissions for SageMaker operations

Note: These examples show the API usage. Actual execution requires valid AWS resources.
"""

from mlp_sdk import MLP_Session
from mlp_sdk.exceptions import MLPSDKError


def example_training_job():
    """Example: Run a training job with defaults"""
    print("\n=== Example: Training Job ===\n")
    
    try:
        session = MLP_Session()
        
        # Training job configuration
        # The SDK will automatically apply defaults from admin-config.yaml
        training_config = {
            "job_name": "my-training-job-001",
            "algorithm_specification": {
                "training_image": "382416733822.dkr.ecr.us-west-2.amazonaws.com/xgboost:latest",
                "training_input_mode": "File"
            },
            "input_data_config": [
                {
                    "ChannelName": "train",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": "s3://my-bucket/train/",
                            "S3DataDistributionType": "FullyReplicated"
                        }
                    }
                }
            ],
            "hyperparameters": {
                "max_depth": "5",
                "eta": "0.2",
                "objective": "binary:logistic",
                "num_round": "100"
            }
        }
        
        print("📋 Training job configuration:")
        print(f"   Job name: {training_config['job_name']}")
        print(f"   Algorithm: XGBoost")
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print("   Defaults applied from config:")
            print(f"   - Instance type: {mlp_config.compute_config.training_instance_type}")
            print(f"   - Instance count: {mlp_config.compute_config.training_instance_count}")
            print(f"   - VPC: {mlp_config.networking_config.vpc_id}")
            print(f"   - Execution role: {mlp_config.iam_config.execution_role}")
        else:
            print("   Using SageMaker SDK defaults")
        
        # Uncomment to actually run the training job
        # result = session.run_training_job(**training_config)
        # print(f"✅ Training job started: {result}")
        
        print("\n💡 To run this job, uncomment the run_training_job() call")
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_processing_job():
    """Example: Run a processing job with defaults"""
    print("\n=== Example: Processing Job ===\n")
    
    try:
        session = MLP_Session()
        
        # Processing job configuration
        processing_config = {
            "job_name": "my-processing-job-001",
            "app_specification": {
                "image_uri": "382416733822.dkr.ecr.us-west-2.amazonaws.com/sagemaker-scikit-learn:0.23-1-cpu-py3"
            },
            "processing_inputs": [
                {
                    "InputName": "input-1",
                    "S3Input": {
                        "S3Uri": "s3://my-bucket/input/",
                        "LocalPath": "/opt/ml/processing/input",
                        "S3DataType": "S3Prefix",
                        "S3InputMode": "File"
                    }
                }
            ],
            "processing_outputs": [
                {
                    "OutputName": "output-1",
                    "S3Output": {
                        "S3Uri": "s3://my-bucket/output/",
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob"
                    }
                }
            ]
        }
        
        print("📋 Processing job configuration:")
        print(f"   Job name: {processing_config['job_name']}")
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print("   Defaults applied from config:")
            print(f"   - Instance type: {mlp_config.compute_config.processing_instance_type}")
            print(f"   - Instance count: {mlp_config.compute_config.processing_instance_count}")
            print(f"   - VPC: {mlp_config.networking_config.vpc_id}")
        else:
            print("   Using SageMaker SDK defaults")
        
        # Uncomment to actually run the processing job
        # result = session.run_processing_job(**processing_config)
        # print(f"✅ Processing job started: {result}")
        
        print("\n💡 To run this job, uncomment the run_processing_job() call")
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_feature_group():
    """Example: Create a feature group with defaults"""
    print("\n=== Example: Feature Group ===\n")
    
    try:
        session = MLP_Session()
        
        # Feature group configuration
        feature_group_config = {
            "name": "my-feature-group",
            "record_identifier_name": "customer_id",
            "event_time_feature_name": "event_time",
            "feature_definitions": [
                {"FeatureName": "customer_id", "FeatureType": "String"},
                {"FeatureName": "event_time", "FeatureType": "String"},
                {"FeatureName": "feature_1", "FeatureType": "Fractional"},
                {"FeatureName": "feature_2", "FeatureType": "Integral"}
            ]
        }
        
        print("📋 Feature group configuration:")
        print(f"   Name: {feature_group_config['name']}")
        print(f"   Record identifier: {feature_group_config['record_identifier_name']}")
        print(f"   Features: {len(feature_group_config['feature_definitions'])}")
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print("   Defaults applied from config:")
            print(f"   - Offline store: {mlp_config.feature_store_config.offline_store_s3_uri}")
            print(f"   - Online store: {mlp_config.feature_store_config.enable_online_store}")
        else:
            print("   Using SageMaker SDK defaults")
        
        # Uncomment to actually create the feature group
        # result = session.create_feature_group(**feature_group_config)
        # print(f"✅ Feature group created: {result}")
        
        print("\n💡 To create this feature group, uncomment the create_feature_group() call")
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_pipeline():
    """Example: Create a pipeline with multiple steps"""
    print("\n=== Example: Pipeline ===\n")
    
    try:
        session = MLP_Session()
        
        print("📋 Pipeline configuration:")
        print("   Pipeline: data-processing-training-pipeline")
        print("   Steps:")
        print("   1. Processing step (data preparation)")
        print("   2. Training step (model training)")
        print("   3. Evaluation step (model evaluation)")
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print("\n   Defaults applied from config:")
            print(f"   - All steps use VPC: {mlp_config.networking_config.vpc_id}")
            print(f"   - Processing uses: {mlp_config.compute_config.processing_instance_type}")
            print(f"   - Training uses: {mlp_config.compute_config.training_instance_type}")
        else:
            print("\n   Using SageMaker SDK defaults")
        
        # Pipeline creation would involve:
        # 1. Define processing step
        # 2. Define training step
        # 3. Define evaluation step
        # 4. Connect steps with dependencies
        # 5. Create pipeline with session.create_pipeline()
        
        print("\n💡 See docs/USAGE_EXAMPLES.md for complete pipeline example")
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_runtime_overrides():
    """Example: Override defaults at runtime"""
    print("\n=== Example: Runtime Parameter Overrides ===\n")
    
    try:
        session = MLP_Session()
        
        print("📋 Demonstrating parameter precedence:")
        
        mlp_config = session.config_manager.MLP_config
        if mlp_config:
            print("\n1. Default from config:")
            print(f"   Instance type: {mlp_config.compute_config.training_instance_type}")
        else:
            print("\n1. No config loaded, using SageMaker SDK defaults")
        
        print("\n2. Runtime override:")
        training_config = {
            "job_name": "my-custom-training-job",
            "instance_type": "ml.p3.2xlarge",  # Override default
            "instance_count": 2,  # Override default
            # Other parameters use defaults from config
        }
        print(f"   Instance type: {training_config['instance_type']} (overridden)")
        print(f"   Instance count: {training_config['instance_count']} (overridden)")
        
        print("\n3. Precedence order:")
        print("   Runtime parameters > Config defaults > SageMaker SDK defaults")
        
        print("\n💡 This allows flexibility while maintaining sensible defaults")
        
    except MLPSDKError as e:
        print(f"❌ SDK Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all examples"""
    print("=" * 70)
    print("mlp_sdk SageMaker Operations Examples")
    print("=" * 70)
    
    # Run examples
    example_training_job()
    example_processing_job()
    example_feature_group()
    example_pipeline()
    example_runtime_overrides()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)
    print("\n📚 Additional Resources:")
    print("   - docs/USAGE_EXAMPLES.md - Complete working examples")
    print("   - docs/CONFIGURATION_GUIDE.md - Configuration details")
    print("   - README.md - Getting started guide")
    print()


if __name__ == "__main__":
    main()
