# SageMigrator

**Intelligent EC2 to SageMaker Migration System**

SageMigrator is a comprehensive CLI tool that automates the migration of machine learning training code from EC2 instances to Amazon SageMaker. It analyzes your existing code, generates SageMaker-compatible artifacts, and provides a complete MLOps pipeline with training, evaluation, and conditional model registration.

## 🚀 Features

- **Automated Code Analysis**: Analyzes existing ML training code for SageMaker compatibility
- **Complete Migration**: Generates SageMaker training scripts, pipelines, and infrastructure
- **MLOps Pipeline**: Creates end-to-end pipelines with preprocessing, training, evaluation, and conditional model registration
- **Infrastructure as Code**: Generates CloudFormation templates for AWS resources
- **Validation Suite**: Comprehensive testing and validation of generated artifacts
- **Multiple Processor Support**: Supports both PyTorch and SKLearn processors for evaluation
- **Cost Optimization**: Uses spot instances and compute-optimized instance types
- **CloudFormation Integration**: Automatically retrieves execution roles and S3 buckets from deployed stacks

## 📋 Prerequisites

- **Python 3.8+**
- **AWS CLI configured** with appropriate permissions
- **AWS Account** with SageMaker access
- **Virtual Environment** (recommended)

### Required AWS Permissions

Your AWS credentials need the following permissions:
- SageMaker full access
- S3 bucket creation and management
- IAM role creation and management
- CloudFormation stack operations
- CloudWatch logs access

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd genai-ml-platform-examples/migration
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install SageMigrator in Development Mode

```bash
pip install -e .
```

### 5. Verify Installation

```bash
python -m sagemigrator --help
```

You should see the SageMigrator CLI help menu with available commands.

### 6. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

## 📖 Usage Guide

SageMigrator follows a three-step workflow: **Migrate** → **Deploy** → **Execute**

### Step 1: Migrate Your Code

The `migrate` command analyzes your existing ML training code and generates SageMaker-compatible artifacts.

#### Basic Migration

```bash
python -m sagemigrator migrate <source-directory> -o <output-directory>
```

#### Example

```bash
python -m sagemigrator migrate ./my-ml-project -o ./sagemaker-artifacts
```

#### Advanced Migration Options

```bash
python -m sagemigrator migrate ./my-ml-project \
  -o ./sagemaker-artifacts \
  --processor-type sklearn \
  --interactive \
  --skip-validation
```

#### Migration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `source-directory` | Path to your existing ML training code | Required |
| `-o, --output` | Output directory for generated artifacts | Required |
| `--processor-type` | Processor for evaluation step (`pytorch` or `sklearn`) | `sklearn` |
| `--interactive` | Interactive mode with confirmations | `False` |
| `--dry-run` | Preview what would be generated without creating files | `False` |
| `--skip-validation` | Skip validation of generated artifacts | `False` |

#### What Gets Generated

The migration creates the following structure:

```
sagemaker-artifacts/
├── training/
│   ├── train.py              # SageMaker training script
│   ├── pipeline.py           # Complete MLOps pipeline
│   ├── preprocessing.py      # Data preprocessing script
│   ├── evaluation.py         # Model evaluation script
│   └── deploy_pipeline.py    # Pipeline deployment script
├── infrastructure/
│   └── cloudformation/
│       └── main.yaml         # CloudFormation template
├── tests/                    # Generated test suites
└── documentation/            # Migration documentation
```

### Step 2: Deploy Infrastructure

The `deploy` command creates the necessary AWS infrastructure using CloudFormation.

#### Basic Deployment

```bash
python -m sagemigrator deploy <artifacts-directory>
```

#### Example

```bash
python -m sagemigrator deploy ./sagemaker-artifacts
```

#### Advanced Deployment Options

```bash
python -m sagemigrator deploy ./sagemaker-artifacts \
  --region us-west-2 \
  --interactive \
  --stack-name my-custom-stack
```

#### Deployment Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `artifacts-directory` | Path to migration artifacts | Required |
| `--region` | AWS region for deployment | `us-east-1` |
| `--interactive` | Interactive deployment with confirmations | `False` |
| `--dry-run` | Show deployment plan without creating resources | `False` |
| `--stack-name` | Custom CloudFormation stack name | Auto-generated |

#### What Gets Deployed

The deployment creates:

- **IAM Execution Role** for SageMaker with appropriate permissions
- **S3 Bucket** for storing training data, models, and artifacts
- **KMS Key** for encryption (optional)
- **CloudWatch Log Groups** for monitoring
- **SageMaker Model Package Group** for model registry

#### Deployment Output

After successful deployment, you'll see:

```
✅ Deployment Completed Successfully!

🏗️  Stack Name: sagemigrator-project-dev
🌍 Region: us-east-1
📊 Resources Created: 5
🔑 ExecutionRoleArn: arn:aws:iam::123456789012:role/sagemigrator-project-SageMaker-ExecutionRole-dev
🪣 S3BucketName: sagemigrator-project-sagemaker-bucket-123456789012-us-east-1

Next steps:
1. Execute SageMaker pipeline: sagemigrator execute ./sagemaker-artifacts/training/pipeline.py
2. Test your SageMaker pipeline
3. Monitor CloudWatch logs
4. Check AWS console for resources
```

### Step 3: Execute Your Pipeline

The `execute` command runs your SageMaker training pipeline.

#### Basic Execution

```bash
python -m sagemigrator execute <pipeline-file>
```

#### Example

```bash
python -m sagemigrator execute ./sagemaker-artifacts/training/pipeline.py
```

#### Advanced Execution Options

