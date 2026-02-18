"""
Configuration management for SageBridge

Handles loading and managing configuration from files, environment variables,
and command-line options.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict


@dataclass
class AnalysisConfig:
    """Configuration for code analysis engine"""
    max_file_size_mb: int = 10
    supported_extensions: list = None
    ignore_patterns: list = None
    dependency_timeout_seconds: int = 30
    
    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = ['.py', '.ipynb', '.txt', '.yml', '.yaml']
        if self.ignore_patterns is None:
            self.ignore_patterns = ['__pycache__', '.git', '.venv', 'node_modules']


@dataclass
class CompatibilityConfig:
    """Configuration for compatibility engine"""
    sagemaker_sdk_version: str = "2.x"
    pytorch_version: str = "2.0"
    tensorflow_version: str = "2.13"
    python_version: str = "3.10"
    enable_torchscript: bool = True
    enable_local_testing: bool = True


@dataclass
class InfrastructureConfig:
    """Configuration for infrastructure generation"""
    default_region: str = "us-east-1"
    default_instance_type: str = "ml.m5.large"
    enable_encryption: bool = True
    enable_vpc: bool = False
    cost_optimization: bool = True
    backup_retention_days: int = 30


@dataclass
class ValidationConfig:
    """Configuration for validation suite"""
    enable_security_checks: bool = True
    enable_cost_checks: bool = True
    enable_performance_checks: bool = True
    max_test_timeout_minutes: int = 30
    property_test_iterations: int = 100


@dataclass
class Config:
    """Main configuration class for SageMigrator"""
    analysis: AnalysisConfig
    compatibility: CompatibilityConfig
    infrastructure: InfrastructureConfig
    validation: ValidationConfig
    
    # Global settings
    project_name: str = "sagemigrator-project"
    log_level: str = "INFO"
    output_format: str = "json"  # json, yaml
    parallel_processing: bool = True
    max_workers: int = 4
    
    @classmethod
    def default(cls) -> 'Config':
        """Create default configuration"""
        return cls(
            analysis=AnalysisConfig(),
            compatibility=CompatibilityConfig(),
            infrastructure=InfrastructureConfig(),
            validation=ValidationConfig()
        )
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'Config':
        """Load configuration from file, environment, and defaults"""
        # Start with default configuration
        config = cls.default()
        
        # Load from file if provided
        if config_path and config_path.exists():
            config = cls._load_from_file(config_path)
        
        # Override with environment variables
        config = cls._load_from_environment(config)
        
        return config
    
    @classmethod
    def _load_from_file(cls, config_path: Path) -> 'Config':
        """Load configuration from JSON or YAML file"""
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() in ['.yml', '.yaml']:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            return cls._from_dict(data)
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_path}: {str(e)}")
    
    @classmethod
    def _load_from_environment(cls, config: 'Config') -> 'Config':
        """Override configuration with environment variables"""
        # Map environment variables to config fields
        env_mappings = {
            'SAGEBRIDGE_LOG_LEVEL': ('log_level', str),
            'SAGEBRIDGE_MAX_WORKERS': ('max_workers', int),
            'SAGEBRIDGE_DEFAULT_REGION': ('infrastructure.default_region', str),
            'SAGEBRIDGE_ENABLE_ENCRYPTION': ('infrastructure.enable_encryption', bool),
            'SAGEBRIDGE_PROPERTY_TEST_ITERATIONS': ('validation.property_test_iterations', int),
        }
        
        for env_var, (config_path, value_type) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    # Convert value to appropriate type
                    if value_type == bool:
                        value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif value_type == int:
                        value = int(env_value)
                    else:
                        value = env_value
                    
                    # Set nested configuration value
                    cls._set_nested_value(config, config_path, value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid value for {env_var}: {env_value} ({str(e)})")
        
        return config
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create configuration from dictionary"""
        # Extract nested configurations
        analysis_data = data.get('analysis', {})
        compatibility_data = data.get('compatibility', {})
        infrastructure_data = data.get('infrastructure', {})
        validation_data = data.get('validation', {})
        
        return cls(
            analysis=AnalysisConfig(**analysis_data),
            compatibility=CompatibilityConfig(**compatibility_data),
            infrastructure=InfrastructureConfig(**infrastructure_data),
            validation=ValidationConfig(**validation_data),
            project_name=data.get('project_name', 'sagemigrator-project'),
            log_level=data.get('log_level', 'INFO'),
            output_format=data.get('output_format', 'json'),
            parallel_processing=data.get('parallel_processing', True),
            max_workers=data.get('max_workers', 4)
        )
    
    @staticmethod
    def _set_nested_value(obj: Any, path: str, value: Any) -> None:
        """Set nested attribute value using dot notation"""
        parts = path.split('.')
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'analysis': asdict(self.analysis),
            'compatibility': asdict(self.compatibility),
            'infrastructure': asdict(self.infrastructure),
            'validation': asdict(self.validation),
            'project_name': self.project_name,
            'log_level': self.log_level,
            'output_format': self.output_format,
            'parallel_processing': self.parallel_processing,
            'max_workers': self.max_workers
        }
    
    def save(self, config_path: Path) -> None:
        """Save configuration to file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            if config_path.suffix.lower() in ['.yml', '.yaml']:
                yaml.dump(self.to_dict(), f, default_flow_style=False, indent=2)
            else:
                json.dump(self.to_dict(), f, indent=2)
    
    def validate(self) -> None:
        """Validate configuration values"""
        errors = []
        
        # Validate analysis config
        if self.analysis.max_file_size_mb <= 0:
            errors.append("analysis.max_file_size_mb must be positive")
        
        if self.analysis.dependency_timeout_seconds <= 0:
            errors.append("analysis.dependency_timeout_seconds must be positive")
        
        # Validate infrastructure config
        if not self.infrastructure.default_region:
            errors.append("infrastructure.default_region cannot be empty")
        
        if self.infrastructure.backup_retention_days < 0:
            errors.append("infrastructure.backup_retention_days cannot be negative")
        
        # Validate validation config
        if self.validation.property_test_iterations <= 0:
            errors.append("validation.property_test_iterations must be positive")
        
        if self.validation.max_test_timeout_minutes <= 0:
            errors.append("validation.max_test_timeout_minutes must be positive")
        
        # Validate global settings
        if self.max_workers <= 0:
            errors.append("max_workers must be positive")
        
        if self.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append("log_level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        
        if self.output_format not in ['json', 'yaml']:
            errors.append("output_format must be 'json' or 'yaml'")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")