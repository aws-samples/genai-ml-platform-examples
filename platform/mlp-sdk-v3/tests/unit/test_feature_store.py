"""
Unit tests for Feature Store wrapper functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from mlp_sdk.wrappers.feature_store import FeatureStoreWrapper
from mlp_sdk.config import ConfigurationManager, FeatureStoreConfig, IAMConfig, KMSConfig
from mlp_sdk.exceptions import ValidationError, AWSServiceError


class TestFeatureStoreWrapper:
    """Test FeatureStoreWrapper functionality"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock configuration manager"""
        config_manager = Mock(spec=ConfigurationManager)
        
        # Set up default configurations
        config_manager.get_feature_store_config.return_value = FeatureStoreConfig(
            offline_store_s3_uri="s3://test-bucket/feature-store/",
            enable_online_store=False
        )
        config_manager.get_iam_config.return_value = IAMConfig(
            execution_role="arn:aws:iam::123456789012:role/TestRole"
        )
        config_manager.get_kms_config.return_value = KMSConfig(
            key_id="arn:aws:kms:REGION:ACCOUNT-ID:key/test-key"
        )
        config_manager.get_networking_config.return_value = None
        
        return config_manager
    
    @pytest.fixture
    def feature_store_wrapper(self, mock_config_manager):
        """Create a FeatureStoreWrapper instance"""
        return FeatureStoreWrapper(mock_config_manager)
    
    def test_validate_parameter_override_valid(self, feature_store_wrapper):
        """Test validation of valid runtime parameters"""
        runtime_params = {
            'enable_online_store': True,
            'role_arn': 'arn:aws:iam::123456789012:role/CustomRole',
            'offline_store_config': {
                'S3StorageConfig': {
                    'S3Uri': 's3://custom-bucket/path/'
                }
            }
        }
        
        # Should not raise any exception
        feature_store_wrapper.validate_parameter_override(runtime_params)
    
    def test_validate_parameter_override_invalid_enable_online_store(self, feature_store_wrapper):
        """Test validation fails for invalid enable_online_store type"""
        runtime_params = {
            'enable_online_store': 'true'  # Should be boolean
        }
        
        with pytest.raises(ValidationError, match="enable_online_store must be a boolean"):
            feature_store_wrapper.validate_parameter_override(runtime_params)
    
    def test_validate_parameter_override_invalid_role_arn(self, feature_store_wrapper):
        """Test validation fails for invalid role ARN format"""
        runtime_params = {
            'role_arn': 'invalid-arn'
        }
        
        with pytest.raises(ValidationError, match="Invalid IAM role ARN format"):
            feature_store_wrapper.validate_parameter_override(runtime_params)
    
    def test_validate_parameter_override_invalid_offline_store_config(self, feature_store_wrapper):
        """Test validation fails for invalid offline store config"""
        runtime_params = {
            'offline_store_config': {
                'S3StorageConfig': {}  # Missing S3Uri
            }
        }
        
        with pytest.raises(ValidationError, match="S3StorageConfig must contain 'S3Uri'"):
            feature_store_wrapper.validate_parameter_override(runtime_params)
    
    def test_build_config_uses_defaults(self, feature_store_wrapper):
        """Test that config builder uses defaults when no runtime params provided"""
        config = feature_store_wrapper._build_feature_group_config({})
        
        assert config['offline_store_config']['S3StorageConfig']['S3Uri'] == "s3://test-bucket/feature-store/"
        assert config['enable_online_store'] is False
        assert config['role_arn'] == "arn:aws:iam::123456789012:role/TestRole"
    
    def test_build_config_runtime_overrides_defaults(self, feature_store_wrapper):
        """Test that runtime parameters override configuration defaults"""
        runtime_params = {
            'enable_online_store': True,
            'role_arn': 'arn:aws:iam::123456789012:role/CustomRole',
            'offline_store_config': {
                'S3StorageConfig': {
                    'S3Uri': 's3://custom-bucket/path/'
                }
            }
        }
        
        config = feature_store_wrapper._build_feature_group_config(runtime_params)
        
        # Runtime parameters should take precedence
        assert config['enable_online_store'] is True
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/CustomRole'
        assert config['offline_store_config']['S3StorageConfig']['S3Uri'] == 's3://custom-bucket/path/'
    
    def test_build_config_partial_override(self, feature_store_wrapper):
        """Test that partial runtime parameters override only specified values"""
        runtime_params = {
            'enable_online_store': True  # Only override this
        }
        
        config = feature_store_wrapper._build_feature_group_config(runtime_params)
        
        # Overridden value
        assert config['enable_online_store'] is True
        
        # Default values should still be used
        assert config['offline_store_config']['S3StorageConfig']['S3Uri'] == "s3://test-bucket/feature-store/"
        assert config['role_arn'] == "arn:aws:iam::123456789012:role/TestRole"
    
    def test_create_feature_group_validation_errors(self, feature_store_wrapper):
        """Test that create_feature_group validates required parameters"""
        mock_session = Mock()
        
        # Test missing feature_group_name
        with pytest.raises(ValidationError, match="feature_group_name is required"):
            feature_store_wrapper.create_feature_group(
                sagemaker_session=mock_session,
                feature_group_name="",
                record_identifier_name="id",
                event_time_feature_name="time",
                feature_definitions=[{'FeatureName': 'test', 'FeatureType': 'String'}]
            )
        
        # Test missing record_identifier_name
        with pytest.raises(ValidationError, match="record_identifier_name is required"):
            feature_store_wrapper.create_feature_group(
                sagemaker_session=mock_session,
                feature_group_name="test-fg",
                record_identifier_name="",
                event_time_feature_name="time",
                feature_definitions=[{'FeatureName': 'test', 'FeatureType': 'String'}]
            )
        
        # Test empty feature_definitions
        with pytest.raises(ValidationError, match="feature_definitions is required and cannot be empty"):
            feature_store_wrapper.create_feature_group(
                sagemaker_session=mock_session,
                feature_group_name="test-fg",
                record_identifier_name="id",
                event_time_feature_name="time",
                feature_definitions=[]
            )


