"""
Deployment wrapper for mlp_sdk
Provides simplified model deployment with configuration-driven defaults

Uses SageMaker SDK v3 ModelBuilder API for modern deployment.
"""

from typing import Optional, Dict, Any
from ..exceptions import MLPSDKError, ValidationError, AWSServiceError, MLPLogger
from ..config import ConfigurationManager


class PredictorWrapper:
    """
    Wrapper around SDK v3 Endpoint object to provide a predict() method.
    
    SDK v3's ModelBuilder.deploy() returns an Endpoint object with invoke() method.
    This wrapper provides backward compatibility by adding a predict() method
    that calls invoke() internally.
    """
    
    def __init__(self, endpoint, logger: Optional[MLPLogger] = None):
        """
        Initialize predictor wrapper.
        
        Args:
            endpoint: SDK v3 Endpoint object returned by ModelBuilder.deploy()
            logger: Optional logger instance
        """
        self._endpoint = endpoint
        self.logger = logger or MLPLogger("mlp_sdk.predictor")
        
        # Expose endpoint attributes
        self.endpoint_name = getattr(endpoint, 'endpoint_name', None)
    
    def predict(self, data, content_type: str = 'text/csv'):
        """
        Make predictions using the endpoint.
        
        This method provides backward compatibility with SDK v2 Predictor interface.
        Uses boto3 sagemaker-runtime client for reliable invocation.
        
        Args:
            data: Input data for prediction (string or bytes)
            content_type: Content type of the input data (default: 'text/csv')
            
        Returns:
            Prediction results as string
            
        Raises:
            AWSServiceError: If prediction fails
        """
        try:
            import boto3
            
            # Convert string to bytes if needed (boto3 expects bytes)
            if isinstance(data, str):
                body_data = data.encode('utf-8')
            else:
                body_data = data
            
            # Use boto3 sagemaker-runtime client for reliable invocation
            # This is more stable than SDK v3 Endpoint.invoke() which has serialization issues
            runtime_client = boto3.client('sagemaker-runtime')
            
            response = runtime_client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType=content_type,
                Body=body_data
            )
            
            # Read and decode the response body
            result = response['Body'].read().decode('utf-8')
            
            return result
            
        except Exception as e:
            self.logger.error("Prediction failed", error=e)
            raise AWSServiceError(
                f"Failed to make prediction: {e}",
                aws_error=e
            ) from e
    
    def invoke(self, body, content_type: str = 'application/json'):
        """
        Invoke the endpoint directly using boto3 sagemaker-runtime client.
        
        Args:
            body: Request body (bytes or string)
            content_type: Content type of the request
            
        Returns:
            Response from the endpoint
            
        Raises:
            AWSServiceError: If invocation fails
        """
        try:
            import boto3
            
            # Convert string to bytes if needed
            if isinstance(body, str):
                body_data = body.encode('utf-8')
            else:
                body_data = body
            
            # Use boto3 sagemaker-runtime client
            runtime_client = boto3.client('sagemaker-runtime')
            
            response = runtime_client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType=content_type,
                Body=body_data
            )
            
            return response
            
        except Exception as e:
            self.logger.error("Invocation failed", error=e)
            raise AWSServiceError(
                f"Failed to invoke endpoint: {e}",
                aws_error=e
            ) from e
    
    def delete_endpoint(self):
        """
        Delete the endpoint.
        
        Raises:
            AWSServiceError: If deletion fails
        """
        try:
            if hasattr(self._endpoint, 'delete'):
                self._endpoint.delete()
            else:
                raise MLPSDKError("Endpoint object does not support delete operation")
        except Exception as e:
            self.logger.error("Failed to delete endpoint", error=e)
            raise AWSServiceError(
                f"Failed to delete endpoint: {e}",
                aws_error=e
            ) from e


