"""Deployment scripts generator for SageMaker infrastructure automation."""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from ..models.analysis import AnalysisReport
from ..models.deployment import DeploymentScripts

logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    """Configuration for deployment script generation."""
    project_name: str
    region: str
    account_id: str
    environment: str = "dev"
    stack_name: Optional[str] = None
    profile: Optional[str] = None


class DeploymentScriptsGenerator:
    """Generates deployment automation scripts with proper role assumption and region handling."""
    
    def __init__(self, config):
        # Extract relevant config from main Config object
        if hasattr(config, 'infrastructure'):
            self.project_name = config.project_name
            self.region = config.infrastructure.default_region
            self.account_id = getattr(config, 'account_id', '123456789012')
            self.environment = getattr(config, 'environment', 'dev')
            self.stack_name = f"{self.project_name}-{self.environment}"
        else:
            # Fallback for direct DeploymentConfig
            self.config = config
            self.project_name = getattr(config, 'project_name', 'sagemigrator-project')
            self.region = getattr(config, 'region', 'us-east-1')
            self.account_id = getattr(config, 'account_id', '123456789012')
            self.environment = getattr(config, 'environment', 'dev')
            self.stack_name = getattr(config, 'stack_name', f"{self.project_name}-{self.environment}")
        
    def generate_deployment_scripts(self, analysis: AnalysisReport) -> DeploymentScripts:
        """Generate complete set of deployment scripts."""
        return DeploymentScripts(
            deploy_script=self._generate_deploy_script(),
            cleanup_script=self._generate_cleanup_script(),
            monitoring_script=self._generate_monitoring_script(),
            pipeline_execution_script=self._generate_pipeline_execution_script(),
            cost_management_script=self._generate_cost_management_script()
        )
    
    def _generate_deploy_script(self) -> str:
        """Generate main deployment script with proper error handling."""
        script = f'''#!/bin/bash
set -e

# SageMaker Infrastructure Deployment Script
# Project: {self.project_name}
# Environment: {self.environment}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PROJECT_NAME="{self.project_name}"
ENVIRONMENT="{self.environment}"
REGION="{self.region}"
STACK_NAME="{self.stack_name}"
TEMPLATE_FILE="$SCRIPT_DIR/cloudformation.yaml"

# Color codes for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Logging function
log() {{
    echo -e "${{GREEN}}[$(date +'%Y-%m-%d %H:%M:%S')] $1${{NC}}"
}}

error() {{
    echo -e "${{RED}}[ERROR] $1${{NC}}" >&2
}}

warn() {{
    echo -e "${{YELLOW}}[WARNING] $1${{NC}}"
}}

# Check prerequisites
check_prerequisites() {{
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured"
        exit 1
    fi
    
    # Check CloudFormation template exists
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        error "CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    log "Prerequisites check passed"
}}

# Validate CloudFormation template
validate_template() {{
    log "Validating CloudFormation template..."
    
    if aws cloudformation validate-template \\
        --template-body file://"$TEMPLATE_FILE" \\
        --region "$REGION" &> /dev/null; then
        log "Template validation passed"
    else
        error "Template validation failed"
        exit 1
    fi
}}'''
        return script
    
    def _generate_cleanup_script(self) -> str:
        """Generate cleanup script for resource management."""
        return f'''#!/bin/bash
set -e

# SageMaker Infrastructure Cleanup Script
# Project: {self.project_name}

STACK_NAME="{self.stack_name}"
REGION="{self.region}"
PROJECT_NAME="{self.project_name}"

log() {{
    echo -e "\\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\\033[0m"
}}

error() {{
    echo -e "\\033[0;31m[ERROR] $1\\033[0m" >&2
}}

# Function to cleanup SageMaker resources
cleanup_sagemaker_resources() {{
    log "Cleaning up SageMaker resources..."
    
    # Stop and delete endpoints
    ENDPOINTS=$(aws sagemaker list-endpoints \\
        --name-contains "$PROJECT_NAME" \\
        --region "$REGION" \\
        --query 'Endpoints[].EndpointName' \\
        --output text)
    
    for endpoint in $ENDPOINTS; do
        if [[ -n "$endpoint" ]]; then
            log "Deleting endpoint: $endpoint"
            aws sagemaker delete-endpoint \\
                --endpoint-name "$endpoint" \\
                --region "$REGION" || true
        fi
    done
    
    # Delete models
    MODELS=$(aws sagemaker list-models \\
        --name-contains "$PROJECT_NAME" \\
        --region "$REGION" \\
        --query 'Models[].ModelName' \\
        --output text)
    
    for model in $MODELS; do
        if [[ -n "$model" ]]; then
            log "Deleting model: $model"
            aws sagemaker delete-model \\
                --model-name "$model" \\
                --region "$REGION" || true
        fi
    done
}}

# Function to empty S3 bucket
empty_s3_bucket() {{
    BUCKET_NAME=$(aws cloudformation describe-stacks \\
        --stack-name "$STACK_NAME" \\
        --region "$REGION" \\
        --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \\
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$BUCKET_NAME" ]]; then
        log "Emptying S3 bucket: $BUCKET_NAME"
        aws s3 rm s3://"$BUCKET_NAME" --recursive || true
    fi
}}

# Main cleanup process
main() {{
    log "Starting cleanup process..."
    
    cleanup_sagemaker_resources
    empty_s3_bucket
    
    # Delete CloudFormation stack
    log "Deleting CloudFormation stack: $STACK_NAME"
    aws cloudformation delete-stack \\
        --stack-name "$STACK_NAME" \\
        --region "$REGION"
    
    log "Cleanup completed. Stack deletion in progress."
    log "Monitor progress: aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION"
}}

main "$@"'''
    def _generate_monitoring_script(self) -> str:
        """Generate monitoring and alerting script."""
        return f'''#!/bin/bash
set -e

# SageMaker Monitoring Script
# Project: {self.project_name}

REGION="{self.region}"
PROJECT_NAME="{self.project_name}"

log() {{
    echo -e "\\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\\033[0m"
}}

# Monitor training jobs
monitor_training_jobs() {{
    log "Monitoring training jobs..."
    
    aws sagemaker list-training-jobs \\
        --name-contains "$PROJECT_NAME" \\
        --region "$REGION" \\
        --query 'TrainingJobSummaries[?TrainingJobStatus==`InProgress`].[TrainingJobName,TrainingJobStatus,CreationTime]' \\
        --output table
}}

# Monitor endpoints
monitor_endpoints() {{
    log "Monitoring endpoints..."
    
    aws sagemaker list-endpoints \\
        --name-contains "$PROJECT_NAME" \\
        --region "$REGION" \\
        --query 'Endpoints[].[EndpointName,EndpointStatus,CreationTime]' \\
        --output table
}}

# Check CloudWatch logs
check_logs() {{
    LOG_GROUP="/aws/sagemaker/$PROJECT_NAME"
    
    log "Recent log events from $LOG_GROUP:"
    
    aws logs describe-log-streams \\
        --log-group-name "$LOG_GROUP" \\
        --region "$REGION" \\
        --order-by LastEventTime \\
        --descending \\
        --max-items 5 \\
        --query 'logStreams[0].logStreamName' \\
        --output text | while read -r stream; do
        if [[ -n "$stream" ]]; then
            aws logs get-log-events \\
                --log-group-name "$LOG_GROUP" \\
                --log-stream-name "$stream" \\
                --region "$REGION" \\
                --limit 10 \\
                --query 'events[].[timestamp,message]' \\
                --output text
        fi
    done
}}

# Main monitoring function
main() {{
    log "Starting monitoring check..."
    
    monitor_training_jobs
    monitor_endpoints
    check_logs
    
    log "Monitoring check completed"
}}

main "$@"'''
    
    def _generate_pipeline_execution_script(self) -> str:
        """Generate pipeline execution and monitoring utilities."""
        return f'''#!/bin/bash
set -e

# SageMaker Pipeline Execution Script
# Project: {self.project_name}

REGION="{self.region}"
PROJECT_NAME="{self.project_name}"
PIPELINE_NAME="${{PROJECT_NAME}}-pipeline"

log() {{
    echo -e "\\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\\033[0m"
}}

error() {{
    echo -e "\\033[0;31m[ERROR] $1\\033[0m" >&2
}}

# Start pipeline execution
start_pipeline() {{
    log "Starting pipeline execution: $PIPELINE_NAME"
    
    EXECUTION_ARN=$(aws sagemaker start-pipeline-execution \\
        --pipeline-name "$PIPELINE_NAME" \\
        --region "$REGION" \\
        --query 'PipelineExecutionArn' \\
        --output text)
    
    if [[ -n "$EXECUTION_ARN" ]]; then
        log "Pipeline execution started: $EXECUTION_ARN"
        echo "$EXECUTION_ARN" > pipeline_execution.arn
    else
        error "Failed to start pipeline execution"
        exit 1
    fi
}}

# Monitor pipeline execution
monitor_pipeline() {{
    if [[ -f "pipeline_execution.arn" ]]; then
        EXECUTION_ARN=$(cat pipeline_execution.arn)
    else
        error "No pipeline execution ARN found"
        exit 1
    fi
    
    log "Monitoring pipeline execution: $EXECUTION_ARN"
    
    while true; do
        STATUS=$(aws sagemaker describe-pipeline-execution \\
            --pipeline-execution-arn "$EXECUTION_ARN" \\
            --region "$REGION" \\
            --query 'PipelineExecutionStatus' \\
            --output text)
        
        log "Pipeline status: $STATUS"
        
        case "$STATUS" in
            "Succeeded")
                log "Pipeline execution completed successfully"
                break
                ;;
            "Failed"|"Stopped")
                error "Pipeline execution failed with status: $STATUS"
                exit 1
                ;;
            "Executing"|"Stopping")
                log "Pipeline still running, checking again in 30 seconds..."
                sleep 30
                ;;
            *)
                warn "Unknown status: $STATUS"
                sleep 30
                ;;
        esac
    done
}}

# Restart failed pipeline
restart_pipeline() {{
    log "Restarting pipeline: $PIPELINE_NAME"
    
    # Stop any running executions
    RUNNING_EXECUTIONS=$(aws sagemaker list-pipeline-executions \\
        --pipeline-name "$PIPELINE_NAME" \\
        --region "$REGION" \\
        --query 'PipelineExecutionSummaries[?PipelineExecutionStatus==`Executing`].PipelineExecutionArn' \\
        --output text)
    
    for execution in $RUNNING_EXECUTIONS; do
        if [[ -n "$execution" ]]; then
            log "Stopping execution: $execution"
            aws sagemaker stop-pipeline-execution \\
                --pipeline-execution-arn "$execution" \\
                --region "$REGION"
        fi
    done
    
    # Wait a bit for cleanup
    sleep 10
    
    # Start new execution
    start_pipeline
}}

# Main function
main() {{
    case "${{1:-start}}" in
        "start")
            start_pipeline
            ;;
        "monitor")
            monitor_pipeline
            ;;
        "restart")
            restart_pipeline
            ;;
        *)
            echo "Usage: $0 {{start|monitor|restart}}"
            exit 1
            ;;
    esac
}}

main "$@"'''
    
    def _generate_cost_management_script(self) -> str:
        """Generate cost management and optimization tools."""
        return f'''#!/bin/bash
set -e

# SageMaker Cost Management Script
# Project: {self.project_name}

REGION="{self.region}"
PROJECT_NAME="{self.project_name}"

log() {{
    echo -e "\\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\\033[0m"
}}

warn() {{
    echo -e "\\033[1;33m[WARNING] $1\\033[0m"
}}

# Check running resources that incur costs
check_running_resources() {{
    log "Checking running resources..."
    
    # Check training jobs
    TRAINING_JOBS=$(aws sagemaker list-training-jobs \\
        --name-contains "$PROJECT_NAME" \\
        --status-equals InProgress \\
        --region "$REGION" \\
        --query 'TrainingJobSummaries[].TrainingJobName' \\
        --output text)
    
    if [[ -n "$TRAINING_JOBS" ]]; then
        warn "Running training jobs found:"
        echo "$TRAINING_JOBS"
    fi
    
    # Check endpoints
    ENDPOINTS=$(aws sagemaker list-endpoints \\
        --name-contains "$PROJECT_NAME" \\
        --status-equals InService \\
        --region "$REGION" \\
        --query 'Endpoints[].[EndpointName,InstanceType]' \\
        --output text)
    
    if [[ -n "$ENDPOINTS" ]]; then
        warn "Running endpoints found:"
        echo "$ENDPOINTS"
    fi
    
    # Check notebook instances
    NOTEBOOKS=$(aws sagemaker list-notebook-instances \\
        --name-contains "$PROJECT_NAME" \\
        --status-equals InService \\
        --region "$REGION" \\
        --query 'NotebookInstances[].[NotebookInstanceName,InstanceType]' \\
        --output text)
    
    if [[ -n "$NOTEBOOKS" ]]; then
        warn "Running notebook instances found:"
        echo "$NOTEBOOKS"
    fi
}}

# Generate cost report
generate_cost_report() {{
    log "Generating cost report for the last 30 days..."
    
    START_DATE=$(date -d "30 days ago" +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)
    
    aws ce get-cost-and-usage \\
        --time-period Start="$START_DATE",End="$END_DATE" \\
        --granularity DAILY \\
        --metrics BlendedCost \\
        --group-by Type=DIMENSION,Key=SERVICE \\
        --filter file://<(cat <<EOF
{{
    "Dimensions": {{
        "Key": "SERVICE",
        "Values": ["Amazon SageMaker"]
    }}
}}
EOF
) \\
        --region "$REGION" \\
        --query 'ResultsByTime[].Groups[?Keys[0]==`Amazon SageMaker`].Metrics.BlendedCost.Amount' \\
        --output text | awk '{{sum += $1}} END {{printf "Total SageMaker cost (last 30 days): $%.2f\\n", sum}}'
}}

# Stop non-essential resources
stop_resources() {{
    log "Stopping non-essential resources to save costs..."
    
    # Stop notebook instances
    NOTEBOOKS=$(aws sagemaker list-notebook-instances \\
        --name-contains "$PROJECT_NAME" \\
        --status-equals InService \\
        --region "$REGION" \\
        --query 'NotebookInstances[].NotebookInstanceName' \\
        --output text)
    
    for notebook in $NOTEBOOKS; do
        if [[ -n "$notebook" ]]; then
            log "Stopping notebook instance: $notebook"
            aws sagemaker stop-notebook-instance \\
                --notebook-instance-name "$notebook" \\
                --region "$REGION"
        fi
    done
    
    # Note: Endpoints and training jobs require manual decision
    warn "Manual review required for endpoints and training jobs"
}}

# Main function
main() {{
    case "${{1:-check}}" in
        "check")
            check_running_resources
            ;;
        "report")
            generate_cost_report
            ;;
        "stop")
            stop_resources
            ;;
        *)
            echo "Usage: $0 {{check|report|stop}}"
            exit 1
            ;;
    esac
}}

main "$@"'''

    def generate_makefile(self) -> str:
        """Generate Makefile for easy deployment management."""
        return f'''# Makefile for {self.project_name} SageMaker deployment

PROJECT_NAME = {self.project_name}
ENVIRONMENT = {self.environment}
REGION = {self.region}
STACK_NAME = {self.stack_name}

.PHONY: help deploy validate clean monitor pipeline cost

help:
\t@echo "Available targets:"
\t@echo "  deploy    - Deploy infrastructure"
\t@echo "  validate  - Validate CloudFormation template"
\t@echo "  clean     - Clean up all resources"
\t@echo "  monitor   - Monitor running resources"
\t@echo "  pipeline  - Execute pipeline"
\t@echo "  cost      - Check cost and running resources"

deploy:
\t@echo "Deploying $(PROJECT_NAME) infrastructure..."
\t./scripts/deploy.sh

validate:
\t@echo "Validating CloudFormation template..."
\taws cloudformation validate-template --template-body file://cloudformation.yaml --region $(REGION)

clean:
\t@echo "Cleaning up resources..."
\t./scripts/cleanup.sh

monitor:
\t@echo "Monitoring resources..."
\t./scripts/monitor.sh

pipeline:
\t@echo "Executing pipeline..."
\t./scripts/pipeline.sh start

cost:
\t@echo "Checking costs and running resources..."
\t./scripts/cost_management.sh check'''

    def generate_deployment_plan(self, artifacts, region: str):
        """Generate deployment plan for migration artifacts."""
        from ..models.deployment import DeploymentPlan, DeploymentStep, DeploymentStatus
        
        steps = [
            DeploymentStep(
                step_name="validate_template",
                description="Validate the CloudFormation template syntax",
                status=DeploymentStatus.PENDING,
                estimated_duration_minutes=2,
                dependencies=[],
                resources_created=[]
            ),
            DeploymentStep(
                step_name="deploy_infrastructure",
                description="Deploy the CloudFormation stack",
                status=DeploymentStatus.PENDING,
                estimated_duration_minutes=15,
                dependencies=["validate_template"],
                resources_created=[]
            ),
            DeploymentStep(
                step_name="verify_deployment",
                description="Verify that all resources were created successfully",
                status=DeploymentStatus.PENDING,
                estimated_duration_minutes=3,
                dependencies=["deploy_infrastructure"],
                resources_created=[]
            )
        ]
        
        return DeploymentPlan(
            plan_name=f"{self.project_name}-deployment-plan",
            region=region,
            steps=steps,
            total_estimated_duration_minutes=sum(step.estimated_duration_minutes for step in steps),
            prerequisites=[
                "AWS CLI configured with appropriate permissions",
                "CloudFormation template validated"
            ],
            rollback_plan=[
                "Delete CloudFormation stack",
                "Clean up any remaining resources"
            ]
        )
    
    def execute_deployment(self, artifacts, region: str):
        """Execute deployment using AWS CloudFormation."""
        from ..models.deployment import DeploymentResult, DeploymentPlan
        import boto3
        import time
        import json
        
        logger.info(f"Starting real AWS deployment to region: {region}")
        
        # Create a deployment plan
        deployment_plan = self.generate_deployment_plan(artifacts, region)
        
        # Initialize AWS clients
        try:
            cf_client = boto3.client('cloudformation', region_name=region)
            sts_client = boto3.client('sts', region_name=region)
            
            # Get account ID for resource naming
            account_id = sts_client.get_caller_identity()['Account']
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            
            # Provide helpful error messages for common issues
            error_message = str(e)
            if "NoCredentialsError" in error_message or "Unable to locate credentials" in error_message:
                error_message = "AWS credentials not configured. Please run 'aws configure' or set AWS environment variables."
            elif "InvalidUserID.NotFound" in error_message:
                error_message = "AWS credentials are invalid or expired. Please check your AWS access keys."
            elif "UnauthorizedOperation" in error_message:
                error_message = "Insufficient AWS permissions. Please ensure your AWS user/role has CloudFormation and SageMaker permissions."
            
            return DeploymentResult(
                success=False,
                deployment_plan=deployment_plan,
                stack_name=self.stack_name,
                region=region,
                resources_created=[],
                errors=[f"AWS client initialization failed: {error_message}"],
                warnings=[],
                deployment_duration_minutes=0.0,
                endpoints_created=[]
            )
        
        # Get CloudFormation template
        cf_template = artifacts.infrastructure.cloudformation_templates.get("main.yaml")
        if not cf_template:
            logger.error("No CloudFormation template found in artifacts")
            return DeploymentResult(
                success=False,
                deployment_plan=deployment_plan,
                stack_name=self.stack_name,
                region=region,
                resources_created=[],
                errors=["No CloudFormation template found in artifacts"],
                warnings=[],
                deployment_duration_minutes=0.0,
                endpoints_created=[]
            )
        
        # Prepare template parameters
        template_parameters = []
        if hasattr(artifacts.infrastructure, 'template_parameters') and artifacts.infrastructure.template_parameters:
            for key, value in artifacts.infrastructure.template_parameters.items():
                template_parameters.append({
                    'ParameterKey': key,
                    'ParameterValue': str(value)
                })
        
        start_time = time.time()
        resources_created = []
        errors = []
        warnings = []
        stack_outputs = {}
        
        try:
            # Check if stack already exists
            try:
                cf_client.describe_stacks(StackName=self.stack_name)
                logger.warning(f"Stack {self.stack_name} already exists, updating...")
                
                # Update existing stack
                response = cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=cf_template,
                    Parameters=template_parameters,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
                )
                operation = "UPDATE"
                
            except cf_client.exceptions.ClientError as e:
                if "does not exist" in str(e):
                    logger.info(f"Creating new stack: {self.stack_name}")
                    
                    # Create new stack
                    response = cf_client.create_stack(
                        StackName=self.stack_name,
                        TemplateBody=cf_template,
                        Parameters=template_parameters,
                        Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
                        OnFailure='ROLLBACK'
                    )
                    operation = "CREATE"
                else:
                    raise e
            
            stack_id = response['StackId']
            logger.info(f"Stack {operation} initiated: {stack_id}")
            
            # Wait for stack operation to complete
            logger.info("Waiting for stack operation to complete...")
            waiter_name = 'stack_create_complete' if operation == "CREATE" else 'stack_update_complete'
            waiter = cf_client.get_waiter(waiter_name)
            
            try:
                waiter.wait(
                    StackName=self.stack_name,
                    WaiterConfig={
                        'Delay': 30,  # Check every 30 seconds
                        'MaxAttempts': 60  # Wait up to 30 minutes
                    }
                )
                logger.info(f"Stack {operation.lower()} completed successfully")
                
                # Get stack resources
                resources_response = cf_client.describe_stack_resources(StackName=self.stack_name)
                for resource in resources_response['StackResources']:
                    if resource['ResourceStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                        resources_created.append(f"{resource['ResourceType']}: {resource['LogicalResourceId']}")
                
                # Get stack outputs
                stack_response = cf_client.describe_stacks(StackName=self.stack_name)
                stack = stack_response['Stacks'][0]
                
                stack_outputs = {}
                if 'Outputs' in stack:
                    for output in stack['Outputs']:
                        logger.info(f"Stack output - {output['OutputKey']}: {output['OutputValue']}")
                        stack_outputs[output['OutputKey']] = output['OutputValue']
                
                success = True
                
            except Exception as e:
                logger.error(f"Stack operation failed: {str(e)}")
                errors.append(f"Stack {operation.lower()} failed: {str(e)}")
                success = False
                
                # Try to get stack events for more details
                try:
                    events_response = cf_client.describe_stack_events(StackName=self.stack_name)
                    failed_events = [
                        event for event in events_response['StackEvents']
                        if event.get('ResourceStatus', '').endswith('_FAILED')
                    ]
                    for event in failed_events[-3:]:  # Show last 3 failed events
                        errors.append(f"Resource {event['LogicalResourceId']}: {event.get('ResourceStatusReason', 'Unknown error')}")
                except Exception:
                    pass  # Ignore errors getting stack events
        
        except Exception as e:
            logger.error(f"CloudFormation deployment failed: {str(e)}")
            errors.append(f"CloudFormation deployment failed: {str(e)}")
            success = False
        
        end_time = time.time()
        deployment_duration = (end_time - start_time) / 60.0  # Convert to minutes
        
        # Check for SageMaker endpoints in created resources
        endpoints_created = []
        for resource in resources_created:
            if "AWS::SageMaker::Endpoint" in resource:
                endpoint_name = resource.split(": ")[-1]
                endpoints_created.append(endpoint_name)
        
        return DeploymentResult(
            success=success,
            deployment_plan=deployment_plan,
            stack_name=self.stack_name,
            region=region,
            resources_created=resources_created,
            errors=errors,
            warnings=warnings,
            deployment_duration_minutes=deployment_duration,
            endpoints_created=endpoints_created,
            stack_outputs=stack_outputs if success else {}
        )