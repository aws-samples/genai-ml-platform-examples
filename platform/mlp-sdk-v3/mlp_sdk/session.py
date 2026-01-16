"""
Core MLP_Session class - main interface for all SDK operations
"""

from typing import Optional, Dict, Any, List
import logging
from .config import ConfigurationManager
from .exceptions import MLPSDKError, SessionError, AWSServiceError, ValidationError, MLPLogger, AuditTrail
from .wrappers import FeatureStoreWrapper, ProcessingWrapper, TrainingWrapper, PipelineWrapper, DeploymentWrapper


class MLP_Session:
    """
    Main interface for all mlp_sdk operations.
    
    Provides simplified SageMaker operations with configuration-driven defaults.
    Built on top of SageMaker Python SDK v3.
    """
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 log_level: int = logging.INFO,
                 enable_audit_trail: bool = True,
                 **kwargs):
        """
        Initialize session with optional custom config path.
        
        Args:
            config_path: Optional path to configuration file. 
                        Defaults to /home/sagemaker-user/.config/admin-config.yaml
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_audit_trail: Whether to enable audit trail recording
            **kwargs: Additional session parameters passed to SageMaker session
                     (e.g., boto_session, sagemaker_client, sagemaker_runtime_client)
        
        Raises:
            SessionError: If session initialization fails
            ConfigurationError: If configuration loading fails
        """
        # Initialize logging
        self.logger = MLPLogger("mlp_sdk.session", level=log_level)
        self.logger.info("Initializing MLP_Session", config_path=config_path or "default")
        
        # Initialize audit trail
        self.audit_trail = AuditTrail() if enable_audit_trail else None
        if self.audit_trail is not None:
            self.audit_trail.record("session_init", "started", config_path=config_path)
        
        try:
            # Load configuration
            self.config_manager = ConfigurationManager(config_path)
            
            # Initialize wrappers
            self._feature_store_wrapper = FeatureStoreWrapper(self.config_manager, self.logger)
            self._processing_wrapper = ProcessingWrapper(self.config_manager, self.logger)
            self._training_wrapper = TrainingWrapper(self.config_manager, self.logger)
            self._pipeline_wrapper = PipelineWrapper(self.config_manager, self.logger)
            self._deployment_wrapper = DeploymentWrapper(self.config_manager, self.logger)
            
            # Initialize SageMaker session
            self._sagemaker_session = None
            self._session_kwargs = kwargs
            self._initialize_sagemaker_session()
            
            # Log successful initialization
            self.logger.info("MLP_Session initialized successfully", 
                           has_config=self.config_manager.has_config)
            
            if self.audit_trail is not None:
                self.audit_trail.record("session_init", "completed", 
                                      has_config=self.config_manager.has_config)
                
        except Exception as e:
            self.logger.error("Failed to initialize MLP_Session", error=e)
            if self.audit_trail is not None:
                self.audit_trail.record("session_init", "failed", error=str(e))
            raise SessionError(f"Failed to initialize MLP_Session: {e}") from e
    
    def _initialize_sagemaker_session(self) -> None:
        """
        Initialize underlying SageMaker session.
        
        In SageMaker SDK v3, we use boto3 clients directly along with SessionSettings.
        
        Raises:
            SessionError: If SageMaker session initialization fails
        """
        try:
            # SageMaker SDK v3 uses SessionSettings for configuration
            from sagemaker.core.session_settings import SessionSettings
            from botocore.exceptions import ClientError, NoCredentialsError
            import boto3
            
            # Get default bucket from config if available
            default_bucket = None
            if 'default_bucket' in self._session_kwargs:
                default_bucket = self._session_kwargs.pop('default_bucket')
            else:
                s3_config = self.config_manager.get_s3_config()
                if s3_config:
                    default_bucket = s3_config.default_bucket
            
            # Create boto3 session if not provided
            boto_session = self._session_kwargs.pop('boto_session', None)
            if boto_session is None:
                boto_session = boto3.Session()
            
            # Store boto session and default bucket
            self._boto_session = boto_session
            self._default_bucket = default_bucket
            self._region_name = boto_session.region_name
            
            # Create SageMaker SessionSettings (SDK v3)
            self._sagemaker_session = SessionSettings(**self._session_kwargs)
            
            # Create boto3 clients
            self._sagemaker_client = boto_session.client('sagemaker')
            self._sagemaker_runtime_client = boto_session.client('sagemaker-runtime')
            
            self.logger.debug("SageMaker SessionSettings initialized",
                            region=self._region_name,
                            default_bucket=default_bucket)
            
        except ImportError as e:
            raise SessionError(
                "SageMaker SDK v3 not installed. Install with: pip install sagemaker>=3.0.0"
            ) from e
        except (ClientError, NoCredentialsError) as e:
            raise SessionError(
                f"Failed to initialize SageMaker session due to AWS credentials issue: {e}"
            ) from e
        except Exception as e:
            raise SessionError(
                f"Failed to initialize SageMaker session: {e}"
            ) from e
    
    @property
    def sagemaker_session(self):
        """
        Get underlying SageMaker session for advanced use cases.
        
        This property exposes the underlying SageMaker SDK session object,
        allowing advanced users to access all SageMaker SDK functionality
        directly while still benefiting from mlp_sdk configuration management.
        
        Returns:
            sagemaker.Session object
            
        Example:
            >>> session = MLP_Session()
            >>> # Use underlying SageMaker session for advanced operations
            >>> session.sagemaker_session.list_training_jobs()
        """
        return self._sagemaker_session
    
    @property
    def boto_session(self):
        """
        Get underlying boto3 session.
        
        Provides access to the boto3 session used by SageMaker SDK,
        enabling direct AWS service calls and custom boto3 operations.
        
        Returns:
            boto3.Session object or None
            
        Example:
            >>> session = MLP_Session()
            >>> s3_client = session.boto_session.client('s3')
        """
        return getattr(self, '_boto_session', None)
    
    @property
    def sagemaker_client(self):
        """
        Get underlying SageMaker boto3 client.
        
        Provides direct access to the SageMaker boto3 client for
        low-level API operations not covered by the SageMaker SDK.
        
        Returns:
            boto3 SageMaker client or None
            
        Example:
            >>> session = MLP_Session()
            >>> response = session.sagemaker_client.describe_training_job(
            ...     TrainingJobName='my-job'
            ... )
        """
        return getattr(self, '_sagemaker_client', None)
    
    @property
    def sagemaker_runtime_client(self):
        """
        Get underlying SageMaker Runtime boto3 client.
        
        Provides access to the SageMaker Runtime client for
        invoking deployed endpoints.
        
        Returns:
            boto3 SageMaker Runtime client or None
            
        Example:
            >>> session = MLP_Session()
            >>> response = session.sagemaker_runtime_client.invoke_endpoint(
            ...     EndpointName='my-endpoint',
            ...     Body=json.dumps(data)
            ... )
        """
        return getattr(self, '_sagemaker_runtime_client', None)
    
    @property
    def region_name(self) -> Optional[str]:
        """
        Get AWS region name.
        
        Returns:
            AWS region name or None
        """
        return getattr(self, '_region_name', None)
    
    @property
    def default_bucket(self) -> Optional[str]:
        """
        Get default S3 bucket.
        
        Returns:
            Default S3 bucket name or None
        """
        return getattr(self, '_default_bucket', None)
    
    @property
    def account_id(self) -> Optional[str]:
        """
        Get AWS account ID.
        
        Returns:
            AWS account ID or None
        """
        boto_session = getattr(self, '_boto_session', None)
        if boto_session:
            try:
                sts_client = boto_session.client('sts')
                return sts_client.get_caller_identity()['Account']
            except Exception:
                return None
        return None
    
    def set_log_level(self, level: int) -> None:
        """
        Set logging level.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger.set_level(level)
        self.logger.info("Log level changed", level=logging.getLevelName(level))
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        Get current configuration as dictionary.
        
        Returns:
            Configuration dictionary or None if no config loaded
            
        Example:
            >>> session = MLP_Session()
            >>> config = session.get_config()
            >>> print(config['defaults']['s3']['default_bucket'])
        """
        return self.config_manager._config if self.config_manager.has_config else None
    
    def get_execution_role(self) -> Optional[str]:
        """
        Get IAM execution role ARN from configuration.
        
        Returns:
            IAM role ARN or None if not configured
            
        Example:
            >>> session = MLP_Session()
            >>> role = session.get_execution_role()
        """
        iam_config = self.config_manager.get_iam_config()
        return iam_config.execution_role if iam_config else None
    
    def update_session_config(self, **kwargs) -> None:
        """
        Update session configuration at runtime.
        
        Allows dynamic configuration updates for advanced use cases.
        Note: This recreates the underlying SageMaker session.
        
        Args:
            **kwargs: Configuration parameters to update
                     (e.g., default_bucket, boto_session, sagemaker_client)
        
        Raises:
            SessionError: If session update fails
            
        Example:
            >>> session = MLP_Session()
            >>> session.update_session_config(default_bucket='my-new-bucket')
        """
        self.logger.info("Updating session configuration", params=list(kwargs.keys()))
        
        if self.audit_trail is not None:
            self.audit_trail.record("update_session_config", "started", params=list(kwargs.keys()))
        
        try:
            # Merge with existing kwargs
            self._session_kwargs.update(kwargs)
            
            # Reinitialize SageMaker session
            self._initialize_sagemaker_session()
            
            self.logger.info("Session configuration updated successfully")
            
            if self.audit_trail is not None:
                self.audit_trail.record("update_session_config", "completed")
                
        except Exception as e:
            self.logger.error("Failed to update session configuration", error=e)
            if self.audit_trail is not None:
                self.audit_trail.record("update_session_config", "failed", error=str(e))
            raise SessionError(f"Failed to update session configuration: {e}") from e
    
    def get_audit_trail(self, operation: Optional[str] = None,
                       status: Optional[str] = None,
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get audit trail entries.
        
        Args:
            operation: Filter by operation name
            status: Filter by status
            limit: Maximum number of entries to return
            
        Returns:
            List of audit trail entries
        """
        if not self.audit_trail:
            return []
        return self.audit_trail.get_entries(operation=operation, status=status, limit=limit)
    
    def get_audit_trail_summary(self) -> Dict[str, Any]:
        """
        Get audit trail summary statistics.
        
        Returns:
            Dictionary with summary statistics including operation counts,
            status counts, and failed operations
            
        Raises:
            SessionError: If audit trail is not enabled
        """
        if not self.audit_trail:
            raise SessionError("Audit trail is not enabled for this session")
        
        return self.audit_trail.get_summary()
    
    def export_audit_trail(self, file_path: str, format: str = 'json') -> None:
        """
        Export audit trail to file.
        
        Args:
            file_path: Path to output file
            format: Export format ('json' or 'csv')
            
        Raises:
            SessionError: If audit trail is not enabled
            ValidationError: If format is invalid
        """
        if not self.audit_trail:
            raise SessionError("Audit trail is not enabled for this session")
        
        if format not in ['json', 'csv']:
            raise ValidationError(f"Invalid export format: {format}. Must be 'json' or 'csv'")
        
        if format == 'json':
            self.audit_trail.export_json(file_path)
        else:
            self.audit_trail.export_csv(file_path)
        
        self.logger.info("Audit trail exported", file_path=file_path, format=format)
        
    def create_feature_group(self, 
                            feature_group_name: str,
                            record_identifier_name: str,
                            event_time_feature_name: str,
                            feature_definitions: List[Dict[str, str]],
                            **kwargs):
        """
        Create feature group with defaults.
        
        Args:
            feature_group_name: Name of the feature group
            record_identifier_name: Name of the record identifier feature
            event_time_feature_name: Name of the event time feature
            feature_definitions: List of feature definitions with FeatureName and FeatureType
            **kwargs: Additional feature group parameters that override defaults
            
        Returns:
            FeatureGroup object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            SessionError: If session is not initialized
            AWSServiceError: If feature group creation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters at session level
        if not feature_group_name or not isinstance(feature_group_name, str):
            raise ValidationError("feature_group_name must be a non-empty string")
        
        if not record_identifier_name or not isinstance(record_identifier_name, str):
            raise ValidationError("record_identifier_name must be a non-empty string")
        
        if not event_time_feature_name or not isinstance(event_time_feature_name, str):
            raise ValidationError("event_time_feature_name must be a non-empty string")
        
        if not feature_definitions or not isinstance(feature_definitions, list):
            raise ValidationError("feature_definitions must be a non-empty list")
        
        self.logger.info("create_feature_group called", name=feature_group_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("create_feature_group", "started", name=feature_group_name)
        
        try:
            feature_group = self._feature_store_wrapper.create_feature_group(
                sagemaker_session=self._sagemaker_session,
                feature_group_name=feature_group_name,
                record_identifier_name=record_identifier_name,
                event_time_feature_name=event_time_feature_name,
                feature_definitions=feature_definitions,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("create_feature_group", "completed", name=feature_group_name)
            
            return feature_group
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("create_feature_group", "failed", 
                                      name=feature_group_name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("create_feature_group", "failed", 
                                      name=feature_group_name, error=str(e))
            raise
        
    def run_processing_job(self, 
                          job_name: str,
                          processing_script: Optional[str] = None,
                          inputs: Optional[List[Dict[str, Any]]] = None,
                          outputs: Optional[List[Dict[str, Any]]] = None,
                          **kwargs):
        """
        Execute processing job with defaults.
        
        Args:
            job_name: Processing job name
            processing_script: Optional path to custom processing script
            inputs: Optional list of processing inputs
            outputs: Optional list of processing outputs
            **kwargs: Additional processing job parameters that override defaults
            
        Returns:
            Processor object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            SessionError: If session is not initialized
            AWSServiceError: If processing job execution fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters at session level
        if not job_name or not isinstance(job_name, str):
            raise ValidationError("job_name must be a non-empty string")
        
        # Validate optional parameters if provided
        if inputs is not None and not isinstance(inputs, list):
            raise ValidationError("inputs must be a list if provided")
        
        if outputs is not None and not isinstance(outputs, list):
            raise ValidationError("outputs must be a list if provided")
        
        if processing_script is not None and not isinstance(processing_script, str):
            raise ValidationError("processing_script must be a string if provided")
        
        self.logger.info("run_processing_job called", name=job_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("run_processing_job", "started", name=job_name)
        
        try:
            processor = self._processing_wrapper.run_processing_job(
                sagemaker_session=self._sagemaker_session,
                job_name=job_name,
                processing_script=processing_script,
                inputs=inputs,
                outputs=outputs,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("run_processing_job", "completed", name=job_name)
            
            return processor
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("run_processing_job", "failed",
                                      name=job_name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("run_processing_job", "failed",
                                      name=job_name, error=str(e))
            raise
        
    def run_training_job(self, 
                        job_name: str,
                        training_image: str,
                        source_code_dir: Optional[str] = None,
                        entry_script: Optional[str] = None,
                        requirements: Optional[str] = None,
                        inputs: Optional[Dict[str, Any]] = None,
                        **kwargs):
        """
        Execute training job with defaults using ModelTrainer (SDK v3).
        
        Args:
            job_name: Training job name (used as base_job_name)
            training_image: Container image URI for training
            source_code_dir: Directory containing training script and dependencies
            entry_script: Entry point script for training (e.g., 'train.py')
            requirements: Path to requirements.txt file for dependencies
            inputs: Training data inputs (dict of channel_name: S3 path)
            **kwargs: Additional training job parameters that override defaults
                     (e.g., hyperparameters, environment, distributed_runner)
            
        Returns:
            ModelTrainer object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            SessionError: If session is not initialized
            AWSServiceError: If training job execution fails
            
        Example:
            >>> session = MLP_Session()
            >>> trainer = session.run_training_job(
            ...     job_name='my-training-job',
            ...     training_image='763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.0.0-cpu-py310',
            ...     source_code_dir='training-scripts',
            ...     entry_script='train.py',
            ...     inputs={'train': 's3://my-bucket/data/train/'}
            ... )
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters at session level
        if not job_name or not isinstance(job_name, str):
            raise ValidationError("job_name must be a non-empty string")
        
        if not training_image or not isinstance(training_image, str):
            raise ValidationError("training_image must be a non-empty string")
        
        # Validate optional parameters if provided
        if source_code_dir is not None and not isinstance(source_code_dir, str):
            raise ValidationError("source_code_dir must be a string if provided")
        
        if entry_script is not None and not isinstance(entry_script, str):
            raise ValidationError("entry_script must be a string if provided")
        
        if requirements is not None and not isinstance(requirements, str):
            raise ValidationError("requirements must be a string if provided")
        
        if inputs is not None and not isinstance(inputs, (dict, list)):
            raise ValidationError("inputs must be a dictionary or list if provided")
        
        self.logger.info("run_training_job called", name=job_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("run_training_job", "started", name=job_name)
        
        try:
            trainer = self._training_wrapper.run_training_job(
                sagemaker_session=self._sagemaker_session,
                job_name=job_name,
                training_image=training_image,
                source_code_dir=source_code_dir,
                entry_script=entry_script,
                requirements=requirements,
                inputs=inputs,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("run_training_job", "completed", name=job_name)
            
            return trainer
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("run_training_job", "failed",
                                      name=job_name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("run_training_job", "failed",
                                      name=job_name, error=str(e))
            raise
        
    def deploy_model(self,
                    model_data: str,
                    image_uri: str,
                    endpoint_name: str,
                    enable_vpc: bool = False,
                    **kwargs):
        """
        Deploy a trained model to a SageMaker endpoint with defaults.
        
        Applies defaults from configuration for:
        - Instance type and count (via Compute config)
        - IAM execution role
        - VPC configuration (optional, controlled by enable_vpc flag)
        - KMS encryption key
        
        Runtime parameters override configuration defaults.
        
        Args:
            model_data: S3 URI of the model artifacts (e.g., 's3://bucket/model.tar.gz')
            image_uri: Container image URI for inference
            endpoint_name: Name for the endpoint
            enable_vpc: If True, applies VPC configuration from config (default: False)
            **kwargs: Additional parameters that override defaults
                     (e.g., instance_type, instance_count, environment, subnets, security_group_ids)
            
        Returns:
            Predictor object for making predictions
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            SessionError: If session is not initialized
            AWSServiceError: If deployment fails
            
        Example:
            >>> session = MLP_Session()
            >>> # Deploy without VPC
            >>> predictor = session.deploy_model(
            ...     model_data='s3://my-bucket/model.tar.gz',
            ...     image_uri='683313688378.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1',
            ...     endpoint_name='my-endpoint'
            ... )
            >>> # Deploy with VPC configuration
            >>> predictor = session.deploy_model(
            ...     model_data='s3://my-bucket/model.tar.gz',
            ...     image_uri='683313688378.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1',
            ...     endpoint_name='my-endpoint',
            ...     enable_vpc=True
            ... )
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters at session level
        if not model_data or not isinstance(model_data, str):
            raise ValidationError("model_data must be a non-empty string")
        
        if not image_uri or not isinstance(image_uri, str):
            raise ValidationError("image_uri must be a non-empty string")
        
        if not endpoint_name or not isinstance(endpoint_name, str):
            raise ValidationError("endpoint_name must be a non-empty string")
        
        self.logger.info("deploy_model called", endpoint_name=endpoint_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("deploy_model", "started", endpoint_name=endpoint_name)
        
        try:
            predictor = self._deployment_wrapper.deploy_model(
                model_data=model_data,
                image_uri=image_uri,
                endpoint_name=endpoint_name,
                enable_vpc=enable_vpc,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("deploy_model", "completed", endpoint_name=endpoint_name)
            
            return predictor
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("deploy_model", "failed",
                                      endpoint_name=endpoint_name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("deploy_model", "failed",
                                      endpoint_name=endpoint_name, error=str(e))
            raise
    
    def delete_endpoint(self, endpoint_name: str) -> None:
        """
        Delete a SageMaker endpoint.
        
        Args:
            endpoint_name: Name of the endpoint to delete
            
        Raises:
            ValidationError: If endpoint_name is invalid
            SessionError: If session is not initialized
            AWSServiceError: If deletion fails
            
        Example:
            >>> session = MLP_Session()
            >>> session.delete_endpoint('my-endpoint')
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not endpoint_name or not isinstance(endpoint_name, str):
            raise ValidationError("endpoint_name must be a non-empty string")
        
        self.logger.info("delete_endpoint called", endpoint_name=endpoint_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("delete_endpoint", "started", endpoint_name=endpoint_name)
        
        try:
            # Use boto3 client to delete endpoint
            self._sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
            
            self.logger.info("Endpoint deleted successfully", endpoint_name=endpoint_name)
            
            if self.audit_trail is not None:
                self.audit_trail.record("delete_endpoint", "completed", endpoint_name=endpoint_name)
            
        except Exception as e:
            self.logger.error("Failed to delete endpoint",
                            endpoint_name=endpoint_name,
                            error=e)
            if self.audit_trail is not None:
                self.audit_trail.record("delete_endpoint", "failed",
                                      endpoint_name=endpoint_name, error=str(e))
            raise AWSServiceError(
                f"Failed to delete endpoint '{endpoint_name}': {e}",
                aws_error=e
            ) from e
        
    def create_pipeline(self, 
                       pipeline_name: str, 
                       steps: List,
                       parameters: Optional[List] = None,
                       **kwargs):
        """
        Create pipeline with consistent defaults.
        
        Applies default configurations across all pipeline steps and supports
        parameter passing between steps.
        
        Args:
            pipeline_name: Pipeline name
            steps: List of pipeline steps (ProcessingStep, TrainingStep, etc.)
            parameters: Optional list of pipeline parameters for cross-step communication
            **kwargs: Additional pipeline parameters that override defaults
            
        Returns:
            Pipeline object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            SessionError: If session is not initialized
            AWSServiceError: If pipeline creation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters at session level
        if not pipeline_name or not isinstance(pipeline_name, str):
            raise ValidationError("pipeline_name must be a non-empty string")
        
        if not steps or not isinstance(steps, list):
            raise ValidationError("steps must be a non-empty list")
        
        # Validate optional parameters if provided
        if parameters is not None and not isinstance(parameters, list):
            raise ValidationError("parameters must be a list if provided")
        
        self.logger.info("create_pipeline called", name=pipeline_name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("create_pipeline", "started", name=pipeline_name)
        
        try:
            pipeline = self._pipeline_wrapper.create_pipeline(
                sagemaker_session=self._sagemaker_session,
                pipeline_name=pipeline_name,
                steps=steps,
                parameters=parameters,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("create_pipeline", "completed", name=pipeline_name)
            
            return pipeline
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("create_pipeline", "failed",
                                      name=pipeline_name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("create_pipeline", "failed",
                                      name=pipeline_name, error=str(e))
            raise
    
    def upsert_pipeline(self, pipeline, **kwargs) -> Dict[str, Any]:
        """
        Create or update a pipeline definition.
        
        Args:
            pipeline: Pipeline object to upsert
            **kwargs: Additional parameters for upsert operation
            
        Returns:
            Dictionary with pipeline ARN and other metadata
            
        Raises:
            ValidationError: If pipeline is invalid
            SessionError: If session is not initialized
            AWSServiceError: If upsert operation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not pipeline:
            raise ValidationError("pipeline is required")
        
        if not hasattr(pipeline, 'name'):
            raise ValidationError("pipeline must have a 'name' attribute")
        
        self.logger.info("upsert_pipeline called", name=pipeline.name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("upsert_pipeline", "started", name=pipeline.name)
        
        try:
            response = self._pipeline_wrapper.upsert_pipeline(
                pipeline=pipeline,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("upsert_pipeline", "completed", 
                                      name=pipeline.name,
                                      arn=response.get('PipelineArn'))
            
            return response
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("upsert_pipeline", "failed",
                                      name=pipeline.name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("upsert_pipeline", "failed",
                                      name=pipeline.name, error=str(e))
            raise
    
    def start_pipeline_execution(self,
                                pipeline,
                                execution_display_name: Optional[str] = None,
                                execution_parameters: Optional[Dict[str, Any]] = None,
                                **kwargs):
        """
        Start pipeline execution with monitoring support.
        
        Args:
            pipeline: Pipeline object to execute
            execution_display_name: Optional display name for the execution
            execution_parameters: Optional parameters to override pipeline defaults
            **kwargs: Additional execution parameters
            
        Returns:
            PipelineExecution object
            
        Raises:
            ValidationError: If pipeline is invalid
            SessionError: If session is not initialized
            AWSServiceError: If execution start fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not pipeline:
            raise ValidationError("pipeline is required")
        
        if not hasattr(pipeline, 'name'):
            raise ValidationError("pipeline must have a 'name' attribute")
        
        # Validate optional parameters if provided
        if execution_display_name is not None and not isinstance(execution_display_name, str):
            raise ValidationError("execution_display_name must be a string if provided")
        
        if execution_parameters is not None and not isinstance(execution_parameters, dict):
            raise ValidationError("execution_parameters must be a dictionary if provided")
        
        self.logger.info("start_pipeline_execution called", name=pipeline.name)
        
        if self.audit_trail is not None:
            self.audit_trail.record("start_pipeline_execution", "started", 
                                  name=pipeline.name,
                                  display_name=execution_display_name)
        
        try:
            execution = self._pipeline_wrapper.start_pipeline_execution(
                pipeline=pipeline,
                execution_display_name=execution_display_name,
                execution_parameters=execution_parameters,
                **kwargs
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("start_pipeline_execution", "completed",
                                      name=pipeline.name,
                                      execution_arn=execution.arn)
            
            return execution
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("start_pipeline_execution", "failed",
                                      name=pipeline.name, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("start_pipeline_execution", "failed",
                                      name=pipeline.name, error=str(e))
            raise
    
    def describe_pipeline_execution(self, pipeline_execution) -> Dict[str, Any]:
        """
        Get pipeline execution status and details.
        
        Args:
            pipeline_execution: PipelineExecution object
            
        Returns:
            Dictionary with execution status and details
            
        Raises:
            ValidationError: If pipeline_execution is invalid
            SessionError: If session is not initialized
            AWSServiceError: If describe operation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        if not hasattr(pipeline_execution, 'arn'):
            raise ValidationError("pipeline_execution must have an 'arn' attribute")
        
        self.logger.info("describe_pipeline_execution called", arn=pipeline_execution.arn)
        
        if self.audit_trail is not None:
            self.audit_trail.record("describe_pipeline_execution", "started",
                                  arn=pipeline_execution.arn)
        
        try:
            response = self._pipeline_wrapper.describe_pipeline_execution(
                pipeline_execution=pipeline_execution
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("describe_pipeline_execution", "completed",
                                      arn=pipeline_execution.arn,
                                      status=response.get('PipelineExecutionStatus'))
            
            return response
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("describe_pipeline_execution", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("describe_pipeline_execution", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
    
    def list_pipeline_execution_steps(self, pipeline_execution) -> List[Dict[str, Any]]:
        """
        List all steps in a pipeline execution with their status.
        
        Args:
            pipeline_execution: PipelineExecution object
            
        Returns:
            List of step details with status information
            
        Raises:
            ValidationError: If pipeline_execution is invalid
            SessionError: If session is not initialized
            AWSServiceError: If list operation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        if not hasattr(pipeline_execution, 'arn'):
            raise ValidationError("pipeline_execution must have an 'arn' attribute")
        
        self.logger.info("list_pipeline_execution_steps called", arn=pipeline_execution.arn)
        
        if self.audit_trail is not None:
            self.audit_trail.record("list_pipeline_execution_steps", "started",
                                  arn=pipeline_execution.arn)
        
        try:
            steps = self._pipeline_wrapper.list_pipeline_execution_steps(
                pipeline_execution=pipeline_execution
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("list_pipeline_execution_steps", "completed",
                                      arn=pipeline_execution.arn,
                                      step_count=len(steps))
            
            return steps
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("list_pipeline_execution_steps", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("list_pipeline_execution_steps", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
    
    def wait_for_pipeline_execution(self,
                                   pipeline_execution,
                                   delay: int = 30,
                                   max_attempts: int = 60) -> Dict[str, Any]:
        """
        Wait for pipeline execution to complete.
        
        Args:
            pipeline_execution: PipelineExecution object
            delay: Delay between status checks in seconds (default: 30)
            max_attempts: Maximum number of status checks (default: 60)
            
        Returns:
            Final execution status dictionary
            
        Raises:
            ValidationError: If pipeline_execution is invalid or parameters are invalid
            SessionError: If session is not initialized
            AWSServiceError: If wait operation fails
        """
        # Validate session is initialized
        if not self._sagemaker_session:
            raise SessionError("SageMaker session is not initialized")
        
        # Validate required parameters
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        if not hasattr(pipeline_execution, 'arn'):
            raise ValidationError("pipeline_execution must have an 'arn' attribute")
        
        # Validate delay and max_attempts
        if not isinstance(delay, int) or delay < 1:
            raise ValidationError("delay must be a positive integer")
        
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValidationError("max_attempts must be a positive integer")
        
        self.logger.info("wait_for_pipeline_execution called", 
                        arn=pipeline_execution.arn,
                        delay=delay,
                        max_attempts=max_attempts)
        
        if self.audit_trail is not None:
            self.audit_trail.record("wait_for_pipeline_execution", "started",
                                  arn=pipeline_execution.arn)
        
        try:
            final_status = self._pipeline_wrapper.wait_for_pipeline_execution(
                pipeline_execution=pipeline_execution,
                delay=delay,
                max_attempts=max_attempts
            )
            
            if self.audit_trail is not None:
                self.audit_trail.record("wait_for_pipeline_execution", "completed",
                                      arn=pipeline_execution.arn,
                                      status=final_status.get('PipelineExecutionStatus'))
            
            return final_status
            
        except (ValidationError, SessionError) as e:
            # Re-raise validation and session errors without wrapping
            if self.audit_trail is not None:
                self.audit_trail.record("wait_for_pipeline_execution", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
        except Exception as e:
            if self.audit_trail is not None:
                self.audit_trail.record("wait_for_pipeline_execution", "failed",
                                      arn=pipeline_execution.arn, error=str(e))
            raise
