import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration class for LLaMA fine-tuning pipeline"""
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    SAGEMAKER_ROLE: str = os.getenv("SAGEMAKER_ROLE", "")
    
    # S3 Configuration
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    S3_PREFIX: str = os.getenv("S3_PREFIX", "llama-finetuning")
    
    # Data paths - computed as properties
    @property
    def TRAIN_DATA(self) -> str:
        return f"s3://{self.S3_BUCKET}/{self.S3_PREFIX}/data/train"
    
    @property 
    def TEST_DATA(self) -> str:
        return f"s3://{self.S3_BUCKET}/{self.S3_PREFIX}/data/test"
    
    @property
    def EVAL_RESULTS(self) -> str:
        return f"s3://{self.S3_BUCKET}/{self.S3_PREFIX}/evaluation"
    
    # Model Configuration
    MODEL_ID: str = "meta-textgeneration-llama-2-7b-f"
    MODEL_VERSION: str = "*"  # Use latest version
    
    # Instance Types for different steps
    TRAINING_INSTANCE_TYPE: str = "ml.g5.2xlarge"
    BATCH_TRANSFORM_INSTANCE_TYPE: str = "ml.g5.2xlarge"
    
    # Deprecated - kept for backward compatibility
    INSTANCE_TYPE: str = "ml.g5.2xlarge"
    
    # Pipeline Configuration
    PIPELINE_NAME: str = "llama-finetuning-pipeline"
    MODEL_PACKAGE_GROUP_NAME: str = "llama-finetuned-models"
    
    # MLflow Configuration
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "")
    MLFLOW_TRACKING_ARN: str = os.getenv("MLFLOW_TRACKING_ARN", "")
    
    # Processing Configuration
    PROCESSING_INSTANCE_TYPE: str = "ml.m5.xlarge"
    PROCESSING_INSTANCE_COUNT: int = 1
    
    # Training Hyperparameters
    EPOCHS: str = "4"
    MAX_INPUT_LENGTH: str = "2048"
    INSTRUCTION_TUNED: str = "True"
    
    @classmethod
    def from_file(cls, config_file: str) -> 'Config':
        """Load configuration from a file"""
        import json
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Create a new instance with updated values
        config = cls()
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def validate(self) -> bool:
        """Validate required configuration values"""
        required_fields = [
            'SAGEMAKER_ROLE',
            'S3_BUCKET'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
        
        return True