# Automate AIOps with Amazon SageMaker Unified Studio projects - Model Deploy

This repository contains the model deployment pipeline for the SMUS framework. It provides automated deployment of approved ML models from SageMaker Model Registry to SageMaker endpoints using event-driven GitHub Actions workflows.

**Note**: Please refer to the model build section and complete the model training process before proceeding with deployment.

## Repository Structure

```
model_deploy/
├── README.md                           # This guide
├── .github/workflows/                  # GitHub Actions CI/CD
│   └── deploy_model_pipeline.yml      # Main deployment workflow
├── config/dev/                        # Configuration management
│   └── endpoint-config.yml            # Endpoint configuration
├── deploy_endpoint/                    # Core deployment logic
│   ├── deploy_endpoint_stack.py       # CDK deployment stack
│   └── get_approved_package.py        # Model package discovery
├── tests/                             # Testing framework
│   ├── integration_tests/             # Integration tests
│   └── unittests/                     # Unit tests
├── app.py                             # CDK application entry point
└── requirements.txt                   # Core dependencies
```
## Architecture Overview

![aiops project architecture](/images/github_action_mlops_architecture.png)

The SMUS framework implements an event-driven architecture that automates the complete AIOps lifecycle through a sequential workflow, seamlessly connecting SageMaker Unified Studio project creation with production-ready infrastructure.

1. The first step is configuring SageMaker Unified Studio environment, setting up domains, project profiles, and establishing the foundational infrastructure required for automated project creation and management.

2. GitHub connections are configured and necessary AWS infrastructure is deployed including EventBridge rules, Step Functions workflows, and Lambda functions that will orchestrate the automated repository setup and deployment processes.

3. Data scientists log into SageMaker Unified Studio and create a new project by selecting from available project templates defined in the project profile and configuring GitHub integration settings.

4. Project creation generates a CreateProject event that is captured by EventBridge, triggering a Step Functions workflow that automatically creates and configures both build and deploy repositories in your GitHub organization, complete with template-specific seed code and GitHub Actions workflows.

5. Code changes are pushed to the build repository or the workflow is manually triggered, causing the GitHub Actions build pipeline to automatically activate, executing environment setup, dependency installation, and pipeline validation.

6. The build workflow orchestrates the execution of the SageMaker pipeline, which processes data through preprocessing, feature engineering, model training, and evaluation with comprehensive monitoring and logging.

7. ML pipeline tracking occurs if tracking server is setup, enabling experiment tracking and model lineage management throughout the training process.

8. Model registration automatically occurs upon successful pipeline completion, registering the trained model in SageMaker Model Registry with detailed metadata, training metrics, and lineage information, initially set to "PendingManualApproval" status.

9. Data scientists or ML engineers review the model performance metrics and manually approve the model in SageMaker Model Registry, changing its status from "PendingManualApproval" to "Approved".

10. The model approval event is automatically detected by EventBridge, which invokes a deployment Lambda function that triggers the GitHub Actions deployment workflow in the deploy repository using the workflow_dispatch mechanism.

11. The deployment workflow retrieves the approved model, applies infrastructure as code definitions using AWS CDK, and provisions or updates a SageMaker endpoint with comprehensive validation, error handling, and rollback capabilities.

12. The deployed endpoint becomes active and ready to serve real-time predictions, completing the automated journey from project creation to production deployment with full traceability and governance.

This repository handles steps 10-12 of the AIOps workflow, focusing on the model deployment and endpoint management phases.

## Configuration Requirements

### Configuration File
All deployment settings are managed in `config/deploy_config.json`:

```json
{
  "aws_region": "us-east-1",              // AWS region for deployment
  "deploy_account": "123456789012",       // AWS account ID
  "model_package_group_name": "bank-model-group",  // Model Registry group
  "DataBucketName": "my-artifacts-bucket",         // S3 bucket for models
  "endpoint_config": {
    "initial_instance_count": 1,          // Number of instances
    "initial_variant_weight": 1.0,        // Traffic weight
    "instance_type": "ml.m5.large",       // Instance type
    "variant_name": "AllTraffic"          // Variant name
  }
}
```