```bash
python -m sagemigrator execute ./sagemaker-artifacts/training/pipeline.py \
  --working-dir ./sagemaker-artifacts/training \
  --env-vars AWS_REGION=us-west-2 \
  --env-vars CUSTOM_PARAM=value \
  --timeout 7200 \
  --capture-output
```

#### Execution Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `pipeline-file` | Path to the pipeline.py file | Required |
| `-w, --working-dir` | Working directory for execution | Pipeline file directory |
| `-e, --env-vars` | Environment variables (format: KEY=VALUE) | None |
| `-t, --timeout` | Timeout in seconds | 3600 (1 hour) |
| `--capture-output` | Display real-time pipeline output | `False` |

#### Execution Output

During execution, you'll see:

```
🚀 Executing SageMaker pipeline: pipeline.py
📂 Working directory: ./sagemaker-artifacts/training
✓ Detected SageMaker components: sagemaker, Pipeline, TrainingStep, ProcessingStep
⏱️  Timeout: 3600 seconds

Starting pipeline execution...
✅ Using execution role from CloudFormation stack: arn:aws:iam::123456789012:role/...
✅ Using S3 bucket from CloudFormation stack: sagemigrator-project-sagemaker-bucket-...
✅ Pipeline 'sagemigrator-pipeline' deployed successfully!
✅ Pipeline execution started: arn:aws:sagemaker:us-east-1:123456789012:pipeline/...

🚀 Pipeline deployed and executed!
📊 Monitor execution: https://console.aws.amazon.com/sagemaker/home#/pipelines
```

## 🔧 Advanced Usage

### Analyzing Code Before Migration

```bash
python -m sagemigrator analyze <source-directory> --output ./analysis-report
```

### Validating Generated Artifacts

```bash
python -m sagemigrator validate <artifacts-directory> --detailed
```

### Generating Standalone Pipelines

```bash
python -m sagemigrator generate-standalone-pipeline ./my-pipeline \
  --source-dir ./my-ml-code \
  --processor-type sklearn \
  --accuracy-threshold 0.85
```

### Interactive Help

```bash
python -m sagemigrator help-guide --topic migration
python -m sagemigrator help-guide --topic deployment
python -m sagemigrator help-guide --topic troubleshooting
```

## 📊 Pipeline Architecture

SageMigrator generates a complete MLOps pipeline with the following steps:

1. **Data Preprocessing** - Prepares training and test datasets
2. **Model Training** - Trains your ML model using PyTorch
3. **Model Evaluation** - Evaluates model performance and generates metrics
4. **Conditional Registration** - Automatically registers models that meet accuracy thresholds

### Pipeline Features

- **Spot Instance Support** - Reduces training costs by up to 70%
- **Automatic Scaling** - Handles compute resources automatically
- **Model Registry Integration** - Tracks model versions and performance
- **Conditional Approval** - Only registers models meeting quality thresholds
- **Comprehensive Metrics** - Generates detailed evaluation reports

## 🛡️ Security & Best Practices

### IAM Permissions

SageMigrator follows the principle of least privilege:

- Execution roles have minimal required permissions
- S3 buckets use server-side encryption
- KMS keys for additional encryption (optional)
- VPC support for network isolation (optional)

### Cost Optimization

- Uses **compute-optimized instances** (ml.c5.xlarge) by default
- Enables **spot instances** for training jobs
- Implements **automatic cleanup** of temporary resources
- Provides **cost monitoring** and alerts

### Monitoring

- **CloudWatch integration** for logs and metrics
- **Real-time pipeline monitoring** through SageMaker console
- **Automated alerting** for pipeline failures
- **Performance tracking** across model versions

## 🐛 Troubleshooting

### Common Issues

#### 1. Permission Denied Errors

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify SageMaker permissions
aws sagemaker list-training-jobs --max-items 1
```

#### 2. Pipeline Execution Failures

```bash
# Check CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix /aws/sagemaker

# Validate pipeline syntax
python -c "from sagemaker.workflow.pipeline import Pipeline; print('✅ SageMaker SDK working')"
```

#### 3. Resource Not Found

```bash
# Verify CloudFormation stack exists
aws cloudformation describe-stacks --stack-name sagemigrator-project-dev

# Check S3 bucket access
aws s3 ls s3://your-bucket-name
```

#### 4. Dependency Issues

```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Check SageMaker SDK version
pip show sagemaker
```

### Getting Help

1. **Check logs** - Enable verbose logging with `-v` flag
2. **Use help guides** - `python -m sagemigrator help-guide --topic troubleshooting`
3. **Validate environment** - Run dependency checks before migration
4. **Check AWS console** - Monitor resources in SageMaker and CloudFormation consoles

## 📝 Configuration

### Environment Variables

```bash
export SAGEBRIDGE_LOG_LEVEL=DEBUG
export SAGEBRIDGE_DEFAULT_REGION=us-west-2
export SAGEBRIDGE_ENABLE_ENCRYPTION=true
export SAGEBRIDGE_PROPERTY_TEST_ITERATIONS=100
```

### Configuration File

Create a `config.yaml` file:

```yaml
analysis:
  max_file_size_mb: 10
  supported_extensions: ['.py', '.ipynb']
  
compatibility:
  sagemaker_sdk_version: "2.x"
  pytorch_version: "2.0"
  
infrastructure:
  default_region: "us-east-1"
  default_instance_type: "ml.c5.xlarge"
  enable_encryption: true
  
validation:
  enable_security_checks: true
  max_test_timeout_minutes: 30
```

Use with: `python -m sagemigrator migrate <source> -o <output> --config config.yaml`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the help guides: `python -m sagemigrator help-guide`
3. Check existing issues in the repository
4. Create a new issue with detailed information about your problem

---

**Happy Migrating! 🚀**