class TestParameterPrecedence:
    """Test parameter precedence: runtime > config > SageMaker defaults"""
    
    @pytest.fixture
    def config_manager_with_config(self):
        """Create a config manager with configuration"""
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.get_feature_store_config.return_value = FeatureStoreConfig(
            offline_store_s3_uri="s3://config-bucket/feature-store/",
            enable_online_store=False
        )
        config_manager.get_iam_config.return_value = IAMConfig(
            execution_role="arn:aws:iam::123456789012:role/ConfigRole"
        )
        config_manager.get_kms_config.return_value = None
        config_manager.get_networking_config.return_value = None
        return config_manager
    
    @pytest.fixture
    def config_manager_without_config(self):
        """Create a config manager without configuration"""
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.get_feature_store_config.return_value = None
        config_manager.get_iam_config.return_value = None
        config_manager.get_kms_config.return_value = None
        config_manager.get_networking_config.return_value = None
        return config_manager
    
    def test_precedence_runtime_over_config(self, config_manager_with_config):
        """Test that runtime parameters take precedence over config"""
        wrapper = FeatureStoreWrapper(config_manager_with_config)
        
        runtime_params = {
            'role_arn': 'arn:aws:iam::123456789012:role/RuntimeRole',
            'enable_online_store': True
        }
        
        config = wrapper._build_feature_group_config(runtime_params)
        
        # Runtime values should win
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/RuntimeRole'
        assert config['enable_online_store'] is True
        
        # Config value should be used for non-overridden parameter
        assert config['offline_store_config']['S3StorageConfig']['S3Uri'] == 's3://config-bucket/feature-store/'
    
    def test_precedence_config_when_no_runtime(self, config_manager_with_config):
        """Test that config values are used when no runtime parameters provided"""
        wrapper = FeatureStoreWrapper(config_manager_with_config)
        
        config = wrapper._build_feature_group_config({})
        
        # Config values should be used
        assert config['role_arn'] == 'arn:aws:iam::123456789012:role/ConfigRole'
        assert config['enable_online_store'] is False
        assert config['offline_store_config']['S3StorageConfig']['S3Uri'] == 's3://config-bucket/feature-store/'
    
    def test_precedence_sagemaker_defaults_when_no_config(self, config_manager_without_config):
        """Test that SageMaker defaults are used when no config available"""
        wrapper = FeatureStoreWrapper(config_manager_without_config)
        
        config = wrapper._build_feature_group_config({})
        
        # No config values should be present (SageMaker SDK will use its defaults)
        assert 'role_arn' not in config
        assert 'enable_online_store' not in config
        assert 'offline_store_config' not in config
