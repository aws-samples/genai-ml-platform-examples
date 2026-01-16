# Configuration Guide for mlp_sdk

This guide explains how to configure mlp_sdk for your SageMaker workflows.

## Table of Contents

- [Overview](#overview)
- [Configuration File Location](#configuration-file-location)
- [Configuration File Format](#configuration-file-format)
- [Configuration Sections](#configuration-sections)
- [Configuration Precedence](#configuration-precedence)
- [Validation Rules](#validation-rules)
- [Examples](#examples)
- [Best Practices](#best-practices)

## Overview

mlp_sdk uses YAML configuration files to define default values for AWS resources and SageMaker operations. This allows you to:

- Define infrastructure defaults once and reuse them across all operations
- Avoid repeating VPC, security group, and S3 bucket configurations
- Maintain consistent settings across your team
- Override defaults at runtime when needed

## Configuration File Location

### Default Location

By default, mlp_sdk loads configuration from:

```
/home/sagemaker-user/.config/admin-config.yaml
```

This is the standard location for SageMaker Studio and SageMaker Notebook instances.

### Custom Location

You can specify a custom configuration path:

```python
from mlp_sdk import MLP_Session

# Use custom configuration file
session = MLP_Session(config_path="/path/to/custom-config.yaml")
```

### No Configuration

If no configuration file exists, mlp_sdk will use SageMaker SDK defaults:

```python
from mlp_sdk import MLP_Session

# Will use SageMaker SDK defaults if config file doesn't exist
session = MLP_Session()
```

## Configuration File Format

Configuration files use YAML format with the following structure:

```yaml
defaults:
  s3:
    # S3 configuration
  networking:
    # VPC, security groups, subnets
  compute:
    # Instance types and counts
  feature_store:
    # Feature Store settings
  iam:
    # IAM roles
  kms:
    # KMS encryption keys (optional)
```

## Configuration Sections

### S3 Configuration

Defines default S3 bucket and prefixes for data storage.

```yaml
defaults:
  s3:
    default_bucket: "my-sagemaker-bucket"
    input_prefix: "input/"
    output_prefix: "output/"
    model_prefix: "models/"
```

**Fields:**

- `default_bucket` (required): Default S3 bucket for all operations
  - Must be a valid S3 bucket name (3-63 characters, lowercase, alphanumeric, hyphens, dots)
  - Example: `"my-sagemaker-bucket"`

- `input_prefix` (optional): Default prefix for input data
  - Default: `"input/"`
  - Must end with `/`
  - Example: `"data/input/"`

- `output_prefix` (optional): Default prefix for output data
  - Default: `"output/"`
  - Must end with `/`
  - Example: `"data/output/"`

- `model_prefix` (optional): Default prefix for model artifacts
  - Default: `"models/"`
  - Must end with `/`
  - Example: `"artifacts/models/"`

### Networking Configuration

Defines VPC, security groups, and subnets for SageMaker operations.

```yaml
defaults:
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids:
      - "sg-12345678"
      - "sg-87654321"
    subnets:
      - "subnet-12345678"
      - "subnet-87654321"
```

**Fields:**

- `vpc_id` (required): VPC ID for SageMaker resources
  - Format: `vpc-` followed by 8-17 hexadecimal characters
  - Example: `"vpc-0a1b2c3d4e5f6g7h8"`

- `security_group_ids` (required): List of security group IDs
  - At least one security group required
  - Format: `sg-` followed by 8-17 hexadecimal characters
  - Example: `["sg-12345678", "sg-87654321"]`

- `subnets` (required): List of subnet IDs
  - At least one subnet required
  - Format: `subnet-` followed by 8-17 hexadecimal characters
  - Example: `["subnet-12345678", "subnet-87654321"]`
  - Recommendation: Use subnets in different availability zones for high availability

### Compute Configuration

Defines default instance types and counts for processing and training jobs.

```yaml
defaults:
  compute:
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
    processing_instance_count: 1
    training_instance_count: 1
```

**Fields:**

- `processing_instance_type` (optional): Default instance type for processing jobs
  - Default: `"ml.m5.large"`
  - Format: `ml.` followed by instance family and size
  - Examples: `"ml.m5.large"`, `"ml.m5.4xlarge"`, `"ml.c5.2xlarge"`

- `training_instance_type` (optional): Default instance type for training jobs
  - Default: `"ml.m5.xlarge"`
  - Format: `ml.` followed by instance family and size
  - Examples: `"ml.p3.2xlarge"`, `"ml.g4dn.xlarge"`, `"ml.m5.2xlarge"`

- `processing_instance_count` (optional): Default number of instances for processing
  - Default: `1`
  - Range: 1-100
  - Example: `2`

- `training_instance_count` (optional): Default number of instances for training
  - Default: `1`
  - Range: 1-100
  - Example: `4` (for distributed training)

### Feature Store Configuration

Defines default settings for SageMaker Feature Store.

```yaml
defaults:
  feature_store:
    offline_store_s3_uri: "s3://my-sagemaker-bucket/feature-store/"
    enable_online_store: false
```

**Fields:**

- `offline_store_s3_uri` (required): S3 URI for offline feature store
  - Format: `s3://` followed by bucket and prefix
  - Must end with `/`
  - Example: `"s3://my-bucket/features/offline/"`

- `enable_online_store` (optional): Enable online feature store by default
  - Default: `false`
  - Values: `true` or `false`
  - Note: Online store incurs additional costs

### IAM Configuration

Defines IAM execution role for SageMaker operations.

```yaml
defaults:
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
```

**Fields:**

- `execution_role` (required): IAM role ARN for SageMaker execution
  - Format: `arn:aws:iam::` followed by account ID and role name
  - Example: `"arn:aws:iam::123456789012:role/SageMakerExecutionRole"`
  - Required permissions: SageMaker, S3, CloudWatch Logs access

### KMS Configuration (Optional)

Defines KMS key for encryption.

```yaml
defaults:
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
```

**Fields:**

- `key_id` (optional): KMS key ID or ARN for encryption
  - Format: Full ARN or just the key ID (UUID)
  - Example (ARN): `"arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"`
  - Example (ID): `"KEY-ID"`

## Configuration Precedence

Configuration values are applied in the following order (later values override earlier ones):

1. **SageMaker SDK defaults** - Built-in defaults from the SageMaker SDK
2. **YAML configuration** - Values from your configuration file
3. **Runtime parameters** - Values passed directly to method calls

### Example

```yaml
# config.yaml
defaults:
  compute:
    training_instance_type: "ml.m5.xlarge"
```

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

# Uses config value: ml.m5.xlarge
trainer1 = session.run_training_job(job_name="job1", ...)

# Overrides config: uses ml.p3.2xlarge
trainer2 = session.run_training_job(
    job_name="job2",
    instance_type="ml.p3.2xlarge",  # Runtime override
    ...
)
```

## Validation Rules

mlp_sdk validates configuration files using Pydantic schemas. Common validation rules:

### S3 Bucket Names

- 3-63 characters
- Lowercase letters, numbers, hyphens, dots only
- Must start and end with letter or number

### VPC IDs

- Format: `vpc-` followed by 8-17 hexadecimal characters
- Example: `vpc-0a1b2c3d`

### Security Group IDs

- Format: `sg-` followed by 8-17 hexadecimal characters
- Example: `sg-12345678`

### Subnet IDs

- Format: `subnet-` followed by 8-17 hexadecimal characters
- Example: `subnet-12345678`

### Instance Types

- Format: `ml.` followed by instance family and size
- Example: `ml.m5.large`

### IAM Role ARNs

- Format: `arn:aws:iam::{account-id}:role/{role-name}`
- Example: `arn:aws:iam::123456789012:role/MyRole`

### S3 URIs

- Format: `s3://{bucket}/{prefix}`
- Must start with `s3://`
- Example: `s3://my-bucket/data/`

## Examples

### Minimal Configuration

```yaml
defaults:
  s3:
    default_bucket: "my-sagemaker-bucket"
    
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids: ["sg-12345678"]
    subnets: ["subnet-12345678"]
    
  feature_store:
    offline_store_s3_uri: "s3://my-sagemaker-bucket/feature-store/"
    
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
```

### Complete Configuration

```yaml
defaults:
  # S3 Configuration
  s3:
    default_bucket: "my-sagemaker-bucket"
    input_prefix: "data/input/"
    output_prefix: "data/output/"
    model_prefix: "artifacts/models/"
    
  # Networking Configuration
  networking:
    vpc_id: "vpc-0a1b2c3d4e5f6g7h8"
    security_group_ids:
      - "sg-12345678"
      - "sg-87654321"
    subnets:
      - "subnet-12345678"  # us-west-2a
      - "subnet-87654321"  # us-west-2b
      
  # Compute Configuration
  compute:
    processing_instance_type: "ml.m5.2xlarge"
    training_instance_type: "ml.p3.2xlarge"
    processing_instance_count: 2
    training_instance_count: 1
    
  # Feature Store Configuration
  feature_store:
    offline_store_s3_uri: "s3://my-sagemaker-bucket/feature-store/offline/"
    enable_online_store: true
    
  # IAM Configuration
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    
  # KMS Configuration (optional)
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
```

### Development Environment

```yaml
defaults:
  s3:
    default_bucket: "dev-sagemaker-bucket"
    input_prefix: "dev/input/"
    output_prefix: "dev/output/"
    model_prefix: "dev/models/"
    
  networking:
    vpc_id: "vpc-dev123456"
    security_group_ids: ["sg-dev12345"]
    subnets: ["subnet-dev1234"]
    
  compute:
    processing_instance_type: "ml.t3.medium"  # Cost-effective for dev
    training_instance_type: "ml.m5.large"     # Smaller for dev
    processing_instance_count: 1
    training_instance_count: 1
    
  feature_store:
    offline_store_s3_uri: "s3://dev-sagemaker-bucket/feature-store/"
    enable_online_store: false  # Disable for dev to save costs
    
  iam:
    execution_role: "arn:aws:iam::123456789012:role/DevSageMakerRole"
```

### Production Environment

```yaml
defaults:
  s3:
    default_bucket: "prod-sagemaker-bucket"
    input_prefix: "prod/input/"
    output_prefix: "prod/output/"
    model_prefix: "prod/models/"
    
  networking:
    vpc_id: "vpc-prod123456"
    security_group_ids:
      - "sg-prod12345"
      - "sg-prod67890"
    subnets:
      - "subnet-prod1234"  # Multi-AZ for HA
      - "subnet-prod5678"
      - "subnet-prod9012"
    
  compute:
    processing_instance_type: "ml.m5.4xlarge"
    training_instance_type: "ml.p3.8xlarge"
    processing_instance_count: 4
    training_instance_count: 2
    
  feature_store:
    offline_store_s3_uri: "s3://prod-sagemaker-bucket/feature-store/"
    enable_online_store: true
    
  iam:
    execution_role: "arn:aws:iam::123456789012:role/ProdSageMakerRole"
    
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/prod-key-id"
```

## Best Practices

### 1. Use Separate Configurations for Each Environment

Create separate configuration files for development, staging, and production:

```
configs/
├── dev-config.yaml
├── staging-config.yaml
└── prod-config.yaml
```

```python
import os
from mlp_sdk import MLP_Session

# Load environment-specific configuration
env = os.environ.get('ENVIRONMENT', 'dev')
config_path = f"configs/{env}-config.yaml"
session = MLP_Session(config_path=config_path)
```

### 2. Use Version Control

- Commit configuration files to version control
- Use separate branches or repositories for different environments
- Encrypt sensitive values before committing (see Encryption Guide)

### 3. Document Your Configuration

Add comments to explain configuration choices:

```yaml
defaults:
  s3:
    # Main bucket for all SageMaker operations
    # Lifecycle policy: Delete objects after 90 days
    default_bucket: "my-sagemaker-bucket"
    
  compute:
    # Using m5.2xlarge for processing to handle large datasets
    processing_instance_type: "ml.m5.2xlarge"
    
    # Using p3.2xlarge for GPU-accelerated training
    training_instance_type: "ml.p3.2xlarge"
```

### 4. Use Multi-AZ Subnets

For high availability, use subnets in different availability zones:

```yaml
defaults:
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids: ["sg-12345678"]
    subnets:
      - "subnet-12345678"  # us-west-2a
      - "subnet-87654321"  # us-west-2b
      - "subnet-abcdef12"  # us-west-2c
```

### 5. Start with Conservative Instance Types

Begin with smaller, cost-effective instance types and scale up as needed:

```yaml
defaults:
  compute:
    # Start with general-purpose instances
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
    
    # Scale up for production:
    # processing_instance_type: "ml.m5.4xlarge"
    # training_instance_type: "ml.p3.8xlarge"
```

### 6. Use Consistent Naming Conventions

Use consistent prefixes and naming patterns:

```yaml
defaults:
  s3:
    default_bucket: "mycompany-sagemaker-prod"
    input_prefix: "ml-workflows/input/"
    output_prefix: "ml-workflows/output/"
    model_prefix: "ml-workflows/models/"
```

### 7. Validate Configuration Before Deployment

Test configuration files before deploying:

```python
from mlp_sdk.config import ConfigurationManager

try:
    config_manager = ConfigurationManager(config_path="config.yaml")
    print("Configuration is valid")
    print(f"Loaded config: {config_manager.has_config}")
except Exception as e:
    print(f"Configuration error: {e}")
```

### 8. Use KMS for Sensitive Environments

Enable KMS encryption for production environments:

```yaml
defaults:
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/prod-key-id"
```

### 9. Monitor Configuration Usage

Use audit trails to track configuration usage:

```python
from mlp_sdk import MLP_Session

session = MLP_Session(enable_audit_trail=True)

# Perform operations...

# Review configuration usage
summary = session.get_audit_trail_summary()
print(f"Operations performed: {summary['total_entries']}")
```

### 10. Keep Configuration DRY

Use YAML anchors and aliases to avoid repetition:

```yaml
# Define common settings
common_settings: &common
  vpc_id: "vpc-12345678"
  security_group_ids: ["sg-12345678"]

defaults:
  networking:
    <<: *common
    subnets: ["subnet-12345678", "subnet-87654321"]
```

## Troubleshooting

### Configuration Not Loading

**Problem**: Configuration file exists but isn't being loaded.

**Solutions**:

1. Check file path:
   ```python
   import os
   config_path = "/home/sagemaker-user/.config/admin-config.yaml"
   print(f"File exists: {os.path.exists(config_path)}")
   ```

2. Check file permissions:
   ```bash
   ls -la /home/sagemaker-user/.config/admin-config.yaml
   ```

3. Check YAML syntax:
   ```python
   import yaml
   with open("config.yaml") as f:
       config = yaml.safe_load(f)
   ```

### Validation Errors

**Problem**: Configuration file has validation errors.

**Solutions**:

1. Check error message for specific field
2. Verify field format matches requirements
3. Use validation examples from this guide

### Runtime Overrides Not Working

**Problem**: Runtime parameters aren't overriding configuration.

**Solution**: Ensure you're passing parameters correctly:

```python
# Correct: parameter name matches SageMaker SDK
session.run_training_job(
    job_name="my-job",
    instance_type="ml.p3.2xlarge",  # Correct parameter name
    ...
)

# Incorrect: wrong parameter name
session.run_training_job(
    job_name="my-job",
    training_instance_type="ml.p3.2xlarge",  # Wrong parameter name
    ...
)
```

## Additional Resources

- [YAML Specification](https://yaml.org/spec/)
- [AWS VPC Documentation](https://docs.aws.amazon.com/vpc/)
- [SageMaker Instance Types](https://aws.amazon.com/sagemaker/pricing/)
- [IAM Roles for SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)
