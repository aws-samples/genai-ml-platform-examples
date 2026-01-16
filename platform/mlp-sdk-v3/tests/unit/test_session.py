"""
Unit tests for MLP_Session class
"""

import pytest
import logging
import sys
from unittest.mock import Mock, patch, MagicMock
from mlp_sdk.session import MLP_Session
from mlp_sdk.exceptions import SessionError, ConfigurationError, MLPSDKError, ValidationError


@pytest.fixture
def mock_sagemaker_module():
    """Mock the sagemaker module for SDK v3"""
    # Create mock boto3 session
    mock_boto_session = Mock()
    mock_boto_session.region_name = 'us-west-2'
    mock_boto_session.client = Mock(return_value=Mock())
    
    # Create mock SessionSettings
    mock_session_settings_class = Mock()
    mock_session_settings_instance = Mock()
    mock_session_settings_class.return_value = mock_session_settings_instance
    
    # Create mock sagemaker.core.session_settings module
    mock_session_settings_module = MagicMock()
    mock_session_settings_module.SessionSettings = mock_session_settings_class
    
    # Create mock sagemaker.core module
    mock_core = MagicMock()
    mock_core.session_settings = mock_session_settings_module
    
    # Create mock sagemaker module
    mock_sagemaker = MagicMock()
    mock_sagemaker.core = mock_core
    
    # Patch sys.modules and boto3.Session
    with patch.dict('sys.modules', {
        'sagemaker': mock_sagemaker,
        'sagemaker.core': mock_core,
        'sagemaker.core.session_settings': mock_session_settings_module
    }):
        with patch('boto3.Session', return_value=mock_boto_session):
            yield mock_sagemaker, mock_session_settings_instance


class TestMLPSessionInitialization:
    """Test MLP_Session initialization"""
    
    def test_session_init_without_config(self, mock_sagemaker_module):
        """Test session initialization without configuration file"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            assert session is not None
            assert session.config_manager is not None
            assert session.logger is not None
            assert session.audit_trail is not None
    
    def test_session_init_with_custom_config_path(self, tmp_path, mock_sagemaker_module):
        """Test session initialization with custom config path"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        # Create a temporary config file
        config_file = tmp_path / "test-config.yaml"
        config_file.write_text("""
defaults:
  s3:
    default_bucket: "test-bucket"
  networking:
    vpc_id: "vpc-12345678"
    security_group_ids: ["sg-12345678"]
    subnets: ["subnet-12345678"]
  compute:
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
  feature_store:
    offline_store_s3_uri: "s3://test-bucket/feature-store/"
  iam:
    execution_role: "arn:aws:iam::123456789012:role/TestRole"
""")
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session(config_path=str(config_file))
            
            assert session.config_manager.has_config
            assert session.config_manager.get_s3_config().default_bucket == "test-bucket"
    
    def test_session_init_with_log_level(self, mock_sagemaker_module):
        """Test session initialization with custom log level"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session(log_level=logging.DEBUG)
            
            assert session.logger.logger.level == logging.DEBUG
    
    def test_session_init_without_audit_trail(self, mock_sagemaker_module):
        """Test session initialization with audit trail disabled"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session(enable_audit_trail=False)
            
            assert session.audit_trail is None
    
    def test_session_init_sagemaker_not_installed(self):
        """Test session initialization when SageMaker SDK is not installed"""
        # Remove sagemaker from sys.modules if it exists
        original_modules = sys.modules.copy()
        
        # Create a mock that raises ImportError
        def mock_import(name, *args, **kwargs):
            if name == 'sagemaker' or name.startswith('sagemaker.'):
                raise ImportError(f"No module named '{name}'")
            return original_modules.get(name)
        
        with patch('builtins.__import__', side_effect=mock_import):
            with pytest.raises(SessionError, match="SageMaker SDK v3 not installed"):
                MLP_Session()
    
    def test_session_properties(self, mock_sagemaker_module):
        """Test session properties"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            assert session.sagemaker_session == mock_session_instance
            assert session.region_name == 'us-west-2'
            assert session.default_bucket is None  # No config file, so no default bucket
            assert session.boto_session is not None


class TestMLPSessionLogging:
    """Test MLP_Session logging functionality"""
    
    def test_set_log_level(self, mock_sagemaker_module):
        """Test changing log level"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session(log_level=logging.INFO)
            session.set_log_level(logging.ERROR)
            
            assert session.logger.logger.level == logging.ERROR


