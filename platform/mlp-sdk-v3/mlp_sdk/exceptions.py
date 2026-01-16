"""
Custom exceptions for mlp_sdk
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json


class MLPSDKError(Exception):
    """Base exception for all mlp_sdk errors"""
    pass


class ConfigurationError(MLPSDKError):
    """Configuration loading or validation errors"""
    pass


class ValidationError(MLPSDKError):
    """Parameter validation errors"""
    pass


class AWSServiceError(MLPSDKError):
    """AWS service operation errors with detailed error information"""
    
    def __init__(self, message: str, aws_error: Optional[Exception] = None):
        """
        Initialize AWS service error with detailed error information.
        
        Extracts and preserves AWS error details including:
        - Error code
        - Error message
        - Request ID
        - HTTP status code
        - Operation name
        
        Args:
            message: Error message
            aws_error: Original AWS exception (ClientError, BotoCoreError, etc.)
        """
        super().__init__(message)
        self.aws_error = aws_error
        self.error_code = None
        self.error_message = None
        self.request_id = None
        self.http_status_code = None
        self.operation_name = None
        
        # Extract AWS error details if available
        if aws_error:
            self._extract_aws_error_details(aws_error)
    
    def _extract_aws_error_details(self, aws_error: Exception) -> None:
        """
        Extract detailed error information from AWS exception.
        
        Handles both boto3 ClientError and other AWS SDK exceptions.
        
        Args:
            aws_error: AWS exception object
        """
        try:
            # Check if it's a boto3 ClientError
            if hasattr(aws_error, 'response'):
                response = aws_error.response
                
                # Extract error details from response
                if isinstance(response, dict):
                    # Get error code and message
                    error_info = response.get('Error', {})
                    self.error_code = error_info.get('Code')
                    self.error_message = error_info.get('Message')
                    
                    # Get request ID
                    self.request_id = response.get('ResponseMetadata', {}).get('RequestId')
                    
                    # Get HTTP status code
                    self.http_status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            
            # Check if it's a SageMaker SDK exception with operation_name
            if hasattr(aws_error, 'operation_name'):
                self.operation_name = aws_error.operation_name
                
        except Exception:
            # If extraction fails, just keep the original error
            pass
    
    def get_error_details(self) -> Dict[str, Any]:
        """
        Get structured error details.
        
        Returns:
            Dictionary with error details including code, message, request ID, etc.
        """
        details = {
            'message': str(self),
            'error_code': self.error_code,
            'error_message': self.error_message,
            'request_id': self.request_id,
            'http_status_code': self.http_status_code,
            'operation_name': self.operation_name,
        }
        
        # Remove None values
        return {k: v for k, v in details.items() if v is not None}
    
    def __str__(self) -> str:
        """
        String representation with AWS error details.
        
        Returns:
            Formatted error message with AWS details
        """
        base_message = super().__str__()
        
        # Add AWS error details if available
        details = []
        if self.error_code:
            details.append(f"ErrorCode: {self.error_code}")
        if self.request_id:
            details.append(f"RequestId: {self.request_id}")
        if self.http_status_code:
            details.append(f"HTTPStatus: {self.http_status_code}")
        if self.operation_name:
            details.append(f"Operation: {self.operation_name}")
        
        if details:
            return f"{base_message} [{', '.join(details)}]"
        
        return base_message


class SessionError(MLPSDKError):
    """Session initialization or lifecycle errors"""
    pass


# Logging infrastructure
class MLPLogger:
    """
    Structured logging for mlp_sdk operations.
    Provides configurable log levels and audit trail functionality.
    """
    
    def __init__(self, name: str = "mlp_sdk", level: int = logging.INFO):
        """
        Initialize logger with configurable level.
        
        Args:
            name: Logger name
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Add console handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def set_level(self, level: int) -> None:
        """
        Set logging level.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with optional context"""
        self.logger.debug(self._format_message(message, kwargs))
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with optional context"""
        self.logger.info(self._format_message(message, kwargs))
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with optional context"""
        self.logger.warning(self._format_message(message, kwargs))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """
        Log error message with optional exception details.
        
        Automatically extracts AWS error details if the error is an AWSServiceError.
        
        Args:
            message: Error message
            error: Optional exception object
            **kwargs: Additional context
        """
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_details'] = str(error)
            
            # Extract AWS error details if available
            if hasattr(error, 'get_error_details'):
                aws_details = error.get_error_details()
                for key, value in aws_details.items():
                    if key != 'message':  # Avoid duplicate message
                        kwargs[f'aws_{key}'] = value
            elif hasattr(error, 'response'):
                # Handle boto3 ClientError directly
                try:
                    response = error.response
                    if isinstance(response, dict):
                        error_info = response.get('Error', {})
                        kwargs['aws_error_code'] = error_info.get('Code')
                        kwargs['aws_error_message'] = error_info.get('Message')
                        kwargs['aws_request_id'] = response.get('ResponseMetadata', {}).get('RequestId')
                        kwargs['aws_http_status'] = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
                except Exception:
                    pass
        
        self.logger.error(self._format_message(message, kwargs))
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """
        Log critical message with optional exception details.
        
        Args:
            message: Critical error message
            error: Optional exception object
            **kwargs: Additional context
        """
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_details'] = str(error)
        self.logger.critical(self._format_message(message, kwargs))
    
    def _format_message(self, message: str, context: Dict[str, Any]) -> str:
        """
        Format log message with context.
        
        Args:
            message: Base message
            context: Additional context dictionary
            
        Returns:
            Formatted message string
        """
        if not context:
            return message
        
        context_str = " | ".join(f"{k}={v}" for k, v in context.items())
        return f"{message} | {context_str}"


