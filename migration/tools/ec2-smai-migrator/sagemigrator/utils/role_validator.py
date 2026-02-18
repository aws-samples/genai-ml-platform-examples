"""
IAM Role validation and discovery utilities for SageMigrator
"""

import boto3
import json
from typing import List, Dict, Optional, Tuple
from botocore.exceptions import ClientError, NoCredentialsError


class SageMakerRoleValidator:
    """Validates and discovers SageMaker execution roles"""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the role validator
        
        Args:
            region: AWS region for SageMaker operations
        """
        self.region = region
        try:
            self.iam_client = boto3.client('iam')
            self.sts_client = boto3.client('sts')
            self.sagemaker_client = boto3.client('sagemaker', region_name=region)
        except NoCredentialsError:
            raise ValueError("AWS credentials not configured. Please run 'aws configure' or set environment variables.")
    
    def get_account_id(self) -> str:
        """Get the current AWS account ID"""
        try:
            return self.sts_client.get_caller_identity()['Account']
        except ClientError as e:
            raise ValueError(f"Failed to get account ID: {e}")
    
    def validate_role_exists(self, role_arn: str) -> bool:
        """
        Check if an IAM role exists and is accessible
        
        Args:
            role_arn: Full ARN of the IAM role
            
        Returns:
            True if role exists and is accessible
        """
        try:
            # Extract role name from ARN
            role_name = role_arn.split('/')[-1]
            self.iam_client.get_role(RoleName=role_name)
            return True
        except ClientError:
            return False
    
    def validate_sagemaker_permissions(self, role_arn: str) -> Tuple[bool, List[str]]:
        """
        Validate that a role has necessary SageMaker permissions
        
        Args:
            role_arn: Full ARN of the IAM role
            
        Returns:
            Tuple of (has_permissions, missing_permissions)
        """
        try:
            role_name = role_arn.split('/')[-1]
            role = self.iam_client.get_role(RoleName=role_name)
            
            # Check trust policy allows SageMaker
            trust_policy = role['Role']['AssumeRolePolicyDocument']
            sagemaker_trusted = False
            
            for statement in trust_policy.get('Statement', []):
                if statement.get('Effect') == 'Allow':
                    principal = statement.get('Principal', {})
                    if isinstance(principal, dict):
                        service = principal.get('Service', [])
                        if isinstance(service, str):
                            service = [service]
                        if 'sagemaker.amazonaws.com' in service:
                            sagemaker_trusted = True
                            break
            
            if not sagemaker_trusted:
                return False, ['SageMaker service trust relationship']
            
            # Check attached policies
            attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
            policy_arns = [p['PolicyArn'] for p in attached_policies['AttachedPolicies']]
            
            # Check for SageMaker execution policy
            sagemaker_policy_found = any(
                'SageMakerFullAccess' in arn or 'SageMakerExecutionRole' in arn 
                for arn in policy_arns
            )
            
            missing_permissions = []
            if not sagemaker_policy_found:
                missing_permissions.append('SageMaker execution permissions')
            
            return len(missing_permissions) == 0, missing_permissions
            
        except ClientError as e:
            return False, [f'Role validation error: {e}']
    
    def discover_sagemaker_roles(self) -> List[Dict[str, str]]:
        """
        Discover existing SageMaker-compatible roles in the account
        
        Returns:
            List of role information dictionaries
        """
        roles = []
        
        try:
            paginator = self.iam_client.get_paginator('list_roles')
            
            for page in paginator.paginate():
                for role in page['Roles']:
                    role_name = role['RoleName']
                    role_arn = role['Arn']
                    
                    # Check if role has SageMaker trust relationship
                    trust_policy = role['AssumeRolePolicyDocument']
                    for statement in trust_policy.get('Statement', []):
                        if statement.get('Effect') == 'Allow':
                            principal = statement.get('Principal', {})
                            if isinstance(principal, dict):
                                service = principal.get('Service', [])
                                if isinstance(service, str):
                                    service = [service]
                                if 'sagemaker.amazonaws.com' in service:
                                    # Check permissions
                                    has_perms, missing = self.validate_sagemaker_permissions(role_arn)
                                    
                                    roles.append({
                                        'name': role_name,
                                        'arn': role_arn,
                                        'has_permissions': has_perms,
                                        'missing_permissions': missing,
                                        'created': role['CreateDate'].isoformat()
                                    })
                                    break
        
        except ClientError as e:
            print(f"Warning: Could not list roles: {e}")
        
        return roles
    
    def suggest_role_creation(self, project_name: str) -> Dict[str, str]:
        """
        Generate role creation suggestions
        
        Args:
            project_name: Name of the project for role naming
            
        Returns:
            Dictionary with role creation information
        """
        account_id = self.get_account_id()
        role_name = f"{project_name}-SageMaker-ExecutionRole"
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sagemaker.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        return {
            'role_name': role_name,
            'role_arn': role_arn,
            'trust_policy': json.dumps(trust_policy, indent=2),
            'managed_policies': [
                'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess'
            ],
            'cli_command': f"""
