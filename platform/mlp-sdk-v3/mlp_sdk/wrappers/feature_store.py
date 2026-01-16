"""
Feature Store wrapper for mlp_sdk
Provides simplified feature group creation with configuration-driven defaults
"""

from typing import Optional, Dict, Any, List
from ..exceptions import MLPSDKError, ValidationError, AWSServiceError, MLPLogger
from ..config import ConfigurationManager


class FeatureStoreWrapper:
    """
    Wrapper for SageMaker Feature Store operations.
    Applies default configurations from ConfigurationManager.
    """
    
    def __init__(self, config_manager: ConfigurationManager, logger: Optional[MLPLogger] = None):
        """
        Initialize Feature Store wrapper.
        
        Args:
            config_manager: Configuration manager instance
            logger: Optional logger instance
        """
        self.config_manager = config_manager
        self.logger = logger or MLPLogger("mlp_sdk.feature_store")
    
    def create_feature_group(self, 
                            sagemaker_session,
                            feature_group_name: str,
                            record_identifier_name: str,
                            event_time_feature_name: str,
                            feature_definitions: List[Dict[str, str]],
                            **kwargs) -> Any:
        """
        Create a feature group with default configurations.
        
        Applies defaults from configuration for:
        - Offline store S3 URI
        - Online store enablement
        - Security group IDs
        - Subnets
        - KMS key ID
        - IAM role
        
        Runtime parameters override configuration defaults.
        
        Args:
            sagemaker_session: SageMaker session object
            feature_group_name: Name of the feature group
            record_identifier_name: Name of the record identifier feature
            event_time_feature_name: Name of the event time feature
            feature_definitions: List of feature definitions
            **kwargs: Additional parameters that override defaults
            
        Returns:
            FeatureGroup object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            AWSServiceError: If feature group creation fails
        """
        self.logger.info("Creating feature group", name=feature_group_name)
        
        # Validate required parameters
        if not feature_group_name:
            raise ValidationError("feature_group_name is required")
        if not record_identifier_name:
            raise ValidationError("record_identifier_name is required")
        if not event_time_feature_name:
            raise ValidationError("event_time_feature_name is required")
        if not feature_definitions:
            raise ValidationError("feature_definitions is required and cannot be empty")
        
        # Validate runtime parameter overrides
        self.validate_parameter_override(kwargs)
        
        try:
            from sagemaker.feature_store.feature_group import FeatureGroup
        except ImportError as e:
            raise MLPSDKError(
                "SageMaker SDK not installed. Install with: pip install sagemaker>=3.0.0"
            ) from e
        
        # Build configuration with defaults
        config = self._build_feature_group_config(kwargs)
        
        # Create FeatureGroup object
        feature_group = FeatureGroup(
            name=feature_group_name,
            sagemaker_session=sagemaker_session
        )
        
        # Load feature definitions
        feature_group.load_feature_definitions(feature_definitions)
        
        try:
            # Create the feature group with merged configuration
            self.logger.debug("Creating feature group with config", 
                            name=feature_group_name,
                            has_online_store=config.get('enable_online_store', False),
                            has_offline_store=bool(config.get('offline_store_config')))
            
            # Build create parameters
            create_params = {
                'record_identifier_name': record_identifier_name,
                'event_time_feature_name': event_time_feature_name,
            }
            
            # Add role ARN if available
            if config.get('role_arn'):
                create_params['role_arn'] = config['role_arn']
            
            # Add online store config if enabled
            if config.get('enable_online_store'):
                online_store_config = {'EnableOnlineStore': True}
                
                # Add security config if available
                if config.get('online_store_security_config'):
                    online_store_config['SecurityConfig'] = config['online_store_security_config']
                
                create_params['online_store_config'] = online_store_config
            
            # Add offline store config if available
            if config.get('offline_store_config'):
                create_params['offline_store_config'] = config['offline_store_config']
            
            # Add description if provided
            if config.get('description'):
                create_params['description'] = config['description']
            
            # Add tags if provided
            if config.get('tags'):
                create_params['tags'] = config['tags']
            
            # Create the feature group
            feature_group.create(**create_params)
            
            self.logger.info("Feature group created successfully", name=feature_group_name)
            return feature_group
            
        except Exception as e:
            self.logger.error("Failed to create feature group", 
                            name=feature_group_name, 
                            error=e)
            raise AWSServiceError(
                f"Failed to create feature group '{feature_group_name}': {e}",
                aws_error=e
            ) from e
    
    def _build_feature_group_config(self, runtime_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build feature group configuration by merging defaults with runtime parameters.
        
        Parameter precedence: runtime > config > SageMaker defaults
        
        This implements the parameter override behavior specified in Requirements 3.5 and 8.2:
        - Runtime parameters always take precedence over configuration defaults
        - Configuration defaults take precedence over SageMaker SDK defaults
        - SageMaker SDK defaults are used when neither runtime nor config provide values
        
        Args:
            runtime_params: Runtime parameters provided by user
            
        Returns:
            Merged configuration dictionary
        """
        config = {}
        
        # Get configuration objects
        feature_store_config = self.config_manager.get_feature_store_config()
        networking_config = self.config_manager.get_networking_config()
        iam_config = self.config_manager.get_iam_config()
        kms_config = self.config_manager.get_kms_config()
        
        # Apply offline store defaults (runtime > config)
        if feature_store_config:
            # Offline store configuration
            if 'offline_store_config' in runtime_params:
                # Runtime parameter takes precedence
                config['offline_store_config'] = runtime_params['offline_store_config']
                self.logger.debug("Using runtime offline_store_config")
            else:
                # Use config default
                offline_store_config = {
                    'S3StorageConfig': {
                        'S3Uri': feature_store_config.offline_store_s3_uri
                    }
                }
                
                # Add KMS key if available
                if kms_config and kms_config.key_id:
                    offline_store_config['S3StorageConfig']['KmsKeyId'] = kms_config.key_id
                
                config['offline_store_config'] = offline_store_config
                self.logger.debug("Using config offline_store_config", 
                                s3_uri=feature_store_config.offline_store_s3_uri)
            
            # Online store enablement (runtime > config)
            if 'enable_online_store' in runtime_params:
                config['enable_online_store'] = runtime_params['enable_online_store']
                self.logger.debug("Using runtime enable_online_store", 
                                value=runtime_params['enable_online_store'])
            else:
                config['enable_online_store'] = feature_store_config.enable_online_store
                self.logger.debug("Using config enable_online_store", 
                                value=feature_store_config.enable_online_store)
        
        # Apply networking defaults for online store (runtime > config)
        if config.get('enable_online_store'):
            if 'online_store_security_config' in runtime_params:
                config['online_store_security_config'] = runtime_params['online_store_security_config']
                self.logger.debug("Using runtime online_store_security_config")
            elif kms_config and kms_config.key_id:
                config['online_store_security_config'] = {
                    'KmsKeyId': kms_config.key_id
                }
                self.logger.debug("Using config online_store_security_config")
        
        # Apply IAM role default (runtime > config)
        if 'role_arn' in runtime_params:
            config['role_arn'] = runtime_params['role_arn']
            self.logger.debug("Using runtime role_arn")
        elif iam_config:
            config['role_arn'] = iam_config.execution_role
            self.logger.debug("Using config role_arn", role=iam_config.execution_role)
        
        # Apply any remaining runtime parameters (these override everything)
        for key, value in runtime_params.items():
            if key not in ['offline_store_config', 'enable_online_store', 
                          'online_store_security_config', 'role_arn']:
                config[key] = value
                self.logger.debug(f"Using runtime parameter: {key}")
        
        return config
    
    def _validate_feature_definitions(self, feature_definitions: List[Dict[str, str]]) -> None:
        """
        Validate feature definitions format.
        
        Args:
            feature_definitions: List of feature definitions
            
        Raises:
            ValidationError: If feature definitions are invalid
        """
        if not isinstance(feature_definitions, list):
            raise ValidationError("feature_definitions must be a list")
        
        if not feature_definitions:
            raise ValidationError("feature_definitions cannot be empty")
        
        for idx, feature_def in enumerate(feature_definitions):
            if not isinstance(feature_def, dict):
                raise ValidationError(f"Feature definition at index {idx} must be a dictionary")
            
            if 'FeatureName' not in feature_def:
                raise ValidationError(f"Feature definition at index {idx} missing 'FeatureName'")
            
            if 'FeatureType' not in feature_def:
                raise ValidationError(f"Feature definition at index {idx} missing 'FeatureType'")
    
    def validate_parameter_override(self, runtime_params: Dict[str, Any]) -> None:
        """
        Validate runtime parameter overrides.
        
        This ensures that runtime parameters are valid and compatible with the configuration.
        Implements validation requirements from Requirements 3.5 and 8.2.
        
        Args:
            runtime_params: Runtime parameters to validate
            
        Raises:
            ValidationError: If runtime parameters are invalid
        """
        # Validate offline_store_config structure if provided
        if 'offline_store_config' in runtime_params:
            offline_config = runtime_params['offline_store_config']
            if not isinstance(offline_config, dict):
                raise ValidationError("offline_store_config must be a dictionary")
            
            if 'S3StorageConfig' in offline_config:
                s3_config = offline_config['S3StorageConfig']
                if not isinstance(s3_config, dict):
                    raise ValidationError("S3StorageConfig must be a dictionary")
                
                if 'S3Uri' not in s3_config:
                    raise ValidationError("S3StorageConfig must contain 'S3Uri'")
        
        # Validate enable_online_store type if provided
        if 'enable_online_store' in runtime_params:
            if not isinstance(runtime_params['enable_online_store'], bool):
                raise ValidationError("enable_online_store must be a boolean")
        
        # Validate role_arn format if provided
        if 'role_arn' in runtime_params:
            role_arn = runtime_params['role_arn']
            if not isinstance(role_arn, str):
                raise ValidationError("role_arn must be a string")
            
            if not role_arn.startswith('arn:aws:iam::'):
                raise ValidationError(f"Invalid IAM role ARN format: {role_arn}")
        
        # Validate online_store_security_config if provided
        if 'online_store_security_config' in runtime_params:
            security_config = runtime_params['online_store_security_config']
            if not isinstance(security_config, dict):
                raise ValidationError("online_store_security_config must be a dictionary")
