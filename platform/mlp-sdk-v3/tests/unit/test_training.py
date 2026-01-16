"""
Unit tests for Training Job wrapper
Tests validation, configuration building, and parameter precedence
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from mlp_sdk.wrappers.training import TrainingWrapper
from mlp_sdk.config import ConfigurationManager
from mlp_sdk.models import ComputeConfig, NetworkingConfig, IAMConfig, S3Config, KMSConfig
from mlp_sdk.exceptions import ValidationError, AWSServiceError


class TestTrainingWrapper:
    """Test TrainingWrapper validation and configuration building"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock configuration manager with default values"""
        config_manager = Mock(spec=ConfigurationManager)
        
        # Set up default configurations
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
            execution_role="arn:aws:iam::123456789012:role/SageMakerRole"
        )
        
        config_manager.get_s3_config.return_value = S3Config(
            default_bucket="my-sagemaker-bucket",
            input_prefix="input/",
            output_prefix="output/",
            model_prefix="models/"
        )
        
        config_manager.get_kms_config.return_value = KMSConfig(
            key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
        )
        
        return config_manager
    
    def test_validate_parameter_override_valid(self, mock_config_manager):
        """Test that valid runtime parameters pass validation"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        valid_params = {
            'instance_type': 'ml.m5.2xlarge',
            'instance_count': 2,
            'role_arn': 'arn:aws:iam::123456789012:role/CustomRole',
            'subnets': ['subnet-11111111'],
            'security_group_ids': ['sg-11111111'],
            'output_path': 's3://my-bucket/output/',
            'volume_size': 30,
            'max_run': 3600,
            'inputs': {'training': 's3://my-bucket/data/'},
            'hyperparameters': {'max_depth': '5'},
            'image_uri': '123456789012.dkr.ecr.us-west-2.amazonaws.com/my-training:latest'
        }
        
        # Should not raise any exception
        wrapper.validate_parameter_override(valid_params)
    
    def test_validate_parameter_override_invalid_instance_type(self, mock_config_manager):
        """Test that invalid instance type format is rejected"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        with pytest.raises(ValidationError, match="Invalid instance type format"):
            wrapper.validate_parameter_override({'instance_type': 'invalid-type'})
    
    def test_validate_parameter_override_invalid_instance_count(self, mock_config_manager):
        """Test that invalid instance count is rejected"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        with pytest.raises(ValidationError, match="instance_count must be at least 1"):
            wrapper.validate_parameter_override({'instance_count': 0})
    
    def test_validate_parameter_override_invalid_role_arn(self, mock_config_manager):
        """Test that invalid IAM role ARN format is rejected"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        with pytest.raises(ValidationError, match="Invalid IAM role ARN format"):
            wrapper.validate_parameter_override({'role_arn': 'invalid-arn'})
    
    def test_build_config_uses_defaults(self, mock_config_manager):
        """Test that configuration uses defaults when no runtime params provided"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        config = wrapper._build_training_config({})
        
        assert config['instance_type'] == 'ml.m5.xlarge'
        assert config['instance_count'] == 1
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/SageMakerRole'
        assert config['subnets'] == ['subnet-12345678', 'subnet-87654321']
        assert config['security_group_ids'] == ['sg-12345678']
        assert config['output_path'] == 's3://my-sagemaker-bucket/models/'
        assert config['volume_kms_key'] == 'arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID'
    
    def test_build_config_runtime_overrides_defaults(self, mock_config_manager):
        """Test that runtime parameters override configuration defaults"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        runtime_params = {
            'instance_type': 'ml.p3.2xlarge',
            'instance_count': 4,
            'role_arn': 'arn:aws:iam::123456789012:role/CustomRole',
            'output_path': 's3://custom-bucket/models/'
        }
        
        config = wrapper._build_training_config(runtime_params)
        
        assert config['instance_type'] == 'ml.p3.2xlarge'
        assert config['instance_count'] == 4
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/CustomRole'
        assert config['output_path'] == 's3://custom-bucket/models/'
        # Other defaults should still be applied
        assert config['subnets'] == ['subnet-12345678', 'subnet-87654321']
    
    def test_build_config_partial_override(self, mock_config_manager):
        """Test that partial runtime overrides work correctly"""
        wrapper = TrainingWrapper(mock_config_manager)
        
        runtime_params = {
            'instance_type': 'ml.g4dn.xlarge',
            # instance_count not provided, should use default
        }
        
        config = wrapper._build_training_config(runtime_params)
        
        assert config['instance_type'] == 'ml.g4dn.xlarge'
        assert config['instance_count'] == 1  # Default
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/SageMakerRole'  # Default
    
    def test_run_training_job_validation_errors(self, mock_config_manager):
        """Test that training job execution validates required parameters"""
        wrapper = TrainingWrapper(mock_config_manager)
        mock_session = Mock()
        
        # Missing job_name
        with pytest.raises(ValidationError, match="job_name is required"):
            wrapper.run_training_job(mock_session, job_name="")


