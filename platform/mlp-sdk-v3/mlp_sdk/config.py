"""
Configuration management for mlp_sdk
"""

from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator
import yaml
import os
import base64
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from .exceptions import ConfigurationError


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


# Pydantic models for YAML schema validation
class S3ConfigSchema(BaseModel):
    """Pydantic schema for S3 configuration validation"""
    default_bucket: str = Field(..., min_length=3, max_length=63)
    input_prefix: str = Field(default="input/", pattern=r"^[a-zA-Z0-9\-_/]*/$")
    output_prefix: str = Field(default="output/", pattern=r"^[a-zA-Z0-9\-_/]*/$")
    model_prefix: str = Field(default="models/", pattern=r"^[a-zA-Z0-9\-_/]*/$")

    @field_validator('default_bucket')
    @classmethod
    def validate_bucket_name(cls, v):
        """Validate S3 bucket name format"""
        if not v.replace('-', '').replace('.', '').isalnum():
            raise ValueError('Bucket name must contain only alphanumeric characters, hyphens, and dots')
        return v


class NetworkingConfigSchema(BaseModel):
    """Pydantic schema for networking configuration validation"""
    vpc_id: str = Field(..., pattern=r"^vpc-[a-f0-9]{8,17}$")
    security_group_ids: List[str] = Field(..., min_length=1)
    subnets: List[str] = Field(..., min_length=1)

    @field_validator('security_group_ids')
    @classmethod
    def validate_security_group_id(cls, v):
        """Validate security group ID format"""
        for sg_id in v:
            if not sg_id.startswith('sg-') or len(sg_id) < 11:
                raise ValueError(f'Invalid security group ID format: {sg_id}')
        return v

    @field_validator('subnets')
    @classmethod
    def validate_subnet_id(cls, v):
        """Validate subnet ID format"""
        for subnet_id in v:
            if not subnet_id.startswith('subnet-') or len(subnet_id) < 15:
                raise ValueError(f'Invalid subnet ID format: {subnet_id}')
        return v


class ComputeConfigSchema(BaseModel):
    """Pydantic schema for compute configuration validation"""
    processing_instance_type: str = Field(default="ml.m5.large", pattern=r"^ml\.[a-z0-9]+\.[a-z0-9]+$")
    training_instance_type: str = Field(default="ml.m5.xlarge", pattern=r"^ml\.[a-z0-9]+\.[a-z0-9]+$")
    processing_instance_count: int = Field(default=1, ge=1, le=100)
    training_instance_count: int = Field(default=1, ge=1, le=100)


class FeatureStoreConfigSchema(BaseModel):
    """Pydantic schema for feature store configuration validation"""
    offline_store_s3_uri: str = Field(..., pattern=r"^s3://[a-zA-Z0-9\-_./]+$")
    enable_online_store: bool = Field(default=False)


class IAMConfigSchema(BaseModel):
    """Pydantic schema for IAM configuration validation"""
    execution_role: str = Field(..., pattern=r"^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@\-_/]+$")


class KMSConfigSchema(BaseModel):
    """Pydantic schema for KMS configuration validation"""
    key_id: Optional[str] = Field(None, pattern=r"^(arn:aws:kms:[a-z0-9\-]+:\d{12}:key/)?[a-f0-9\-]{36}$")


class DefaultsConfigSchema(BaseModel):
    """Pydantic schema for the defaults section of YAML config"""
    s3: S3ConfigSchema
    networking: NetworkingConfigSchema
    compute: ComputeConfigSchema = Field(default_factory=ComputeConfigSchema)
    feature_store: FeatureStoreConfigSchema
    iam: IAMConfigSchema
    kms: Optional[KMSConfigSchema] = None


class MLPConfigSchema(BaseModel):
    """Pydantic schema for the complete YAML configuration"""
    defaults: DefaultsConfigSchema


