"""
Pytest configuration and shared fixtures
"""

import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for configuration files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config_yaml():
    """Sample YAML configuration content"""
    return """
defaults:
  s3:
    default_bucket: "test-sagemaker-bucket"
    input_prefix: "input/"
    output_prefix: "output/"
    model_prefix: "models/"
    
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids: ["sg-12345678"]
    subnets: ["subnet-12345678", "subnet-87654321"]
    
  compute:
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
    processing_instance_count: 1
    training_instance_count: 1
    
  feature_store:
    offline_store_s3_uri: "s3://test-sagemaker-bucket/feature-store/"
    enable_online_store: false
    
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
"""


@pytest.fixture
def mock_sagemaker_session():
    """Mock SageMaker session for testing"""
    # This will be implemented when we add SageMaker integration
    pass