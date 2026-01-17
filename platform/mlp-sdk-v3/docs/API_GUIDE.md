# mlp_sdk Developer API Guide

## Table of Contents

1. [Overview](#overview)
2. [Configuration Management](#configuration-management)
3. [Session Management](#session-management)
4. [Wrapper APIs](#wrapper-apis)
5. [Error Handling](#error-handling)
6. [Best Practices](#best-practices)

---

## Overview

The mlp_sdk provides a configuration-driven approach to AWS SageMaker operations with intelligent wrappers that reduce boilerplate code by up to 95%. This guide covers the core APIs for configuration, session management, and wrapper usage.

### Key Features

- **Configuration-driven defaults**: Define once, use everywhere
- **Three-tier parameter precedence**: Runtime > Configuration > SDK defaults
- **Intelligent wrappers**: Simplified APIs for training, processing, deployment, pipelines, and feature store
- **Enterprise-ready**: Built-in encryption, VPC support, audit trails, and logging

---

## Configuration Management

### ConfigurationManager

The `ConfigurationManager` class handles loading, validating, and managing configuration from YAML files.

#### Initialization

```python
from mlp_sdk import ConfigurationManager

# Load from file
config_manager = ConfigurationManager.from_file('config.yaml')

# Load from encrypted file
config_manager = ConfigurationManager.from_encrypted_file(
    'config.yaml.enc',
    kms_key_id='arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
)
```

#### Configuration Structure

```yaml
compute:
  training_instance_type: ml.m5.xlarge
  training_instance_count: 1
  processing_instance_type: ml.m5.large
  processing_instance_count: 1
  inference_instance_type: ml.m5.large
  inference_instance_count: 1

networking:
  vpc_id: vpc-xxxxx
  subnets:
    - subnet-xxxxx
    - subnet-yyyyy
  security_group_ids:
    - sg-xxxxx

iam:
  execution_role: arn:aws:iam::ACCOUNT-ID:role/SageMakerRole

s3:
  default_bucket: my-ml-bucket
  input_prefix: data/input
  output_prefix: data/output
  model_prefix: models

kms:
  key_id: arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID

feature_store:
  offline_store_s3_uri: s3://my-ml-bucket/feature-store
  enable_online_store: true
```

#### Accessing Configuration

```python
# Get specific configuration sections
compute_config = config_manager.get_compute_config()
networking_config = config_manager.get_networking_config()
iam_config = config_manager.get_iam_config()
s3_config = config_manager.get_s3_config()
kms_config = config_manager.get_kms_config()
feature_store_config = config_manager.get_feature_store_config()

# Access individual values
instance_type = compute_config.training_instance_type
role_arn = iam_config.execution_role
bucket = s3_config.default_bucket
```

#### Encryption Support

```python
# Encrypt configuration file
ConfigurationManager.encrypt_file(
    input_file='config.yaml',
    output_file='config.yaml.enc',
    kms_key_id='arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
)

# Decrypt configuration file
ConfigurationManager.decrypt_file(
    input_file='config.yaml.enc',
    output_file='config.yaml',
    kms_key_id='arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
)
```

---

## Session Management

### MLP_Session

The `MLP_Session` class provides a unified interface for all SageMaker operations with built-in configuration management, logging, and audit trails.

#### Initialization

```python
from mlp_sdk import MLP_Session

# Initialize with configuration file
session = MLP_Session(config_file='config.yaml')

# Initialize with encrypted configuration
session = MLP_Session(
    config_file='config.yaml.enc',
    kms_key_id='arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
)

# Initialize with AWS profile and region
session = MLP_Session(
    config_file='config.yaml',
    aws_profile='my-profile',
    region='us-west-2'
)

# Enable audit trail
session = MLP_Session(
    config_file='config.yaml',
    enable_audit_trail=True
)
```

#### Properties

```python
# Access underlying SageMaker session
sagemaker_session = session.sagemaker_session

# Access boto3 clients
sagemaker_client = session.sagemaker_client
s3_client = session.s3_client

# Access configuration manager
config_manager = session.config_manager

# Access logger
logger = session.logger

# Access audit trail (if enabled)
audit_trail = session.audit_trail

# Get AWS region
region = session.region

# Get default S3 bucket
bucket = session.default_bucket
```

#### Training Operations

```python
# Run training job with ModelTrainer (SDK v3)
model_trainer = session.run_training_job(
    job_name='my-training-job',
    training_image='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0-gpu-py310',
    source_code_dir='./code',
    entry_script='train.py',
    inputs={
        'training': 's3://my-bucket/data/train',
        'validation': 's3://my-bucket/data/val'
    },
    hyperparameters={
        'epochs': 10,
        'batch-size': 32
    }
)

# Override configuration defaults at runtime
model_trainer = session.run_training_job(
    job_name='my-training-job',
    training_image='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0-gpu-py310',
    source_code_dir='./code',
    entry_script='train.py',
    inputs={'training': 's3://my-bucket/data/train'},
    instance_type='ml.p3.2xlarge',  # Override config default
    instance_count=2,  # Override config default
    volume_size_in_gb=100
)
```

#### Processing Operations

```python
# Run processing job
processor = session.run_processing_job(
    job_name='my-processing-job',
    processing_script='preprocess.py',
    inputs=[{
        'source': 's3://my-bucket/raw-data',
        'destination': '/opt/ml/processing/input'
    }],
    outputs=[{
        'source': '/opt/ml/processing/output',
        'destination': 's3://my-bucket/processed-data'
    }]
)

# Override configuration defaults
processor = session.run_processing_job(
    job_name='my-processing-job',
    processing_script='preprocess.py',
    inputs=[...],
    outputs=[...],
    instance_type='ml.m5.2xlarge',  # Override config default
    instance_count=2
)
```

#### Deployment Operations

```python
# Deploy model to endpoint
predictor = session.deploy_model(
    model_data='s3://my-bucket/models/model.tar.gz',
    image_uri='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.0-cpu-py310',
    endpoint_name='my-endpoint'
)

# Make predictions
result = predictor.predict('1.0,2.0,3.0,4.0')

# Deploy with VPC configuration
predictor = session.deploy_model(
    model_data='s3://my-bucket/models/model.tar.gz',
    image_uri='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.0-cpu-py310',
    endpoint_name='my-endpoint',
    enable_vpc=True  # Uses VPC config from configuration file
)

# Override configuration defaults
predictor = session.deploy_model(
    model_data='s3://my-bucket/models/model.tar.gz',
    image_uri='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.0-cpu-py310',
    endpoint_name='my-endpoint',
    instance_type='ml.m5.xlarge',  # Override config default
    instance_count=2
)

# Delete endpoint
session.delete_endpoint('my-endpoint')
```

#### Pipeline Operations

```python
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.parameters import ParameterString

# Define pipeline parameters
input_data = ParameterString(name='InputData', default_value='s3://my-bucket/data')

# Create pipeline steps
processing_step = ProcessingStep(...)
training_step = TrainingStep(...)

# Create pipeline
pipeline = session.create_pipeline(
    pipeline_name='my-pipeline',
    steps=[processing_step, training_step],
    parameters=[input_data]
)

# Upsert pipeline definition
response = session.upsert_pipeline(pipeline)

# Start pipeline execution
execution = session.start_pipeline_execution(
    pipeline=pipeline,
    execution_display_name='my-execution',
    execution_parameters={'InputData': 's3://my-bucket/new-data'}
)

# Monitor pipeline execution
status = session.describe_pipeline_execution(execution)
steps = session.list_pipeline_execution_steps(execution)

# Wait for completion
final_status = session.wait_for_pipeline_execution(
    execution,
    delay=30,
    max_attempts=60
)
```

#### Feature Store Operations

```python
# Create feature group
feature_group = session.create_feature_group(
    feature_group_name='customer-features',
    record_identifier_name='customer_id',
    event_time_feature_name='event_time',
    feature_definitions=[
        {'FeatureName': 'customer_id', 'FeatureType': 'String'},
        {'FeatureName': 'age', 'FeatureType': 'Integral'},
        {'FeatureName': 'income', 'FeatureType': 'Fractional'},
        {'FeatureName': 'event_time', 'FeatureType': 'String'}
    ]
)

# Override configuration defaults
feature_group = session.create_feature_group(
    feature_group_name='customer-features',
    record_identifier_name='customer_id',
    event_time_feature_name='event_time',
    feature_definitions=[...],
    enable_online_store=False,  # Override config default
    offline_store_config={
        'S3StorageConfig': {
            'S3Uri': 's3://my-bucket/custom-feature-store'
        }
    }
)
```

---

## Wrapper APIs

### TrainingWrapper

Simplified training job execution using SageMaker SDK v3 ModelTrainer API.

#### Methods

##### run_training_job()

```python
from mlp_sdk.wrappers import TrainingWrapper

wrapper = TrainingWrapper(config_manager, logger)

model_trainer = wrapper.run_training_job(
    sagemaker_session=session.sagemaker_session,
    job_name='my-training-job',
    training_image='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0-gpu-py310',
    source_code_dir='./code',
    entry_script='train.py',
    requirements='requirements.txt',
    inputs={
        'training': 's3://my-bucket/data/train',
        'validation': 's3://my-bucket/data/val'
    },
    hyperparameters={'epochs': 10, 'batch-size': 32},
    environment={'MY_VAR': 'value'},
    instance_type='ml.p3.2xlarge',  # Optional override
    instance_count=2,  # Optional override
    volume_size_in_gb=100,
    max_run_in_seconds=86400
)
```

**Parameters:**
- `sagemaker_session`: SageMaker session object (required)
- `job_name`: Training job name (required)
- `training_image`: Container image URI (required)
- `source_code_dir`: Directory with training code (optional)
- `entry_script`: Entry point script (optional)
- `requirements`: Requirements file path (optional)
- `inputs`: Training data inputs (optional)
- `hyperparameters`: Training hyperparameters (optional)
- `environment`: Environment variables (optional)
- `instance_type`: Override config default (optional)
- `instance_count`: Override config default (optional)
- `volume_size_in_gb`: EBS volume size (optional)
- `max_run_in_seconds`: Maximum runtime (optional)

**Returns:** ModelTrainer object

**Raises:**
- `ValidationError`: Invalid parameters
- `AWSServiceError`: Training job execution failed

---

### ProcessingWrapper

Simplified processing job execution.

#### Methods

##### run_processing_job()

```python
from mlp_sdk.wrappers import ProcessingWrapper

wrapper = ProcessingWrapper(config_manager, logger)

processor = wrapper.run_processing_job(
    sagemaker_session=session.sagemaker_session,
    job_name='my-processing-job',
    processing_script='preprocess.py',
    inputs=[{
        'source': 's3://my-bucket/raw-data',
        'destination': '/opt/ml/processing/input'
    }],
    outputs=[{
        'source': '/opt/ml/processing/output',
        'destination': 's3://my-bucket/processed-data'
    }],
    arguments=['--normalize', '--split', '0.8'],
    env={'MY_VAR': 'value'},
    instance_type='ml.m5.2xlarge',  # Optional override
    instance_count=2  # Optional override
)
```

**Parameters:**
- `sagemaker_session`: SageMaker session object (required)
- `job_name`: Processing job name (required)
- `processing_script`: Processing script path (optional)
- `inputs`: List of input configurations (optional)
- `outputs`: List of output configurations (optional)
- `arguments`: Script arguments (optional)
- `env`: Environment variables (optional)
- `instance_type`: Override config default (optional)
- `instance_count`: Override config default (optional)
- `volume_size_in_gb`: EBS volume size (optional)
- `max_runtime_in_seconds`: Maximum runtime (optional)

**Returns:** Processor object

**Raises:**
- `ValidationError`: Invalid parameters
- `AWSServiceError`: Processing job execution failed

---

### DeploymentWrapper

Simplified model deployment using SageMaker SDK v3 ModelBuilder API.

#### Methods

##### deploy_model()

```python
from mlp_sdk.wrappers import DeploymentWrapper

wrapper = DeploymentWrapper(config_manager, logger)

predictor = wrapper.deploy_model(
    model_data='s3://my-bucket/models/model.tar.gz',
    image_uri='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.0-cpu-py310',
    endpoint_name='my-endpoint',
    enable_vpc=True,  # Enable VPC configuration
    environment={'MODEL_NAME': 'my-model'},
    instance_type='ml.m5.xlarge',  # Optional override
    instance_count=2  # Optional override
)

# Make predictions
result = predictor.predict('1.0,2.0,3.0,4.0', content_type='text/csv')

# Delete endpoint
predictor.delete_endpoint()
```

**Parameters:**
- `model_data`: S3 URI of model artifacts (required)
- `image_uri`: Container image URI (required)
- `endpoint_name`: Endpoint name (required)
- `enable_vpc`: Enable VPC configuration (default: False)
- `environment`: Environment variables (optional)
- `instance_type`: Override config default (optional)
- `instance_count`: Override config default (optional)
- `kms_key`: KMS key for encryption (optional)

**Returns:** PredictorWrapper object with `predict()` and `delete_endpoint()` methods

**Raises:**
- `ValidationError`: Invalid parameters
- `AWSServiceError`: Deployment failed

---

### PipelineWrapper

Simplified pipeline creation and execution.

#### Methods

##### create_pipeline()

```python
from mlp_sdk.wrappers import PipelineWrapper
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.parameters import ParameterString

wrapper = PipelineWrapper(config_manager, logger)

# Define pipeline parameters
input_data = ParameterString(name='InputData')

# Create pipeline
pipeline = wrapper.create_pipeline(
    sagemaker_session=session.sagemaker_session,
    pipeline_name='my-pipeline',
    steps=[processing_step, training_step],
    parameters=[input_data]
)
```

##### upsert_pipeline()

```python
response = wrapper.upsert_pipeline(
    pipeline=pipeline,
    description='My ML pipeline',
    tags=[{'Key': 'Environment', 'Value': 'Production'}]
)
```

##### start_pipeline_execution()

```python
execution = wrapper.start_pipeline_execution(
    pipeline=pipeline,
    execution_display_name='my-execution',
    execution_parameters={'InputData': 's3://my-bucket/new-data'}
)
```

##### describe_pipeline_execution()

```python
status = wrapper.describe_pipeline_execution(execution)
print(f"Status: {status['PipelineExecutionStatus']}")
```

##### list_pipeline_execution_steps()

```python
steps = wrapper.list_pipeline_execution_steps(execution)
for step in steps:
    print(f"{step['StepName']}: {step['StepStatus']}")
```

##### wait_for_pipeline_execution()

```python
final_status = wrapper.wait_for_pipeline_execution(
    pipeline_execution=execution,
    delay=30,
    max_attempts=60
)
```

---

### FeatureStoreWrapper

Simplified feature group creation.

#### Methods

##### create_feature_group()

```python
from mlp_sdk.wrappers import FeatureStoreWrapper

wrapper = FeatureStoreWrapper(config_manager, logger)

feature_group = wrapper.create_feature_group(
    sagemaker_session=session.sagemaker_session,
    feature_group_name='customer-features',
    record_identifier_name='customer_id',
    event_time_feature_name='event_time',
    feature_definitions=[
        {'FeatureName': 'customer_id', 'FeatureType': 'String'},
        {'FeatureName': 'age', 'FeatureType': 'Integral'},
        {'FeatureName': 'income', 'FeatureType': 'Fractional'},
        {'FeatureName': 'event_time', 'FeatureType': 'String'}
    ],
    description='Customer demographic features',
    tags=[{'Key': 'Team', 'Value': 'DataScience'}]
)
```

**Parameters:**
- `sagemaker_session`: SageMaker session object (required)
- `feature_group_name`: Feature group name (required)
- `record_identifier_name`: Record identifier feature name (required)
- `event_time_feature_name`: Event time feature name (required)
- `feature_definitions`: List of feature definitions (required)
- `description`: Feature group description (optional)
- `tags`: Resource tags (optional)
- `enable_online_store`: Override config default (optional)
- `offline_store_config`: Override config default (optional)

**Returns:** FeatureGroup object

**Raises:**
- `ValidationError`: Invalid parameters
- `AWSServiceError`: Feature group creation failed

---

## Error Handling

### Exception Hierarchy

```python
MLPSDKError                    # Base exception
├── ValidationError            # Invalid parameters or configuration
├── SessionError              # Session initialization or state errors
├── ConfigurationError        # Configuration loading or validation errors
└── AWSServiceError           # AWS service operation failures
```

### Exception Usage

```python
from mlp_sdk.exceptions import (
    MLPSDKError,
    ValidationError,
    SessionError,
    ConfigurationError,
    AWSServiceError
)

try:
    session = MLP_Session(config_file='config.yaml')
    model_trainer = session.run_training_job(...)
except ValidationError as e:
    print(f"Invalid parameters: {e}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except SessionError as e:
    print(f"Session error: {e}")
except AWSServiceError as e:
    print(f"AWS service error: {e}")
    print(f"Original AWS error: {e.aws_error}")
except MLPSDKError as e:
    print(f"SDK error: {e}")
```

### Logging

```python
from mlp_sdk.exceptions import MLPLogger

# Create logger
logger = MLPLogger("my-app")

# Log messages
logger.debug("Debug message", key="value")
logger.info("Info message", key="value")
logger.warning("Warning message", key="value")
logger.error("Error message", error=exception)

# Access underlying structlog logger
structlog_logger = logger.logger
```

---

## Best Practices

### 1. Configuration Management

**DO:**
- Store configuration in version control (encrypted for sensitive data)
- Use separate configurations for dev, staging, and production
- Encrypt configuration files containing sensitive data
- Validate configuration before deployment

**DON'T:**
- Hardcode credentials or sensitive data in code
- Share unencrypted configuration files containing secrets
- Use production configuration in development environments

### 2. Parameter Precedence

The SDK uses a three-tier parameter precedence system:

1. **Runtime parameters** (highest priority) - Override everything
2. **Configuration defaults** - Applied when runtime parameters not provided
3. **SDK defaults** (lowest priority) - Used when neither runtime nor config provide values

```python
# Configuration file specifies: instance_type = ml.m5.xlarge
# Runtime override takes precedence
model_trainer = session.run_training_job(
    job_name='my-job',
    training_image='...',
    instance_type='ml.p3.2xlarge'  # This overrides config
)
```

### 3. Session Initialization

**DO:**
- Initialize session once and reuse it
- Enable audit trail for production environments
- Use encrypted configuration files in production

```python
# Good: Initialize once, reuse
session = MLP_Session(
    config_file='config.yaml.enc',
    kms_key_id='arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID',
    enable_audit_trail=True
)

# Use session for multiple operations
model_trainer = session.run_training_job(...)
processor = session.run_processing_job(...)
predictor = session.deploy_model(...)
```

**DON'T:**
- Create new session for each operation
- Disable audit trail in production

### 4. Error Handling

**DO:**
- Catch specific exceptions
- Log errors with context
- Handle AWS service errors gracefully

```python
try:
    model_trainer = session.run_training_job(...)
except ValidationError as e:
    logger.error("Invalid parameters", error=e)
    # Fix parameters and retry
except AWSServiceError as e:
    logger.error("AWS service error", error=e, aws_error=e.aws_error)
    # Handle service-specific errors
```

### 5. Resource Cleanup

**DO:**
- Delete endpoints when no longer needed
- Clean up temporary S3 objects
- Monitor resource usage

```python
try:
    predictor = session.deploy_model(...)
    # Use predictor
    result = predictor.predict(data)
finally:
    # Clean up
    session.delete_endpoint(endpoint_name)
```

### 6. VPC Configuration

**DO:**
- Enable VPC for production deployments
- Use VPC configuration from config file
- Test VPC connectivity before deployment

```python
# Enable VPC for endpoint deployment
predictor = session.deploy_model(
    model_data='...',
    image_uri='...',
    endpoint_name='my-endpoint',
    enable_vpc=True  # Uses VPC config from configuration file
)
```

**DON'T:**
- Deploy to public subnets in production
- Skip VPC configuration for sensitive workloads

### 7. Pipeline Best Practices

**DO:**
- Use pipeline parameters for flexibility
- Monitor pipeline execution status
- Handle pipeline failures gracefully

```python
# Define reusable parameters
input_data = ParameterString(name='InputData')
model_approval = ParameterString(name='ModelApproval', default_value='Approved')

# Create pipeline with parameters
pipeline = session.create_pipeline(
    pipeline_name='my-pipeline',
    steps=[...],
    parameters=[input_data, model_approval]
)

# Start execution with custom parameters
execution = session.start_pipeline_execution(
    pipeline=pipeline,
    execution_parameters={
        'InputData': 's3://my-bucket/new-data',
        'ModelApproval': 'PendingManualApproval'
    }
)

# Monitor execution
final_status = session.wait_for_pipeline_execution(execution)
if final_status['PipelineExecutionStatus'] == 'Failed':
    # Handle failure
    steps = session.list_pipeline_execution_steps(execution)
    for step in steps:
        if step['StepStatus'] == 'Failed':
            logger.error(f"Step {step['StepName']} failed", 
                        reason=step.get('FailureReason'))
```

### 8. Feature Store Best Practices

**DO:**
- Enable online store for real-time inference
- Use offline store for training data
- Define clear feature schemas

```python
feature_group = session.create_feature_group(
    feature_group_name='customer-features',
    record_identifier_name='customer_id',
    event_time_feature_name='event_time',
    feature_definitions=[
        {'FeatureName': 'customer_id', 'FeatureType': 'String'},
        {'FeatureName': 'age', 'FeatureType': 'Integral'},
        {'FeatureName': 'income', 'FeatureType': 'Fractional'},
        {'FeatureName': 'event_time', 'FeatureType': 'String'}
    ]
)
```

---

## Additional Resources

- [Configuration Guide](CONFIGURATION_GUIDE.md) - Detailed configuration options
- [Encryption Guide](ENCRYPTION_GUIDE.md) - Encryption setup and best practices
- [Usage Examples](USAGE_EXAMPLES.md) - Complete working examples
- [Blog Post](../BLOG_ML_PLATFORM_SDK.md) - Overview and benefits

---

## Support

For issues, questions, or contributions, please refer to the project repository.
