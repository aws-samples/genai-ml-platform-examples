"""
CloudFormation utilities for SageMigrator
"""

import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class CloudFormationStackManager:
    """Manages CloudFormation stack operations and output retrieval"""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the CloudFormation stack manager
        
        Args:
            region: AWS region for CloudFormation operations
        """
        self.region = region
        try:
            self.cf_client = boto3.client('cloudformation', region_name=region)
        except Exception as e:
            raise ValueError(f"Failed to initialize CloudFormation client: {e}")
    
    def get_stack_outputs(self, stack_name: str) -> Dict[str, str]:
        """
        Get all outputs from a CloudFormation stack
        
        Args:
            stack_name: Name of the CloudFormation stack
            
        Returns:
            Dictionary mapping output keys to output values
        """
        try:
            response = self.cf_client.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            stack_outputs = {}
            if 'Outputs' in stack:
                for output_item in stack['Outputs']:
                    stack_outputs[output_item['OutputKey']] = output_item['OutputValue']
            
            logger.info(f"Retrieved {len(stack_outputs)} outputs from stack {stack_name}")
            return stack_outputs
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                logger.error(f"Stack {stack_name} does not exist")
                raise ValueError(f"CloudFormation stack '{stack_name}' not found")
            else:
                logger.error(f"Failed to get stack outputs: {e}")
                raise ValueError(f"Failed to retrieve stack outputs: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting stack outputs: {e}")
            raise ValueError(f"Unexpected error: {e}")
    
    def get_execution_role_arn(self, stack_name: str) -> Optional[str]:
        """
        Get the SageMaker execution role ARN from CloudFormation stack outputs
        
        Args:
            stack_name: Name of the CloudFormation stack
            
        Returns:
            SageMaker execution role ARN if found, None otherwise
        """
        try:
            outputs = self.get_stack_outputs(stack_name)
            
            # Look for execution role in common output key names
            role_keys = ['ExecutionRoleArn', 'SageMakerExecutionRoleArn', 'ExecutionRole']
            
            for key in role_keys:
                if key in outputs:
                    role_arn = outputs[key]
                    logger.info(f"Found execution role ARN: {role_arn}")
                    return role_arn
            
            logger.warning(f"No execution role found in stack outputs. Available outputs: {list(outputs.keys())}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get execution role from stack: {e}")
            return None
    
    def get_s3_bucket_name(self, stack_name: str) -> Optional[str]:
        """
        Get the S3 bucket name from CloudFormation stack outputs
        
        Args:
            stack_name: Name of the CloudFormation stack
            
        Returns:
            S3 bucket name if found, None otherwise
        """
        try:
            outputs = self.get_stack_outputs(stack_name)
            
            # Look for S3 bucket in common output key names
            bucket_keys = ['S3BucketName', 'SageMakerS3Bucket', 'BucketName']
            
            for key in bucket_keys:
                if key in outputs:
                    bucket_name = outputs[key]
                    logger.info(f"Found S3 bucket name: {bucket_name}")
                    return bucket_name
            
            logger.warning(f"No S3 bucket found in stack outputs. Available outputs: {list(outputs.keys())}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get S3 bucket from stack: {e}")
            return None
    
    def list_stacks_by_prefix(self, prefix: str) -> list:
        """
        List CloudFormation stacks that start with a given prefix
        
        Args:
            prefix: Stack name prefix to search for
            
        Returns:
            List of stack names matching the prefix
        """
        try:
            paginator = self.cf_client.get_paginator('list_stacks')
            stack_names = []
            
            for page in paginator.paginate(StackStatusFilter=[
                'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'
            ]):
                for stack in page['StackSummaries']:
                    if stack['StackName'].startswith(prefix):
                        stack_names.append(stack['StackName'])
            
            logger.info(f"Found {len(stack_names)} stacks with prefix '{prefix}'")
            return stack_names
            
        except Exception as e:
            logger.error(f"Failed to list stacks: {e}")
            return []
    
    def find_sagemigrator_stack(self, project_name: str = None) -> Optional[str]:
        """
        Find the SageMigrator CloudFormation stack for a project
        
        Args:
            project_name: Optional project name to search for
            
        Returns:
            Stack name if found, None otherwise
        """
        try:
            # Common stack name patterns for SageMigrator
            prefixes = []
            if project_name:
                prefixes.extend([
                    f"{project_name}-sagemigrator",
                    f"sagemigrator-{project_name}",
                    project_name
                ])
            
            # Default prefixes
            prefixes.extend([
                "sagemigrator",
                "sagemaker-migration",
                "ml-migration"
            ])
            
            for prefix in prefixes:
                stacks = self.list_stacks_by_prefix(prefix)
                if stacks:
                    # Return the first matching stack
                    stack_name = stacks[0]
                    logger.info(f"Found SageMigrator stack: {stack_name}")
                    return stack_name
            
            logger.warning("No SageMigrator CloudFormation stack found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find SageMigrator stack: {e}")
            return None


def get_deployment_resources(stack_name: str = None, project_name: str = None, region: str = "us-east-1") -> Dict[str, Optional[str]]:
    """
    Get deployment resources (role ARN, S3 bucket) from CloudFormation stack
    
    Args:
        stack_name: Specific stack name to query
        project_name: Project name to search for stack
        region: AWS region
        
    Returns:
        Dictionary with 'role_arn', 'bucket_name', and 'stack_name' keys
    """
    try:
        cf_manager = CloudFormationStackManager(region)
        
        # Find stack if not provided
        if not stack_name:
            stack_name = cf_manager.find_sagemigrator_stack(project_name)
            if not stack_name:
                return {
                    'role_arn': None,
                    'bucket_name': None,
                    'stack_name': None,
                    'error': 'No SageMigrator CloudFormation stack found'
                }
        
        # Get resources from stack
        role_arn = cf_manager.get_execution_role_arn(stack_name)
        bucket_name = cf_manager.get_s3_bucket_name(stack_name)
        
        return {
            'role_arn': role_arn,
            'bucket_name': bucket_name,
            'stack_name': stack_name,
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Failed to get deployment resources: {e}")
        return {
            'role_arn': None,
            'bucket_name': None,
            'stack_name': None,
            'error': str(e)
        }


def validate_stack_resources(stack_name: str, region: str = "us-east-1") -> Dict[str, any]:
    """
    Validate that required resources exist in the CloudFormation stack
    
    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        
    Returns:
        Validation result dictionary
    """
    try:
        cf_manager = CloudFormationStackManager(region)
        outputs = cf_manager.get_stack_outputs(stack_name)
        
        # Check for required outputs
        required_outputs = ['ExecutionRoleArn', 'S3BucketName']
        missing_outputs = []
        
        for output_key in required_outputs:
            if output_key not in outputs:
                missing_outputs.append(output_key)
        
        return {
            'valid': len(missing_outputs) == 0,
            'outputs': outputs,
            'missing_outputs': missing_outputs,
            'stack_name': stack_name
        }
        
    except Exception as e:
        return {
            'valid': False,
            'outputs': {},
            'missing_outputs': required_outputs,
            'stack_name': stack_name,
            'error': str(e)
        }