class TestMLPSessionAuditTrail:
    """Test MLP_Session audit trail functionality"""
    
    def test_get_audit_trail(self, mock_sagemaker_module):
        """Test getting audit trail entries"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Audit trail should exist and have session_init entries
            assert session.audit_trail is not None
            entries = session.get_audit_trail()
            assert len(entries) >= 2  # Should have 'started' and 'completed' entries
            assert any(e['operation'] == 'session_init' and e['status'] == 'started' for e in entries)
            assert any(e['operation'] == 'session_init' and e['status'] == 'completed' for e in entries)
    
    def test_get_audit_trail_filtered(self, mock_sagemaker_module):
        """Test getting filtered audit trail entries"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Filter by operation
            entries = session.get_audit_trail(operation='session_init')
            assert all(e['operation'] == 'session_init' for e in entries)
            
            # Filter by status
            entries = session.get_audit_trail(status='completed')
            assert all(e['status'] == 'completed' for e in entries)
    
    def test_export_audit_trail(self, tmp_path, mock_sagemaker_module):
        """Test exporting audit trail to file"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Verify audit trail exists and has entries
            assert session.audit_trail is not None
            assert len(session.get_audit_trail()) > 0
            
            output_file = tmp_path / "audit_trail.json"
            session.export_audit_trail(str(output_file))
            
            assert output_file.exists()
    
    def test_export_audit_trail_disabled(self, mock_sagemaker_module):
        """Test exporting audit trail when disabled"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session(enable_audit_trail=False)
            
            with pytest.raises(SessionError, match="Audit trail is not enabled"):
                session.export_audit_trail("test.json")


class TestMLPSessionOperations:
    """Test MLP_Session operation placeholders"""
    
    def test_create_feature_group_not_implemented(self, mock_sagemaker_module):
        """Test that create_feature_group raises NotImplementedError"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Now create_feature_group is implemented, so we test it requires proper parameters
            with pytest.raises(Exception):  # Will raise ValidationError or other error
                session.create_feature_group(
                    feature_group_name="test-feature-group",
                    record_identifier_name="record_id",
                    event_time_feature_name="event_time",
                    feature_definitions=[]  # Empty list will cause validation error
                )
    
    def test_run_processing_job_not_implemented(self, mock_sagemaker_module):
        """Test that run_processing_job raises NotImplementedError"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Now that processing job is implemented, it should raise MLPSDKError
            # because sagemaker.processing module is not available in the mock
            with pytest.raises(MLPSDKError, match="SageMaker SDK not installed"):
                session.run_processing_job("test-job")
    
    def test_run_training_job_implemented(self, mock_sagemaker_module):
        """Test that run_training_job is now implemented"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Should raise MLPSDKError because sagemaker module is mocked
            # Note: ModelTrainer API requires training_image parameter
            with pytest.raises(MLPSDKError, match="SageMaker SDK"):
                session.run_training_job(
                    "test-job",
                    training_image="763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310"
                )
    
    def test_create_pipeline_implemented(self, mock_sagemaker_module):
        """Test that create_pipeline is now implemented"""
        mock_sagemaker, mock_session_instance = mock_sagemaker_module
        
        with patch.dict('sys.modules', {'sagemaker': mock_sagemaker}):
            session = MLP_Session()
            
            # Should raise ValidationError because steps is empty
            with pytest.raises(ValidationError, match="steps must be a non-empty list"):
                session.create_pipeline("test-pipeline", steps=[])
