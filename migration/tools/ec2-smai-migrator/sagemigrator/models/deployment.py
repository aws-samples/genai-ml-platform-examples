"""
Deployment models for SageBridge

Data structures for deployment planning and results.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from .artifacts import MigrationArtifacts


@dataclass
class InfrastructureCode:
    """Infrastructure as code artifacts."""
    cloudformation_template: str
    template_parameters: Dict[str, str]
    iam_policies: Dict[str, str] = None
    
    def __post_init__(self):
        if self.iam_policies is None:
            self.iam_policies = {}


@dataclass
class DeploymentScripts:
    """Deployment automation scripts."""
    deploy_script: str
    cleanup_script: str
    monitoring_script: str
    pipeline_execution_script: str
    cost_management_script: str
    makefile: Optional[str] = None


class DeploymentStatus(Enum):
    """Status of deployment operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentStep:
    """Individual deployment step"""
    step_name: str
    description: str
    status: DeploymentStatus
    estimated_duration_minutes: int
    dependencies: List[str]
    resources_created: List[str]
    error_message: Optional[str] = None


@dataclass
class DeploymentPlan:
    """Deployment plan with ordered steps"""
    plan_name: str
    region: str
    steps: List[DeploymentStep]
    total_estimated_duration_minutes: int
    prerequisites: List[str]
    rollback_plan: List[str]
    
    @classmethod
    def create_placeholder(cls, artifacts: MigrationArtifacts, region: str) -> 'DeploymentPlan':
        """Create placeholder deployment plan for testing"""
        return cls(
            plan_name="SageBridge Migration Deployment",
            region=region,
            steps=[
                DeploymentStep(
                    step_name="create_iam_roles",
                    description="Create IAM roles and policies for SageMaker",
                    status=DeploymentStatus.PENDING,
                    estimated_duration_minutes=5,
                    dependencies=[],
                    resources_created=["SageMakerExecutionRole", "SageMakerPipelineRole"]
                ),
                DeploymentStep(
                    step_name="create_s3_buckets",
                    description="Create S3 buckets for data and artifacts",
                    status=DeploymentStatus.PENDING,
                    estimated_duration_minutes=3,
                    dependencies=["create_iam_roles"],
                    resources_created=["sagebridge-data-bucket", "sagebridge-artifacts-bucket"]
                ),
                DeploymentStep(
                    step_name="deploy_training_job",
                    description="Deploy SageMaker training job",
                    status=DeploymentStatus.PENDING,
                    estimated_duration_minutes=15,
                    dependencies=["create_s3_buckets"],
                    resources_created=["SageMakerTrainingJob"]
                ),
                DeploymentStep(
                    step_name="create_model_registry",
                    description="Create model registry and register model",
                    status=DeploymentStatus.PENDING,
                    estimated_duration_minutes=5,
                    dependencies=["deploy_training_job"],
                    resources_created=["ModelPackageGroup", "ModelPackage"]
                ),
                DeploymentStep(
                    step_name="deploy_inference_endpoint",
                    description="Deploy inference endpoint",
                    status=DeploymentStatus.PENDING,
                    estimated_duration_minutes=10,
                    dependencies=["create_model_registry"],
                    resources_created=["SageMakerModel", "SageMakerEndpointConfig", "SageMakerEndpoint"]
                )
            ],
            total_estimated_duration_minutes=38,
            prerequisites=[
                "AWS CLI configured with appropriate permissions",
                "SageMaker service limits sufficient for deployment",
                "VPC and subnets available (if VPC deployment)"
            ],
            rollback_plan=[
                "Delete SageMaker endpoint",
                "Delete SageMaker model",
                "Delete model registry entries",
                "Delete S3 buckets (after confirming no important data)",
                "Delete IAM roles and policies"
            ]
        )
    
    def get_next_step(self) -> Optional[DeploymentStep]:
        """Get the next step to execute"""
        for step in self.steps:
            if step.status == DeploymentStatus.PENDING:
                # Check if all dependencies are completed
                dependencies_met = all(
                    any(s.step_name == dep and s.status == DeploymentStatus.COMPLETED 
                        for s in self.steps)
                    for dep in step.dependencies
                )
                if dependencies_met or not step.dependencies:
                    return step
        return None
    
    def mark_step_completed(self, step_name: str, resources_created: Optional[List[str]] = None) -> None:
        """Mark a step as completed"""
        for step in self.steps:
            if step.step_name == step_name:
                step.status = DeploymentStatus.COMPLETED
                if resources_created:
                    step.resources_created.extend(resources_created)
                break
    
    def mark_step_failed(self, step_name: str, error_message: str) -> None:
        """Mark a step as failed"""
        for step in self.steps:
            if step.step_name == step_name:
                step.status = DeploymentStatus.FAILED
                step.error_message = error_message
                break
    
    def is_completed(self) -> bool:
        """Check if all steps are completed"""
        return all(step.status == DeploymentStatus.COMPLETED for step in self.steps)
    
    def has_failures(self) -> bool:
        """Check if any steps have failed"""
        return any(step.status == DeploymentStatus.FAILED for step in self.steps)


@dataclass
class DeploymentResult:
    """Result of deployment operation"""
    success: bool
    deployment_plan: DeploymentPlan
    stack_name: Optional[str]
    region: str
    resources_created: List[str]
    errors: List[str]
    warnings: List[str]
    deployment_duration_minutes: float
    endpoints_created: List[str]
    stack_outputs: Dict[str, str] = None  # Add stack outputs
    
    def __post_init__(self):
        """Initialize stack_outputs if None"""
        if self.stack_outputs is None:
            self.stack_outputs = {}
    
    def get_execution_role_arn(self) -> Optional[str]:
        """Get the ExecutionRoleArn from stack outputs"""
        return self.stack_outputs.get('ExecutionRoleArn')
    
    def get_s3_bucket_name(self) -> Optional[str]:
        """Get the S3BucketName from stack outputs"""
        return self.stack_outputs.get('S3BucketName')
    
    @classmethod
    def create_placeholder(cls, artifacts: MigrationArtifacts, region: str) -> 'DeploymentResult':
        """Create placeholder deployment result for testing"""
        plan = DeploymentPlan.create_placeholder(artifacts, region)
        
        return cls(
            success=True,
            deployment_plan=plan,
            stack_name="sagebridge-migration-stack",
            region=region,
            resources_created=[
                "SageMakerExecutionRole",
                "sagebridge-data-bucket",
                "SageMakerTrainingJob",
                "SageMakerEndpoint"
            ],
            errors=[],
            warnings=["Training job may take longer than expected"],
            deployment_duration_minutes=35.5,
            endpoints_created=["sagebridge-inference-endpoint"],
            stack_outputs={
                "ExecutionRoleArn": f"arn:aws:iam::123456789012:role/sagebridge-migration-stack-SageMakerExecutionRole",
                "S3BucketName": f"sagebridge-migration-stack-s3bucket-{region}"
            }
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of deployment results"""
        return {
            "success": self.success,
            "region": self.region,
            "stack_name": self.stack_name,
            "resources_created": len(self.resources_created),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "duration_minutes": self.deployment_duration_minutes,
            "endpoints": len(self.endpoints_created)
        }