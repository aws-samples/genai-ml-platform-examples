# mlp_sdk_v3

A Python wrapper library for SageMaker SDK v3 with configuration-driven defaults.

## Overview

The mlp_sdk_v3 simplifies SageMaker operations by providing a session-based interface with configuration-driven defaults. Built on top of the SageMaker Python SDK v3, it abstracts infrastructure complexity while maintaining full compatibility with the underlying SDK.

### Key Features

- **Configuration-driven defaults**: Define AWS resources (VPCs, security groups, S3 buckets) in YAML configuration files
- **Simple session interface**: Single entry point for all SageMaker operations
- **Runtime parameter override**: Override any default configuration at runtime
- **Full SageMaker SDK compatibility**: Access underlying SageMaker SDK objects for advanced use cases
- **Comprehensive error handling**: Clear error messages with actionable guidance
- **Encryption support**: AES-256-GCM encryption for sensitive configuration values
- **Audit trail**: Track all operations for debugging and compliance

## Installation

```bash
pip install mlp_sdk_v3
```

## Quick Start

### Generate Configuration

First, generate your configuration file:

```bash
# Interactive mode (recommended)
python examples/generate_admin_config.py --interactive

# Or use defaults
python examples/generate_admin_config.py --output /home/sagemaker-user/.config/admin-config.yaml
```

See [examples/QUICKSTART.md](examples/QUICKSTART.md) for a complete quick start guide.

### Basic Usage

```python
from mlp_sdk_v3 import MLP_Session

# Initialize session with default configuration
session = MLP_Session()

# Create a feature group
feature_group = session.create_feature_group(
    feature_group_name="customer-features",
    record_identifier_name="customer_id",
    event_time_feature_name="event_time",
    feature_definitions=[
        {"FeatureName": "customer_id", "FeatureType": "String"},
        {"FeatureName": "age", "FeatureType": "Integral"},
        {"FeatureName": "income", "FeatureType": "Fractional"},
        {"FeatureName": "event_time", "FeatureType": "String"}
    ]
)

# Run a processing job
processor = session.run_processing_job(
    job_name="data-preprocessing",
    processing_script="preprocess.py",
    inputs=[{"source": "s3://my-bucket/raw-data/", "destination": "/opt/ml/processing/input"}],
    outputs=[{"source": "/opt/ml/processing/output", "destination": "s3://my-bucket/processed-data/"}]
)

# Run a training job
trainer = session.run_training_job(
    job_name="model-training",
    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310",
    source_code_dir="training-scripts",
    entry_script="train.py",
    inputs={"train": "s3://my-bucket/processed-data/"}
)

# Create a pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

pipeline = session.create_pipeline(
    pipeline_name="ml-workflow",
    steps=[
        ProcessingStep(name="preprocess", processor=processor),
        TrainingStep(name="train", estimator=trainer)
    ]
)
```

## Configuration

### Configuration File Location

By default, mlp_sdk_v3 loads configuration from:
```
/home/sagemaker-user/.config/admin-config.yaml
```

You can specify a custom configuration path:
```python
session = MLP_Session(config_path="/path/to/custom-config.yaml")
```

### Configuration File Format

Create a YAML configuration file with the following structure:

```yaml
defaults:
  # S3 Configuration
  s3:
    default_bucket: "my-sagemaker-bucket"
    input_prefix: "input/"
    output_prefix: "output/"
    model_prefix: "models/"
    
  # Networking Configuration  
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids: ["sg-12345678"]
    subnets: ["subnet-12345678", "subnet-87654321"]
    
  # Compute Configuration
  compute:
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
    processing_instance_count: 1
    training_instance_count: 1
    
  # Feature Store Configuration
  feature_store:
    offline_store_s3_uri: "s3://my-sagemaker-bucket/feature-store/"
    enable_online_store: false
    
  # IAM Configuration
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    
  # KMS Configuration (optional)
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
```

### Configuration Precedence

Configuration values are applied in the following order (later values override earlier ones):

1. **SageMaker SDK defaults** - Built-in defaults from the SageMaker SDK
2. **YAML configuration** - Values from your configuration file
3. **Runtime parameters** - Values passed directly to method calls

Example:
```python
# This will use the training_instance_type from config (ml.m5.xlarge)
trainer = session.run_training_job(job_name="my-job", ...)

# This will override the config and use ml.p3.2xlarge
trainer = session.run_training_job(
    job_name="my-job",
    instance_type="ml.p3.2xlarge",  # Runtime override
    ...
)
```

## Encryption Setup

mlp_sdk_v3 supports AES-256-GCM encryption for sensitive configuration values.