class DeploymentWrapper:
    """
    Wrapper for SageMaker Model Deployment operations (SDK v3).
    Applies default configurations from ConfigurationManager.
    """
    
    def __init__(self, config_manager: ConfigurationManager, logger: Optional[MLPLogger] = None):
        """
        Initialize Deployment wrapper.
        
        Args:
            config_manager: Configuration manager instance
            logger: Optional logger instance
        """
        self.config_manager = config_manager
        self.logger = logger or MLPLogger("mlp_sdk.deployment")
    
    def deploy_model(self,
                    model_data: str,
                    image_uri: str,
                    endpoint_name: str,
                    enable_vpc: bool = False,
                    **kwargs) -> Any:
        """
        Deploy a trained model to a SageMaker endpoint with default configurations.
        
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
            AWSServiceError: If deployment fails
        """
        self.logger.info("Deploying model to endpoint", endpoint_name=endpoint_name)
        
        # Validate required parameters
        if not model_data:
            raise ValidationError("model_data is required")
        
        if not image_uri:
            raise ValidationError("image_uri is required")
        
        if not endpoint_name:
            raise ValidationError("endpoint_name is required")
        
        # Validate runtime parameter overrides
        self.validate_parameter_override(kwargs)
        
        try:
            from sagemaker.serve.model_builder import ModelBuilder
        except ImportError as e:
            raise MLPSDKError(
                "SageMaker SDK v3 not installed. "
                "Install with: pip install sagemaker>=3.0.0"
            ) from e
        
        # Build configuration with defaults
        config = self._build_deployment_config(kwargs, enable_vpc=enable_vpc)
        
        try:
            # Create ModelBuilder with model artifacts
            model_builder_params = {
                's3_model_data_url': model_data,  # SDK v3 uses s3_model_data_url
                'image_uri': image_uri,
            }
            
            # Add role if available
            if config.get('role_arn'):
                model_builder_params['role_arn'] = config['role_arn']
            
            # Add environment variables if provided
            if config.get('environment'):
                model_builder_params['env_vars'] = config['environment']
            
            # Add instance type if provided
            if config.get('instance_type'):
                model_builder_params['instance_type'] = config['instance_type']
            
            self.logger.debug("Creating ModelBuilder", 
                            model_data=model_data,
                            image_uri=image_uri)
            
            # Create ModelBuilder
            model_builder = ModelBuilder(**model_builder_params)
            
            # Build the model
            model = model_builder.build()
            
            # Set VPC config on the built model if available and enabled
            # ModelBuilder doesn't accept vpc_config, but the underlying Model object does
            # SDK v3 Model expects lowercase keys: 'subnets' and 'security_group_ids'
            if enable_vpc and config.get('subnets') and config.get('security_group_ids'):
                vpc_config = {
                    'subnets': config['subnets'],
                    'security_group_ids': config['security_group_ids']
                }
                # Set vpc_config on the model object
                if hasattr(model, 'vpc_config'):
                    model.vpc_config = vpc_config
                    self.logger.info("VPC configuration enabled for endpoint", 
                                   subnets=config['subnets'],
                                   security_groups=config['security_group_ids'])
                else:
                    self.logger.warning("Model object does not support vpc_config attribute")
            elif enable_vpc:
                self.logger.warning("VPC configuration requested but subnets or security groups not available in config")
            else:
                self.logger.info("VPC configuration disabled for endpoint deployment")
            
            # Deploy model to endpoint using ModelBuilder.deploy()
            # SDK v3: ModelBuilder.deploy() returns an Endpoint object (not Predictor)
            deploy_params = {
                'model': model,
                'endpoint_name': endpoint_name,
            }
            
            # Add instance count
            if config.get('instance_count'):
                deploy_params['initial_instance_count'] = config['instance_count']
            
            # Add wait flag (default is True)
            if 'wait' in config:
                deploy_params['wait'] = config['wait']
            
            self.logger.debug("Deploying model to endpoint",
                            endpoint_name=endpoint_name,
                            instance_type=config.get('instance_type'),
                            instance_count=config.get('instance_count'))
            
            # Deploy the model using ModelBuilder.deploy()
            # SDK v3: ModelBuilder.deploy() returns an Endpoint object (not Predictor)
            # The Endpoint object has invoke() method with PascalCase parameters
            endpoint = model_builder.deploy(**deploy_params)
            
            # Wrap the endpoint to provide predict() method for backward compatibility
            predictor = PredictorWrapper(endpoint, self.logger)
            
            self.logger.info("Model deployed successfully", endpoint_name=endpoint_name)
            return predictor
            
        except Exception as e:
            self.logger.error("Failed to deploy model",
                            endpoint_name=endpoint_name,
                            error=e)
            raise AWSServiceError(
                f"Failed to deploy model to endpoint '{endpoint_name}': {e}",
                aws_error=e
            ) from e
    
    def _build_deployment_config(self, runtime_params: Dict[str, Any], enable_vpc: bool = False) -> Dict[str, Any]:
        """
        Build deployment configuration by merging defaults with runtime parameters.
        
        Parameter precedence: runtime > config > SageMaker defaults
        
        Args:
            runtime_params: Runtime parameters provided by user
            enable_vpc: If True, includes VPC configuration from config
            
        Returns:
            Merged configuration dictionary
        """
        config = {}
        
        # Get configuration objects
        compute_config = self.config_manager.get_compute_config()
        networking_config = self.config_manager.get_networking_config()
        iam_config = self.config_manager.get_iam_config()
        kms_config = self.config_manager.get_kms_config()
        
        # Apply compute defaults (runtime > config)
        if 'instance_type' in runtime_params:
            config['instance_type'] = runtime_params['instance_type']
            self.logger.debug("Using runtime instance_type", value=runtime_params['instance_type'])
        elif compute_config and hasattr(compute_config, 'inference_instance_type'):
            config['instance_type'] = compute_config.inference_instance_type
            self.logger.debug("Using config instance_type", value=compute_config.inference_instance_type)
        else:
            # Use default for inference
            config['instance_type'] = 'ml.m5.large'
            self.logger.debug("Using default instance_type", value='ml.m5.large')
        
        if 'instance_count' in runtime_params:
            config['instance_count'] = runtime_params['instance_count']
            self.logger.debug("Using runtime instance_count", value=runtime_params['instance_count'])
        elif compute_config and hasattr(compute_config, 'inference_instance_count'):
            config['instance_count'] = compute_config.inference_instance_count
            self.logger.debug("Using config instance_count", value=compute_config.inference_instance_count)
        else:
            # Use default for inference
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
        
        # Apply networking defaults (runtime > config) - only if VPC is enabled
        if enable_vpc:
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
        else:
            self.logger.debug("VPC configuration disabled, skipping network config")
        
        # Apply KMS encryption defaults (runtime > config)
        if 'kms_key' in runtime_params:
            config['kms_key'] = runtime_params['kms_key']
            self.logger.debug("Using runtime kms_key")
        elif kms_config and kms_config.key_id:
            config['kms_key'] = kms_config.key_id
            self.logger.debug("Using config kms_key", key_id=kms_config.key_id)
        
        # Apply any remaining runtime parameters
        for key, value in runtime_params.items():
            if key not in ['instance_type', 'instance_count', 'role_arn', 
                          'subnets', 'security_group_ids', 'kms_key']:
                config[key] = value
                self.logger.debug(f"Using runtime parameter: {key}")
        
        return config
    
    def validate_parameter_override(self, runtime_params: Dict[str, Any]) -> None:
        """
        Validate runtime parameter overrides.
        
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
        
        # Validate environment if provided
        if 'environment' in runtime_params:
            environment = runtime_params['environment']
            if not isinstance(environment, dict):
                raise ValidationError("environment must be a dictionary")
