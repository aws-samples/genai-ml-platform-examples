"""
Custom exceptions for SageMigrator

Defines specific exception types for different error conditions in the migration system.
"""

from typing import Optional, List, Dict, Any


class SageMigratorError(Exception):
    """Base exception class for all SageMigrator errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class ConfigurationError(SageMigratorError):
    """Raised when configuration is invalid or missing"""
    pass


class AnalysisError(SageMigratorError):
    """Raised when source code analysis fails"""
    
    def __init__(self, message: str, source_path: Optional[str] = None, 
                 failed_files: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.source_path = source_path
        self.failed_files = failed_files or []


class CompatibilityError(SageMigratorError):
    """Raised when compatibility issues cannot be resolved"""
    
    def __init__(self, message: str, incompatible_packages: Optional[List[str]] = None,
                 unsupported_patterns: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.incompatible_packages = incompatible_packages or []
        self.unsupported_patterns = unsupported_patterns or []


class DependencyError(SageMigratorError):
    """Raised when dependency resolution fails"""
    
    def __init__(self, message: str, problematic_dependencies: Optional[List[str]] = None,
                 resolution_failures: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.problematic_dependencies = problematic_dependencies or []
        self.resolution_failures = resolution_failures or {}


class CodeGenerationError(SageMigratorError):
    """Raised when code generation fails"""
    
    def __init__(self, message: str, generation_stage: Optional[str] = None,
                 template_errors: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.generation_stage = generation_stage
        self.template_errors = template_errors or []


class InfrastructureError(SageMigratorError):
    """Raised when infrastructure generation or deployment fails"""
    
    def __init__(self, message: str, resource_type: Optional[str] = None,
                 aws_errors: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.aws_errors = aws_errors or []


class ValidationError(SageMigratorError):
    """Raised when validation fails"""
    
    def __init__(self, message: str, validation_type: Optional[str] = None,
                 failed_checks: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.validation_type = validation_type
        self.failed_checks = failed_checks or []


class DeploymentError(SageMigratorError):
    """Raised when deployment fails"""
    
    def __init__(self, message: str, deployment_stage: Optional[str] = None,
                 stack_name: Optional[str] = None, region: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.deployment_stage = deployment_stage
        self.stack_name = stack_name
        self.region = region


class ModelError(SageMigratorError):
    """Raised when model-related operations fail"""
    
    def __init__(self, message: str, model_type: Optional[str] = None,
                 model_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.model_type = model_type
        self.model_path = model_path


class TestingError(SageMigratorError):
    """Raised when testing operations fail"""
    
    def __init__(self, message: str, test_type: Optional[str] = None,
                 failed_tests: Optional[List[str]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.test_type = test_type
        self.failed_tests = failed_tests or []


class MigrationError(SageMigratorError):
    """Raised when migration operations fail"""
    
    def __init__(self, message: str, migration_id: Optional[str] = None,
                 component_id: Optional[str] = None, phase: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.migration_id = migration_id
        self.component_id = component_id
        self.phase = phase


def handle_exception(func):
    """
    Decorator to handle exceptions and convert them to SageMigrator exceptions.
    
    Usage:
        @handle_exception
        def my_function():
            # function implementation
            pass
    """
    import functools
    import logging
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        
        try:
            return func(*args, **kwargs)
        except SageMigratorError:
            # Re-raise SageMigrator exceptions as-is
            raise
        except FileNotFoundError as e:
            logger.error(f"File not found in {func.__name__}: {str(e)}")
            raise AnalysisError(f"Required file not found: {str(e)}", details={'original_error': str(e)})
        except PermissionError as e:
            logger.error(f"Permission denied in {func.__name__}: {str(e)}")
            raise SageMigratorError(f"Permission denied: {str(e)}", details={'original_error': str(e)})
        except ValueError as e:
            logger.error(f"Invalid value in {func.__name__}: {str(e)}")
            raise ConfigurationError(f"Invalid configuration or input: {str(e)}", details={'original_error': str(e)})
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            raise SageMigratorError(f"Unexpected error in {func.__name__}: {str(e)}", details={'original_error': str(e)})
    
    return wrapper