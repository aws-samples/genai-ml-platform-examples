# SDK v3 Parameter Guide for mlp_sdk

## Overview
This guide shows the correct parameter format for using mlp_sdk with SageMaker SDK v3. The wrapper uses ModelTrainer-style parameters, not boto3 API parameters.

## Training Job Parameters

### ✅ Correct Format (SDK v3 ModelTrainer)

```python
from mlp_sdk import MLP_Session

session = MLP_Session()

trainer = session.run_training_job(
    job_name='my-training-job',
    training_image='683313688378.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1',
    inputs={
        'train': 's3://my-bucket/data/train/',
        'validation': 's3://my-bucket/data/validation/'
    },
    hyperparameters={
        'objective': 'binary:logistic',
        'num_round': '100',
        'max_depth': '5'
    },
    output_path='s3://my-bucket/output/',
    max_run_in_seconds=3600
)
```

### ❌ Wrong Format (boto3 API)

```python
# DON'T DO THIS - This is boto3 API format, not SDK v3 format
trainer = session.run_training_job(
    job_name='my-training-job',
    algorithm_specification={
        "TrainingImage": xgboost_container,
        "TrainingInputMode": "File"
    },
    input_data_config=[
        {
            "ChannelName": "train",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": train_s3_path
                }
            }
        }
    ],
    output_data_config={
        "S3OutputPath": output_s3_path
    },
    stopping_condition={
        "MaxRuntimeInSeconds": 3600
    }
)
```

## Parameter Mapping

| boto3 API Parameter | SDK v3 ModelTrainer Parameter | Type | Notes |
|---------------------|-------------------------------|------|-------|
| `algorithm_specification.TrainingImage` | `training_image` | string | Direct parameter |
| `input_data_config` | `inputs` | dict of {channel: s3_uri} | Simplified format |
| `output_data_config.S3OutputPath` | `output_path` | string | Direct parameter |
| `stopping_condition.MaxRuntimeInSeconds` | `max_run_in_seconds` | int | Wrapper converts to StoppingCondition object |
| `hyperparameters` | `hyperparameters` | dict (same) | No change |
| `role_arn` | `role_arn` | string (same) | No change |

## Input Data Format

### Simple Format (Recommended)
```python
inputs = {
    'train': 's3://bucket/train/',
    'validation': 's3://bucket/val/',
    'test': 's3://bucket/test/'
}
```

The wrapper automatically converts this to `InputData` objects internally with `content_type='text/csv'` for CSV data.

**Important**: S3 paths must point to directories (ending with `/`), not individual files.

### Advanced Format (Optional)
```python
from sagemaker.train.model_trainer import InputData

inputs = [
    InputData(
        channel_name='train',
        data_source='s3://bucket/train/',
        content_type='text/csv'  # Specify content type explicitly
    ),
    InputData(
        channel_name='validation',
        data_source='s3://bucket/val/',
        content_type='text/csv'
    )
]
```

**Note**: When using the simple dict format, the wrapper automatically sets `content_type='text/csv'`. For other data formats (libsvm, parquet, etc.), use the advanced format to specify the content type explicitly.

## Complete Example

```python
#!/usr/bin/env python3
from mlp_sdk import MLP_Session

# Initialize session
session = MLP_Session(config_path='path/to/admin-config.yaml')

# XGBoost training example
trainer = session.run_training_job(
    # Required parameters
    job_name='xgboost-example',
    training_image='683313688378.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1',
    
    # Input data (simple dict format)
    inputs={
        'train': 's3://my-bucket/data/train/',
        'validation': 's3://my-bucket/data/validation/'
    },
    
    # Hyperparameters
    hyperparameters={
        'objective': 'binary:logistic',
        'num_round': '100',
        'max_depth': '5',
        'eta': '0.2',
        'eval_metric': 'auc'
    },
    
    # Output configuration
    output_path='s3://my-bucket/models/',
    
    # Optional: Override defaults from config
    instance_type='ml.m5.xlarge',
    instance_count=1,
    max_run_in_seconds=3600,
    
    # Optional: Add tags
    tags=[
        {'Key': 'Project', 'Value': 'MyProject'},
        {'Key': 'Environment', 'Value': 'Development'}
    ]
)

print(f"Training job started: {trainer}")
```

## Custom Training Script Example

```python
trainer = session.run_training_job(
    job_name='custom-training',
    training_image='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310',
    
    # Source code configuration
    source_code_dir='./training-scripts',
    entry_script='train.py',
    requirements='requirements.txt',
    
    # Input data
    inputs={
        'train': 's3://my-bucket/data/train/',
        'validation': 's3://my-bucket/data/validation/'
    },
    
    # Hyperparameters passed to your script
    hyperparameters={
        'epochs': '10',
        'batch-size': '32',
        'learning-rate': '0.001'
    },
    
    # Environment variables
    environment={
        'MY_CUSTOM_VAR': 'value'
    },
    
    output_path='s3://my-bucket/models/'
)
```

