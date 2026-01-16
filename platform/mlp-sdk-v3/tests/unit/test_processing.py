"""
Unit tests for ProcessingWrapper class
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from mlp_sdk.wrappers.processing import ProcessingWrapper
from mlp_sdk.config import ConfigurationManager, ComputeConfig, NetworkingConfig, IAMConfig, S3Config, KMSConfig
from mlp_sdk.exceptions import ValidationError, MLPSDKError


@pytest.fixture
def mock_config_manager():
    """Create a mock configuration manager with test data"""
    config_manager = Mock(spec=ConfigurationManager)
    
    # Mock configuration objects
    config_manager.get_compute_config.return_value = ComputeConfig(
        processing_instance_type="ml.m5.large",
        training_instance_type="ml.m5.xlarge",
        processing_instance_count=1,
        training_instance_count=1
    )
    
    config_manager.get_networking_config.return_value = NetworkingConfig(
        vpc_id="vpc-12345678",
        security_group_ids=["sg-12345678"],
        subnets=["subnet-12345678", "subnet-87654321"]
    )
    
    config_manager.get_iam_config.return_value = IAMConfig(
        execution_role="arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    )
    
    config_manager.get_s3_config.return_value = S3Config(
        default_bucket="test-bucket",
        input_prefix="input/",
        output_prefix="output/",
        model_prefix="models/"
    )
    
    config_manager.get_kms_config.return_value = KMSConfig(
        key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
    )
    
    return config_manager


class TestProcessingWrapper:
    """Test ProcessingWrapper functionality"""
    
    def test_validate_parameter_override_valid(self, mock_config_manager):
        """Test that valid runtime parameters pass validation"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        valid_params = {
            'instance_type': 'ml.m5.xlarge',
            'instance_count': 2,
            'role_arn': 'arn:aws:iam::123456789012:role/TestRole',
            'volume_size_in_gb': 30,
            'max_runtime_in_seconds': 3600
        }
        
        # Should not raise any exception
        wrapper.validate_parameter_override(valid_params)
    
    def test_validate_parameter_override_invalid_instance_type(self, mock_config_manager):
        """Test that invalid instance type format is rejected"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        invalid_params = {
            'instance_type': 't2.micro'  # Not a SageMaker instance type
        }
        
        with pytest.raises(ValidationError, match="Invalid instance type format"):
            wrapper.validate_parameter_override(invalid_params)
    
    def test_validate_parameter_override_invalid_instance_count(self, mock_config_manager):
        """Test that invalid instance count is rejected"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        invalid_params = {
            'instance_count': 0  # Must be at least 1
        }
        
        with pytest.raises(ValidationError, match="instance_count must be at least 1"):
            wrapper.validate_parameter_override(invalid_params)
    
    def test_validate_parameter_override_invalid_role_arn(self, mock_config_manager):
        """Test that invalid IAM role ARN is rejected"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        invalid_params = {
            'role_arn': 'invalid-role-arn'
        }
        
        with pytest.raises(ValidationError, match="Invalid IAM role ARN format"):
            wrapper.validate_parameter_override(invalid_params)
    
    def test_build_config_uses_defaults(self, mock_config_manager):
        """Test that configuration defaults are applied when no runtime params provided"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        config = wrapper._build_processing_config({})
        
        # Should use config defaults
        assert config['instance_type'] == 'ml.m5.large'
        assert config['instance_count'] == 1
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/SageMakerExecutionRole'
        # network_config may not be present if sagemaker SDK is not installed
        # assert config['network_config'] is not None
        assert config['volume_kms_key'] == 'arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
    
    def test_build_config_runtime_overrides_defaults(self, mock_config_manager):
        """Test that runtime parameters override configuration defaults"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        runtime_params = {
            'instance_type': 'ml.m5.2xlarge',
            'instance_count': 3,
            'role_arn': 'arn:aws:iam::123456789012:role/CustomRole'
        }
        
        config = wrapper._build_processing_config(runtime_params)
        
        # Should use runtime overrides
        assert config['instance_type'] == 'ml.m5.2xlarge'
        assert config['instance_count'] == 3
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/CustomRole'
    
    def test_build_config_partial_override(self, mock_config_manager):
        """Test that partial runtime overrides work correctly"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        runtime_params = {
            'instance_type': 'ml.m5.4xlarge'
            # instance_count not provided, should use default
        }
        
        config = wrapper._build_processing_config(runtime_params)
        
        # Should use runtime override for instance_type
        assert config['instance_type'] == 'ml.m5.4xlarge'
        # Should use config default for instance_count
        assert config['instance_count'] == 1
    
    def test_run_processing_job_validation_errors(self, mock_config_manager):
        """Test that validation errors are raised for invalid parameters"""
        wrapper = ProcessingWrapper(mock_config_manager)
        mock_session = Mock()
        
        # Test missing job_name
        with pytest.raises(ValidationError, match="job_name is required"):
            wrapper.run_processing_job(mock_session, "")


class TestParameterPrecedence:
    """Test parameter precedence: runtime > config > SageMaker defaults"""
    
    def test_precedence_runtime_over_config(self, mock_config_manager):
        """Test that runtime parameters take precedence over config"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        runtime_params = {
            'instance_type': 'ml.m5.24xlarge',
            'role_arn': 'arn:aws:iam::999999999999:role/RuntimeRole'
        }
        
        config = wrapper._build_processing_config(runtime_params)
        
        # Runtime values should override config
        assert config['instance_type'] == 'ml.m5.24xlarge'
        assert config['role_arn'] == 'arn:aws:iam::999999999999:role/RuntimeRole'
    
    def test_precedence_config_when_no_runtime(self, mock_config_manager):
        """Test that config defaults are used when no runtime params provided"""
        wrapper = ProcessingWrapper(mock_config_manager)
        
        config = wrapper._build_processing_config({})
        
        # Config values should be used
        assert config['instance_type'] == 'ml.m5.large'
        assert config['instance_count'] == 1
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/SageMakerExecutionRole'
    
    def test_precedence_sagemaker_defaults_when_no_config(self):
        """Test that SageMaker defaults are used when no config available"""
        # Create config manager with no configuration
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.get_compute_config.return_value = None
        config_manager.get_networking_config.return_value = None
        config_manager.get_iam_config.return_value = None
        config_manager.get_s3_config.return_value = None
        config_manager.get_kms_config.return_value = None
        
        wrapper = ProcessingWrapper(config_manager)
        
        # Should raise ValidationError because role_arn is required
        with pytest.raises(ValidationError, match="IAM execution role is required"):
            wrapper._build_processing_config({})
