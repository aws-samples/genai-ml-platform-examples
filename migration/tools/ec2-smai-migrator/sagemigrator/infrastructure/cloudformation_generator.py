"""CloudFormation template generator for SageMaker infrastructure."""

import json
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..models.analysis import AnalysisReport
from ..models.artifacts import InfrastructureCode
from ..utils.s3_arn_validator import (
    validate_s3_arn_comprehensive,
    CloudFormationValidationResult,
    is_valid_s3_arn
)


@dataclass
class CloudFormationConfig:
    """Configuration for CloudFormation template generation."""
    project_name: str
    region: str = "us-east-1"
    enable_encryption: bool = True
    enable_versioning: bool = True
    lifecycle_days: int = 30
    kms_key_id: Optional[str] = None


class CloudFormationGenerator:
    """Generates CloudFormation templates with proper resource dependencies."""
    
    def __init__(self, config):
        # Extract relevant config from main Config object
        if hasattr(config, 'infrastructure'):
            self.project_name = config.project_name
            self.region = config.infrastructure.default_region
            self.enable_encryption = config.infrastructure.enable_encryption
        else:
            # Fallback for direct CloudFormationConfig
            self.config = config
            self.project_name = getattr(config, 'project_name', 'sagemigrator-project')
            self.region = getattr(config, 'region', 'us-east-1')
            self.enable_encryption = getattr(config, 'enable_encryption', True)
        
    def generate_template(self, analysis: AnalysisReport) -> InfrastructureCode:
        """Generate complete CloudFormation template with all required resources."""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"SageMaker infrastructure for {self.project_name}",
            "Parameters": self._generate_parameters(),
            "Resources": self._generate_resources(analysis),
            "Outputs": self._generate_outputs()
        }
        
        # Validate S3 ARN references in the template
        validation_result = self.validate_s3_arn_references(template)
        if not validation_result.is_valid:
            # Fix S3 ARN issues automatically
            template = validation_result.fixed_template or template
        
        return InfrastructureCode(
            cloudformation_templates={"main.yaml": yaml.dump(template, default_flow_style=False)},
            iam_policies={},
            deployment_scripts={},
            configuration_files={}
        )
    
    def _generate_parameters(self) -> Dict[str, Any]:
        """Generate CloudFormation parameters."""
        return {
            "ProjectName": {
                "Type": "String",
                "Default": self.project_name,
                "Description": "Name of the project for resource naming"
            },
            "Environment": {
                "Type": "String",
                "Default": "dev",
                "AllowedValues": ["dev", "staging", "prod"],
                "Description": "Environment name"
            },
            "InstanceType": {
                "Type": "String",
                "Default": "ml.m5.large",
                "Description": "SageMaker training instance type"
            },
            "KMSKeyId": {
                "Type": "String",
                "Default": "",
                "Description": "KMS Key ID for encryption (optional)"
            }
        }
    
    def _generate_resources(self, analysis: AnalysisReport) -> Dict[str, Any]:
        """Generate all CloudFormation resources with proper dependencies."""
        resources = {}
        
        # VPC and networking resources (required for Studio Domain)
        resources.update(self._generate_vpc_resources())
        
        # S3 Bucket for data and artifacts
        resources.update(self._generate_s3_resources())
        
        # IAM roles and policies
        resources.update(self._generate_iam_resources(analysis))
        
        # SageMaker resources
        resources.update(self._generate_sagemaker_resources())
        
        return resources
    
    def _generate_s3_resources(self) -> Dict[str, Any]:
        """Generate S3 bucket with encryption and lifecycle policies."""
        bucket_name = f"{self.project_name.lower()}-sagemaker-bucket"
        
        resources = {
            "SageMakerS3Bucket": {
                "Type": "AWS::S3::Bucket",
                "Properties": {
                    "BucketName": {
                        "Fn::Sub": f"{bucket_name}-${{AWS::AccountId}}-${{AWS::Region}}"
                    },
                    "VersioningConfiguration": {
                        "Status": "Enabled"
                    },
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {
                                "ServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256"
                                },
                                "BucketKeyEnabled": True
                            }
                        ]
                    } if self.enable_encryption else {},
                    "LifecycleConfiguration": {
                        "Rules": [
                            {
                                "Id": "DeleteIncompleteMultipartUploads",
                                "Status": "Enabled",
                                "AbortIncompleteMultipartUpload": {
                                    "DaysAfterInitiation": 7
                                }
                            },
                            {
                                "Id": "TransitionToIA",
                                "Status": "Enabled",
                                "Transitions": [
                                    {
                                        "StorageClass": "STANDARD_IA",
                                        "TransitionInDays": 30
                                    }
                                ]
                            }
                        ]
                    },
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True
                    },
                    "NotificationConfiguration": {
                        "LambdaConfigurations": [],
                        "TopicConfigurations": [],
                        "QueueConfigurations": []
                    }
                }
            }
        }
        
        # Add KMS key encryption if specified (disabled for now)
        # if hasattr(self, 'kms_key_id') and self.kms_key_id:
        #     resources["SageMakerS3Bucket"]["Properties"]["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["KMSMasterKeyID"] = self.kms_key_id
        
        return resources
    
    def _generate_iam_resources(self, analysis: AnalysisReport) -> Dict[str, Any]:
        """Generate IAM roles and policies with least-privilege access."""
        resources = {
            "SageMakerExecutionRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": {
                        "Fn::Sub": "${ProjectName}-SageMaker-ExecutionRole-${Environment}"
                    },
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowSageMakerAssumeRole",
                                "Effect": "Allow",
                                "Principal": {
                                    "Service": [
                                        "sagemaker.amazonaws.com"
                                    ]
                                },
                                "Action": "sts:AssumeRole"
                            }
                        ]
                    },
                    "ManagedPolicyArns": [
                        "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
                    ],
                    "Policies": [
                        {
                            "PolicyName": "SageMakerS3Access",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Sid": "AllowS3BucketAccess",
                                        "Effect": "Allow",
                                        "Action": [
                                            "s3:GetObject",
                                            "s3:PutObject",
                                            "s3:DeleteObject",
                                            "s3:ListBucket"
                                        ],
                                        "Resource": [
                                            {
                                                "Fn::GetAtt": ["SageMakerS3Bucket", "Arn"]
                                            },
                                            {
                                                "Fn::Sub": [
                                                    "${BucketArn}/*",
                                                    {
                                                        "BucketArn": {
                                                            "Fn::GetAtt": ["SageMakerS3Bucket", "Arn"]
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "PolicyName": "SageMakerLogsAccess",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Sid": "AllowCloudWatchLogs",
                                        "Effect": "Allow",
                                        "Action": [
                                            "logs:CreateLogGroup",
                                            "logs:CreateLogStream",
                                            "logs:PutLogEvents",
                                            "logs:DescribeLogStreams"
                                        ],
                                        "Resource": [
                                            {
                                                "Fn::GetAtt": ["SageMakerLogGroup", "Arn"]
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        
        # Add KMS permissions if encryption is enabled
        if self.enable_encryption:
            kms_policy = {
                "PolicyName": "SageMakerKMSAccess",
                "PolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowKMSAccess",
                            "Effect": "Allow",
                            "Action": [
                                "kms:Decrypt",
                                "kms:GenerateDataKey",
                                "kms:DescribeKey"
                            ],
                            "Resource": [
                                {
                                    "Fn::Sub": "arn:aws:kms:${AWS::Region}:${AWS::AccountId}:key/*"
                                }
                            ]
                        }
                    ]
                }
            }
            resources["SageMakerExecutionRole"]["Properties"]["Policies"].append(kms_policy)
        
        return resources
    
    def _generate_vpc_resources(self) -> Dict[str, Any]:
        """Generate VPC and networking resources required for SageMaker Studio Domain."""
        return {
            "SageMakerVPC": {
                "Type": "AWS::EC2::VPC",
                "Properties": {
                    "CidrBlock": "10.0.0.0/16",
                    "EnableDnsHostnames": True,
                    "EnableDnsSupport": True,
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": {
                                "Fn::Sub": "${ProjectName}-vpc"
                            }
                        }
                    ]
                }
            },
            "SageMakerPrivateSubnet": {
                "Type": "AWS::EC2::Subnet",
                "Properties": {
                    "VpcId": {
                        "Ref": "SageMakerVPC"
                    },
                    "CidrBlock": "10.0.1.0/24",
                    "AvailabilityZone": {
                        "Fn::Select": [
                            0,
                            {
                                "Fn::GetAZs": ""
                            }
                        ]
                    },
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": {
                                "Fn::Sub": "${ProjectName}-private-subnet"
                            }
                        }
                    ]
                }
            },
            "SageMakerStudioSecurityGroup": {
                "Type": "AWS::EC2::SecurityGroup",
                "Properties": {
                    "GroupDescription": "Security group for SageMaker Studio Domain",
                    "VpcId": {
                        "Ref": "SageMakerVPC"
                    },
                    "SecurityGroupEgress": [
                        {
                            "IpProtocol": "-1",
                            "CidrIp": "0.0.0.0/0",
                            "Description": "Allow all outbound traffic"
                        }
                    ],
                    "SecurityGroupIngress": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 443,
                            "ToPort": 443,
                            "CidrIp": "10.0.0.0/16",
                            "Description": "Allow HTTPS within VPC"
                        }
                    ],
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": {
                                "Fn::Sub": "${ProjectName}-studio-sg"
                            }
                        }
                    ]
                }
            },
            "SageMakerVPCEndpoint": {
                "Type": "AWS::EC2::VPCEndpoint",
                "Properties": {
                    "VpcId": {
                        "Ref": "SageMakerVPC"
                    },
                    "ServiceName": {
                        "Fn::Sub": "com.amazonaws.${AWS::Region}.sagemaker.api"
                    },
                    "VpcEndpointType": "Interface",
                    "SubnetIds": [
                        {
                            "Ref": "SageMakerPrivateSubnet"
                        }
                    ],
                    "SecurityGroupIds": [
                        {
                            "Ref": "SageMakerStudioSecurityGroup"
                        }
                    ],
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": "*",
                                "Action": [
                                    "sagemaker:*"
                                ],
                                "Resource": "*"
                            }
                        ]
                    }
                }
            }
        }
    
    def _generate_sagemaker_resources(self) -> Dict[str, Any]:
        """Generate SageMaker-specific resources including Studio Domain and Model Package Group."""
        return {
            "SageMakerLogGroup": {
                "Type": "AWS::Logs::LogGroup",
                "Properties": {
                    "LogGroupName": {
                        "Fn::Sub": "/aws/sagemaker/${ProjectName}-${Environment}"
                    },
                    "RetentionInDays": 14
                }
            },
            "SageMakerStudioDomain": {
                "Type": "AWS::SageMaker::Domain",
                "Properties": {
                    "DomainName": {
                        "Fn::Sub": "${ProjectName}-studio-domain-${Environment}"
                    },
                    "AuthMode": "IAM",
                    "DefaultUserSettings": {
                        "ExecutionRole": {
                            "Fn::GetAtt": ["SageMakerExecutionRole", "Arn"]
                        },
                        "SecurityGroups": [
                            {
                                "Ref": "SageMakerStudioSecurityGroup"
                            }
                        ],
                        "SharingSettings": {
                            "NotebookOutputOption": "Allowed",
                            "S3OutputPath": {
                                "Fn::Sub": "s3://${SageMakerS3Bucket}/studio-notebooks/"
                            }
                        }
                    },
                    "VpcId": {
                        "Ref": "SageMakerVPC"
                    },
                    "SubnetIds": [
                        {
                            "Ref": "SageMakerPrivateSubnet"
                        }
                    ],
                    "DomainSettings": {
                        "SecurityGroupIds": [
                            {
                                "Ref": "SageMakerStudioSecurityGroup"
                            }
                        ]
                    }
                },
                "DependsOn": ["SageMakerExecutionRole", "SageMakerVPC", "SageMakerPrivateSubnet"]
            },
            "SageMakerDefaultUserProfile": {
                "Type": "AWS::SageMaker::UserProfile",
                "Properties": {
                    "DomainId": {
                        "Ref": "SageMakerStudioDomain"
                    },
                    "UserProfileName": {
                        "Fn::Sub": "${ProjectName}-default-user"
                    },
                    "UserSettings": {
                        "ExecutionRole": {
                            "Fn::GetAtt": ["SageMakerExecutionRole", "Arn"]
                        }
                    }
                },
                "DependsOn": ["SageMakerStudioDomain"]
            },
            "SageMakerPrivateSpace": {
                "Type": "AWS::SageMaker::Space",
                "Properties": {
                    "DomainId": {
                        "Ref": "SageMakerStudioDomain"
                    },
                    "SpaceName": {
                        "Fn::Sub": "${ProjectName}-private-space"
                    },
                    "OwnershipSettings": {
                        "OwnerUserProfileName": {
                            "Fn::Sub": "${ProjectName}-default-user"
                        }
                    },
                    "SpaceSharingSettings": {
                        "SharingType": "Private"
                    },
                    "SpaceSettings": {
                        "AppType": "JupyterLab",
                        "SpaceStorageSettings": {
                            "EbsStorageSettings": {
                                "EbsVolumeSizeInGb": 20
                            }
                        }
                    }
                },
                "DependsOn": ["SageMakerDefaultUserProfile"]
            },
            "SageMakerModelPackageGroup": {
                "Type": "AWS::SageMaker::ModelPackageGroup",
                "Properties": {
                    "ModelPackageGroupName": {
                        "Fn::Sub": "${ProjectName}-model-package-group"
                    },
                    "ModelPackageGroupDescription": {
                        "Fn::Sub": "Model package group for ${ProjectName} project"
                    },
                    "ModelPackageGroupPolicy": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowModelPackageAccess",
                                "Effect": "Allow",
                                "Principal": {
                                    "AWS": {
                                        "Fn::Sub": "arn:aws:iam::${AWS::AccountId}:root"
                                    }
                                },
                                "Action": [
                                    "sagemaker:DescribeModelPackage",
                                    "sagemaker:ListModelPackages",
                                    "sagemaker:UpdateModelPackage",
                                    "sagemaker:CreateModel"
                                ],
                                "Resource": {
                                    "Fn::Sub": "arn:aws:sagemaker:${AWS::Region}:${AWS::AccountId}:model-package-group/${ProjectName}-model-package-group"
                                }
                            }
                        ]
                    },
                    "Tags": [
                        {
                            "Key": "Project",
                            "Value": {
                                "Ref": "ProjectName"
                            }
                        },
                        {
                            "Key": "Environment",
                            "Value": {
                                "Ref": "Environment"
                            }
                        }
                    ]
                }
            }
        }
    
    def _generate_outputs(self) -> Dict[str, Any]:
        """Generate CloudFormation outputs."""
        return {
            "S3BucketName": {
                "Description": "Name of the S3 bucket for SageMaker artifacts",
                "Value": {
                    "Ref": "SageMakerS3Bucket"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-S3Bucket"
                    }
                }
            },
            "ExecutionRoleArn": {
                "Description": "ARN of the SageMaker execution role",
                "Value": {
                    "Fn::GetAtt": ["SageMakerExecutionRole", "Arn"]
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-ExecutionRole"
                    }
                }
            },
            "LogGroupName": {
                "Description": "Name of the CloudWatch log group",
                "Value": {
                    "Ref": "SageMakerLogGroup"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-LogGroup"
                    }
                }
            },
            "StudioDomainId": {
                "Description": "ID of the SageMaker Studio Domain",
                "Value": {
                    "Ref": "SageMakerStudioDomain"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-StudioDomain"
                    }
                }
            },
            "DefaultUserProfileName": {
                "Description": "Name of the default user profile",
                "Value": {
                    "Ref": "SageMakerDefaultUserProfile"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-DefaultUserProfile"
                    }
                }
            },
            "PrivateSpaceName": {
                "Description": "Name of the private space",
                "Value": {
                    "Ref": "SageMakerPrivateSpace"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-PrivateSpace"
                    }
                }
            },
            "ModelPackageGroupName": {
                "Description": "Name of the model package group",
                "Value": {
                    "Ref": "SageMakerModelPackageGroup"
                },
                "Export": {
                    "Name": {
                        "Fn::Sub": "${AWS::StackName}-ModelPackageGroup"
                    }
                }
            }
        }
    
    def _get_default_parameters(self) -> Dict[str, str]:
        """Get default parameter values for template deployment."""
        return {
            "ProjectName": self.project_name,
            "Environment": "dev",
            "InstanceType": "ml.m5.large",
            "KMSKeyId": ""
        }
    
    def validate_template(self, template: str) -> List[str]:
        """Validate CloudFormation template syntax and best practices."""
        errors = []
        
        try:
            parsed = yaml.safe_load(template)
        except yaml.YAMLError as e:
            errors.append(f"YAML syntax error: {e}")
            return errors
        
        # Check required sections
        required_sections = ["AWSTemplateFormatVersion", "Resources"]
        for section in required_sections:
            if section not in parsed:
                errors.append(f"Missing required section: {section}")
        
        # Validate resources
        if "Resources" in parsed:
            for resource_name, resource in parsed["Resources"].items():
                if "Type" not in resource:
                    errors.append(f"Resource {resource_name} missing Type")
                
                # Check IAM policies have Sid fields
                if resource.get("Type") == "AWS::IAM::Role":
                    policies = resource.get("Properties", {}).get("Policies", [])
                    for policy in policies:
                        statements = policy.get("PolicyDocument", {}).get("Statement", [])
                        for stmt in statements:
                            if "Sid" not in stmt:
                                errors.append(f"IAM policy statement in {resource_name} missing Sid field")
        
        # Validate S3 ARN references
        s3_validation = self.validate_s3_arn_references(parsed)
        errors.extend(s3_validation.s3_arn_errors)
        
        return errors
    
    def validate_s3_arn_references(self, template: Dict[str, Any]) -> CloudFormationValidationResult:
        """
        Validate all S3 ARN references in CloudFormation template.
        
        This method provides comprehensive validation of S3 ARN references throughout
        the CloudFormation template, including:
        - IAM policy statements with S3 resource references
        - CloudFormation intrinsic functions that produce S3 ARNs
        - S3 bucket policy documents
        - Cross-references between S3 resources and other AWS services
        
        Args:
            template: CloudFormation template dictionary
            
        Returns:
            CloudFormationValidationResult with validation details and fixed template
        """
        result = CloudFormationValidationResult(is_valid=True)
        fixed_template = self._deep_copy_template(template)
        
        if "Resources" not in template:
            result.s3_arn_warnings.append("Template contains no Resources section")
            return result
        
        # Track all S3 bucket resources for cross-reference validation
        s3_buckets = self._find_s3_bucket_resources(template)
        
        # Validate IAM roles and their policies
        self._validate_iam_role_s3_references(template, fixed_template, result, s3_buckets)
        
        # Validate S3 bucket policies
        self._validate_s3_bucket_policies(template, fixed_template, result)
        
        # Validate CloudFormation intrinsic functions
        intrinsic_errors = self.validate_cloudformation_intrinsic_functions(fixed_template)
        result.s3_arn_errors.extend(intrinsic_errors)
        
        # Validate cross-references between resources
        cross_ref_errors = self._validate_s3_cross_references(fixed_template, s3_buckets)
        result.s3_arn_errors.extend(cross_ref_errors)
        
        # Final validation check
        result.is_valid = len(result.s3_arn_errors) == 0
        result.fixed_template = fixed_template
        
        return result
    
    def fix_iam_policy_s3_arns(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix S3 ARN formatting in IAM policy documents.
        
        Args:
            policy: IAM policy document
            
        Returns:
            Fixed IAM policy document with proper S3 ARN formatting
        """
        if "Statement" not in policy:
            return policy
        
        import copy
        fixed_policy = copy.deepcopy(policy)
        statements = fixed_policy["Statement"]
        if not isinstance(statements, list):
            statements = [statements]
            fixed_policy["Statement"] = statements
        
        for statement in statements:
            if "Resource" in statement:
                resources = statement["Resource"]
                
                # Handle single resource
                if isinstance(resources, str):
                    if self._is_s3_resource_reference(resources):
                        try:
                            validation_result = validate_s3_arn_comprehensive(resources)
                            if validation_result.corrected_arn != resources:
                                statement["Resource"] = validation_result.corrected_arn
                        except Exception:
                            # If validation fails, try basic fix or leave as-is for CloudFormation intrinsic functions
                            if resources.startswith("aws:s3:::"):
                                # Fix common malformed ARN missing "arn:" prefix
                                statement["Resource"] = f"arn:{resources}"
                            elif resources.startswith("arn:aws:s4:::"):
                                # Fix common typo: s4 instead of s3
                                statement["Resource"] = resources.replace("arn:aws:s4:::", "arn:aws:s3:::")
                
                # Handle list of resources
                elif isinstance(resources, list):
                    fixed_resources = []
                    for resource in resources:
                        if isinstance(resource, str) and self._is_s3_resource_reference(resource):
                            try:
                                validation_result = validate_s3_arn_comprehensive(resource)
                                fixed_resources.append(validation_result.corrected_arn)
                            except Exception:
                                # If validation fails, try basic fix or leave as-is for CloudFormation intrinsic functions
                                if resource.startswith("aws:s3:::"):
                                    # Fix common malformed ARN missing "arn:" prefix
                                    fixed_resources.append(f"arn:{resource}")
                                elif resource.startswith("arn:aws:s4:::"):
                                    # Fix common typo: s4 instead of s3
                                    fixed_resources.append(resource.replace("arn:aws:s4:::", "arn:aws:s3:::"))
                                else:
                                    fixed_resources.append(resource)
                        else:
                            fixed_resources.append(resource)
                    statement["Resource"] = fixed_resources
                
                # Handle CloudFormation intrinsic functions (dict format)
                elif isinstance(resources, dict):
                    # Don't modify CloudFormation intrinsic functions, but validate they produce valid ARNs
                    pass
        
        return fixed_policy
    
    def validate_cloudformation_intrinsic_functions(self, template: Dict[str, Any]) -> List[str]:
        """
        Validate CloudFormation intrinsic functions produce valid S3 ARNs.
        
        Args:
            template: CloudFormation template dictionary
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if "Resources" not in template:
            return errors
        
        for resource_name, resource in template["Resources"].items():
            if resource.get("Type") == "AWS::IAM::Role":
                properties = resource.get("Properties", {})
                policies = properties.get("Policies", [])
                
                for policy in policies:
                    policy_doc = policy.get("PolicyDocument", {})
                    policy_name = policy.get("PolicyName", "Unknown")
                    
                    if "Statement" not in policy_doc:
                        continue
                    
                    statements = policy_doc["Statement"]
                    if not isinstance(statements, list):
                        statements = [statements]
                    
                    for statement in statements:
                        if "Resource" not in statement:
                            continue
                        
                        resources = statement["Resource"]
                        if isinstance(resources, list):
                            for resource_ref in resources:
                                if isinstance(resource_ref, dict):
                                    validation_errors = self._validate_intrinsic_function_s3_arn(
                                        resource_ref, resource_name, policy_name
                                    )
                                    errors.extend(validation_errors)
                        elif isinstance(resources, dict):
                            validation_errors = self._validate_intrinsic_function_s3_arn(
                                resources, resource_name, policy_name
                            )
                            errors.extend(validation_errors)
        
        return errors
    
    def _is_s3_resource_reference(self, resource: str) -> bool:
        """Check if a resource reference is related to S3."""
        if not isinstance(resource, str):
            return False
        
        # Skip CloudFormation intrinsic functions
        if resource.startswith("${") or resource.startswith("!"):
            return False
        
        return (
            resource.startswith("arn:aws:s3:::") or
            resource.startswith("aws:s3:::") or  # Malformed ARN missing "arn:" prefix
            resource.startswith("arn:aws:s4:::") or  # Common typo: s4 instead of s3
            resource.startswith("s3://") or
            # Bucket name or bucket/path without ARN prefix (but not other ARN types)
            (not resource.startswith("arn:") and not resource.startswith("*") and 
             (("/" in resource) or (len(resource) >= 3 and resource.replace("-", "").replace(".", "").isalnum())))
        )
    
    def _validate_policy_s3_arns(self, policy: Dict[str, Any], resource_name: str, policy_name: str) -> List[str]:
        """Validate S3 ARNs in a policy document."""
        errors = []
        
        if "Statement" not in policy:
            return errors
        
        statements = policy["Statement"]
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            if "Resource" not in statement:
                continue
            
            resources = statement["Resource"]
            if isinstance(resources, str):
                if self._is_s3_resource_reference(resources) and not is_valid_s3_arn(resources):
                    errors.append(
                        f"Invalid S3 ARN format in policy '{policy_name}' of resource '{resource_name}': {resources}"
                    )
            elif isinstance(resources, list):
                for resource in resources:
                    if isinstance(resource, str) and self._is_s3_resource_reference(resource) and not is_valid_s3_arn(resource):
                        errors.append(
                            f"Invalid S3 ARN format in policy '{policy_name}' of resource '{resource_name}': {resource}"
                        )
        
        return errors
    
    def _validate_intrinsic_function_s3_arn(self, resource_ref: Dict[str, Any], resource_name: str, policy_name: str) -> List[str]:
        """Validate CloudFormation intrinsic functions that should produce S3 ARNs."""
        errors = []
        
        # Check Fn::Sub patterns that should produce S3 ARNs
        if "Fn::Sub" in resource_ref:
            sub_value = resource_ref["Fn::Sub"]
            if isinstance(sub_value, str):
                # Simple substitution - check if it looks like it will produce a valid S3 ARN
                if "${BucketArn}" in sub_value:
                    # This is likely valid if BucketArn is properly defined
                    if sub_value.startswith("${BucketArn}") and (sub_value == "${BucketArn}" or sub_value.endswith("/*")):
                        # Valid patterns: ${BucketArn} or ${BucketArn}/*
                        pass
                    else:
                        errors.append(
                            f"CloudFormation Fn::Sub in policy '{policy_name}' of resource '{resource_name}' "
                            f"may not produce valid S3 ARN: {sub_value}"
                        )
            elif isinstance(sub_value, list) and len(sub_value) == 2:
                # Substitution with variable map
                template_str = sub_value[0]
                variable_map = sub_value[1]
                if "${BucketArn}" in template_str:
                    # Check if BucketArn is properly defined in the variable map
                    if "BucketArn" in variable_map:
                        bucket_arn_def = variable_map["BucketArn"]
                        if isinstance(bucket_arn_def, dict) and "Fn::GetAtt" in bucket_arn_def:
                            # This looks like a proper S3 bucket ARN reference
                            if template_str.startswith("${BucketArn}") and (template_str == "${BucketArn}" or template_str.endswith("/*")):
                                # Valid patterns: ${BucketArn} or ${BucketArn}/*
                                pass
                            else:
                                errors.append(
                                    f"CloudFormation Fn::Sub in policy '{policy_name}' of resource '{resource_name}' "
                                    f"may not produce valid S3 ARN: {template_str}"
                                )
                        else:
                            errors.append(
                                f"CloudFormation Fn::Sub in policy '{policy_name}' of resource '{resource_name}' "
                                f"BucketArn variable may not produce valid S3 ARN: {bucket_arn_def}"
                            )
                    else:
                        errors.append(
                            f"CloudFormation Fn::Sub in policy '{policy_name}' of resource '{resource_name}' "
                            f"references undefined BucketArn variable: {template_str}"
                        )
        
        # Check Fn::GetAtt for S3 bucket ARNs
        elif "Fn::GetAtt" in resource_ref:
            get_att = resource_ref["Fn::GetAtt"]
            if isinstance(get_att, list) and len(get_att) == 2:
                resource_logical_id, attribute = get_att
                if attribute == "Arn" and "S3" in resource_logical_id:
                    # This should produce a valid S3 bucket ARN - no error
                    pass
        
        return errors
    
    def _deep_copy_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of the CloudFormation template."""
        import copy
        return copy.deepcopy(template)
    
    def _find_s3_bucket_resources(self, template: Dict[str, Any]) -> Dict[str, str]:
        """
        Find all S3 bucket resources in the template.
        
        Returns:
            Dictionary mapping logical resource ID to bucket name/reference
        """
        s3_buckets = {}
        
        if "Resources" not in template:
            return s3_buckets
        
        for resource_name, resource in template["Resources"].items():
            if resource.get("Type") == "AWS::S3::Bucket":
                properties = resource.get("Properties", {})
                bucket_name = properties.get("BucketName", resource_name)
                s3_buckets[resource_name] = bucket_name
        
        return s3_buckets
    
    def _validate_iam_role_s3_references(self, template: Dict[str, Any], fixed_template: Dict[str, Any], 
                                       result: CloudFormationValidationResult, s3_buckets: Dict[str, str]):
        """Validate S3 references in IAM roles and policies."""
        if "Resources" not in template:
            return
        
        for resource_name, resource in template["Resources"].items():
            if resource.get("Type") == "AWS::IAM::Role":
                properties = resource.get("Properties", {})
                policies = properties.get("Policies", [])
                
                for policy_idx, policy in enumerate(policies):
                    policy_doc = policy.get("PolicyDocument", {})
                    policy_name = policy.get("PolicyName", "Unknown")
                    
                    # Create a deep copy for comparison
                    import copy
                    original_policy_doc = copy.deepcopy(policy_doc)
                    fixed_policy_doc = self.fix_iam_policy_s3_arns(policy_doc)
                    
                    # Check if any fixes were applied
                    if fixed_policy_doc != original_policy_doc:
                        result.s3_arn_warnings.append(
                            f"Fixed S3 ARN references in IAM policy '{policy_name}' "
                            f"for resource '{resource_name}'"
                        )
                        # Update the fixed template
                        fixed_template["Resources"][resource_name]["Properties"]["Policies"][policy_idx]["PolicyDocument"] = fixed_policy_doc
                    
                    # Validate the fixed policy with enhanced error messages
                    validation_errors = self._validate_policy_s3_arns_comprehensive(
                        fixed_policy_doc, resource_name, policy_name, s3_buckets
                    )
                    result.s3_arn_errors.extend(validation_errors)
    
    def _validate_s3_bucket_policies(self, template: Dict[str, Any], fixed_template: Dict[str, Any], 
                                   result: CloudFormationValidationResult):
        """Validate S3 bucket policies for proper ARN references."""
        if "Resources" not in template:
            return
        
        for resource_name, resource in template["Resources"].items():
            if resource.get("Type") == "AWS::S3::Bucket":
                properties = resource.get("Properties", {})
                
                # Check bucket policy if present
                if "BucketPolicy" in properties:
                    bucket_policy = properties["BucketPolicy"]
                    if isinstance(bucket_policy, dict) and "PolicyDocument" in bucket_policy:
                        policy_doc = bucket_policy["PolicyDocument"]
                        
                        # Validate S3 ARNs in bucket policy
                        validation_errors = self._validate_policy_s3_arns_comprehensive(
                            policy_doc, resource_name, "BucketPolicy", {}
                        )
                        result.s3_arn_errors.extend(validation_errors)
                
                # Check notification configurations
                if "NotificationConfiguration" in properties:
                    notification_config = properties["NotificationConfiguration"]
                    self._validate_notification_s3_references(
                        notification_config, resource_name, result
                    )
    
    def _validate_s3_cross_references(self, template: Dict[str, Any], s3_buckets: Dict[str, str]) -> List[str]:
        """Validate cross-references between S3 resources and other AWS services."""
        errors = []
        
        if "Resources" not in template:
            return errors
        
        for resource_name, resource in template["Resources"].items():
            resource_type = resource.get("Type", "")
            
            # Check SageMaker resources that reference S3
            if resource_type.startswith("AWS::SageMaker::"):
                properties = resource.get("Properties", {})
                
                # Check for S3 references in SageMaker resources
                s3_refs = self._extract_s3_references_from_properties(properties)
                for s3_ref in s3_refs:
                    # Skip CloudFormation intrinsic functions and valid S3 URIs
                    if (s3_ref.startswith("s3://") or 
                        s3_ref.startswith("${") or 
                        isinstance(s3_ref, dict) or
                        s3_ref.startswith("arn:aws:s3:::")):
                        continue
                    
                    if not self._is_valid_s3_reference(s3_ref, s3_buckets):
                        errors.append(
                            f"Invalid S3 reference in {resource_type} '{resource_name}': {s3_ref}. "
                            f"Ensure the S3 bucket exists in the template or use proper ARN format."
                        )
            
            # Check Lambda functions that might reference S3
            elif resource_type == "AWS::Lambda::Function":
                properties = resource.get("Properties", {})
                
                # Check environment variables for S3 references
                env_vars = properties.get("Environment", {}).get("Variables", {})
                for var_name, var_value in env_vars.items():
                    if isinstance(var_value, str) and self._looks_like_s3_reference(var_value):
                        if not self._is_valid_s3_reference(var_value, s3_buckets):
                            errors.append(
                                f"Invalid S3 reference in Lambda function '{resource_name}' "
                                f"environment variable '{var_name}': {var_value}"
                            )
        
        return errors
    
    def _validate_policy_s3_arns_comprehensive(self, policy: Dict[str, Any], resource_name: str, 
                                             policy_name: str, s3_buckets: Dict[str, str]) -> List[str]:
        """
        Comprehensive validation of S3 ARNs in a policy document with specific error messages.
        
        Args:
            policy: IAM policy document
            resource_name: Name of the resource containing the policy
            policy_name: Name of the policy
            s3_buckets: Dictionary of S3 buckets in the template
            
        Returns:
            List of specific validation error messages
        """
        errors = []
        
        if "Statement" not in policy:
            return errors
        
        statements = policy["Statement"]
        if not isinstance(statements, list):
            statements = [statements]
        
        for stmt_idx, statement in enumerate(statements):
            if "Resource" not in statement:
                continue
            
            resources = statement["Resource"]
            if isinstance(resources, str):
                resources = [resources]
            elif not isinstance(resources, list):
                continue
            
            for res_idx, resource in enumerate(resources):
                if isinstance(resource, str) and self._is_s3_resource_reference(resource):
                    # Validate S3 ARN format
                    if not is_valid_s3_arn(resource):
                        errors.append(
                            f"Malformed S3 ARN in policy '{policy_name}' of resource '{resource_name}', "
                            f"statement {stmt_idx}, resource {res_idx}: '{resource}'. "
                            f"Expected format: 'arn:aws:s3:::bucket-name' or 'arn:aws:s3:::bucket-name/*'"
                        )
                    
                    # Check for common mistakes
                    if resource.startswith("aws:s3:::"):
                        errors.append(
                            f"Missing 'arn:' prefix in S3 ARN in policy '{policy_name}' of resource '{resource_name}': "
                            f"'{resource}' should be 'arn:{resource}'"
                        )
                    elif resource.startswith("arn:aws:s4:::"):
                        errors.append(
                            f"Incorrect service name in ARN in policy '{policy_name}' of resource '{resource_name}': "
                            f"'{resource}' should use 's3' not 's4'"
                        )
                    elif resource.startswith("s3://"):
                        errors.append(
                            f"S3 URI format not allowed in IAM policy in '{policy_name}' of resource '{resource_name}': "
                            f"'{resource}' should be converted to ARN format 'arn:aws:s3:::bucket-name'"
                        )
                    
                    # Validate bucket name format if it's a bucket ARN
                    if resource.startswith("arn:aws:s3:::") and "/" not in resource[14:]:
                        bucket_name = resource[14:]  # Remove "arn:aws:s3:::" prefix
                        if not self._is_valid_bucket_name(bucket_name):
                            errors.append(
                                f"Invalid S3 bucket name in ARN in policy '{policy_name}' of resource '{resource_name}': "
                                f"'{bucket_name}' does not follow S3 bucket naming conventions"
                            )
                
                elif isinstance(resource, dict):
                    # Validate CloudFormation intrinsic functions
                    intrinsic_errors = self._validate_intrinsic_function_s3_arn(
                        resource, resource_name, policy_name
                    )
                    errors.extend(intrinsic_errors)
        
        return errors
    
    def _validate_notification_s3_references(self, notification_config: Dict[str, Any], 
                                           resource_name: str, result: CloudFormationValidationResult):
        """Validate S3 references in bucket notification configurations."""
        # Check Lambda configurations
        lambda_configs = notification_config.get("LambdaConfigurations", [])
        for config in lambda_configs:
            if "Function" in config:
                function_ref = config["Function"]
                if isinstance(function_ref, str) and self._looks_like_s3_reference(function_ref):
                    result.s3_arn_warnings.append(
                        f"S3 bucket '{resource_name}' notification configuration references "
                        f"what appears to be an S3 resource as Lambda function: {function_ref}"
                    )
        
        # Check SNS topic configurations
        topic_configs = notification_config.get("TopicConfigurations", [])
        for config in topic_configs:
            if "Topic" in config:
                topic_ref = config["Topic"]
                if isinstance(topic_ref, str) and self._looks_like_s3_reference(topic_ref):
                    result.s3_arn_warnings.append(
                        f"S3 bucket '{resource_name}' notification configuration references "
                        f"what appears to be an S3 resource as SNS topic: {topic_ref}"
                    )
    
    def _extract_s3_references_from_properties(self, properties: Dict[str, Any]) -> List[str]:
        """Extract potential S3 references from resource properties."""
        s3_refs = []
        
        def extract_from_value(value):
            if isinstance(value, str):
                # Only extract obvious S3 references, not policy versions or other strings
                if (value.startswith("arn:aws:s3:::") or 
                    value.startswith("s3://") or 
                    value.startswith("aws:s3:::")):
                    s3_refs.append(value)
            elif isinstance(value, dict):
                # Skip CloudFormation intrinsic functions
                if not any(key.startswith("Fn::") or key == "Ref" for key in value.keys()):
                    for v in value.values():
                        extract_from_value(v)
            elif isinstance(value, list):
                for item in value:
                    extract_from_value(item)
        
        extract_from_value(properties)
        return s3_refs
    
    def _is_valid_s3_reference(self, reference: str, s3_buckets: Dict[str, str]) -> bool:
        """Check if an S3 reference is valid within the template context."""
        # Valid S3 ARN
        if is_valid_s3_arn(reference):
            return True
        
        # Valid S3 URI (allowed for SageMaker)
        if reference.startswith("s3://"):
            return True
        
        # CloudFormation intrinsic function
        if reference.startswith("${") or reference.startswith("!"):
            return True
        
        # Reference to a bucket defined in the template
        if reference in s3_buckets:
            return True
        
        # Check if it's a bucket name that exists in the template
        for bucket_logical_id, bucket_name in s3_buckets.items():
            if isinstance(bucket_name, str) and bucket_name == reference:
                return True
        
        return False
    
    def _looks_like_s3_reference(self, value: str) -> bool:
        """Check if a string looks like it might be an S3 reference."""
        if not isinstance(value, str):
            return False
        
        return (
            value.startswith("arn:aws:s3:::") or
            value.startswith("s3://") or
            value.startswith("aws:s3:::") or
            # Bucket name pattern (simple heuristic)
            (len(value) >= 3 and len(value) <= 63 and 
             value.replace("-", "").replace(".", "").isalnum() and
             not value.startswith("arn:") and
             ("." in value or "-" in value))
        )
    
    def _is_valid_bucket_name(self, bucket_name: str) -> bool:
        """Validate S3 bucket name according to AWS naming rules."""
        if not bucket_name or len(bucket_name) < 3 or len(bucket_name) > 63:
            return False
        
        # Must start and end with lowercase letter or number
        if not (bucket_name[0].islower() or bucket_name[0].isdigit()):
            return False
        if not (bucket_name[-1].islower() or bucket_name[-1].isdigit()):
            return False
        
        # Can only contain lowercase letters, numbers, hyphens, and periods
        allowed_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-.')
        if not all(c in allowed_chars for c in bucket_name):
            return False
        
        # Cannot have consecutive periods or hyphens
        if '..' in bucket_name or '--' in bucket_name:
            return False
        
        # Cannot be formatted as an IP address
        parts = bucket_name.split('.')
        if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
            return False
        
        return True