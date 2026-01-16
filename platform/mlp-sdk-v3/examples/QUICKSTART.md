# Quick Start Guide

Get started with mlp_sdk in 5 minutes!

## Step 1: Install mlp_sdk

```bash
pip install mlp_sdk
```

## Step 2: Generate Configuration

```bash
# Interactive mode (recommended for first-time setup)
python examples/generate_admin_config.py --interactive

# Or use defaults and customize later
python examples/generate_admin_config.py
```

## Step 3: Customize Your Configuration

Edit the generated `admin-config.yaml` file:

```yaml
defaults:
  s3:
    default_bucket: YOUR-BUCKET-NAME  # ← Change this
  networking:
    vpc_id: vpc-XXXXXXXX              # ← Change this
    security_group_ids:
      - sg-XXXXXXXX                   # ← Change this
    subnets:
      - subnet-XXXXXXXX               # ← Change this
      - subnet-YYYYYYYY               # ← Change this
  iam:
    execution_role: arn:aws:iam::YOUR-ACCOUNT:role/YOUR-ROLE  # ← Change this
  # ... other settings
```

## Step 4: Move Config to Default Location

```bash
mkdir -p /home/sagemaker-user/.config
mv admin-config.yaml /home/sagemaker-user/.config/
```

Or keep it anywhere and specify the path when initializing.

## Step 5: Use mlp_sdk

```python
from mlp_sdk import MLP_Session

# Initialize session (loads config automatically)
session = MLP_Session()

# Run a training job with defaults
session.run_training_job(
    job_name="my-training-job",
    algorithm_specification={
        "training_image": "382416733822.dkr.ecr.us-west-2.amazonaws.com/xgboost:latest",
        "training_input_mode": "File"
    },
    input_data_config=[{
        "ChannelName": "train",
        "DataSource": {
            "S3DataSource": {
                "S3DataType": "S3Prefix",
                "S3Uri": "s3://my-bucket/train/"
            }
        }
    }],
    hyperparameters={
        "max_depth": "5",
        "eta": "0.2",
        "objective": "binary:logistic"
    }
    # Instance type, VPC, role, etc. come from config!
)
```

## Common Tasks

### Use Custom Config Path

```python
session = MLP_Session(config_path="/path/to/my-config.yaml")
```

### Override Defaults at Runtime

```python
session.run_training_job(
    job_name="my-job",
    instance_type="ml.p3.2xlarge",  # Override config default
    instance_count=2,                # Override config default
    # Other params use config defaults
)
```

### Enable Debug Logging

```python
session = MLP_Session(log_level="DEBUG")
```

### View Audit Trail

```python
audit_entries = session.get_audit_trail()
for entry in audit_entries:
    print(f"{entry['timestamp']}: {entry['operation']}")
```

## Example Scripts

Run the example scripts to see mlp_sdk in action:

```bash
# Basic usage examples
python examples/basic_usage.py

# SageMaker operations examples
python examples/sagemaker_operations.py
```

## Next Steps

- 📖 Read [docs/USAGE_EXAMPLES.md](../docs/USAGE_EXAMPLES.md) for complete examples
- 🔧 See [docs/CONFIGURATION_GUIDE.md](../docs/CONFIGURATION_GUIDE.md) for all config options
- 🔒 Learn about [docs/ENCRYPTION_GUIDE.md](../docs/ENCRYPTION_GUIDE.md) for securing configs
- 📚 Check [README.md](../README.md) for full documentation

## Troubleshooting

### Config file not found

```
ConfigurationError: Configuration file not found
```

**Solution:** Generate config with `python examples/generate_admin_config.py` or specify custom path.

### Invalid AWS resources

```
AWSServiceError: VPC vpc-12345678 not found
```

**Solution:** Update the config file with your actual AWS resource IDs.

### Permission denied

```
AWSServiceError: User is not authorized to perform: sagemaker:CreateTrainingJob
```

**Solution:** Ensure your IAM role has the necessary SageMaker permissions.

## Support

- 🐛 Report issues: [GitHub Issues](https://github.com/example/mlp_sdk/issues)
- 📧 Contact: visa-sdk@example.com
- 📖 Documentation: [Full Docs](https://visa-sdk.readthedocs.io/)