### Generating an Encryption Key

```python
from mlp_sdk_v3.config import ConfigurationManager

# Generate a new encryption key
key = ConfigurationManager.generate_key()
print(f"Encryption key: {key}")
# Save this key securely!
```

### Loading Encryption Keys

#### From Environment Variable

```python
import os
from mlp_sdk_v3.config import ConfigurationManager

# Set environment variable
os.environ['MLP_SDK_ENCRYPTION_KEY'] = 'your-base64-encoded-key'

# Load key from environment
key = ConfigurationManager.load_key_from_env()
session = MLP_Session(config_path="encrypted-config.yaml")
```

#### From File

```python
from mlp_sdk_v3.config import ConfigurationManager

# Load key from file
key = ConfigurationManager.load_key_from_file("/path/to/keyfile")
config_manager = ConfigurationManager(
    config_path="encrypted-config.yaml",
    encryption_key=key
)
```

#### From AWS KMS

```python
from mlp_sdk_v3.config import ConfigurationManager

# Load key from KMS
key = ConfigurationManager.load_key_from_kms(
    key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID",
    region="us-west-2"
)
config_manager = ConfigurationManager(
    config_path="encrypted-config.yaml",
    encryption_key=key
)
```

### Encrypting Configuration Files

```python
from mlp_sdk_v3.config import ConfigurationManager

# Generate or load encryption key
key = ConfigurationManager.generate_key()

# Create configuration manager
config_manager = ConfigurationManager(encryption_key=key)

# Encrypt specific fields in configuration file
config_manager.encrypt_config_file(
    input_path="plain-config.yaml",
    output_path="encrypted-config.yaml",
    fields_to_encrypt=[
        "defaults.iam.execution_role",
        "defaults.kms.key_id"
    ]
)
```

### Decrypting Configuration Files

```python
from mlp_sdk_v3.config import ConfigurationManager

# Load encryption key
key = ConfigurationManager.load_key_from_env()

# Create configuration manager
config_manager = ConfigurationManager(encryption_key=key)

# Decrypt specific fields
config_manager.decrypt_config_file(
    input_path="encrypted-config.yaml",
    output_path="decrypted-config.yaml",
    fields_to_decrypt=[
        "defaults.iam.execution_role",
        "defaults.kms.key_id"
    ]
)
```

## Advanced Usage

### Accessing Underlying SageMaker SDK Objects

```python
session = MLP_Session()

# Access SageMaker session
sagemaker_session = session.sagemaker_session

# Access boto3 clients
s3_client = session.boto_session.client('s3')
sagemaker_client = session.sagemaker_client
runtime_client = session.sagemaker_runtime_client

# Get session properties
print(f"Region: {session.region_name}")
print(f"Account ID: {session.account_id}")
print(f"Default bucket: {session.default_bucket}")
```

### Audit Trail

Track all operations for debugging and compliance:

```python
# Initialize session with audit trail enabled (default)
session = MLP_Session(enable_audit_trail=True)

# Perform operations
session.create_feature_group(...)
session.run_processing_job(...)

# Get audit trail entries
entries = session.get_audit_trail(operation="create_feature_group")
print(f"Found {len(entries)} feature group operations")

# Get audit trail summary
summary = session.get_audit_trail_summary()
print(f"Total operations: {summary['total_entries']}")
print(f"Failed operations: {len(summary['failed_operations'])}")

# Export audit trail
session.export_audit_trail("audit-trail.json", format="json")
session.export_audit_trail("audit-trail.csv", format="csv")
```

### Logging Configuration

```python
import logging

# Initialize with custom log level
session = MLP_Session(log_level=logging.DEBUG)

# Change log level at runtime
session.set_log_level(logging.WARNING)
```

### Runtime Configuration Updates

```python
session = MLP_Session()

# Update session configuration at runtime
session.update_session_config(default_bucket="new-bucket-name")

# Get current configuration
config = session.get_config()
print(config)
```

## Error Handling

mlp_sdk_v3 provides detailed error messages with AWS error details:

