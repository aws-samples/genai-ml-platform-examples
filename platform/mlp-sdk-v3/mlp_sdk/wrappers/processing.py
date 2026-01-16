"""
Processing Job wrapper for mlp_sdk
Provides simplified processing job execution with configuration-driven defaults
"""

from typing import Optional, Dict, Any, List
from ..exceptions import MLPSDKError, ValidationError, AWSServiceError, MLPLogger
from ..config import ConfigurationManager


class ProcessingWrapper:
    """
    Wrapper for SageMaker Processing Job operations.
    Applies default configurations from ConfigurationManager.
    """
    
    def __init__(self, config_manager: ConfigurationManager, logger: Optional[MLPLogger] = None):
        """
        Initialize Processing wrapper.
        
        Args:
            config_manager: Configuration manager instance
            logger: Optional logger instance
        """
        self.config_manager = config_manager
        self.logger = logger or MLPLogger("mlp_sdk.processing")
    
    def run_processing_job(self,
                          sagemaker_session,
                          job_name: str,
                          processing_script: Optional[str] = None,
                          inputs: Optional[List[Dict[str, Any]]] = None,
                          outputs: Optional[List[Dict[str, Any]]] = None,
                          **kwargs) -> Any:
        """
        Execute processing job with default configurations.
        
        Applies defaults from configuration for:
        - Instance type and count
        - IAM execution role
        - VPC configuration (VPC ID, security groups, subnets)
        - S3 input/output paths
        - KMS encryption key
        
        Runtime parameters override configuration defaults.
        
        Args:
            sagemaker_session: SageMaker session object
            job_name: Name of the processing job
            processing_script: Optional path to custom processing script
            inputs: Optional list of processing inputs
            outputs: Optional list of processing outputs
            **kwargs: Additional parameters that override defaults
            
        Returns:
            Processor object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            AWSServiceError: If processing job execution fails
        """
        self.logger.info("Running processing job", name=job_name)
        
        # Validate required parameters
        if not job_name:
            raise ValidationError("job_name is required")
        
        # Validate runtime parameter overrides
        self.validate_parameter_override(kwargs)
        
        try:
            from sagemaker.processing import Processor, ProcessingInput, ProcessingOutput
            from sagemaker.network import NetworkConfig
        except ImportError as e:
            raise MLPSDKError(
                "SageMaker SDK not installed. Install with: pip install sagemaker>=3.0.0"
            ) from e
        
        # Build configuration with defaults
        config = self._build_processing_config(kwargs)
        
        # Create Processor object
        processor_params = {
            'role': config['role_arn'],
            'instance_type': config['instance_type'],
            'instance_count': config['instance_count'],
            'sagemaker_session': sagemaker_session,
        }
        
        # Add base job name if provided
        if config.get('base_job_name'):
            processor_params['base_job_name'] = config['base_job_name']
        
        # Add volume size if provided
        if config.get('volume_size_in_gb'):
            processor_params['volume_size_in_gb'] = config['volume_size_in_gb']
        
        # Add volume KMS key if provided
        if config.get('volume_kms_key'):
            processor_params['volume_kms_key'] = config['volume_kms_key']
        
        # Add output KMS key if provided
        if config.get('output_kms_key'):
            processor_params['output_kms_key'] = config['output_kms_key']
        
        # Add max runtime if provided
        if config.get('max_runtime_in_seconds'):
            processor_params['max_runtime_in_seconds'] = config['max_runtime_in_seconds']
        
        # Add environment variables if provided
        if config.get('env'):
            processor_params['env'] = config['env']
        
        # Add tags if provided
        if config.get('tags'):
            processor_params['tags'] = config['tags']
        
        # Add network config if available
        if config.get('network_config'):
            processor_params['network_config'] = config['network_config']
        
        # Determine processor image
        if config.get('image_uri'):
            processor_params['image_uri'] = config['image_uri']
        else:
            # Use default SageMaker processing container
            # This will use the SageMaker SDK default
            pass
        
        # Create processor
        processor = Processor(**processor_params)
        
        try:
            # Build run parameters
            run_params = {
                'job_name': job_name,
            }
            
            # Add processing script if provided
            if processing_script:
                run_params['code'] = processing_script
            elif config.get('code'):
                run_params['code'] = config['code']
            
            # Add inputs
            if inputs:
                run_params['inputs'] = [ProcessingInput(**inp) for inp in inputs]
            elif config.get('inputs'):
                run_params['inputs'] = [ProcessingInput(**inp) for inp in config['inputs']]
            
            # Add outputs
            if outputs:
                run_params['outputs'] = [ProcessingOutput(**out) for out in outputs]
            elif config.get('outputs'):
                run_params['outputs'] = [ProcessingOutput(**out) for out in config['outputs']]
            
            # Add arguments if provided
            if config.get('arguments'):
                run_params['arguments'] = config['arguments']
            
            # Add wait flag if provided
            if 'wait' in config:
                run_params['wait'] = config['wait']
            
            # Add logs flag if provided
            if 'logs' in config:
                run_params['logs'] = config['logs']
            
            self.logger.debug("Starting processing job",
                            name=job_name,
                            instance_type=config['instance_type'],
                            instance_count=config['instance_count'])
            
            # Run the processing job
            processor.run(**run_params)
            
            self.logger.info("Processing job started successfully", name=job_name)
            return processor
            
        except Exception as e:
            self.logger.error("Failed to run processing job",
                            name=job_name,
                            error=e)
            raise AWSServiceError(
                f"Failed to run processing job '{job_name}': {e}",
                aws_error=e
            ) from e
    
    def _build_processing_config(self, runtime_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build processing job configuration by merging defaults with runtime parameters.
        
        Parameter precedence: runtime > config > SageMaker defaults
        
        This implements the parameter override behavior specified in Requirements 4.1, 4.2, 4.3:
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
        compute_config = self.config_manager.get_compute_config()
        networking_config = self.config_manager.get_networking_config()
        iam_config = self.config_manager.get_iam_config()
        s3_config = self.config_manager.get_s3_config()
        kms_config = self.config_manager.get_kms_config()
        
        # Apply compute defaults (runtime > config)
        if 'instance_type' in runtime_params:
            config['instance_type'] = runtime_params['instance_type']
            self.logger.debug("Using runtime instance_type", value=runtime_params['instance_type'])
        elif compute_config:
            config['instance_type'] = compute_config.processing_instance_type
            self.logger.debug("Using config instance_type", value=compute_config.processing_instance_type)
        else:
            # Will use SageMaker SDK default
            config['instance_type'] = 'ml.m5.large'
            self.logger.debug("Using default instance_type", value='ml.m5.large')
        
        if 'instance_count' in runtime_params:
            config['instance_count'] = runtime_params['instance_count']
            self.logger.debug("Using runtime instance_count", value=runtime_params['instance_count'])
        elif compute_config:
            config['instance_count'] = compute_config.processing_instance_count
            self.logger.debug("Using config instance_count", value=compute_config.processing_instance_count)
        else:
            # Will use SageMaker SDK default
            config['instance_count'] = 1
            self.logger.debug("Using default instance_count", value=1)
        
        # Apply IAM role default (runtime > config)
        if 'role_arn' in runtime_params:
            config['role_arn'] = runtime_params['role_arn']
            self.logger.debug("Using runtime role_arn")
        elif iam_config:
            config['role_arn'] = iam_config.execution_role
            self.logger.debug("Using config role_arn", role=iam_config.execution_role)
        else:
            raise ValidationError("IAM execution role is required. Provide via runtime parameter or configuration.")
        
        # Apply networking defaults (runtime > config)
        if 'network_config' in runtime_params:
            config['network_config'] = runtime_params['network_config']
            self.logger.debug("Using runtime network_config")
        elif networking_config:
            try:
                from sagemaker.network import NetworkConfig
                config['network_config'] = NetworkConfig(
                    enable_network_isolation=False,
                    security_group_ids=networking_config.security_group_ids,
                    subnets=networking_config.subnets
                )
                self.logger.debug("Using config network_config",
                                vpc_id=networking_config.vpc_id,
                                security_groups=networking_config.security_group_ids,
                                subnets=networking_config.subnets)
            except ImportError:
                # SageMaker SDK not available, skip network config
                self.logger.debug("SageMaker SDK not available, skipping network config")
                pass
        
        # Apply KMS encryption defaults (runtime > config)
        if 'volume_kms_key' in runtime_params:
            config['volume_kms_key'] = runtime_params['volume_kms_key']
            self.logger.debug("Using runtime volume_kms_key")
        elif kms_config and kms_config.key_id:
            config['volume_kms_key'] = kms_config.key_id
            self.logger.debug("Using config volume_kms_key", key_id=kms_config.key_id)
        
        if 'output_kms_key' in runtime_params:
            config['output_kms_key'] = runtime_params['output_kms_key']
            self.logger.debug("Using runtime output_kms_key")
        elif kms_config and kms_config.key_id:
            config['output_kms_key'] = kms_config.key_id
            self.logger.debug("Using config output_kms_key", key_id=kms_config.key_id)
        
        # Apply S3 defaults for inputs/outputs if not provided (runtime > config)
        # Note: inputs and outputs are typically provided at runtime, but we can set defaults
        if s3_config:
            if 'inputs' not in runtime_params and 'inputs' not in config:
                # Default input location
                default_input_uri = f"s3://{s3_config.default_bucket}/{s3_config.input_prefix}"
                self.logger.debug("Default input S3 URI available", uri=default_input_uri)
            
            if 'outputs' not in runtime_params and 'outputs' not in config:
                # Default output location
                default_output_uri = f"s3://{s3_config.default_bucket}/{s3_config.output_prefix}"
                self.logger.debug("Default output S3 URI available", uri=default_output_uri)
        
        # Apply any remaining runtime parameters (these override everything)
        for key, value in runtime_params.items():
            if key not in ['instance_type', 'instance_count', 'role_arn', 
                          'network_config', 'volume_kms_key', 'output_kms_key']:
                config[key] = value
                self.logger.debug(f"Using runtime parameter: {key}")
        
        return config
    
    def validate_parameter_override(self, runtime_params: Dict[str, Any]) -> None:
        """
        Validate runtime parameter overrides.
        
        This ensures that runtime parameters are valid and compatible with the configuration.
        Implements validation requirements from Requirements 4.1, 4.2, 4.3, 4.4.
        
        Args:
            runtime_params: Runtime parameters to validate
            
        Raises:
            ValidationError: If runtime parameters are invalid
        """
        # Validate instance_type format if provided
        if 'instance_type' in runtime_params:
            instance_type = runtime_params['instance_type']
            if not isinstance(instance_type, str):
                raise ValidationError("instance_type must be a string")
            
            if not instance_type.startswith('ml.'):
                raise ValidationError(f"Invalid instance type format: {instance_type}. Must start with 'ml.'")
        
        # Validate instance_count if provided
        if 'instance_count' in runtime_params:
            instance_count = runtime_params['instance_count']
            if not isinstance(instance_count, int):
                raise ValidationError("instance_count must be an integer")
            
            if instance_count < 1:
                raise ValidationError(f"instance_count must be at least 1, got {instance_count}")
        
        # Validate role_arn format if provided
        if 'role_arn' in runtime_params:
            role_arn = runtime_params['role_arn']
            if not isinstance(role_arn, str):
                raise ValidationError("role_arn must be a string")
            
            if not role_arn.startswith('arn:aws:iam::'):
                raise ValidationError(f"Invalid IAM role ARN format: {role_arn}")
        
        # Validate network_config if provided
        if 'network_config' in runtime_params:
            network_config = runtime_params['network_config']
            # NetworkConfig should be a NetworkConfig object or dict
            if not hasattr(network_config, 'security_group_ids') and not isinstance(network_config, dict):
                raise ValidationError("network_config must be a NetworkConfig object or dictionary")
        
        # Validate volume_size_in_gb if provided
        if 'volume_size_in_gb' in runtime_params:
            volume_size = runtime_params['volume_size_in_gb']
            if not isinstance(volume_size, int):
                raise ValidationError("volume_size_in_gb must be an integer")
            
            if volume_size < 1:
                raise ValidationError(f"volume_size_in_gb must be at least 1, got {volume_size}")
        
        # Validate max_runtime_in_seconds if provided
        if 'max_runtime_in_seconds' in runtime_params:
            max_runtime = runtime_params['max_runtime_in_seconds']
            if not isinstance(max_runtime, int):
                raise ValidationError("max_runtime_in_seconds must be an integer")
            
            if max_runtime < 1:
                raise ValidationError(f"max_runtime_in_seconds must be at least 1, got {max_runtime}")
        
        # Validate inputs if provided
        if 'inputs' in runtime_params:
            inputs = runtime_params['inputs']
            if not isinstance(inputs, list):
                raise ValidationError("inputs must be a list")
        
        # Validate outputs if provided
        if 'outputs' in runtime_params:
            outputs = runtime_params['outputs']
            if not isinstance(outputs, list):
                raise ValidationError("outputs must be a list")
