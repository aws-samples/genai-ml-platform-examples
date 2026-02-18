"""IAM policy generator with least-privilege access patterns."""

import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

from ..models.analysis import AnalysisReport


class ServiceType(Enum):
    """Supported AWS services for policy generation."""
    SAGEMAKER = "sagemaker"
    S3 = "s3"
    CLOUDWATCH = "cloudwatch"
    ECR = "ecr"
    KMS = "kms"
    IAM = "iam"


@dataclass
class PolicyConfig:
    """Configuration for IAM policy generation."""
    account_id: str
    region: str
    project_name: str
    environment: str = "dev"
    enable_encryption: bool = True
    s3_bucket_name: Optional[str] = None
    kms_key_id: Optional[str] = None


class IAMPolicyGenerator:
    """Generates IAM policies with specific resource ARNs and proper trust relationships."""
    
    def __init__(self, config):
        # Extract relevant config from main Config object
        if hasattr(config, 'infrastructure'):
            self.project_name = config.project_name
            self.region = config.infrastructure.default_region
            self.enable_encryption = config.infrastructure.enable_encryption
            # Use placeholder account ID for testing
            self.account_id = getattr(config, 'account_id', '123456789012')
        else:
            # Fallback for direct PolicyConfig
            self.config = config
            self.account_id = getattr(config, 'account_id', '123456789012')
            self.region = getattr(config, 'region', 'us-east-1')
            self.project_name = getattr(config, 'project_name', 'sagemigrator-project')
            self.enable_encryption = getattr(config, 'enable_encryption', True)
        
    def generate_sagemaker_execution_policy(self, analysis: AnalysisReport) -> Dict[str, Any]:
        """Generate SageMaker execution role policy with least-privilege access."""
        statements = []
        
        # Core SageMaker permissions
        statements.extend(self._generate_sagemaker_statements())
        
        # S3 permissions
        statements.extend(self._generate_s3_statements())
        
        # CloudWatch permissions
        statements.extend(self._generate_cloudwatch_statements())
        
        # ECR permissions if container customization is needed
        if self._requires_ecr_access(analysis):
            statements.extend(self._generate_ecr_statements())
        
        # KMS permissions if encryption is enabled
        if self.enable_encryption:
            statements.extend(self._generate_kms_statements())
        
        return {
            "Version": "2012-10-17",
            "Statement": statements
        }
    
    def generate_trust_policy(self, services: List[str]) -> Dict[str, Any]:
        """Generate trust relationship policy for IAM role."""
        principals = []
        
        for service in services:
            if service == "sagemaker":
                principals.append("sagemaker.amazonaws.com")
            elif service == "lambda":
                principals.append("lambda.amazonaws.com")
            elif service == "ec2":
                principals.append("ec2.amazonaws.com")
        
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowServiceAssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": principals
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
    
    def generate_model_registry_policy(self) -> Dict[str, Any]:
        """Generate policy for SageMaker Model Registry operations."""
        statements = [
            {
                "Sid": "AllowModelRegistryAccess",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateModelPackage",
                    "sagemaker:CreateModelPackageGroup",
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:DescribeModelPackageGroup",
                    "sagemaker:ListModelPackages",
                    "sagemaker:ListModelPackageGroups",
                    "sagemaker:UpdateModelPackage"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:model-package/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:model-package-group/*"
                ]
            },
            {
                "Sid": "AllowModelApprovalWorkflow",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:UpdateModelPackage"
                ],
                "Resource": f"arn:aws:sagemaker:{self.region}:{self.account_id}:model-package/*",
                "Condition": {
                    "StringEquals": {
                        "sagemaker:ModelApprovalStatus": ["Approved", "Rejected"]
                    }
                }
            }
        ]
        
        return {
            "Version": "2012-10-17",
            "Statement": statements
        }
    
    def generate_endpoint_deployment_policy(self) -> Dict[str, Any]:
        """Generate policy for endpoint deployment and management."""
        statements = [
            {
                "Sid": "AllowEndpointOperations",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateEndpoint",
                    "sagemaker:CreateEndpointConfig",
                    "sagemaker:CreateModel",
                    "sagemaker:DeleteEndpoint",
                    "sagemaker:DeleteEndpointConfig",
                    "sagemaker:DeleteModel",
                    "sagemaker:DescribeEndpoint",
                    "sagemaker:DescribeEndpointConfig",
                    "sagemaker:DescribeModel",
                    "sagemaker:InvokeEndpoint",
                    "sagemaker:ListEndpoints",
                    "sagemaker:ListEndpointConfigs",
                    "sagemaker:ListModels",
                    "sagemaker:UpdateEndpoint",
                    "sagemaker:UpdateEndpointWeightsAndCapacities"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:endpoint/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:endpoint-config/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:model/*"
                ]
            },
            {
                "Sid": "AllowAutoScaling",
                "Effect": "Allow",
                "Action": [
                    "application-autoscaling:DeleteScalingPolicy",
                    "application-autoscaling:DeregisterScalableTarget",
                    "application-autoscaling:DescribeScalableTargets",
                    "application-autoscaling:DescribeScalingPolicies",
                    "application-autoscaling:PutScalingPolicy",
                    "application-autoscaling:RegisterScalableTarget"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "application-autoscaling:service-namespace": "sagemaker"
                    }
                }
            }
        ]
        
        return {
            "Version": "2012-10-17",
            "Statement": statements
        }
    
    def _generate_sagemaker_statements(self) -> List[Dict[str, Any]]:
        """Generate SageMaker-specific policy statements."""
        return [
            {
                "Sid": "AllowSageMakerTrainingJobs",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateTrainingJob",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:StopTrainingJob",
                    "sagemaker:ListTrainingJobs"
                ],
                "Resource": f"arn:aws:sagemaker:{self.region}:{self.account_id}:training-job/*"
            },
            {
                "Sid": "AllowSageMakerProcessingJobs",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:StopProcessingJob",
                    "sagemaker:ListProcessingJobs"
                ],
                "Resource": f"arn:aws:sagemaker:{self.region}:{self.account_id}:processing-job/*"
            },
            {
                "Sid": "AllowSageMakerPipelines",
                "Effect": "Allow",
                "Action": [
                    "sagemaker:CreatePipeline",
                    "sagemaker:StartPipelineExecution",
                    "sagemaker:StopPipelineExecution",
                    "sagemaker:DescribePipeline",
                    "sagemaker:DescribePipelineExecution",
                    "sagemaker:ListPipelineExecutions",
                    "sagemaker:ListPipelines"
                ],
                "Resource": [
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:pipeline/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account_id}:pipeline-execution/*"
                ]
            }
        ]
    
    def _generate_s3_statements(self) -> List[Dict[str, Any]]:
        """Generate S3 policy statements with specific bucket ARNs."""
        # Use individual attributes instead of self.config
        s3_bucket_name = getattr(self, 's3_bucket_name', None)
        if not s3_bucket_name:
            s3_bucket_name = f"{self.project_name.lower()}-sagemaker-bucket-{self.account_id}-{self.region}"
        
        # Ensure proper ARN format for S3 resources using validator
        try:
            from ..utils.s3_arn_validator import validate_s3_resource_arn
            bucket_arn = validate_s3_resource_arn(s3_bucket_name)
            bucket_objects_arn = validate_s3_resource_arn(f"{s3_bucket_name}/*")
        except ImportError:
            # Fallback if validator is not available
            bucket_arn = f"arn:aws:s3:::{s3_bucket_name}"
            bucket_objects_arn = f"arn:aws:s3:::{s3_bucket_name}/*"
        
        return [
            {
                "Sid": "AllowS3BucketAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:ListBucket"
                ],
                "Resource": bucket_arn
            },
            {
                "Sid": "AllowS3ObjectAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": bucket_objects_arn
            },
            {
                "Sid": "AllowS3MultipartUpload",
                "Effect": "Allow",
                "Action": [
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts"
                ],
                "Resource": bucket_objects_arn
            }
        ]
    
    def _generate_cloudwatch_statements(self) -> List[Dict[str, Any]]:
        """Generate CloudWatch policy statements."""
        environment = getattr(self, 'environment', 'dev')
        log_group_name = f"/aws/sagemaker/{self.project_name}-{environment}"
        
        return [
            {
                "Sid": "AllowCloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams"
                ],
                "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:{log_group_name}:*"
            },
            {
                "Sid": "AllowCloudWatchMetrics",
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:ListMetrics"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "AWS/SageMaker"
                    }
                }
            }
        ]
    
    def _generate_ecr_statements(self) -> List[Dict[str, Any]]:
        """Generate ECR policy statements for custom containers."""
        return [
            {
                "Sid": "AllowECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                "Resource": f"arn:aws:ecr:{self.region}:{self.account_id}:repository/{self.project_name}-*"
            },
            {
                "Sid": "AllowECRAuth",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            }
        ]
    
    def _generate_kms_statements(self) -> List[Dict[str, Any]]:
        """Generate KMS policy statements for encryption."""
        kms_key_id = getattr(self, 'kms_key_id', None)
        kms_resource = (
            f"arn:aws:kms:{self.region}:{self.account_id}:key/{kms_key_id}"
            if kms_key_id
            else f"arn:aws:kms:{self.region}:{self.account_id}:key/*"
        )
        
        return [
            {
                "Sid": "AllowKMSAccess",
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey"
                ],
                "Resource": kms_resource
            }
        ]
    
    def _requires_ecr_access(self, analysis: AnalysisReport) -> bool:
        """Determine if ECR access is needed based on analysis."""
        # Check if custom dependencies require container customization
        if hasattr(analysis, 'dependencies') and analysis.dependencies:
            custom_deps = getattr(analysis.dependencies, 'custom_packages', [])
            return len(custom_deps) > 0
        return False
    
    def validate_policy(self, policy: Dict[str, Any]) -> List[str]:
        """Validate IAM policy syntax and best practices."""
        errors = []
        
        # Check required fields
        if "Version" not in policy:
            errors.append("Policy missing Version field")
        
        if "Statement" not in policy:
            errors.append("Policy missing Statement field")
            return errors
        
        statements = policy["Statement"]
        if not isinstance(statements, list):
            statements = [statements]
        
        for i, statement in enumerate(statements):
            # Check required statement fields
            required_fields = ["Effect", "Action"]
            for field in required_fields:
                if field not in statement:
                    errors.append(f"Statement {i} missing {field} field")
            
            # Check for Sid field
            if "Sid" not in statement:
                errors.append(f"Statement {i} missing Sid field")
            
            # Check for wildcard resources
            if "Resource" in statement:
                resources = statement["Resource"]
                if not isinstance(resources, list):
                    resources = [resources]
                
                for resource in resources:
                    if resource == "*" and statement.get("Effect") == "Allow":
                        errors.append(f"Statement {i} uses wildcard resource with Allow effect")
                    
                    # Validate S3 ARN format
                    if isinstance(resource, str) and ("s3" in resource.lower() or "bucket" in resource.lower()):
                        if not resource.startswith("arn:aws:s3:::") and resource != "*":
                            errors.append(f"Statement {i} has invalid S3 resource format: {resource}. Must be in ARN format (arn:aws:s3:::bucket-name or arn:aws:s3:::bucket-name/*)")
        
        return errors
    
    def generate_policy_document(self, policy_type: str, analysis: AnalysisReport) -> str:
        """Generate complete policy document as JSON string."""
        if policy_type == "execution":
            policy = self.generate_sagemaker_execution_policy(analysis)
        elif policy_type == "model_registry":
            policy = self.generate_model_registry_policy()
        elif policy_type == "endpoint_deployment":
            policy = self.generate_endpoint_deployment_policy()
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")
        
        return json.dumps(policy, indent=2)