```python
from mlp_sdk_v3 import MLP_Session, ValidationError, AWSServiceError, ConfigurationError

try:
    session = MLP_Session()
    feature_group = session.create_feature_group(
        feature_group_name="",  # Invalid: empty name
        ...
    )
except ValidationError as e:
    print(f"Validation error: {e}")
except AWSServiceError as e:
    print(f"AWS error: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Request ID: {e.request_id}")
    print(f"Details: {e.get_error_details()}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

## API Reference

### MLP_Session

Main interface for all mlp_sdk_v3 operations.

#### Methods

- `__init__(config_path=None, log_level=logging.INFO, enable_audit_trail=True, **kwargs)` - Initialize session
- `create_feature_group(feature_group_name, record_identifier_name, event_time_feature_name, feature_definitions, **kwargs)` - Create feature group
- `run_processing_job(job_name, processing_script=None, inputs=None, outputs=None, **kwargs)` - Execute processing job
- `run_training_job(job_name, training_image, source_code_dir=None, entry_script=None, requirements=None, inputs=None, **kwargs)` - Execute training job
- `create_pipeline(pipeline_name, steps, parameters=None, **kwargs)` - Create pipeline
- `upsert_pipeline(pipeline, **kwargs)` - Create or update pipeline
- `start_pipeline_execution(pipeline_name, **kwargs)` - Start pipeline execution
- `get_config()` - Get current configuration
- `get_execution_role()` - Get IAM execution role
- `set_log_level(level)` - Set logging level
- `get_audit_trail(operation=None, status=None, limit=None)` - Get audit trail entries
- `export_audit_trail(file_path, format='json')` - Export audit trail

#### Properties

- `sagemaker_session` - Underlying SageMaker session
- `boto_session` - Underlying boto3 session
- `sagemaker_client` - SageMaker boto3 client
- `sagemaker_runtime_client` - SageMaker Runtime boto3 client
- `region_name` - AWS region name
- `default_bucket` - Default S3 bucket
- `account_id` - AWS account ID

### ConfigurationManager

Handles configuration loading and encryption.

#### Methods

- `__init__(config_path=None, encryption_key=None)` - Initialize configuration manager
- `get_default(key, fallback=None)` - Get configuration value
- `merge_with_runtime(runtime_config)` - Merge runtime parameters with defaults
- `encrypt_value(plaintext, key=None)` - Encrypt a value
- `decrypt_value(encrypted, key=None)` - Decrypt a value
- `encrypt_config_file(input_path, output_path, fields_to_encrypt, key=None)` - Encrypt configuration file
- `decrypt_config_file(input_path, output_path, fields_to_decrypt, key=None)` - Decrypt configuration file

#### Static Methods

- `generate_key()` - Generate new encryption key
- `load_key_from_env(env_var='MLP_SDK_ENCRYPTION_KEY')` - Load key from environment
- `load_key_from_file(file_path)` - Load key from file
- `load_key_from_kms(key_id, region=None)` - Load key from AWS KMS

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/example/mlp_sdk_v3.git
cd mlp_sdk_v3

# Install in development mode with test dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property-based tests only
pytest tests/property/

# Run with coverage
pytest --cov=mlp_sdk_v3

# Run specific test file
pytest tests/unit/test_session.py
```

### Code Quality

```bash
# Format code
black mlp_sdk_v3 tests

# Sort imports
isort mlp_sdk_v3 tests

# Lint code
flake8 mlp_sdk_v3 tests

# Type checking
mypy mlp_sdk_v3
```

## Requirements

- Python >= 3.8
- sagemaker >= 3.0.0
- boto3 >= 1.26.0
- pyyaml >= 6.0
- pydantic >= 2.0.0
- cryptography >= 41.0.0

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to our GitHub repository.

## Support

For issues, questions, or contributions, please visit our [GitHub repository](https://github.com/example/mlp_sdk_v3).

## Examples

The `examples/` directory contains helpful scripts and guides:

- **[generate_admin_config.py](examples/generate_admin_config.py)** - Generate configuration files
- **[basic_usage.py](examples/basic_usage.py)** - Basic SDK usage examples
- **[sagemaker_operations.py](examples/sagemaker_operations.py)** - SageMaker operations examples
- **[xgboost_training_example.ipynb](examples/xgboost_training_example.ipynb)** - XGBoost training notebook ⭐
- **[xgboost_training_script.py](examples/xgboost_training_script.py)** - XGBoost training script
- **[QUICKSTART.md](examples/QUICKSTART.md)** - 5-minute quick start guide
- **[TRAINING_EXAMPLES.md](examples/TRAINING_EXAMPLES.md)** - Detailed training guide
- **[README.md](examples/README.md)** - Examples documentation

Run examples:
```bash
# Generate config
python examples/generate_admin_config.py --interactive

# Run basic examples
python examples/basic_usage.py

# Run SageMaker operations examples
python examples/sagemaker_operations.py

# Run XGBoost training (script)
python examples/xgboost_training_script.py --wait

# Run XGBoost training (notebook)
jupyter notebook examples/xgboost_training_example.ipynb
```