class ConfigurationManager:
    """
    Handles loading and merging configuration from multiple sources.
    Supports encryption/decryption of sensitive configuration values.
    """
    
    DEFAULT_CONFIG_PATH = "/home/sagemaker-user/.config/admin-config.yaml"
    
    def __init__(self, config_path: Optional[str] = None, encryption_key: Optional[Union[str, bytes]] = None):
        """
        Load config from specified path or default location.
        
        Args:
            config_path: Optional custom configuration file path
            encryption_key: Optional encryption key for decrypting sensitive values.
                          Can be a base64-encoded string or raw bytes.
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config = {}
        self._MLP_config: Optional[MLPConfig] = None
        self._encryption_key = self._process_encryption_key(encryption_key) if encryption_key else None
        self._load_configuration()
        
    def _load_configuration(self) -> None:
        """
        Load and validate configuration from YAML file.
        
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        config_file = Path(self.config_path)
        
        # If config file doesn't exist, use empty config (SageMaker SDK defaults will be used)
        if not config_file.exists():
            self._config = {}
            self._MLP_config = None
            return
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
                
            if not raw_config:
                self._config = {}
                self._MLP_config = None
                return
                
            # Validate configuration using Pydantic schema
            validated_config = MLPConfigSchema(**raw_config)
            self._config = validated_config.model_dump()
            
            # Convert to dataclass structure
            defaults = self._config['defaults']
            self._MLP_config = MLPConfig(
                s3_config=S3Config(**defaults['s3']),
                networking_config=NetworkingConfig(**defaults['networking']),
                compute_config=ComputeConfig(**defaults['compute']),
                feature_store_config=FeatureStoreConfig(**defaults['feature_store']),
                iam_config=IAMConfig(**defaults['iam']),
                kms_config=KMSConfig(**defaults['kms']) if defaults.get('kms') else None
            )
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML syntax in config file {self.config_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from {self.config_path}: {e}")
        
    def get_default(self, key: str, fallback: Any = None) -> Any:
        """
        Get configuration value with fallback.
        
        Args:
            key: Configuration key (supports dot notation like 's3.default_bucket')
            fallback: Fallback value if key not found
            
        Returns:
            Configuration value or fallback
        """
        if not self._config:
            return fallback
            
        # Navigate through nested dictionary using dot notation
        keys = key.split('.')
        current = self._config.get('defaults', {})
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return fallback
                
        return current
        
    def merge_with_runtime(self, runtime_config: Dict) -> Dict:
        """
        Merge runtime parameters with defaults.
        
        Args:
            runtime_config: Runtime configuration parameters
            
        Returns:
            Merged configuration dictionary with runtime values taking precedence
        """
        if not self._config:
            return runtime_config
            
        # Start with defaults
        merged = self._config.get('defaults', {}).copy()
        
        # Deep merge runtime config (runtime takes precedence)
        def deep_merge(base: Dict, override: Dict) -> Dict:
            """Recursively merge dictionaries"""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
            
        return deep_merge(merged, runtime_config)
    
    @property
    def MLP_config(self) -> Optional[MLPConfig]:
        """Get the parsed MLPConfig object"""
        return self._MLP_config
    
    @property
    def has_config(self) -> bool:
        """Check if configuration was successfully loaded"""
        return bool(self._config)
    
    def get_s3_config(self) -> Optional[S3Config]:
        """Get S3 configuration"""
        return self._MLP_config.s3_config if self._MLP_config else None
    
    def get_networking_config(self) -> Optional[NetworkingConfig]:
        """Get networking configuration"""
        return self._MLP_config.networking_config if self._MLP_config else None
    
    def get_compute_config(self) -> Optional[ComputeConfig]:
        """Get compute configuration"""
        return self._MLP_config.compute_config if self._MLP_config else None
    
    def get_feature_store_config(self) -> Optional[FeatureStoreConfig]:
        """Get feature store configuration"""
        return self._MLP_config.feature_store_config if self._MLP_config else None
    
    def get_iam_config(self) -> Optional[IAMConfig]:
        """Get IAM configuration"""
        return self._MLP_config.iam_config if self._MLP_config else None
    
    def get_kms_config(self) -> Optional[KMSConfig]:
        """Get KMS configuration"""
        return self._MLP_config.kms_config if self._MLP_config else None
    
    def _process_encryption_key(self, key: Union[str, bytes]) -> bytes:
        """
        Process encryption key from various formats.
        
        Args:
            key: Encryption key as base64 string or raw bytes
            
        Returns:
            32-byte encryption key for AES-256
            
        Raises:
            ConfigurationError: If key format is invalid
        """
        try:
            if isinstance(key, str):
                # Try to decode as base64
                decoded = base64.b64decode(key)
                if len(decoded) != 32:
                    raise ConfigurationError(f"Encryption key must be 32 bytes for AES-256, got {len(decoded)} bytes")
                return decoded
            elif isinstance(key, bytes):
                if len(key) != 32:
                    raise ConfigurationError(f"Encryption key must be 32 bytes for AES-256, got {len(key)} bytes")
                return key
            else:
                raise ConfigurationError(f"Encryption key must be string or bytes, got {type(key)}")
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to process encryption key: {e}")
    
    @staticmethod
    def load_key_from_env(env_var: str = "MLP_SDK_ENCRYPTION_KEY") -> Optional[bytes]:
        """
        Load encryption key from environment variable.
        
        Args:
            env_var: Environment variable name containing the base64-encoded key
            
        Returns:
            32-byte encryption key or None if not found
            
        Raises:
            ConfigurationError: If key format is invalid
        """
        key_str = os.environ.get(env_var)
        if not key_str:
            return None
        
        try:
            decoded = base64.b64decode(key_str)
            if len(decoded) != 32:
                raise ConfigurationError(f"Encryption key from {env_var} must be 32 bytes for AES-256, got {len(decoded)} bytes")
            return decoded
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to load encryption key from environment variable {env_var}: {e}")
    
    @staticmethod
    def load_key_from_file(file_path: str) -> bytes:
        """
        Load encryption key from file.
        
        Args:
            file_path: Path to file containing base64-encoded encryption key
            
        Returns:
            32-byte encryption key
            
        Raises:
            ConfigurationError: If file not found or key format is invalid
        """
        key_file = Path(file_path)
        if not key_file.exists():
            raise ConfigurationError(f"Encryption key file not found: {file_path}")
        
        try:
            with open(key_file, 'r', encoding='utf-8') as f:
                key_str = f.read().strip()
            
            decoded = base64.b64decode(key_str)
            if len(decoded) != 32:
                raise ConfigurationError(f"Encryption key from {file_path} must be 32 bytes for AES-256, got {len(decoded)} bytes")
            return decoded
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to load encryption key from file {file_path}: {e}")
    
    @staticmethod
    def load_key_from_kms(key_id: str, region: Optional[str] = None) -> bytes:
        """
        Load encryption key from AWS KMS.
        
        Args:
            key_id: KMS key ID or ARN
            region: AWS region (optional, uses default if not specified)
            
        Returns:
            32-byte encryption key generated by KMS
            
        Raises:
            ConfigurationError: If KMS operation fails
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Create KMS client
            kms_client = boto3.client('kms', region_name=region) if region else boto3.client('kms')
            
            # Generate a data key using KMS
            response = kms_client.generate_data_key(
                KeyId=key_id,
                KeySpec='AES_256'
            )
            
            # Return the plaintext key (32 bytes for AES-256)
            return response['Plaintext']
            
        except ImportError:
            raise ConfigurationError("boto3 is required for KMS key loading. Install with: pip install boto3")
        except Exception as e:
            raise ConfigurationError(f"Failed to load encryption key from KMS {key_id}: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new random 32-byte encryption key for AES-256-GCM.
        
        Returns:
            Base64-encoded 32-byte encryption key
        """
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')
    
    def encrypt_value(self, plaintext: str, key: Optional[Union[str, bytes]] = None) -> str:
        """
        Encrypt a configuration value using AES-256-GCM.
        
        Args:
            plaintext: Value to encrypt
            key: Optional encryption key (uses instance key if not provided)
            
        Returns:
            Base64-encoded encrypted value with format: nonce:ciphertext:tag
            
        Raises:
            ConfigurationError: If encryption fails or no key available
        """
        encryption_key = self._process_encryption_key(key) if key else self._encryption_key
        
        if not encryption_key:
            raise ConfigurationError("No encryption key available. Provide key during initialization or as parameter.")
        
        try:
            # Create AESGCM cipher
            aesgcm = AESGCM(encryption_key)
            
            # Generate random nonce (96 bits / 12 bytes recommended for GCM)
            nonce = os.urandom(12)
            
            # Encrypt the plaintext
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
            
            # Combine nonce and ciphertext (ciphertext includes auth tag)
            combined = nonce + ciphertext
            
            # Return base64-encoded result
            return base64.b64encode(combined).decode('utf-8')
            
        except Exception as e:
            raise ConfigurationError(f"Failed to encrypt value: {e}")
    
    def decrypt_value(self, encrypted: str, key: Optional[Union[str, bytes]] = None) -> str:
        """
        Decrypt a configuration value using AES-256-GCM.
        
        Args:
            encrypted: Base64-encoded encrypted value with format: nonce:ciphertext:tag
            key: Optional encryption key (uses instance key if not provided)
            
        Returns:
            Decrypted plaintext value
            
        Raises:
            ConfigurationError: If decryption fails or no key available
        """
        encryption_key = self._process_encryption_key(key) if key else self._encryption_key
        
        if not encryption_key:
            raise ConfigurationError("No encryption key available. Provide key during initialization or as parameter.")
        
        try:
            # Decode base64
            combined = base64.b64decode(encrypted)
            
            # Extract nonce (first 12 bytes) and ciphertext (rest includes auth tag)
            nonce = combined[:12]
            ciphertext = combined[12:]
            
            # Create AESGCM cipher
            aesgcm = AESGCM(encryption_key)
            
            # Decrypt the ciphertext
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            
            # Return decoded string
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            raise ConfigurationError(f"Failed to decrypt value: {e}")
    
    def encrypt_config_file(self, input_path: str, output_path: str, 
                           fields_to_encrypt: List[str], 
                           key: Optional[Union[str, bytes]] = None) -> None:
        """
        Encrypt specific fields in a YAML configuration file.
        
        Args:
            input_path: Path to input YAML file
            output_path: Path to output encrypted YAML file
            fields_to_encrypt: List of field paths to encrypt (dot notation, e.g., 'defaults.iam.execution_role')
            key: Optional encryption key (uses instance key if not provided)
            
        Raises:
            ConfigurationError: If encryption fails
        """
        encryption_key = self._process_encryption_key(key) if key else self._encryption_key
        
        if not encryption_key:
            raise ConfigurationError("No encryption key available. Provide key during initialization or as parameter.")
        
        try:
            # Load input file
            with open(input_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Encrypt specified fields
            for field_path in fields_to_encrypt:
                keys = field_path.split('.')
                current = config
                
                # Navigate to parent of target field
                for key in keys[:-1]:
                    if key not in current:
                        raise ConfigurationError(f"Field path not found: {field_path}")
                    current = current[key]
                
                # Encrypt the target field
                final_key = keys[-1]
                if final_key not in current:
                    raise ConfigurationError(f"Field not found: {field_path}")
                
                plaintext = str(current[final_key])
                current[final_key] = self.encrypt_value(plaintext, encryption_key)
            
            # Write encrypted config
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, default_flow_style=False)
                
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to encrypt config file: {e}")
    
    def decrypt_config_file(self, input_path: str, output_path: str,
                           fields_to_decrypt: List[str],
                           key: Optional[Union[str, bytes]] = None) -> None:
        """
        Decrypt specific fields in a YAML configuration file.
        
        Args:
            input_path: Path to input encrypted YAML file
            output_path: Path to output decrypted YAML file
            fields_to_decrypt: List of field paths to decrypt (dot notation)
            key: Optional encryption key (uses instance key if not provided)
            
        Raises:
            ConfigurationError: If decryption fails
        """
        encryption_key = self._process_encryption_key(key) if key else self._encryption_key
        
        if not encryption_key:
            raise ConfigurationError("No encryption key available. Provide key during initialization or as parameter.")
        
        try:
            # Load input file
            with open(input_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Decrypt specified fields
            for field_path in fields_to_decrypt:
                keys = field_path.split('.')
                current = config
                
                # Navigate to parent of target field
                for key in keys[:-1]:
                    if key not in current:
                        raise ConfigurationError(f"Field path not found: {field_path}")
                    current = current[key]
                
                # Decrypt the target field
                final_key = keys[-1]
                if final_key not in current:
                    raise ConfigurationError(f"Field not found: {field_path}")
                
                encrypted = str(current[final_key])
                current[final_key] = self.decrypt_value(encrypted, encryption_key)
            
            # Write decrypted config
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, default_flow_style=False)
                
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to decrypt config file: {e}")