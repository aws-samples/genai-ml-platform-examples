# mlp_sdk Examples

This directory contains example scripts and configurations for using mlp_sdk.

## Configuration Generator

### generate_admin_config.py

A utility script to generate the `admin-config.yaml` file with default values.

**Basic Usage:**

```bash
# Generate config with default values
python generate_admin_config.py

# Generate config at specific location
python generate_admin_config.py --output /home/sagemaker-user/.config/admin-config.yaml

# Interactive mode (prompts for each value)
python generate_admin_config.py --interactive

# Generate encrypted config (requires encryption setup)
python generate_admin_config.py --encrypted --key-source env
```

**Output:**

The script generates a YAML file with the following structure:

```yaml
defaults:
  s3:
    default_bucket: my-sagemaker-bucket
    input_prefix: input/
    output_prefix: output/
    model_prefix: models/
  networking:
    vpc_id: vpc-12345678
    security_group_ids:
    - sg-12345678
    subnets:
    - subnet-12345678
    - subnet-87654321
  compute:
    processing_instance_type: ml.m5.large
    training_instance_type: ml.m5.xlarge
    processing_instance_count: 1
    training_instance_count: 1
  feature_store:
    offline_store_s3_uri: s3://my-sagemaker-bucket/feature-store/
    enable_online_store: false
  iam:
    execution_role: arn:aws:iam::ACCOUNT-ID:role/SageMakerExecutionRole
  kms:
    key_id: arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID
```

**After Generation:**

1. Review and customize the values in the generated file
2. Update AWS resource IDs (VPC, subnets, security groups, etc.)
3. Set the correct IAM execution role ARN
4. Update S3 bucket names to match your environment
5. (Optional) Encrypt the config file - see [docs/ENCRYPTION_GUIDE.md](../docs/ENCRYPTION_GUIDE.md)

## Training Examples

### XGBoost Training Example

Complete examples demonstrating XGBoost model training with synthetic data:

**Jupyter Notebook (Recommended):**
```bash
jupyter notebook examples/xgboost_training_example.ipynb
```

**Python Script:**
```bash
# Basic usage
python examples/xgboost_training_script.py

# Wait for training to complete
python examples/xgboost_training_script.py --wait

# Use custom config
python examples/xgboost_training_script.py --config /path/to/config.yaml --wait
```

**What's Included:**
- Synthetic data generation (10,000 samples, 20 features)
- Data preparation for XGBoost
- S3 upload
- Training job with mlp_sdk wrapper
- Training monitoring
- Audit trail viewing
- Model deployment (notebook only)

## Usage Examples

See [docs/USAGE_EXAMPLES.md](../docs/USAGE_EXAMPLES.md) for complete code examples of using mlp_sdk.

## Quick Start

1. Generate your configuration:
   ```bash
   python examples/generate_admin_config.py --interactive
   ```

2. Move it to the default location:
   ```bash
   mkdir -p /home/sagemaker-user/.config
   mv admin-config.yaml /home/sagemaker-user/.config/
   ```

3. Use mlp_sdk in your code:
   ```python
   from mlp_sdk import MLP_Session
   
   # Initialize session (automatically loads config)
   session = MLP_Session()
   
   # Use SageMaker operations with defaults
   # See docs/USAGE_EXAMPLES.md for more examples
   ```

## Additional Resources

- [Configuration Guide](../docs/CONFIGURATION_GUIDE.md) - Detailed configuration options
- [Encryption Guide](../docs/ENCRYPTION_GUIDE.md) - How to encrypt your config
- [Usage Examples](../docs/USAGE_EXAMPLES.md) - Code examples for all operations
- [README](../README.md) - Main project documentation
