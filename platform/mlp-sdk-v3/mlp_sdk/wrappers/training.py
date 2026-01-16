"""
Training Job wrapper for mlp_sdk
Provides simplified training job execution with configuration-driven defaults

Uses SageMaker SDK v3 ModelTrainer API for modern training job execution.
"""

from typing import Optional, Dict, Any, List
from ..exceptions import MLPSDKError, ValidationError, AWSServiceError, MLPLogger
from ..config import ConfigurationManager


class TrainingWrapper:
    """
    Wrapper for SageMaker Training Job operations using ModelTrainer (SDK v3).
    Applies default configurations from ConfigurationManager.
    
    Note: This wrapper uses the modern ModelTrainer API introduced in SageMaker SDK v2.x
    and recommended for SDK v3, which replaces the legacy Estimator class.
    """
    
    def __init__(self, config_manager: ConfigurationManager, logger: Optional[MLPLogger] = None):
        """
        Initialize Training wrapper.
        
        Args:
            config_manager: Configuration manager instance
            logger: Optional logger instance
        """
        self.config_manager = config_manager
        self.logger = logger or MLPLogger("mlp_sdk.training")
    
    def run_training_job(self,
                        sagemaker_session,
                        job_name: str,
                        training_image: Optional[str] = None,
                        source_code_dir: Optional[str] = None,
                        entry_script: Optional[str] = None,
                        requirements: Optional[str] = None,
                        inputs: Optional[Dict[str, Any]] = None,
                        **kwargs) -> Any:
        """
        Execute training job with default configurations using ModelTrainer.
        
        Applies defaults from configuration for:
        - Instance type and count (via Compute config)
        - IAM execution role
        - VPC configuration (VPC ID, security groups, subnets)
        - S3 input/output paths
        - KMS encryption key
        
        Runtime parameters override configuration defaults.
        
        Supports both custom training scripts and container images.
        
        Args:
            sagemaker_session: SageMaker session object
            job_name: Name of the training job (used as base_job_name)
            training_image: Container image URI for training
            source_code_dir: Directory containing training script and dependencies
            entry_script: Entry point script for training (e.g., 'train.py')
            requirements: Path to requirements.txt file for dependencies
            inputs: Training data inputs (S3 paths or InputData objects)
            **kwargs: Additional parameters that override defaults
                     (e.g., hyperparameters, environment, distributed_runner)
            
        Returns:
            ModelTrainer object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            AWSServiceError: If training job execution fails
        """
        self.logger.info("Running training job with ModelTrainer", name=job_name)
        
        # Validate required parameters
        if not job_name:
            raise ValidationError("job_name is required")
        
        if not training_image:
            raise ValidationError("training_image is required for ModelTrainer")
        
        # Validate runtime parameter overrides
        self.validate_parameter_override(kwargs)
        
        try:
            from sagemaker.train.model_trainer import ModelTrainer, SourceCode, Compute, InputData
            from sagemaker.core.training.configs import Networking, StoppingCondition
            from sagemaker.core.shapes.shapes import OutputDataConfig
        except ImportError as e:
            raise MLPSDKError(
                "SageMaker SDK v3 not installed or ModelTrainer not available. "
                "Install with: pip install sagemaker>=3.0.0"
            ) from e
        
        # Build configuration with defaults
        config = self._build_training_config(kwargs)
        
        # Create SourceCode configuration if script provided
        source_code = None
        if source_code_dir or entry_script:
            source_code_params = {}
            if source_code_dir:
                source_code_params['source_dir'] = source_code_dir
            if entry_script:
                source_code_params['entry_script'] = entry_script
            if requirements:
                source_code_params['requirements'] = requirements
            
            # Add any custom command if provided
            if config.get('command'):
                source_code_params['command'] = config['command']
            
            source_code = SourceCode(**source_code_params)
        
        # Create Compute configuration
        compute_params = {
            'instance_type': config['instance_type'],
            'instance_count': config['instance_count'],
        }
        
        # Add volume size if provided
        if config.get('volume_size_in_gb'):
            compute_params['volume_size_in_gb'] = config['volume_size_in_gb']
        
        # Add volume KMS key if provided (SDK v3 uses volume_kms_key_id)
        if config.get('volume_kms_key'):
            compute_params['volume_kms_key_id'] = config['volume_kms_key']
        
        # Add keep alive period if provided
        if config.get('keep_alive_period_in_seconds'):
            compute_params['keep_alive_period_in_seconds'] = config['keep_alive_period_in_seconds']
        
        compute = Compute(**compute_params)
        
        # Create ModelTrainer parameters
        trainer_params = {
            'training_image': training_image,
            'compute': compute,
            'base_job_name': job_name,
        }
        
        # Add source code if provided
        if source_code:
            trainer_params['source_code'] = source_code
        
        # Add role if available
        if config.get('role_arn'):
            trainer_params['role'] = config['role_arn']
        
        # Add hyperparameters if provided
        if config.get('hyperparameters'):
            trainer_params['hyperparameters'] = config['hyperparameters']
        
        # Add environment variables if provided
        if config.get('environment'):
            trainer_params['environment'] = config['environment']
        
        # Create OutputDataConfig if output path or KMS key provided
        if config.get('output_path') or config.get('output_kms_key'):
            output_config_params = {}
            if config.get('output_path'):
                output_config_params['s3_output_path'] = config['output_path']
            if config.get('output_kms_key'):
                output_config_params['kms_key_id'] = config['output_kms_key']
            
            if output_config_params:
                trainer_params['output_data_config'] = OutputDataConfig(**output_config_params)
        
        # Add stopping condition if max runtime provided
        if config.get('max_run_in_seconds'):
            trainer_params['stopping_condition'] = StoppingCondition(
                max_runtime_in_seconds=config['max_run_in_seconds']
            )
        
        # Add tags if provided
        if config.get('tags'):
            trainer_params['tags'] = config['tags']
        
        # Add distributed runner if provided
        if config.get('distributed_runner'):
            trainer_params['distributed'] = config['distributed_runner']
        
        # Add metric definitions if provided
        if config.get('metric_definitions'):
            trainer_params['metric_definitions'] = config['metric_definitions']
        
        # Add checkpoint config if provided
        if config.get('checkpoint_s3_uri'):
            trainer_params['checkpoint_s3_uri'] = config['checkpoint_s3_uri']
        
        # Create Networking config if subnets, security groups, or encryption settings provided
        networking_params = {}
        if config.get('subnets'):
            networking_params['subnets'] = config['subnets']
        if config.get('security_group_ids'):
            networking_params['security_group_ids'] = config['security_group_ids']
        if config.get('encrypt_inter_container_traffic') is not None:
            networking_params['enable_inter_container_traffic_encryption'] = config['encrypt_inter_container_traffic']
        if config.get('enable_network_isolation') is not None:
            networking_params['enable_network_isolation'] = config['enable_network_isolation']
        
        if networking_params:
            trainer_params['networking'] = Networking(**networking_params)
        
        # Create ModelTrainer
        model_trainer = ModelTrainer(**trainer_params)
        
        try:
            # Prepare input data configuration
            input_data_config = []
            if inputs:
                if isinstance(inputs, dict):
                    # Convert dict to list of InputData objects
                    for channel_name, data_source in inputs.items():
                        input_data_config.append(
                            InputData(
                                channel_name=channel_name,
                                data_source=data_source,
                                content_type='text/csv'  # Default content type for CSV data
                            )
                        )
                elif isinstance(inputs, list):
                    # Already a list of InputData objects
                    input_data_config = inputs
            elif config.get('inputs'):
                # Use inputs from config
                if isinstance(config['inputs'], dict):
                    for channel_name, data_source in config['inputs'].items():
                        input_data_config.append(
                            InputData(
                                channel_name=channel_name,
                                data_source=data_source,
                                content_type='text/csv'  # Default content type for CSV data
                            )
                        )
                else:
                    input_data_config = config['inputs']
            
            # Build train parameters
            train_params = {}
            if input_data_config:
                train_params['input_data_config'] = input_data_config
            
            # Add wait flag if provided (default is True in ModelTrainer)
            if 'wait' in config:
                train_params['wait'] = config['wait']
            
            self.logger.debug("Starting training job with ModelTrainer",
                            name=job_name,
                            instance_type=config['instance_type'],
                            instance_count=config['instance_count'],
                            has_source_code=source_code is not None)
            
            # Start the training job
            model_trainer.train(**train_params)
            
            self.logger.info("Training job started successfully", name=job_name)
            return model_trainer
            
        except Exception as e:
            self.logger.error("Failed to run training job",
                            name=job_name,
                            error=e)
            raise AWSServiceError(
                f"Failed to run training job '{job_name}': {e}",
                aws_error=e
            ) from e
    
    def _build_training_config(self, runtime_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build training job configuration by merging defaults with runtime parameters.
        
        Parameter precedence: runtime > config > SageMaker defaults
        
        This implements the parameter override behavior specified in Requirements 5.1, 5.2, 5.3, 5.4:
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
            config['instance_type'] = compute_config.training_instance_type
            self.logger.debug("Using config instance_type", value=compute_config.training_instance_type)
        else:
            # Will use SageMaker SDK default
            config['instance_type'] = 'ml.m5.xlarge'
            self.logger.debug("Using default instance_type", value='ml.m5.xlarge')
        
        if 'instance_count' in runtime_params:
            config['instance_count'] = runtime_params['instance_count']
            self.logger.debug("Using runtime instance_count", value=runtime_params['instance_count'])
        elif compute_config:
            config['instance_count'] = compute_config.training_instance_count
            self.logger.debug("Using config instance_count", value=compute_config.training_instance_count)
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
        if 'subnets' in runtime_params:
            config['subnets'] = runtime_params['subnets']
            self.logger.debug("Using runtime subnets")
        elif networking_config:
            config['subnets'] = networking_config.subnets
            self.logger.debug("Using config subnets", subnets=networking_config.subnets)
        
        if 'security_group_ids' in runtime_params:
            config['security_group_ids'] = runtime_params['security_group_ids']
            self.logger.debug("Using runtime security_group_ids")
        elif networking_config:
            config['security_group_ids'] = networking_config.security_group_ids
            self.logger.debug("Using config security_group_ids", 
                            security_groups=networking_config.security_group_ids)
        
        # Apply S3 output path defaults (runtime > config)
        if 'output_path' in runtime_params:
            config['output_path'] = runtime_params['output_path']
            self.logger.debug("Using runtime output_path")
        elif s3_config:
            config['output_path'] = f"s3://{s3_config.default_bucket}/{s3_config.model_prefix}"
            self.logger.debug("Using config output_path", path=config['output_path'])
        
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
        
        # Apply S3 defaults for inputs if not provided (runtime > config)
        if s3_config:
            if 'inputs' not in runtime_params and 'inputs' not in config:
                # Default input location
                default_input_uri = f"s3://{s3_config.default_bucket}/{s3_config.input_prefix}"
                self.logger.debug("Default input S3 URI available", uri=default_input_uri)
        
        # Apply any remaining runtime parameters (these override everything)
        for key, value in runtime_params.items():
            if key not in ['instance_type', 'instance_count', 'role_arn', 
                          'subnets', 'security_group_ids', 'output_path',
                          'volume_kms_key', 'output_kms_key']:
                config[key] = value
                self.logger.debug(f"Using runtime parameter: {key}")
        
        return config
    
    def validate_parameter_override(self, runtime_params: Dict[str, Any]) -> None:
        """
        Validate runtime parameter overrides.
        
        This ensures that runtime parameters are valid and compatible with the configuration.
        Implements validation requirements from Requirements 5.1, 5.2, 5.3, 5.4, 5.5.
        
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
        
        # Validate subnets if provided
        if 'subnets' in runtime_params:
            subnets = runtime_params['subnets']
            if not isinstance(subnets, list):
                raise ValidationError("subnets must be a list")
            
            if not subnets:
                raise ValidationError("subnets list cannot be empty")
        
        # Validate security_group_ids if provided
        if 'security_group_ids' in runtime_params:
            security_groups = runtime_params['security_group_ids']
            if not isinstance(security_groups, list):
                raise ValidationError("security_group_ids must be a list")
            
            if not security_groups:
                raise ValidationError("security_group_ids list cannot be empty")
        
        # Validate output_path if provided
        if 'output_path' in runtime_params:
            output_path = runtime_params['output_path']
            if not isinstance(output_path, str):
                raise ValidationError("output_path must be a string")
            
            if not output_path.startswith('s3://'):
                raise ValidationError(f"output_path must be an S3 URI starting with 's3://', got: {output_path}")
        
        # Validate volume_size_in_gb if provided (ModelTrainer uses volume_size_in_gb)
        if 'volume_size_in_gb' in runtime_params:
            volume_size = runtime_params['volume_size_in_gb']
            if not isinstance(volume_size, int):
                raise ValidationError("volume_size_in_gb must be an integer")
            
            if volume_size < 1:
                raise ValidationError(f"volume_size_in_gb must be at least 1, got {volume_size}")
        
        # Validate max_run_in_seconds if provided (ModelTrainer uses max_run_in_seconds)
        if 'max_run_in_seconds' in runtime_params:
            max_run = runtime_params['max_run_in_seconds']
            if not isinstance(max_run, int):
                raise ValidationError("max_run_in_seconds must be an integer")
            
            if max_run < 1:
                raise ValidationError(f"max_run_in_seconds must be at least 1, got {max_run}")
        
        # Validate inputs if provided
        if 'inputs' in runtime_params:
            inputs = runtime_params['inputs']
            if not isinstance(inputs, (dict, list)):
                raise ValidationError("inputs must be a dictionary or list")
        
        # Validate hyperparameters if provided
        if 'hyperparameters' in runtime_params:
            hyperparameters = runtime_params['hyperparameters']
            if not isinstance(hyperparameters, dict):
                raise ValidationError("hyperparameters must be a dictionary")
        
        # Validate image_uri if provided (now called training_image in ModelTrainer)
        if 'training_image' in runtime_params:
            training_image = runtime_params['training_image']
            if not isinstance(training_image, str):
                raise ValidationError("training_image must be a string")
        
        # Also support legacy image_uri parameter name for backward compatibility
        if 'image_uri' in runtime_params:
            image_uri = runtime_params['image_uri']
            if not isinstance(image_uri, str):
                raise ValidationError("image_uri must be a string")
