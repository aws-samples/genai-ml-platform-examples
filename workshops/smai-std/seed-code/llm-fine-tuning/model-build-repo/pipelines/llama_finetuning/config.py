import os
from dataclasses import dataclass, field
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
    # Pinned to the JumpStart 1.x model contract used by Lab 3b, so the
    # container and supported-instance list do not drift between runs.
    MODEL_VERSION: str = "1.1.9"
    
    # Instance Types for different steps
    # Training tries each type in TRAINING_INSTANCE_POOL in order.
    # run_pipeline.py moves to the next type when a type has no capacity or
    # quota, or its training job stays Pending longer than
    # TRAINING_PENDING_TIMEOUT_SECONDS. g4dn.12xlarge goes first: in us-east-1
    # testing it got capacity when the g5 types did not, and with its
    # 1-epoch / 200-sample override it is about the cheapest per job. The g5
    # types are fallbacks. TRAINING_INSTANCE_TYPE is used only when the pool
    # is empty (backward compatible single-type setup); keep it equal to the
    # first pool entry.
    TRAINING_INSTANCE_TYPE: str = "ml.g4dn.12xlarge"
    TRAINING_INSTANCE_POOL: list = field(default_factory=list)
    TRAINING_PENDING_TIMEOUT_SECONDS: int = 360
    # Per-type hyperparameter overrides applied on top of the base values.
    # g4dn.12xlarge (4x T4) is about 4x slower per epoch than g5, so it trains
    # 1 epoch on a 200-sample subset to keep the lab within its time budget.
    # max_train_samples must not exceed the training split (370 rows).
    TRAINING_HP_OVERRIDES: dict = field(default_factory=lambda: {
        "ml.g4dn.12xlarge": {"epoch": "1", "max_train_samples": "200"},
    })
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
    EPOCHS: str = "2"
    MAX_INPUT_LENGTH: str = "2048"
    INSTRUCTION_TUNED: str = "True"
    
    def training_pool(self) -> list:
        """Ordered, de-duplicated training instance types to try."""
        return list(dict.fromkeys(
            self.TRAINING_INSTANCE_POOL or [self.TRAINING_INSTANCE_TYPE]
        ))

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