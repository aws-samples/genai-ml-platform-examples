# Training Examples for mlp_sdk

This guide provides detailed information about the XGBoost training examples.

## Overview

The training examples demonstrate how to use mlp_sdk's training wrapper to train machine learning models on SageMaker with minimal configuration.

## Files

- **xgboost_training_example.ipynb** - Interactive Jupyter notebook (recommended for learning)
- **xgboost_training_script.py** - Python script version (for automation)
- **requirements.txt** - Python dependencies for examples

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r examples/requirements.txt
```

### 2. Configure mlp_sdk

Generate your configuration file:

```bash
python examples/generate_admin_config.py --interactive
```

Move it to the default location:

```bash
mkdir -p /home/sagemaker-user/.config
mv admin-config.yaml /home/sagemaker-user/.config/
```

### 3. AWS Setup

Ensure you have:
- AWS credentials configured
- SageMaker execution role with appropriate permissions
- S3 bucket for storing data and models
- VPC, security groups, and subnets configured (if using VPC)

## Using the Jupyter Notebook

### Start Jupyter

```bash
jupyter notebook examples/xgboost_training_example.ipynb
```

### What You'll Learn

1. **Data Generation**: Create synthetic binary classification data
2. **Data Preparation**: Format data for XGBoost (CSV with target in first column)
3. **Session Initialization**: Initialize mlp_sdk with configuration
4. **S3 Upload**: Upload training and validation data
5. **Training Job**: Start training with automatic defaults
6. **Monitoring**: Track training progress and view metrics
7. **Audit Trail**: Review operation history
8. **Deployment**: Deploy model to endpoint (optional)
9. **Predictions**: Make real-time predictions (optional)

### Key Features Demonstrated

- ✅ Configuration-driven defaults (no need to specify instance types, VPC, etc.)
- ✅ Simplified API (focus on ML, not infrastructure)
- ✅ Automatic audit trail
- ✅ Clear error handling
- ✅ Runtime parameter overrides

## Using the Python Script

### Basic Usage

```bash
python examples/xgboost_training_script.py
```

This will:
1. Generate synthetic data
2. Upload to S3
3. Start training job
4. Return immediately (job runs in background)

### Wait for Completion

```bash
python examples/xgboost_training_script.py --wait
```

This will monitor the training job and wait for completion.

### Custom Configuration

```bash
python examples/xgboost_training_script.py --config /path/to/config.yaml --wait
```

### Script Options

```
--config PATH    Path to admin-config.yaml (default: uses default location)
--wait          Wait for training job to complete (default: False)
--deploy        Deploy model to endpoint after training (default: False)
```

## Example Output

### Successful Training

```
======================================================================
XGBoost Training with mlp_sdk
======================================================================

======================================================================
Step 1: Generating Synthetic Data
======================================================================
✅ Data generated:
   Training samples: 8000
   Validation samples: 2000
   Features: 20
   Class distribution: [5600 2400]

======================================================================
Step 2: Preparing Data Files
======================================================================
✅ Data saved:
   data/train.csv (1234567 bytes)
   data/validation.csv (308642 bytes)

======================================================================
Step 3: Initializing mlp_sdk Session
======================================================================
✅ Session initialized:
   Region: us-west-2
   Default bucket: my-sagemaker-bucket
   Execution role: arn:aws:iam::123456789012:role/SageMakerRole

📋 Configuration:
   Training instance: ml.m5.xlarge
   Instance count: 1
   VPC: vpc-12345678

======================================================================
Step 4: Uploading Data to S3
======================================================================
📤 Uploading to: s3://my-sagemaker-bucket/xgboost-example/20260114-123456
   ✅ s3://my-sagemaker-bucket/xgboost-example/20260114-123456/train/train.csv
   ✅ s3://my-sagemaker-bucket/xgboost-example/20260114-123456/validation/validation.csv

======================================================================
Step 5: Starting Training Job
======================================================================
🚀 Job name: xgboost-training-20260114-123456
   Container: 683313688378.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1
   Hyperparameters: 10 parameters

✅ Training job started!
   Status: InProgress

💡 Monitor in SageMaker console or use --wait flag

======================================================================
Audit Trail
======================================================================

