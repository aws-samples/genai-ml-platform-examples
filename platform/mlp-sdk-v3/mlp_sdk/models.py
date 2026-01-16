"""
Data models and configuration schemas for mlp_sdk
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class S3Config:
    """S3 configuration settings"""
    default_bucket: str
    input_prefix: str = "input/"
    output_prefix: str = "output/"
    model_prefix: str = "models/"


@dataclass
class NetworkingConfig:
    """Networking configuration settings"""
    vpc_id: str
    security_group_ids: List[str]
    subnets: List[str]


@dataclass
class ComputeConfig:
    """Compute configuration settings"""
    processing_instance_type: str = "ml.m5.large"
    training_instance_type: str = "ml.m5.xlarge"
    processing_instance_count: int = 1
    training_instance_count: int = 1


@dataclass
class FeatureStoreConfig:
    """Feature Store configuration settings"""
    offline_store_s3_uri: str
    enable_online_store: bool = False


@dataclass
class IAMConfig:
    """IAM configuration settings"""
    execution_role: str


@dataclass
class KMSConfig:
    """KMS configuration settings"""
    key_id: Optional[str] = None


@dataclass
class MLPConfig:
    """Main configuration container"""
    s3_config: S3Config
    networking_config: NetworkingConfig
    compute_config: ComputeConfig
    feature_store_config: FeatureStoreConfig
    iam_config: IAMConfig
    kms_config: Optional[KMSConfig] = None