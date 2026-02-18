"""
SageBridge - Intelligent EC2 to SageMaker Migration System

An intelligent migration system that generates production-ready, 
SageMaker SDK v3 compatible code with minimal manual iterations.
"""

__version__ = "0.1.0"
__author__ = "SageBridge Team"
__description__ = "Intelligent EC2 to SageMaker Migration System"

from .migration_agent import MigrationAgent
from .config import Config
from .deployment import ModelRegistryIntegration, ModelRegistryConfig, EndpointTestSuite
from .documentation import DocumentationGenerator

__all__ = [
    "MigrationAgent", 
    "Config", 
    "ModelRegistryIntegration", 
    "ModelRegistryConfig", 
    "EndpointTestSuite",
    "DocumentationGenerator"
]