class TestParameterPrecedence:
    """Test parameter precedence: runtime > config > SageMaker defaults"""
    
    @pytest.fixture
    def mock_config_manager_with_config(self):
        """Create a mock configuration manager with configuration values"""
        config_manager = Mock(spec=ConfigurationManager)
        
        config_manager.get_compute_config.return_value = ComputeConfig(
            processing_instance_type="ml.m5.large",
            training_instance_type="ml.m5.xlarge",
            processing_instance_count=1,
            training_instance_count=2
        )
        
        config_manager.get_iam_config.return_value = IAMConfig(
            execution_role="arn:aws:iam::123456789012:role/ConfigRole"
        )
        
        config_manager.get_networking_config.return_value = NetworkingConfig(
            vpc_id="vpc-config",
            security_group_ids=["sg-config"],
            subnets=["subnet-config"]
        )
        
        config_manager.get_s3_config.return_value = S3Config(
            default_bucket="config-bucket",
            input_prefix="input/",
            output_prefix="output/",
            model_prefix="models/"
        )
        
        config_manager.get_kms_config.return_value = KMSConfig(
            key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/config-key"
        )
        
        return config_manager
    
    @pytest.fixture
    def mock_config_manager_no_config(self):
        """Create a mock configuration manager with no configuration values"""
        config_manager = Mock(spec=ConfigurationManager)
        
        config_manager.get_compute_config.return_value = None
        config_manager.get_iam_config.return_value = IAMConfig(
            execution_role="arn:aws:iam::123456789012:role/DefaultRole"
        )
        config_manager.get_networking_config.return_value = None
        config_manager.get_s3_config.return_value = None
        config_manager.get_kms_config.return_value = None
        
        return config_manager
    
    def test_precedence_runtime_over_config(self, mock_config_manager_with_config):
        """Test that runtime parameters take precedence over config"""
        wrapper = TrainingWrapper(mock_config_manager_with_config)
        
        runtime_params = {
            'instance_type': 'ml.p3.2xlarge',
            'instance_count': 8,
            'role_arn': 'arn:aws:iam::123456789012:role/RuntimeRole'
        }
        
        config = wrapper._build_training_config(runtime_params)
        
        # Runtime values should be used
        assert config['instance_type'] == 'ml.p3.2xlarge'
        assert config['instance_count'] == 8
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/RuntimeRole'
    
    def test_precedence_config_when_no_runtime(self, mock_config_manager_with_config):
        """Test that config values are used when no runtime params provided"""
        wrapper = TrainingWrapper(mock_config_manager_with_config)
        
        config = wrapper._build_training_config({})
        
        # Config values should be used
        assert config['instance_type'] == 'ml.m5.xlarge'
        assert config['instance_count'] == 2
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/ConfigRole'
        assert config['subnets'] == ['subnet-config']
        assert config['security_group_ids'] == ['sg-config']
    
    def test_precedence_sagemaker_defaults_when_no_config(self, mock_config_manager_no_config):
        """Test that SageMaker defaults are used when no config provided"""
        wrapper = TrainingWrapper(mock_config_manager_no_config)
        
        config = wrapper._build_training_config({})
        
        # SageMaker defaults should be used
        assert config['instance_type'] == 'ml.m5.xlarge'
        assert config['instance_count'] == 1
        # Role should still come from config (required)
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/DefaultRole'
        # Networking should not be set (no config)
        assert 'subnets' not in config or config.get('subnets') is None
