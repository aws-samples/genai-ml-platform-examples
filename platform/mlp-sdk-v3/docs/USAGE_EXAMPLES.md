# mlp_sdk Usage Examples

This document provides comprehensive usage examples for mlp_sdk.

## Table of Contents

- [Basic Session Initialization](#basic-session-initialization)
- [Feature Store Operations](#feature-store-operations)
- [Processing Jobs](#processing-jobs)
- [Training Jobs](#training-jobs)
- [Pipeline Operations](#pipeline-operations)
- [Configuration Management](#configuration-management)
- [Encryption Examples](#encryption-examples)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)

## Basic Session Initialization

### Default Configuration

```python
from mlp_sdk import MLP_Session

# Initialize with default configuration path
# Loads from /home/sagemaker-user/.config/admin-config.yaml
session = MLP_Session()
```

### Custom Configuration Path

```python
from mlp_sdk import MLP_Session

# Initialize with custom configuration file
session = MLP_Session(config_path="/path/to/custom-config.yaml")
```

### Custom Logging Level

```python
import logging
from mlp_sdk import MLP_Session

# Initialize with DEBUG logging
session = MLP_Session(log_level=logging.DEBUG)

# Change log level at runtime
session.set_log_level(logging.WARNING)
```

### Disable Audit Trail

```python
from mlp_sdk import MLP_Session

# Initialize without audit trail (for performance)
session = MLP_Session(enable_audit_trail=False)
```

## Feature Store Operations

### Create Feature Group with Defaults

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Create feature group using defaults from configuration
feature_group = session.create_feature_group(
    feature_group_name="customer-features",
    record_identifier_name="customer_id",
    event_time_feature_name="event_time",
    feature_definitions=[
        {"FeatureName": "customer_id", "FeatureType": "String"},
        {"FeatureName": "age", "FeatureType": "Integral"},
        {"FeatureName": "income", "FeatureType": "Fractional"},
        {"FeatureName": "credit_score", "FeatureType": "Integral"},
        {"FeatureName": "event_time", "FeatureType": "String"}
    ]
)

print(f"Feature group created: {feature_group.name}")
```

### Create Feature Group with Runtime Overrides

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Override default S3 location and enable online store
feature_group = session.create_feature_group(
    feature_group_name="real-time-features",
    record_identifier_name="transaction_id",
    event_time_feature_name="timestamp",
    feature_definitions=[
        {"FeatureName": "transaction_id", "FeatureType": "String"},
        {"FeatureName": "amount", "FeatureType": "Fractional"},
        {"FeatureName": "timestamp", "FeatureType": "String"}
    ],
    # Runtime overrides
    offline_store_s3_uri="s3://custom-bucket/feature-store/",
    enable_online_store=True
)
```

### Create Feature Group with Online Store

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

feature_group = session.create_feature_group(
    feature_group_name="online-features",
    record_identifier_name="user_id",
    event_time_feature_name="event_time",
    feature_definitions=[
        {"FeatureName": "user_id", "FeatureType": "String"},
        {"FeatureName": "last_login", "FeatureType": "String"},
        {"FeatureName": "session_count", "FeatureType": "Integral"},
        {"FeatureName": "event_time", "FeatureType": "String"}
    ],
    enable_online_store=True,
    online_store_security_config={
        "KmsKeyId": "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
    }
)
```

## Processing Jobs

### Basic Processing Job

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Run processing job with defaults
processor = session.run_processing_job(
    job_name="data-preprocessing",
    processing_script="scripts/preprocess.py",
    inputs=[{
        "source": "s3://my-bucket/raw-data/",
        "destination": "/opt/ml/processing/input"
    }],
    outputs=[{
        "source": "/opt/ml/processing/output",
        "destination": "s3://my-bucket/processed-data/"
    }]
)

print(f"Processing job started: {processor.latest_job_name}")
```

### Processing Job with Custom Instance Type

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Override default instance type
processor = session.run_processing_job(
    job_name="large-data-processing",
    processing_script="scripts/process_large_dataset.py",
    inputs=[{
        "source": "s3://my-bucket/large-dataset/",
        "destination": "/opt/ml/processing/input"
    }],
    outputs=[{
        "source": "/opt/ml/processing/output",
        "destination": "s3://my-bucket/processed-large-dataset/"
    }],
    # Runtime overrides
    instance_type="ml.m5.4xlarge",
    instance_count=2
)
```

### Processing Job with Environment Variables

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

processor = session.run_processing_job(
    job_name="feature-engineering",
    processing_script="scripts/engineer_features.py",
    inputs=[{
        "source": "s3://my-bucket/raw-features/",
        "destination": "/opt/ml/processing/input"
    }],
    outputs=[{
        "source": "/opt/ml/processing/output",
        "destination": "s3://my-bucket/engineered-features/"
    }],
    environment={
        "FEATURE_VERSION": "v2",
        "NORMALIZATION_METHOD": "standard"
    }
)
```

## Training Jobs

### Basic Training Job

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Run training job with PyTorch container
trainer = session.run_training_job(
    job_name="model-training",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310",
    source_code_dir="training-scripts",
    entry_script="train.py",
    inputs={"train": "s3://my-bucket/training-data/"}
)

print(f"Training job started: {trainer.latest_training_job.name}")
```

### Training Job with Hyperparameters

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

trainer = session.run_training_job(
    job_name="hyperparameter-tuning",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-gpu-py310",
    source_code_dir="training-scripts",
    entry_script="train.py",
    inputs={
        "train": "s3://my-bucket/train/",
        "validation": "s3://my-bucket/validation/"
    },
    hyperparameters={
        "epochs": 100,
        "batch_size": 32,
        "learning_rate": 0.001,
        "optimizer": "adam"
    },
    instance_type="ml.p3.2xlarge"
)
```

### Training Job with Custom Requirements

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

trainer = session.run_training_job(
    job_name="custom-dependencies-training",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310",
    source_code_dir="training-scripts",
    entry_script="train.py",
    requirements="training-scripts/requirements.txt",
    inputs={"train": "s3://my-bucket/data/"}
)
```

### Distributed Training Job

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

trainer = session.run_training_job(
    job_name="distributed-training",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-gpu-py310",
    source_code_dir="training-scripts",
    entry_script="train_distributed.py",
    inputs={"train": "s3://my-bucket/large-dataset/"},
    instance_type="ml.p3.8xlarge",
    instance_count=4,
    distributed_runner={
        "type": "pytorch",
        "processes_per_host": 4
    }
)
```

## Pipeline Operations

### Create Simple Pipeline

```python
from mlp_sdk import MLP_Session
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

session = MLP_Session()

# Create processing step
processor = session.run_processing_job(
    job_name="pipeline-preprocessing",
    processing_script="scripts/preprocess.py",
    inputs=[{"source": "s3://my-bucket/raw/", "destination": "/opt/ml/processing/input"}],
    outputs=[{"source": "/opt/ml/processing/output", "destination": "s3://my-bucket/processed/"}]
)

processing_step = ProcessingStep(
    name="PreprocessData",
    processor=processor
)

# Create training step
trainer = session.run_training_job(
    job_name="pipeline-training",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310",
    source_code_dir="training-scripts",
    entry_script="train.py",
    inputs={"train": "s3://my-bucket/processed/"}
)

training_step = TrainingStep(
    name="TrainModel",
    estimator=trainer
)

# Create pipeline
pipeline = session.create_pipeline(
    pipeline_name="ml-workflow",
    steps=[processing_step, training_step]
)

# Upsert pipeline
response = session.upsert_pipeline(pipeline)
print(f"Pipeline ARN: {response['PipelineArn']}")

# Start pipeline execution
execution = session.start_pipeline_execution(pipeline_name="ml-workflow")
print(f"Execution ARN: {execution['PipelineExecutionArn']}")
```

### Pipeline with Parameters

```python
from mlp_sdk import MLP_Session
from sagemaker.workflow.parameters import ParameterString, ParameterInteger
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

session = MLP_Session()

# Define pipeline parameters
input_data = ParameterString(name="InputData", default_value="s3://my-bucket/data/")
instance_type = ParameterString(name="InstanceType", default_value="ml.m5.xlarge")
epochs = ParameterInteger(name="Epochs", default_value=10)

# Create steps using parameters
processor = session.run_processing_job(
    job_name="parameterized-preprocessing",
    processing_script="scripts/preprocess.py",
    inputs=[{"source": input_data, "destination": "/opt/ml/processing/input"}],
    outputs=[{"source": "/opt/ml/processing/output", "destination": "s3://my-bucket/processed/"}],
    instance_type=instance_type
)

processing_step = ProcessingStep(name="Preprocess", processor=processor)

# Create pipeline with parameters
pipeline = session.create_pipeline(
    pipeline_name="parameterized-workflow",
    steps=[processing_step],
    parameters=[input_data, instance_type, epochs]
)

# Upsert and execute with custom parameters
session.upsert_pipeline(pipeline)
execution = session.start_pipeline_execution(
    pipeline_name="parameterized-workflow",
    parameters={
        "InputData": "s3://my-bucket/new-data/",
        "InstanceType": "ml.m5.2xlarge",
        "Epochs": 20
    }
)
```

## Configuration Management

### Get Configuration Values

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Get entire configuration
config = session.get_config()
print(f"S3 bucket: {config['defaults']['s3']['default_bucket']}")

# Get execution role
role = session.get_execution_role()
print(f"Execution role: {role}")

# Get session properties
print(f"Region: {session.region_name}")
print(f"Account ID: {session.account_id}")
print(f"Default bucket: {session.default_bucket}")
```

### Update Configuration at Runtime

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Update session configuration
session.update_session_config(
    default_bucket="new-bucket-name",
    sagemaker_client=custom_sagemaker_client
)
```

### Access Configuration Manager Directly

```python
from mlp_sdk.config import ConfigurationManager

# Create configuration manager
config_manager = ConfigurationManager(config_path="/path/to/config.yaml")

# Get specific configuration values
bucket = config_manager.get_default("s3.default_bucket")
vpc_id = config_manager.get_default("networking.vpc_id")

# Get configuration with fallback
custom_value = config_manager.get_default("custom.setting", fallback="default-value")

# Merge with runtime config
merged = config_manager.merge_with_runtime({
    "s3": {"default_bucket": "runtime-bucket"},
    "compute": {"training_instance_type": "ml.p3.2xlarge"}
})
```

## Encryption Examples

### Generate Encryption Key

```python
from mlp_sdk.config import ConfigurationManager

# Generate a new encryption key
key = ConfigurationManager.generate_key()
print(f"Save this key securely: {key}")

# Save to environment variable or file
import os
os.environ['MLP_SDK_ENCRYPTION_KEY'] = key
```

### Encrypt Configuration File

```python
from mlp_sdk.config import ConfigurationManager

# Load or generate encryption key
key = ConfigurationManager.generate_key()

# Create configuration manager with encryption key
config_manager = ConfigurationManager(encryption_key=key)

# Encrypt sensitive fields in configuration file
config_manager.encrypt_config_file(
    input_path="config.yaml",
    output_path="config-encrypted.yaml",
    fields_to_encrypt=[
        "defaults.iam.execution_role",
        "defaults.kms.key_id",
        "defaults.s3.default_bucket"
    ]
)

print("Configuration file encrypted successfully")
```

### Decrypt Configuration File

```python
from mlp_sdk.config import ConfigurationManager

# Load encryption key from environment
key = ConfigurationManager.load_key_from_env()

# Create configuration manager
config_manager = ConfigurationManager(encryption_key=key)

# Decrypt configuration file
config_manager.decrypt_config_file(
    input_path="config-encrypted.yaml",
    output_path="config-decrypted.yaml",
    fields_to_decrypt=[
        "defaults.iam.execution_role",
        "defaults.kms.key_id",
        "defaults.s3.default_bucket"
    ]
)

print("Configuration file decrypted successfully")
```

### Encrypt/Decrypt Individual Values

```python
from mlp_sdk.config import ConfigurationManager

# Generate key
key = ConfigurationManager.generate_key()
config_manager = ConfigurationManager(encryption_key=key)

# Encrypt a value
plaintext = "arn:aws:iam::123456789012:role/SageMakerRole"
encrypted = config_manager.encrypt_value(plaintext)
print(f"Encrypted: {encrypted}")

# Decrypt the value
decrypted = config_manager.decrypt_value(encrypted)
print(f"Decrypted: {decrypted}")
assert plaintext == decrypted
```

### Load Key from AWS KMS

```python
from mlp_sdk.config import ConfigurationManager

# Load encryption key from KMS
key = ConfigurationManager.load_key_from_kms(
    key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID",
    region="us-west-2"
)

# Use key with configuration manager
config_manager = ConfigurationManager(
    config_path="encrypted-config.yaml",
    encryption_key=key
)
```

## Error Handling

### Handle Validation Errors

```python
from mlp_sdk import MLP_Session, ValidationError

session = MLP_Session()

try:
    # This will raise ValidationError due to empty name
    feature_group = session.create_feature_group(
        feature_group_name="",
        record_identifier_name="id",
        event_time_feature_name="time",
        feature_definitions=[]
    )
except ValidationError as e:
    print(f"Validation error: {e}")
    # Handle validation error (e.g., prompt user for correct input)
```

### Handle AWS Service Errors

```python
from mlp_sdk import MLP_Session, AWSServiceError

session = MLP_Session()

try:
    feature_group = session.create_feature_group(
        feature_group_name="my-features",
        record_identifier_name="id",
        event_time_feature_name="time",
        feature_definitions=[
            {"FeatureName": "id", "FeatureType": "String"},
            {"FeatureName": "time", "FeatureType": "String"}
        ]
    )
except AWSServiceError as e:
    print(f"AWS error: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Request ID: {e.request_id}")
    print(f"HTTP status: {e.http_status_code}")
    
    # Get structured error details
    details = e.get_error_details()
    print(f"Full error details: {details}")
    
    # Handle specific error codes
    if e.error_code == "ResourceInUse":
        print("Feature group already exists")
    elif e.error_code == "AccessDeniedException":
        print("Check IAM permissions")
```

### Handle Configuration Errors

```python
from mlp_sdk import MLP_Session, ConfigurationError

try:
    # This will raise ConfigurationError if config file is invalid
    session = MLP_Session(config_path="/path/to/invalid-config.yaml")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    # Fall back to default configuration
    session = MLP_Session()
```

### Comprehensive Error Handling

```python
from mlp_sdk import (
    MLP_Session,
    MLPSDKError,
    ValidationError,
    AWSServiceError,
    ConfigurationError,
    SessionError
)

try:
    session = MLP_Session()
    
    feature_group = session.create_feature_group(
        feature_group_name="my-features",
        record_identifier_name="id",
        event_time_feature_name="time",
        feature_definitions=[
            {"FeatureName": "id", "FeatureType": "String"},
            {"FeatureName": "value", "FeatureType": "Fractional"},
            {"FeatureName": "time", "FeatureType": "String"}
        ]
    )
    
except ValidationError as e:
    print(f"Invalid parameters: {e}")
except ConfigurationError as e:
    print(f"Configuration issue: {e}")
except SessionError as e:
    print(f"Session initialization failed: {e}")
except AWSServiceError as e:
    print(f"AWS service error: {e}")
    print(f"Details: {e.get_error_details()}")
except MLPSDKError as e:
    print(f"General SDK error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Advanced Usage

### Access Underlying SageMaker SDK

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Access SageMaker session for advanced operations
sagemaker_session = session.sagemaker_session

# List training jobs using SageMaker SDK directly
training_jobs = sagemaker_session.list_training_jobs(MaxResults=10)
print(f"Recent training jobs: {training_jobs}")

# Access boto3 clients
s3_client = session.boto_session.client('s3')
buckets = s3_client.list_buckets()
print(f"S3 buckets: {[b['Name'] for b in buckets['Buckets']]}")

# Use SageMaker client for low-level API calls
response = session.sagemaker_client.describe_training_job(
    TrainingJobName='my-training-job'
)
print(f"Training job status: {response['TrainingJobStatus']}")
```

### Audit Trail Management

```python
from mlp_sdk import MLP_Session

session = MLP_Session(enable_audit_trail=True)

# Perform operations
session.create_feature_group(...)
session.run_processing_job(...)
session.run_training_job(...)

# Get all audit trail entries
all_entries = session.get_audit_trail()
print(f"Total operations: {len(all_entries)}")

# Filter by operation
feature_group_ops = session.get_audit_trail(operation="create_feature_group")
print(f"Feature group operations: {len(feature_group_ops)}")

# Filter by status
failed_ops = session.get_audit_trail(status="failed")
print(f"Failed operations: {len(failed_ops)}")

# Get recent entries
recent_ops = session.get_audit_trail(limit=10)
print(f"Recent 10 operations: {recent_ops}")

# Get audit trail summary
summary = session.get_audit_trail_summary()
print(f"Summary: {summary}")
print(f"Operations by type: {summary['operations']}")
print(f"Operations by status: {summary['statuses']}")
print(f"Failed operations: {summary['failed_operations']}")

# Export audit trail
session.export_audit_trail("audit-trail.json", format="json")
session.export_audit_trail("audit-trail.csv", format="csv")
```

### Custom Boto3 Session

```python
import boto3
from mlp_sdk import MLP_Session

# Create custom boto3 session with specific profile
boto_session = boto3.Session(
    profile_name="my-aws-profile",
    region_name="us-west-2"
)

# Initialize MLP_Session with custom boto session
session = MLP_Session(boto_session=boto_session)

# Or pass custom clients
sagemaker_client = boto_session.client('sagemaker')
session = MLP_Session(sagemaker_client=sagemaker_client)
```

### Dynamic Configuration

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Get current configuration
config = session.get_config()
print(f"Current bucket: {config['defaults']['s3']['default_bucket']}")

# Update configuration at runtime
session.update_session_config(default_bucket="new-bucket")

# Verify update
print(f"New bucket: {session.default_bucket}")
```

### Logging Configuration

```python
import logging
from mlp_sdk import MLP_Session

# Initialize with DEBUG logging
session = MLP_Session(log_level=logging.DEBUG)

# Perform operations (will log detailed debug information)
session.create_feature_group(...)

# Change to WARNING level to reduce noise
session.set_log_level(logging.WARNING)

# Now only warnings and errors will be logged
session.run_processing_job(...)
```
