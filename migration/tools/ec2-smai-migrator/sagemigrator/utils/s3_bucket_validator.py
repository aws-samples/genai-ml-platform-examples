"""
S3 bucket validation and management utilities for SageMigrator
"""

import boto3
import json
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError, NoCredentialsError


class S3BucketValidator:
    """Validates and manages S3 buckets for SageMaker pipelines"""
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the S3 bucket validator
        
        Args:
            region: AWS region for S3 operations
        """
        self.region = region
        try:
            self.s3_client = boto3.client('s3', region_name=region)
            self.sts_client = boto3.client('sts')
        except NoCredentialsError:
            raise ValueError("AWS credentials not configured. Please run 'aws configure' or set environment variables.")
    
    def get_account_id(self) -> str:
        """Get the current AWS account ID"""
        try:
            return self.sts_client.get_caller_identity()['Account']
        except ClientError as e:
            raise ValueError(f"Failed to get account ID: {e}")
    
    def validate_bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if an S3 bucket exists and is accessible
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            True if bucket exists and is accessible
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            elif error_code == '403':
                # Bucket exists but no access
                return False
            else:
                return False
    
    def validate_bucket_permissions(self, bucket_name: str) -> Tuple[bool, List[str]]:
        """
        Validate that we have necessary permissions on the bucket
        
        Args:
            bucket_name: Name of the S3 bucket
            
        Returns:
            Tuple of (has_permissions, missing_permissions)
        """
        if not self.validate_bucket_exists(bucket_name):
            return False, ['Bucket does not exist']
        
        missing_permissions = []
        
        # Test read permission
        try:
            self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        except ClientError:
            missing_permissions.append('s3:ListBucket')
        
        # Test write permission (try to put a small test object)
        try:
            test_key = 'sagemigrator-test-write-permission'
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b'test'
            )
            # Clean up test object
            try:
                self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            except ClientError:
                pass  # Ignore cleanup errors
        except ClientError:
            missing_permissions.append('s3:PutObject')
        
        return len(missing_permissions) == 0, missing_permissions
    
    def generate_bucket_name(self, project_name: str, account_id: Optional[str] = None) -> str:
        """
        Generate a standard bucket name for the project
        
        Args:
            project_name: Name of the project
            account_id: AWS account ID (will be auto-detected if not provided)
            
        Returns:
            Generated bucket name
        """
        if not account_id:
            account_id = self.get_account_id()
        
        # Ensure project name is bucket-name compliant
        clean_project_name = project_name.lower().replace('_', '-')
        return f"{clean_project_name}-sagemaker-bucket-{account_id}-{self.region}"
    
    def create_bucket(self, bucket_name: str, enable_versioning: bool = True, enable_encryption: bool = True) -> bool:
        """
        Create an S3 bucket with SageMaker-appropriate settings
        
        Args:
            bucket_name: Name of the bucket to create
            enable_versioning: Whether to enable versioning
            enable_encryption: Whether to enable server-side encryption
            
        Returns:
            True if bucket was created successfully
        """
        try:
            # Create bucket
            if self.region == 'us-east-1':
                # us-east-1 doesn't need LocationConstraint
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Enable versioning if requested
            if enable_versioning:
                self.s3_client.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
            
            # Enable encryption if requested
            if enable_encryption:
                self.s3_client.put_bucket_encryption(
                    Bucket=bucket_name,
                    ServerSideEncryptionConfiguration={
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'AES256'
                                },
                                'BucketKeyEnabled': True
                            }
                        ]
                    }
                )
            
            # Set public access block (security best practice)
            self.s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            
            return True
            
        except ClientError as e:
            print(f"Failed to create bucket {bucket_name}: {e}")
            return False
    
    def setup_bucket_lifecycle(self, bucket_name: str) -> bool:
        """
        Set up lifecycle policies for cost optimization
        
        Args:
            bucket_name: Name of the bucket
            
        Returns:
            True if lifecycle was configured successfully
        """
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'SageMakerArtifactLifecycle',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': ''},
                        'Transitions': [
                            {
                                'Days': 30,
                                'StorageClass': 'STANDARD_IA'
                            },
                            {
                                'Days': 90,
                                'StorageClass': 'GLACIER'
                            }
                        ],
                        'AbortIncompleteMultipartUpload': {
                            'DaysAfterInitiation': 7
                        }
                    }
                ]
            }
            
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            
            return True
            
        except ClientError as e:
            print(f"Failed to set lifecycle policy for {bucket_name}: {e}")
            return False
    
    def validate_and_setup_bucket(self, bucket_name: Optional[str] = None, project_name: str = "sagemigrator") -> Dict[str, any]:
        """
        Comprehensive bucket validation and setup
        
        Args:
            bucket_name: Optional bucket name to validate
            project_name: Project name for bucket generation
            
        Returns:
            Dictionary with validation results and bucket information
        """
        result = {
            'valid': False,
            'bucket_name': None,
            'created': False,
            'issues': [],
            'suggestions': [],
            'cli_commands': []
        }
        
        # Generate bucket name if not provided
        if not bucket_name:
            bucket_name = self.generate_bucket_name(project_name)
            result['suggestions'].append(f"Generated bucket name: {bucket_name}")
        
        result['bucket_name'] = bucket_name
        
        # Check if bucket exists
        if self.validate_bucket_exists(bucket_name):
            # Bucket exists, check permissions
            has_perms, missing = self.validate_bucket_permissions(bucket_name)
            if has_perms:
                result['valid'] = True
                result['suggestions'].append(f"Using existing bucket: {bucket_name}")
            else:
                result['issues'].extend(missing)
                result['suggestions'].append(f"Bucket {bucket_name} exists but missing permissions: {', '.join(missing)}")
        else:
            # Bucket doesn't exist, try to create it
            result['suggestions'].append(f"Bucket {bucket_name} does not exist")
            
            try:
                if self.create_bucket(bucket_name):
                    result['valid'] = True
                    result['created'] = True
                    result['suggestions'].append(f"✅ Created bucket: {bucket_name}")
                    
                    # Set up lifecycle policies
                    if self.setup_bucket_lifecycle(bucket_name):
                        result['suggestions'].append("✅ Configured lifecycle policies for cost optimization")
                else:
                    result['issues'].append(f"Failed to create bucket {bucket_name}")
                    
                    # Provide CLI commands for manual creation
                    result['cli_commands'] = [
                        f"# Create S3 bucket",
                        f"aws s3 mb s3://{bucket_name} --region {self.region}",
                        f"",
                        f"# Enable versioning",
                        f"aws s3api put-bucket-versioning --bucket {bucket_name} --versioning-configuration Status=Enabled",
                        f"",
                        f"# Enable encryption",
                        f"aws s3api put-bucket-encryption --bucket {bucket_name} --server-side-encryption-configuration '{{",
                        f'    "Rules": [{{',
                        f'        "ApplyServerSideEncryptionByDefault": {{',
                        f'            "SSEAlgorithm": "AES256"',
                        f'        }}',
                        f'    }}]',
                        f"}}'",
                    ]
                    
            except Exception as e:
                result['issues'].append(f"Bucket creation failed: {e}")
                result['cli_commands'] = [
                    f"# Create S3 bucket manually",
                    f"aws s3 mb s3://{bucket_name} --region {self.region}"
                ]
        
        return result


def validate_pipeline_bucket(bucket_name: Optional[str] = None, project_name: str = "sagemigrator", region: str = "us-east-1") -> bool:
    """
    Quick validation function for pipeline execution
    
    Args:
        bucket_name: Optional bucket name to validate
        project_name: Project name for bucket generation
        region: AWS region
        
    Returns:
        True if a valid bucket is available, False otherwise
    """
    try:
        validator = S3BucketValidator(region)
        result = validator.validate_and_setup_bucket(bucket_name, project_name)
        
        if result['valid']:
            if result['created']:
                print(f"✅ Created S3 bucket: {result['bucket_name']}")
            else:
                print(f"✅ Using S3 bucket: {result['bucket_name']}")
            return True
        else:
            print(f"❌ S3 bucket validation failed: {result['bucket_name']}")
            
            if result['issues']:
                print("Issues:")
                for issue in result['issues']:
                    print(f"   - {issue}")
            
            if result['suggestions']:
                print("\\nSuggestions:")
                for suggestion in result['suggestions']:
                    print(f"   - {suggestion}")
            
            if result['cli_commands']:
                print(f"\\n🔧 Manual bucket creation:")
                for cmd in result['cli_commands']:
                    print(cmd)
            
            return False
            
    except Exception as e:
        print(f"❌ Bucket validation failed: {e}")
        return False


def setup_project_bucket(project_name: str, region: str = "us-east-1") -> Optional[str]:
    """
    Set up S3 bucket for a project
    
    Args:
        project_name: Name of the project
        region: AWS region
        
    Returns:
        Bucket name if successful, None otherwise
    """
    try:
        validator = S3BucketValidator(region)
        result = validator.validate_and_setup_bucket(None, project_name)
        
        if result['valid']:
            return result['bucket_name']
        else:
            print(f"Failed to set up bucket for project {project_name}")
            return None
            
    except Exception as e:
        print(f"Bucket setup failed: {e}")
        return None