📊 Training job operations: 1

   2026-01-14 12:34:56: run_training_job
      Status: success
      Job: xgboost-training-20260114-123456

======================================================================
✅ Example completed successfully!
======================================================================

📋 Training job: xgboost-training-20260114-123456
   Monitor: SageMaker Console > Training jobs > xgboost-training-20260114-123456

💡 Next steps:
   - Monitor training in SageMaker console
   - View logs in CloudWatch
   - Deploy model to endpoint
   - See examples/xgboost_training_example.ipynb for more details
```

## Understanding the Training Configuration

### What mlp_sdk Handles Automatically

When you call `session.run_training_job()`, mlp_sdk automatically applies:

1. **Compute Configuration**
   - Instance type (from config: `compute.training_instance_type`)
   - Instance count (from config: `compute.training_instance_count`)

2. **Networking Configuration**
   - VPC ID (from config: `networking.vpc_id`)
   - Security groups (from config: `networking.security_group_ids`)
   - Subnets (from config: `networking.subnets`)

3. **IAM Configuration**
   - Execution role (from config: `iam.execution_role`)

4. **Encryption Configuration**
   - KMS key (from config: `kms.key_id`)

5. **S3 Configuration**
   - Output path (from config: `s3.default_bucket` + `s3.model_prefix`)

### What You Still Specify

You only need to specify ML-specific parameters:

- Training container image
- Hyperparameters
- Input data locations
- Algorithm-specific settings

### Overriding Defaults

You can override any default at runtime:

```python
session.run_training_job(
    job_name="my-job",
    instance_type="ml.p3.2xlarge",  # Override config default
    instance_count=2,                # Override config default
    # ... other parameters use config defaults
)
```

## Customizing the Examples

### Use Your Own Data

Replace the synthetic data generation with your own data:

```python
# Instead of:
# X, y = make_classification(...)

# Use your data:
df = pd.read_csv('your_data.csv')
X = df.drop('target', axis=1).values
y = df['target'].values
```

### Different Algorithms

Change the container image for different algorithms:

```python
# PyTorch
container = f"763104351884.dkr.ecr.{region}.amazonaws.com/pytorch-training:2.0.0-cpu-py310"

# TensorFlow
container = f"763104351884.dkr.ecr.{region}.amazonaws.com/tensorflow-training:2.12.0-cpu-py310"

# Scikit-learn
container = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:1.0-1-cpu-py3"
```

### Custom Hyperparameters

Modify hyperparameters for your use case:

```python
hyperparameters = {
    'objective': 'reg:squarederror',  # Regression instead of classification
    'num_round': '200',                # More training rounds
    'max_depth': '10',                 # Deeper trees
    # ... add more parameters
}
```

## Troubleshooting

### Configuration Not Found

```
ConfigurationError: Configuration file not found
```

**Solution**: Generate config with `python examples/generate_admin_config.py --interactive`

### Invalid AWS Resources

```
AWSServiceError: VPC vpc-12345678 not found
```

**Solution**: Update config file with your actual AWS resource IDs

### Permission Denied

```
AWSServiceError: User is not authorized to perform: sagemaker:CreateTrainingJob
```

**Solution**: Ensure your IAM role has SageMaker permissions

### Training Job Failed

Check CloudWatch logs:

```bash
aws logs tail /aws/sagemaker/TrainingJobs --follow --log-stream-name-prefix xgboost-training-
```

## Next Steps

1. **Try Different Models**: Experiment with PyTorch, TensorFlow, or scikit-learn
2. **Use Real Data**: Replace synthetic data with your own datasets
3. **Create Pipelines**: Combine processing and training into pipelines
4. **Deploy Models**: Deploy trained models to endpoints
5. **Monitor Performance**: Track model metrics and performance

## Resources

- [mlp_sdk Documentation](../README.md)
- [Configuration Guide](../docs/CONFIGURATION_GUIDE.md)
- [Usage Examples](../docs/USAGE_EXAMPLES.md)
- [SageMaker XGBoost Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [SageMaker Training Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/train-model.html)

## Support

For issues or questions:
- 🐛 [GitHub Issues](https://github.com/example/mlp_sdk/issues)
- 📧 Email: visa-sdk@example.com
- 📖 [Full Documentation](https://visa-sdk.readthedocs.io/)
