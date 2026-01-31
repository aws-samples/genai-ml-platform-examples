# SageMaker LLaMA Fine-tuning Pipeline

This repository contains a SageMaker pipeline for fine-tuning LLaMA models using the Dolly dataset.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
# or set environment variables:
# export AWS_ACCESS_KEY_ID=your_key
# export AWS_SECRET_ACCESS_KEY=your_secret
# export AWS_DEFAULT_REGION=us-east-1
```

### 3. Setup Configuration

Run the setup script to create your configuration:

```bash
python setup.py
```

Or use one of the provided environment-specific configs:
- `configs/config.json` - Default configuration template
- `configs/dev-config.json` - Development environment
- `configs/prod-config.json` - Production environment

### 4. Run the Pipeline

#### Test the pipeline (dry run):
```bash
python scripts/run_pipeline.py --dry-run --config configs/dev-config.json
```

#### Execute the pipeline:
```bash
python scripts/run_pipeline.py --config configs/prod-config.json
```

#### Use a custom config file:
```bash
python scripts/run_pipeline.py --config configs/my-config.json
```

#### Override the SageMaker role:
```bash
python scripts/run_pipeline.py --config configs/dev-config.json --role-arn arn:aws:iam::123456789012:role/MySageMakerRole
```

## Project Structure

```
model-build-repo/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── buildspec.yml                      # CodeBuild configuration
├── setup.py                          # Interactive setup script
├── configs/                           # Configuration files
│   ├── config.json                   # Default template
│   ├── dev-config.json              # Development environment
│   └── prod-config.json             # Production environment
├── scripts/                          # Utility scripts
│   ├── run_pipeline.py              # Main pipeline runner
│   └── test_setup.py                # Setup validation
├── src/                              # Source code
│   └── pipelines/
│       └── llama_finetuning/
│           ├── config.py             # Configuration class
│           ├── pipeline.py           # Pipeline definition
│           └── steps/                # Individual pipeline steps
│               ├── preprocess.py
│               ├── train.py
│               ├── evaluate.py
│               └── register.py
└── tests/                            # Unit tests
    └── test_config.py               # Configuration tests
```

## Configuration

The pipeline uses a JSON configuration file with the following parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `AWS_REGION` | AWS region for resources | `us-east-1` |
| `SAGEMAKER_ROLE` | SageMaker execution role ARN | Required |
| `S3_BUCKET` | S3 bucket for pipeline artifacts | Required |
| `S3_PREFIX` | S3 prefix for organizing files | `llama-finetuning` |
| `MODEL_ID` | JumpStart model ID | `meta-textgeneration-llama-2-7b-f` |
| `INSTANCE_TYPE` | Training instance type | `ml.g5.2xlarge` |
| `PIPELINE_NAME` | Name of the SageMaker pipeline | `llama-finetuning-pipeline` |
| `MODEL_PACKAGE_GROUP_NAME` | Model registry group name | `llama-finetuned-models` |
| `MLFLOW_TRACKING_ARN` | MLflow tracking server ARN |
| `PROCESSING_INSTANCE_TYPE` | Processing instance type | `ml.m5.xlarge` |
| `EPOCHS` | Number of training epochs | `2` |
| `MAX_INPUT_LENGTH` | Maximum input sequence length | `1024` |

## Pipeline Steps

1. **Preprocessing**: Downloads and preprocesses the Dolly dataset
2. **Training**: Fine-tunes the LLaMA model using SageMaker JumpStart
3. **Registration**: Registers the model in SageMaker Model Registry

## Monitoring

After starting the pipeline, you can monitor its progress in the SageMaker console. The runner script will provide a direct link to the execution.

## CodeBuild Integration

This setup is designed to work with AWS CodeBuild. The `buildspec.yml` file can be configured to:

1. Install dependencies from `requirements.txt`
2. Use the configuration from environment variables or parameter store
3. Run the pipeline using `run_pipeline.py`

Example buildspec.yml integration:

```yaml
version: 0.2
phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install -r requirements.txt
  build:
    commands:
      - python run_pipeline.py --config $CONFIG_FILE
```

## Troubleshooting

### Common Issues

1. **Role permissions**: Ensure your SageMaker role has the necessary permissions for S3, SageMaker, and other AWS services.

2. **Instance availability**: GPU instances like `ml.g5.2xlarge` may not be available in all regions or may require quota increases.

3. **S3 permissions**: Verify that your role can read/write to the specified S3 bucket.

### Validation

Use the dry-run mode to validate your configuration without incurring costs:

```bash
python scripts/run_pipeline.py --dry-run --config configs/dev-config.json
```

Run the setup validation script:

```bash
python scripts/test_setup.py
```

Run unit tests:

```bash
python -m pytest tests/ -v
```