# Create the IAM role
aws iam create-role \\
    --role-name {role_name} \\
    --assume-role-policy-document '{json.dumps(trust_policy)}'

# Attach SageMaker policy
aws iam attach-role-policy \\
    --role-name {role_name} \\
    --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
""".strip()
        }
    
    def get_default_sagemaker_role(self) -> Optional[str]:
        """
        Try to find a default SageMaker role using SageMaker's built-in method
        
        Returns:
            Role ARN if found, None otherwise
        """
        try:
            import sagemaker
            session = sagemaker.Session(boto3.Session(region_name=self.region))
            return session.get_execution_role()
        except Exception:
            return None
    
    def validate_and_suggest_role(self, role_arn: Optional[str] = None, project_name: str = "sagemigrator") -> Dict[str, any]:
        """
        Comprehensive role validation and suggestion
        
        Args:
            role_arn: Optional role ARN to validate
            project_name: Project name for role suggestions
            
        Returns:
            Dictionary with validation results and suggestions
        """
        result = {
            'valid': False,
            'role_arn': None,
            'issues': [],
            'suggestions': [],
            'available_roles': [],
            'creation_guide': None
        }
        
        # If no role provided, try to discover one
        if not role_arn:
            # Try SageMaker's default role discovery
            default_role = self.get_default_sagemaker_role()
            if default_role:
                role_arn = default_role
                result['suggestions'].append(f"Found SageMaker default role: {role_arn}")
        
        # Validate the role if we have one
        if role_arn:
            if self.validate_role_exists(role_arn):
                has_perms, missing = self.validate_sagemaker_permissions(role_arn)
                if has_perms:
                    result['valid'] = True
                    result['role_arn'] = role_arn
                else:
                    result['issues'].extend(missing)
                    result['suggestions'].append(f"Role {role_arn} exists but missing permissions: {', '.join(missing)}")
            else:
                result['issues'].append(f"Role {role_arn} does not exist or is not accessible")
        
        # Discover available roles
        available_roles = self.discover_sagemaker_roles()
        result['available_roles'] = available_roles
        
        # If no valid role found, suggest alternatives
        if not result['valid']:
            if available_roles:
                valid_roles = [r for r in available_roles if r['has_permissions']]
                if valid_roles:
                    best_role = valid_roles[0]
                    result['suggestions'].append(f"Use existing role: {best_role['arn']}")
                    result['role_arn'] = best_role['arn']
                    result['valid'] = True
                else:
                    result['suggestions'].append("Found SageMaker roles but they need additional permissions")
            
            # Provide role creation guide
            result['creation_guide'] = self.suggest_role_creation(project_name)
            result['suggestions'].append("Create a new SageMaker execution role (see creation_guide)")
        
        return result


def validate_pipeline_role(role_arn: Optional[str] = None, project_name: str = "sagemigrator", region: str = "us-east-1") -> bool:
    """
    Quick validation function for pipeline execution
    
    Args:
        role_arn: Optional role ARN to validate
        project_name: Project name for role suggestions
        region: AWS region
        
    Returns:
        True if a valid role is available, False otherwise
    """
    try:
        validator = SageMakerRoleValidator(region)
        result = validator.validate_and_suggest_role(role_arn, project_name)
        
        if result['valid']:
            print(f"✅ Using SageMaker role: {result['role_arn']}")
            return True
        else:
            print("❌ No valid SageMaker execution role found")
            
            if result['issues']:
                print("Issues:")
                for issue in result['issues']:
                    print(f"   - {issue}")
            
            if result['suggestions']:
                print("\\nSuggestions:")
                for suggestion in result['suggestions']:
                    print(f"   - {suggestion}")
            
            if result['creation_guide']:
                guide = result['creation_guide']
                print(f"\\n🔧 Create a new role:")
                print(f"Role name: {guide['role_name']}")
                print(f"Role ARN: {guide['role_arn']}")
                print(f"\\nCLI commands:")
                print(guide['cli_command'])
            
            return False
            
    except Exception as e:
        print(f"❌ Role validation failed: {e}")
        return False


def discover_and_select_role(project_name: str = "sagemigrator", region: str = "us-east-1") -> Optional[str]:
    """
    Interactive role discovery and selection
    
    Args:
        project_name: Project name for role suggestions
        region: AWS region
        
    Returns:
        Selected role ARN or None if no valid role found
    """
    try:
        validator = SageMakerRoleValidator(region)
        result = validator.validate_and_suggest_role(None, project_name)
        
        if result['valid']:
            return result['role_arn']
        
        # If multiple roles available, could implement selection logic here
        available_roles = [r for r in result['available_roles'] if r['has_permissions']]
        if available_roles:
            return available_roles[0]['arn']
        
        return None
        
    except Exception:
        return None