"""
Pipeline wrapper for mlp_sdk
Provides simplified pipeline creation with configuration-driven defaults
"""

from typing import Optional, Dict, Any, List, Union
from ..exceptions import MLPSDKError, ValidationError, AWSServiceError, MLPLogger
from ..config import ConfigurationManager


class PipelineWrapper:
    """
    Wrapper for SageMaker Pipeline operations.
    Applies default configurations from ConfigurationManager.
    """
    
    def __init__(self, config_manager: ConfigurationManager, logger: Optional[MLPLogger] = None):
        """
        Initialize Pipeline wrapper.
        
        Args:
            config_manager: Configuration manager instance
            logger: Optional logger instance
        """
        self.config_manager = config_manager
        self.logger = logger or MLPLogger("mlp_sdk.pipeline")
    
    def create_pipeline(self,
                       sagemaker_session,
                       pipeline_name: str,
                       steps: List,
                       parameters: Optional[List] = None,
                       **kwargs) -> Any:
        """
        Create pipeline with step connection and consistent default configurations.
        
        Applies defaults from configuration for:
        - IAM execution role
        - Pipeline parameters
        - Step-level configurations (inherited from processing/training defaults)
        
        Runtime parameters override configuration defaults.
        
        Supports parameter passing between pipeline steps.
        
        Args:
            sagemaker_session: SageMaker session object
            pipeline_name: Name of the pipeline
            steps: List of pipeline steps (ProcessingStep, TrainingStep, etc.)
            parameters: Optional list of pipeline parameters for cross-step communication
            **kwargs: Additional parameters that override defaults
            
        Returns:
            Pipeline object
            
        Raises:
            ValidationError: If required parameters are missing or invalid
            AWSServiceError: If pipeline creation fails
        """
        self.logger.info("Creating pipeline", name=pipeline_name)
        
        # Validate required parameters
        if not pipeline_name:
            raise ValidationError("pipeline_name is required")
        
        if not steps:
            raise ValidationError("steps is required and cannot be empty")
        
        if not isinstance(steps, list):
            raise ValidationError("steps must be a list")
        
        # Validate runtime parameter overrides
        self.validate_parameter_override(kwargs)
        
        try:
            from sagemaker.workflow.pipeline import Pipeline
        except ImportError as e:
            raise MLPSDKError(
                "SageMaker SDK not installed. Install with: pip install sagemaker>=3.0.0"
            ) from e
        
        # Build configuration with defaults
        config = self._build_pipeline_config(kwargs)
        
        # Build pipeline parameters
        pipeline_params = {
            'name': pipeline_name,
            'steps': steps,
            'sagemaker_session': sagemaker_session,
        }
        
        # Add parameters if provided
        if parameters:
            pipeline_params['parameters'] = parameters
        elif config.get('parameters'):
            pipeline_params['parameters'] = config['parameters']
        
        # Add role ARN if available
        if config.get('role_arn'):
            pipeline_params['role_arn'] = config['role_arn']
        
        # Add pipeline definition config if provided
        if config.get('pipeline_definition_config'):
            pipeline_params['pipeline_definition_config'] = config['pipeline_definition_config']
        
        try:
            self.logger.debug("Creating pipeline with config",
                            name=pipeline_name,
                            step_count=len(steps),
                            has_parameters=bool(parameters or config.get('parameters')))
            
            # Create the pipeline
            pipeline = Pipeline(**pipeline_params)
            
            self.logger.info("Pipeline created successfully", name=pipeline_name)
            return pipeline
            
        except Exception as e:
            self.logger.error("Failed to create pipeline",
                            name=pipeline_name,
                            error=e)
            raise AWSServiceError(
                f"Failed to create pipeline '{pipeline_name}': {e}",
                aws_error=e
            ) from e
    
    def upsert_pipeline(self,
                       pipeline,
                       **kwargs) -> Dict[str, Any]:
        """
        Create or update a pipeline definition.
        
        Args:
            pipeline: Pipeline object to upsert
            **kwargs: Additional parameters for upsert operation
            
        Returns:
            Dictionary with pipeline ARN and other metadata
            
        Raises:
            ValidationError: If pipeline is invalid
            AWSServiceError: If upsert operation fails
        """
        self.logger.info("Upserting pipeline", name=pipeline.name)
        
        if not pipeline:
            raise ValidationError("pipeline is required")
        
        try:
            # Build upsert parameters
            upsert_params = {}
            
            # Add role ARN if provided
            if 'role_arn' in kwargs:
                upsert_params['role_arn'] = kwargs['role_arn']
            
            # Add description if provided
            if 'description' in kwargs:
                upsert_params['description'] = kwargs['description']
            
            # Add tags if provided
            if 'tags' in kwargs:
                upsert_params['tags'] = kwargs['tags']
            
            # Add parallelism config if provided
            if 'parallelism_config' in kwargs:
                upsert_params['parallelism_config'] = kwargs['parallelism_config']
            
            self.logger.debug("Upserting pipeline", name=pipeline.name)
            
            # Upsert the pipeline
            response = pipeline.upsert(**upsert_params)
            
            self.logger.info("Pipeline upserted successfully", 
                           name=pipeline.name,
                           arn=response.get('PipelineArn'))
            
            return response
            
        except Exception as e:
            self.logger.error("Failed to upsert pipeline",
                            name=pipeline.name,
                            error=e)
            raise AWSServiceError(
                f"Failed to upsert pipeline '{pipeline.name}': {e}",
                aws_error=e
            ) from e
    
    def start_pipeline_execution(self,
                                pipeline,
                                execution_display_name: Optional[str] = None,
                                execution_parameters: Optional[Dict[str, Any]] = None,
                                **kwargs) -> Any:
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
            AWSServiceError: If execution start fails
        """
        self.logger.info("Starting pipeline execution", 
                        name=pipeline.name,
                        display_name=execution_display_name)
        
        if not pipeline:
            raise ValidationError("pipeline is required")
        
        try:
            # Build execution parameters
            exec_params = {}
            
            # Add display name if provided
            if execution_display_name:
                exec_params['execution_display_name'] = execution_display_name
            
            # Add execution parameters if provided
            if execution_parameters:
                exec_params['parameters'] = execution_parameters
            
            # Add parallelism config if provided
            if 'parallelism_config' in kwargs:
                exec_params['parallelism_config'] = kwargs['parallelism_config']
            
            self.logger.debug("Starting pipeline execution",
                            name=pipeline.name,
                            has_parameters=bool(execution_parameters))
            
            # Start the execution
            execution = pipeline.start(**exec_params)
            
            self.logger.info("Pipeline execution started successfully",
                           name=pipeline.name,
                           execution_arn=execution.arn)
            
            return execution
            
        except Exception as e:
            self.logger.error("Failed to start pipeline execution",
                            name=pipeline.name,
                            error=e)
            raise AWSServiceError(
                f"Failed to start pipeline execution for '{pipeline.name}': {e}",
                aws_error=e
            ) from e
    
    def describe_pipeline_execution(self,
                                   pipeline_execution) -> Dict[str, Any]:
        """
        Get pipeline execution status and details.
        
        Args:
            pipeline_execution: PipelineExecution object
            
        Returns:
            Dictionary with execution status and details
            
        Raises:
            ValidationError: If pipeline_execution is invalid
            AWSServiceError: If describe operation fails
        """
        self.logger.info("Describing pipeline execution", arn=pipeline_execution.arn)
        
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        try:
            # Describe the execution
            response = pipeline_execution.describe()
            
            self.logger.debug("Pipeline execution described",
                            arn=pipeline_execution.arn,
                            status=response.get('PipelineExecutionStatus'))
            
            return response
            
        except Exception as e:
            self.logger.error("Failed to describe pipeline execution",
                            arn=pipeline_execution.arn,
                            error=e)
            raise AWSServiceError(
                f"Failed to describe pipeline execution: {e}",
                aws_error=e
            ) from e
    
    def list_pipeline_execution_steps(self,
                                     pipeline_execution) -> List[Dict[str, Any]]:
        """
        List all steps in a pipeline execution with their status.
        
        Args:
            pipeline_execution: PipelineExecution object
            
        Returns:
            List of step details with status information
            
        Raises:
            ValidationError: If pipeline_execution is invalid
            AWSServiceError: If list operation fails
        """
        self.logger.info("Listing pipeline execution steps", arn=pipeline_execution.arn)
        
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        try:
            # List execution steps
            steps = pipeline_execution.list_steps()
            
            self.logger.debug("Pipeline execution steps listed",
                            arn=pipeline_execution.arn,
                            step_count=len(steps))
            
            return steps
            
        except Exception as e:
            self.logger.error("Failed to list pipeline execution steps",
                            arn=pipeline_execution.arn,
                            error=e)
            raise AWSServiceError(
                f"Failed to list pipeline execution steps: {e}",
                aws_error=e
            ) from e
    
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
            ValidationError: If pipeline_execution is invalid
            AWSServiceError: If wait operation fails
        """
        self.logger.info("Waiting for pipeline execution",
                        arn=pipeline_execution.arn,
                        delay=delay,
                        max_attempts=max_attempts)
        
        if not pipeline_execution:
            raise ValidationError("pipeline_execution is required")
        
        try:
            # Wait for completion
            pipeline_execution.wait(delay=delay, max_attempts=max_attempts)
            
            # Get final status
            final_status = pipeline_execution.describe()
            
            self.logger.info("Pipeline execution completed",
                           arn=pipeline_execution.arn,
                           status=final_status.get('PipelineExecutionStatus'))
            
            return final_status
            
        except Exception as e:
            self.logger.error("Failed while waiting for pipeline execution",
                            arn=pipeline_execution.arn,
                            error=e)
            raise AWSServiceError(
                f"Failed while waiting for pipeline execution: {e}",
                aws_error=e
            ) from e
    
    def _build_pipeline_config(self, runtime_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build pipeline configuration by merging defaults with runtime parameters.
        
        Parameter precedence: runtime > config > SageMaker defaults
        
        This implements the parameter override behavior specified in Requirements 6.1, 6.2, 6.3:
        - Runtime parameters always take precedence over configuration defaults
        - Configuration defaults take precedence over SageMaker SDK defaults
        - Individual step configurations can be overridden while maintaining pipeline-level defaults
        
        Args:
            runtime_params: Runtime parameters provided by user
            
        Returns:
            Merged configuration dictionary
        """
        config = {}
        
        # Get configuration objects
        iam_config = self.config_manager.get_iam_config()
        
        # Apply IAM role default (runtime > config)
        if 'role_arn' in runtime_params:
            config['role_arn'] = runtime_params['role_arn']
            self.logger.debug("Using runtime role_arn")
        elif iam_config:
            config['role_arn'] = iam_config.execution_role
            self.logger.debug("Using config role_arn", role=iam_config.execution_role)
        
        # Apply any remaining runtime parameters (these override everything)
        for key, value in runtime_params.items():
            if key not in ['role_arn']:
                config[key] = value
                self.logger.debug(f"Using runtime parameter: {key}")
        
        return config
    
    def validate_parameter_override(self, runtime_params: Dict[str, Any]) -> None:
        """
        Validate runtime parameter overrides.
        
        This ensures that runtime parameters are valid and compatible with the configuration.
        Implements validation requirements from Requirements 6.1, 6.2, 6.3, 6.5.
        
        Args:
            runtime_params: Runtime parameters to validate
            
        Raises:
            ValidationError: If runtime parameters are invalid
        """
        # Validate role_arn format if provided
        if 'role_arn' in runtime_params:
            role_arn = runtime_params['role_arn']
            if not isinstance(role_arn, str):
                raise ValidationError("role_arn must be a string")
            
            if not role_arn.startswith('arn:aws:iam::'):
                raise ValidationError(f"Invalid IAM role ARN format: {role_arn}")
        
        # Validate parameters if provided
        if 'parameters' in runtime_params:
            parameters = runtime_params['parameters']
            if not isinstance(parameters, list):
                raise ValidationError("parameters must be a list")
        
        # Validate pipeline_definition_config if provided
        if 'pipeline_definition_config' in runtime_params:
            pipeline_def_config = runtime_params['pipeline_definition_config']
            if not isinstance(pipeline_def_config, dict):
                raise ValidationError("pipeline_definition_config must be a dictionary")