## Configuration Defaults

The wrapper automatically applies defaults from your `admin-config.yaml`:

```yaml
defaults:
  compute:
    training_instance_type: ml.m5.xlarge
    training_instance_count: 1
  
  networking:
    vpc_id: vpc-12345678
    security_group_ids:
      - sg-12345678
    subnets:
      - subnet-12345678
      - subnet-87654321
  
  iam:
    execution_role: arn:aws:iam::123456789012:role/SageMakerRole
  
  s3:
    default_bucket: my-sagemaker-bucket
    model_prefix: models/
  
  kms:
    key_id: 3521c71b-77ba-4c91-8e53-c85300f451c0
```

These defaults are automatically applied unless you override them with runtime parameters.

## Parameter Precedence

1. **Runtime parameters** (highest priority)
2. **Configuration file** (admin-config.yaml)
3. **SageMaker SDK defaults** (lowest priority)

Example:
```python
# Config file has: training_instance_type: ml.m5.xlarge
# Runtime override:
trainer = session.run_training_job(
    job_name='my-job',
    training_image='my-image',
    instance_type='ml.m5.2xlarge',  # This overrides config
    inputs={'train': 's3://bucket/data/'}
)
```

## Common Errors

### Error: KeyError: 'SM_CHANNEL_TRAIN'
**Cause**: Using boto3 API format instead of SDK v3 format  
**Solution**: Use `inputs` dict instead of `input_data_config` list

### Error: AlgorithmError - validate_data_file_path
**Cause**: S3 paths pointing to individual files instead of directories  
**Solution**: XGBoost expects directory paths, not file paths

**Wrong**:
```python
inputs = {
    'train': 's3://bucket/data/train/train.csv',  # ❌ Points to file
    'validation': 's3://bucket/data/val/val.csv'  # ❌ Points to file
}
```

**Correct**:
```python
inputs = {
    'train': 's3://bucket/data/train/',  # ✅ Points to directory
    'validation': 's3://bucket/data/val/'  # ✅ Points to directory
}
```

**Note**: The XGBoost container expects data in directories. Upload your CSV files to S3 directories and provide the directory path (ending with `/`), not the file path.

### Error: ValidationException: Requested resource not found
**Cause**: Using the base job name instead of the actual training job name created by ModelTrainer  
**Solution**: Retrieve the actual job name from the ModelTrainer object after starting the training job

**Wrong**:
```python
job_name = 'my-training-job'
training_job = session.run_training_job(job_name=job_name, ...)

# Later, in monitoring:
response = sagemaker_client.describe_training_job(TrainingJobName=job_name)  # ❌ May fail
```

**Correct**:
```python
job_name = 'my-training-job'
training_job = session.run_training_job(job_name=job_name, ...)

# Get the actual job name from ModelTrainer
actual_job_name = training_job.training_job_name  # ✅ Use this for monitoring
job_name = actual_job_name  # Update variable

# Later, in monitoring:
response = sagemaker_client.describe_training_job(TrainingJobName=job_name)  # ✅ Works
```

**Note**: ModelTrainer uses `base_job_name` and may append a unique suffix to ensure uniqueness. Always retrieve the actual job name from the returned ModelTrainer object using the `training_job_name` property.

### Error: ValidationError: max_run_in_seconds Extra inputs are not permitted
**Cause**: Trying to pass `max_run_in_seconds` directly to ModelTrainer  
**Solution**: The wrapper automatically converts `max_run_in_seconds` to a `StoppingCondition` object. Just pass it as a parameter to `run_training_job()`.

**Note**: In SDK v3, ModelTrainer expects a `StoppingCondition` object with `max_runtime_in_seconds` (not `max_run_in_seconds`). The mlp_sdk wrapper handles this conversion automatically, so you can use the simpler `max_run_in_seconds` parameter.

### Error: ValidationError: Extra inputs are not permitted
**Cause**: Using incorrect parameter names  
**Solution**: Check this guide for correct parameter names

### Error: training_image is required
**Cause**: Missing required `training_image` parameter  
**Solution**: Always provide `training_image` parameter

## See Also

- [Configuration Guide](CONFIGURATION_GUIDE.md)
- [Usage Examples](USAGE_EXAMPLES.md)
- [Training Examples](../examples/TRAINING_EXAMPLES.md)
- [SDK v3 Fixes Summary](../SDK_V3_FIXES_SUMMARY.md)
