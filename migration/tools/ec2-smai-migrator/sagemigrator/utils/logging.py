"""
Logging configuration and utilities for SageBridge

Provides centralized logging setup with proper formatting, handlers, and levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    max_file_size_mb: int = 10,
    backup_count: int = 5,
    format_string: Optional[str] = None
) -> None:
    """
    Setup centralized logging configuration for SageBridge.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only console logging is used.
        max_file_size_mb: Maximum size of log file before rotation (in MB)
        backup_count: Number of backup log files to keep
        format_string: Custom format string for log messages
    """
    # Default format string
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(filename)s:%(lineno)d - %(message)s'
        )
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Get root logger and clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file is specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=backup_count
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels for third-party libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Log the setup completion
    logger = logging.getLogger(__name__)
    logger.info(f"Logging setup completed - Level: {logging.getLevelName(level)}")
    if log_file:
        logger.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ from calling module)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class that provides a logger property to any class.
    
    Usage:
        class MyClass(LoggerMixin):
            def some_method(self):
                self.logger.info("This is a log message")
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class"""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_execution_time(func):
    """
    Decorator to log execution time of functions.
    
    Usage:
        @log_execution_time
        def my_function():
            # function implementation
            pass
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        
        try:
            logger.debug(f"Starting execution of {func.__name__}")
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"Completed {func.__name__} in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed {func.__name__} after {execution_time:.2f} seconds: {str(e)}")
            raise
    
    return wrapper


def log_method_calls(cls):
    """
    Class decorator to log all method calls.
    
    Usage:
        @log_method_calls
        class MyClass:
            def method1(self):
                pass
    """
    import functools
    
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and not attr_name.startswith('_'):
            setattr(cls, attr_name, log_execution_time(attr))
    
    return cls