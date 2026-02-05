# Automate AIOps with Amazon SageMaker Unified Studio projects - Model Build

This repository contains the model training pipeline for the SMUS framework. It provides automated ML model training, evaluation, and registration using SageMaker Pipelines orchestrated through GitHub Actions.

## Repository Structure
```
model_build/
├── README.md                           # This guide
├── .github/workflows/                  # GitHub Actions CI/CD
│   └── build_sagemaker_pipeline.yml    # Main build workflow
├── ml_pipelines/                       # SageMaker Pipeline definitions
│   ├── run_pipeline.py                 # Pipeline execution script
│   ├── training/pipeline.py            # Main pipeline definition
│   └── requirements.txt                # Pipeline dependencies
└── source_scripts/                     # Processing scripts
   ├── preprocessing/                   # Data preprocessing
   ├── training/xgboost/                # XGBoost training
   ├── evaluate/                        # Model evaluation
   └── helpers/                         # Utility functions
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

This repository handles steps 5-8 of the AIOps workflow, focusing on the model training and registration phases.

## Configuration Requirements

### Required GitHub Secrets
Configure in repository Settings → Secrets and variables → Actions:

- `OIDC_ROLE_GITHUB_WORKFLOW`: IAM role ARN for GitHub Actions authentication
- `SAGEMAKER_PIPELINE_ROLE_ARN`: IAM role for SageMaker pipeline execution
- `SAGEMAKER_PROJECT_NAME`: SageMaker project name
- `SAGEMAKER_PROJECT_ID`: Unique SageMaker project identifier
- `REGION`: AWS region for resource deployment
- `ARTIFACT_BUCKET`: S3 bucket for storing pipeline artifacts
- `MODEL_PACKAGE_GROUP_NAME`: Model Registry package group name
- `GLUE_DATABASE`: Glue database name containing your dataset
- `GLUE_TABLE`: Glue table name with your training data

### Required GitHub Variables
- `TRIGGER_PIPELINE_EXECUTION`: Set to `"true"` to enable pipeline execution (default: `"false"`)

## Setup and Configuration

1. **Configure Glue Data Source**: Create Glue table in SageMaker Unified Studio and update GitHub secrets with actual database and table names.

2. **Enable Pipeline Execution**: Set `TRIGGER_PIPELINE_EXECUTION` variable to `"true"` in repository settings.

3. **Verify Configuration**: Ensure all required secrets and variables are properly configured.

## Pipeline Execution

### Manual Execution
1. Navigate to repository Actions tab
2. Select "Sagemaker Pipeline build SMUS project"
3. Click "Run workflow"

### Automatic Execution
- Triggers on code changes to `ml_pipelines/` or `source_scripts/` directories
- Requires `TRIGGER_PIPELINE_EXECUTION=true` to proceed

## Run Pipeline Locally

### Prerequisites
- Python 3.10 or Miniconda
- AWS CLI configured with appropriate credentials

### Setup Local Environment
```bash
# Clone and setup
cd model_build
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Pipeline Locally
```bash
python ./ml_pipelines/run_pipeline.py \
  --module-name training.pipeline \
  --role-arn <SAGEMAKER_PIPELINE_ROLE_ARN> \
  --tags '[{"Key":"sagemaker:project-name", "Value":"<PROJECT_NAME>"}, {"Key":"sagemaker:project-id", "Value":"<PROJECT_ID>"}]' \
  --kwargs '{"region":"<REGION>","role":"<ROLE_ARN>","default_bucket":"<BUCKET>","pipeline_name":"local-test-pipeline","model_package_group_name":"<MODEL_GROUP>","glue_database_name":"<GLUE_DB>","glue_table_name":"<GLUE_TABLE>"}'
```

## Troubleshooting

### Common Issues:

1. **Pipeline execution is disabled**:
   - **Cause**: `TRIGGER_PIPELINE_EXECUTION` variable is not set to `"true"`
   - **Solution**: Set the variable to `"true"` in repository settings

2. **Glue database/table not found**:
   - **Cause**: `GLUE_DATABASE` or `GLUE_TABLE` secrets have incorrect values
   - **Solution**: Update secrets with actual database and table names from SageMaker Unified Studio

3. **Pipeline monitoring fails**:
   - **Cause**: Missing `sagemaker:ListPipelineExecutions` permission
   - **Solution**: Ensure IAM role has required SageMaker permissions

4. **GitHub Actions cannot assume role**:
   - **Cause**: OIDC trust relationship not configured correctly
   - **Solution**: Verify trust relationship includes correct GitHub organization

5. **Workflow shows "skipped"**:
   - **Cause**: `TRIGGER_PIPELINE_EXECUTION` is set to `"false"`
   - **Solution**: This is expected behavior when pipeline execution is disabled

### Log Locations:
- **GitHub Actions**: Repository → Actions tab → Workflow run
- **SageMaker Pipeline**: AWS Console → SageMaker → Pipelines
- **CloudWatch Logs**: `/aws/sagemaker/ProcessingJobs` and `/aws/sagemaker/TrainingJobs`

### Debug Commands:
```bash
# Check pipeline executions
aws sagemaker list-pipeline-executions --pipeline-name "githubactions-<project-id>"

# Check failed steps
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn "<execution-arn>" --query 'PipelineExecutionSteps[?StepStatus==`Failed`]'
```


## Troubleshooting

### Common Issues:

1. **Pipeline execution is disabled**:
   - **Cause**: `TRIGGER_PIPELINE_EXECUTION` variable is not set to `"true"`
   - **Solution**: Set the variable to `"true"` in repository settings

2. **Glue database/table not found**:
   - **Cause**: `GLUE_DATABASE` or `GLUE_TABLE` secrets have incorrect values
   - **Solution**: Update secrets with actual database and table names from SageMaker Unified Studio

3. **Pipeline monitoring fails**:
   - **Cause**: Missing `sagemaker:ListPipelineExecutions` permission
   - **Solution**: Ensure IAM role has required SageMaker permissions

4. **GitHub Actions cannot assume role**:
   - **Cause**: OIDC trust relationship not configured correctly
   - **Solution**: Verify trust relationship includes correct GitHub organization

5. **Workflow shows "skipped"**:
   - **Cause**: `TRIGGER_PIPELINE_EXECUTION` is set to `"false"`
   - **Solution**: This is expected behavior when pipeline execution is disabled

### Log Locations:
- **GitHub Actions**: Repository → Actions tab → Workflow run
- **SageMaker Pipeline**: AWS Console → SageMaker → Pipelines
- **CloudWatch Logs**: `/aws/sagemaker/ProcessingJobs` and `/aws/sagemaker/TrainingJobs`

### Debug Commands:
```bash
# Check pipeline executions
aws sagemaker list-pipeline-executions --pipeline-name "githubactions-<project-id>"

# Check failed steps
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn "<execution-arn>" --query 'PipelineExecutionSteps[?StepStatus==`Failed`]'
```

## Clean-up

To clean up resources:
1. Delete the SageMaker pipeline from the AWS Console
2. Remove model packages from SageMaker Model Registry
3. Clean up S3 artifacts if no longer needed
4. Delete GitHub repository if no longer needed



