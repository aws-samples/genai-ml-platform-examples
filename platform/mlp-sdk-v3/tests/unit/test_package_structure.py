"""
Unit tests for package structure and imports
"""

import pytest


def test_package_imports():
    """Test that main package components can be imported"""
    from mlp_sdk import MLP_Session, MLPSDKError, ConfigurationError, ValidationError, AWSServiceError
    
    # Verify classes are importable
    assert MLP_Session is not None
    assert MLPSDKError is not None
    assert ConfigurationError is not None
    assert ValidationError is not None
    assert AWSServiceError is not None


def test_package_version():
    """Test that package version is defined"""
    import mlp_sdk
    
    assert hasattr(mlp_sdk, '__version__')
    assert mlp_sdk.__version__ == "0.1.0"


def test_MLP_session_initialization():
    """Test basic MLP_Session initialization"""
    from mlp_sdk import MLP_Session
    from unittest.mock import Mock, MagicMock, patch
    
    # Mock boto3 session
    mock_boto_session = Mock()
    mock_boto_session.region_name = 'us-west-2'
    mock_boto_session.client = Mock(return_value=Mock())
    
    # Mock SessionSettings for SDK v3
    mock_session_settings_class = Mock()
    mock_session_settings_instance = Mock()
    mock_session_settings_class.return_value = mock_session_settings_instance
    
    # Mock sagemaker.core.session_settings module
    mock_session_settings_module = MagicMock()
    mock_session_settings_module.SessionSettings = mock_session_settings_class
    
    # Mock sagemaker.core module
    mock_core = MagicMock()
    mock_core.session_settings = mock_session_settings_module
    
    # Mock sagemaker module
    mock_sagemaker = MagicMock()
    mock_sagemaker.core = mock_core
    
    with patch.dict('sys.modules', {
        'sagemaker': mock_sagemaker,
        'sagemaker.core': mock_core,
        'sagemaker.core.session_settings': mock_session_settings_module
    }):
        with patch('boto3.Session', return_value=mock_boto_session):
            # Should initialize without errors
            session = MLP_Session()
            assert session is not None
            assert hasattr(session, 'config_manager')


def test_exception_hierarchy():
    """Test exception class hierarchy"""
    from mlp_sdk import MLPSDKError, ConfigurationError, ValidationError, AWSServiceError
    
    # Test inheritance
    assert issubclass(ConfigurationError, MLPSDKError)
    assert issubclass(ValidationError, MLPSDKError)
    assert issubclass(AWSServiceError, MLPSDKError)
    
    # Test instantiation
    base_error = MLPSDKError("Base error")
    config_error = ConfigurationError("Config error")
    validation_error = ValidationError("Validation error")
    aws_error = AWSServiceError("AWS error")
    
    assert str(base_error) == "Base error"
    assert str(config_error) == "Config error"
    assert str(validation_error) == "Validation error"
    assert str(aws_error) == "AWS error"


def test_aws_service_error_with_original():
    """Test AWSServiceError with original AWS exception"""
    from mlp_sdk import AWSServiceError
    
    original_error = Exception("Original AWS error")
    aws_error = AWSServiceError("Wrapped error", original_error)
    
    assert str(aws_error) == "Wrapped error"
    assert aws_error.aws_error is original_error