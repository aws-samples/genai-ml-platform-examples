"""
mlp_sdk - A Python wrapper library for SageMaker SDK v3

This package provides simplified SageMaker operations with configuration-driven defaults.
"""

__version__ = "0.1.0"

from .session import MLP_Session
from .exceptions import MLPSDKError, ConfigurationError, ValidationError, AWSServiceError

__all__ = [
    "MLP_Session",
    "MLPSDKError", 
    "ConfigurationError",
    "ValidationError", 
    "AWSServiceError"
]