class AuditTrail:
    """
    Maintains audit trail for mlp_sdk operations.
    Records operation history for debugging and compliance.
    """
    
    def __init__(self, max_entries: int = 1000):
        """
        Initialize audit trail.
        
        Args:
            max_entries: Maximum number of entries to keep in memory
        """
        self._entries: list = []
        self._max_entries = max_entries
    
    def record(self, operation: str, status: str, **kwargs: Any) -> None:
        """
        Record an operation in the audit trail.
        
        Args:
            operation: Operation name (e.g., 'create_feature_group')
            status: Operation status ('started', 'completed', 'failed')
            **kwargs: Additional operation details
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'operation': operation,
            'status': status,
            **kwargs
        }
        
        self._entries.append(entry)
        
        # Maintain max entries limit
        if len(self._entries) > self._max_entries:
            self._entries.pop(0)
    
    def get_entries(self, operation: Optional[str] = None, 
                   status: Optional[str] = None,
                   limit: Optional[int] = None) -> list:
        """
        Get audit trail entries with optional filtering.
        
        Args:
            operation: Filter by operation name
            status: Filter by status
            limit: Maximum number of entries to return
            
        Returns:
            List of audit trail entries
        """
        entries = self._entries
        
        if operation:
            entries = [e for e in entries if e['operation'] == operation]
        
        if status:
            entries = [e for e in entries if e['status'] == status]
        
        if limit:
            entries = entries[-limit:]
        
        return entries
    
    def get_last_entry(self, operation: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the most recent audit trail entry.
        
        Args:
            operation: Optional operation name filter
            
        Returns:
            Most recent entry or None
        """
        entries = self.get_entries(operation=operation, limit=1)
        return entries[0] if entries else None
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for the audit trail.
        
        Returns:
            Dictionary with summary statistics including:
            - total_entries: Total number of entries
            - operations: Count by operation type
            - statuses: Count by status
            - failed_operations: List of failed operations
        """
        summary = {
            'total_entries': len(self._entries),
            'operations': {},
            'statuses': {},
            'failed_operations': []
        }
        
        for entry in self._entries:
            # Count by operation
            operation = entry.get('operation', 'unknown')
            summary['operations'][operation] = summary['operations'].get(operation, 0) + 1
            
            # Count by status
            status = entry.get('status', 'unknown')
            summary['statuses'][status] = summary['statuses'].get(status, 0) + 1
            
            # Track failed operations
            if status == 'failed':
                summary['failed_operations'].append({
                    'timestamp': entry.get('timestamp'),
                    'operation': operation,
                    'error': entry.get('error', 'Unknown error')
                })
        
        return summary
    
    def clear(self) -> None:
        """Clear all audit trail entries"""
        self._entries.clear()
    
    def export_json(self, file_path: str) -> None:
        """
        Export audit trail to JSON file.
        
        Args:
            file_path: Path to output JSON file
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self._entries, f, indent=2)
    
    def export_csv(self, file_path: str) -> None:
        """
        Export audit trail to CSV file.
        
        Args:
            file_path: Path to output CSV file
        """
        import csv
        
        if not self._entries:
            # Create empty CSV with headers
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'operation', 'status'])
            return
        
        # Get all unique keys from entries
        all_keys = set()
        for entry in self._entries:
            all_keys.update(entry.keys())
        
        # Sort keys for consistent column order
        fieldnames = sorted(all_keys)
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._entries)
    
    def __len__(self) -> int:
        """Return number of entries in audit trail"""
        return len(self._entries)