**Required Parameters:**
- `aws_region`: AWS region for deployment
- `deploy_account`: AWS account ID
- `model_package_group_name`: Model Registry group name (must have approved models)
- `DataBucketName`: S3 bucket containing model artifacts
- `endpoint_config`: Endpoint instance configuration

### Required GitHub Secrets
Only one secret is needed for GitHub Actions authentication:

- `OIDC_ROLE_GITHUB_WORKFLOW`: IAM role ARN for GitHub Actions authentication
## Model Deployment Process

There are two methods to deploy models using this repository:

### Method 1: Automatic Deployment (Recommended)

#### Step 1: Approve Model in SageMaker Model Registry
1. **Navigate to SageMaker Unified Studio**
2. **Go to Build → AI OPS → Model Registry**
3. **Find your model package group**: `aiops-{project-id}-models`
4. **Select the model package** to approve
5. **Click "Update model approval status"**
6. **Change status** from "PendingManualApproval" to "Approved"
7. **Add approval comments** (optional)
8. **Click "Update status"**

#### Step 2: Automatic Deployment Trigger
When a model is approved:
1. **SageMaker emits approval event** to EventBridge
2. **EventBridge rule** detects the event
3. **Lambda function** extracts project information and triggers the GitHub Actions deployment workflow automatically
4. **Deployment workflow** executes without any manual intervention

### Method 2: Manual Deployment

#### Step 1: Ensure Model is Approved
- Verify that at least one model in your Model Registry has "Approved" status
- Follow the approval process from Method 1 if needed

#### Step 2: Manual Workflow Trigger
1. **Navigate to repository Actions tab**
2. **Select "Sagemaker Model Deploy Pipeline SMUS project"**
3. **Click "Run workflow"**
4. **Choose log level** (info/warning/debug)
5. **Click "Run workflow" button**


## Local Deployment and Testing

### Prerequisites:
- Python 3.9 or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- Access to SageMaker Model Registry with approved models

### Local Setup:

1. **Clone and setup environment**:
   ```bash
   cd model_deploy
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure deployment**:
   - Update `config/deploy_config.json` with your settings
   - Ensure AWS credentials are configured

3. **Deploy the stack**:
   ```bash
   cdk deploy
   ```

### Endpoint Monitoring:
```bash
# Check endpoint status
aws sagemaker describe-endpoint --endpoint-name <endpoint-name>

# View endpoint metrics in CloudWatch console
# Navigate to: CloudWatch → Metrics → SageMaker → Endpoint Metrics

# List recent deployments
aws sagemaker list-endpoints --sort-by CreationTime --sort-order Descending
```

## Troubleshooting

### Common Issues:

1. **Deployment workflow not triggered**:
   - **Cause**: Model approval event not detected or Lambda function failed
   - **Solution**: Check EventBridge rules and Lambda function logs
   - **Manual workaround**: Trigger workflow manually from GitHub Actions

2. **No approved models found**:
   - **Cause**: No models in "Approved" status in Model Registry
   - **Solution**: Approve a model in SageMaker Model Registry first

3. **Endpoint creation failed**:
   - **Cause**: Insufficient IAM permissions or invalid configuration
   - **Solution**: Check IAM role permissions and endpoint configuration

4. **Endpoint stuck in "Creating" status**:
   - **Cause**: Resource limits or instance type unavailability
   - **Solution**: Check CloudWatch logs and try different instance type

5. **Inference test failed**:
   - **Cause**: Model expects different input format
   - **Solution**: Update test data format in deployment script

### Log Locations:
- **GitHub Actions**: Repository → Actions tab → Workflow run
- **SageMaker Endpoints**: CloudWatch → Log groups → `/aws/sagemaker/Endpoints/<endpoint-name>`
- **Lambda Functions**: CloudWatch → Log groups → `/aws/lambda/<function-name>`
- **EventBridge**: CloudWatch → Log groups → `/aws/events/rule/<rule-name>`

## Clean-up

### Endpoint Cleanup:
```bash
# Delete endpoint
aws sagemaker delete-endpoint --endpoint-name <endpoint-name>

# Delete endpoint configuration
aws sagemaker delete-endpoint-config --endpoint-config-name <config-name>

# Delete model
aws sagemaker delete-model --model-name <model-name>
```
