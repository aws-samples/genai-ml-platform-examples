
"""
S3 ARN validation and formatting utilities for the SageMigrator tool.

This module provides comprehensive S3 ARN validation, formatting, and correction
functionality to ensure CloudFormation templates deploy successfully without
S3 ARN parsing errors.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class S3ARNValidationResult:
    """Result of S3 ARN validation"""
    is_valid: bool
    original_arn: str
    corrected_arn: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CloudFormationValidationResult:
    """Result of CloudFormation template validation"""
    is_valid: bool
    s3_arn_errors: List[str] = field(default_factory=list)
    s3_arn_warnings: List[str] = field(default_factory=list)
    fixed_template: Optional[Dict[str, Any]] = None


class S3ARNPatterns:
    """S3 ARN format patterns and validation rules"""
    
    BUCKET_ARN_PATTERN = r"^arn:aws:s3:::[\w\-\.]+$"
    OBJECT_ARN_PATTERN = r"^arn:aws:s3:::[\w\-\.]+/.*$"
    VALID_BUCKET_NAME_PATTERN = r"^[\w\-\.]+$"
    
    @classmethod
    def is_valid_bucket_arn(cls, arn: str) -> bool:
        """Check if ARN is a valid S3 bucket ARN"""
        return bool(re.match(cls.BUCKET_ARN_PATTERN, arn))
    
    @classmethod
    def is_valid_object_arn(cls, arn: str) -> bool:
        """Check if ARN is a valid S3 object ARN"""
        return bool(re.match(cls.OBJECT_ARN_PATTERN, arn))
    
    @classmethod
    def is_valid_bucket_name(cls, name: str) -> bool:
        """Check if bucket name follows valid naming conventions"""
        return bool(re.match(cls.VALID_BUCKET_NAME_PATTERN, name))


def validate_s3_resource_arn(resource: str) -> str:
    """
    Validate and fix S3 resource ARN format.
    
    Args:
        resource: S3 resource string
        
    Returns:
        Properly formatted S3 ARN
        
    Raises:
        ValueError: If resource format is invalid
    """
    # Use the comprehensive fix function for consistency
    return fix_s3_resource_format(resource)


def is_valid_s3_arn(arn: str) -> bool:
    """
    Check if ARN follows proper S3 format.
    
    Args:
        arn: ARN string to validate
        
    Returns:
        True if ARN is valid, False otherwise
    """
    if not arn or not isinstance(arn, str):
        return False
    
    if arn == "*":
        return True
    
    return S3ARNPatterns.is_valid_bucket_arn(arn) or S3ARNPatterns.is_valid_object_arn(arn)


def fix_s3_resource_format(resource: str) -> str:
    """
    Convert various S3 resource formats to proper ARN format.
    
    Args:
        resource: S3 resource in various formats
        
    Returns:
        Properly formatted S3 ARN
        
    Raises:
        ValueError: If resource cannot be converted to valid ARN
    """
    if not resource or not isinstance(resource, str):
        raise ValueError("Resource must be a non-empty string")
    
    resource = resource.strip()
    
    # Handle wildcard
    if resource == "*":
        return resource
    
    # Handle malformed ARN missing "arn:" prefix
    if resource.startswith("aws:s3:::"):
        # Add missing "arn:" prefix
        return f"arn:{resource}"
    
    # Handle common typo: s4 instead of s3
    if resource.startswith("arn:aws:s4:::"):
        # Fix service name typo
        return resource.replace("arn:aws:s4:::", "arn:aws:s3:::")
    
    # Already a valid ARN
    if is_valid_s3_arn(resource):
        return resource
    
    # Handle CloudFormation intrinsic functions (basic detection)
    if resource.startswith("!") or "${" in resource or resource.startswith("Ref:"):
        # Don't modify CloudFormation intrinsic functions
        return resource
    
    # Extract bucket name and path
    if resource.startswith("s3://"):
        # Remove s3:// prefix and handle the rest
        s3_path = resource[5:]
        if "/" in s3_path:
            parts = s3_path.split("/", 1)
            bucket_name = parts[0]
            path = parts[1].strip()  # Strip whitespace from path
            
            if not bucket_name:
                raise ValueError("Empty bucket name in S3 URI")
            
            if not S3ARNPatterns.is_valid_bucket_name(bucket_name):
                raise ValueError(f"Invalid bucket name: {bucket_name}")
            
            # Validate path doesn't contain invalid characters
            if '\n' in path or '\r' in path or '\t' in path:
                raise ValueError(f"Invalid characters in object path: {path}")
            
            if path == "*" or path.endswith("/*"):
                return f"arn:aws:s3:::{bucket_name}/*"
            else:
                return f"arn:aws:s3:::{bucket_name}/{path}"
        else:
            # Just bucket name from s3:// URI
            bucket_name = s3_path.strip()
            if not bucket_name:
                raise ValueError("Empty bucket name in S3 URI")
            
            if not S3ARNPatterns.is_valid_bucket_name(bucket_name):
                raise ValueError(f"Invalid bucket name: {bucket_name}")
            
            return f"arn:aws:s3:::{bucket_name}"
    
    # Handle regular bucket/path format
    if "/" in resource:
        parts = resource.split("/", 1)
        bucket_name = parts[0].strip()
        path = parts[1].strip()
        
        if not bucket_name:
            raise ValueError("Empty bucket name")
        
        if not S3ARNPatterns.is_valid_bucket_name(bucket_name):
            raise ValueError(f"Invalid bucket name: {bucket_name}")
        
        # Validate path doesn't contain invalid characters
        if '\n' in path or '\r' in path or '\t' in path:
            raise ValueError(f"Invalid characters in object path: {path}")
        
        if path == "*" or path.endswith("/*"):
            return f"arn:aws:s3:::{bucket_name}/*"
        else:
            return f"arn:aws:s3:::{bucket_name}/{path}"
    else:
        # Just bucket name
        bucket_name = resource.strip()
        if not bucket_name:
            raise ValueError("Empty bucket name")
        
        if not S3ARNPatterns.is_valid_bucket_name(bucket_name):
            raise ValueError(f"Invalid bucket name: {bucket_name}")
        
        return f"arn:aws:s3:::{bucket_name}"


def validate_s3_arn_comprehensive(resource: str) -> S3ARNValidationResult:
    """
    Comprehensive S3 ARN validation with detailed results.
    
    Args:
        resource: S3 resource string to validate
        
    Returns:
        S3ARNValidationResult with validation details
    """
    result = S3ARNValidationResult(
        is_valid=False,
        original_arn=resource,
        corrected_arn=resource
    )
    
    try:
        corrected = fix_s3_resource_format(resource)
        result.corrected_arn = corrected
        result.is_valid = is_valid_s3_arn(corrected)
        
        if result.original_arn != result.corrected_arn:
            result.warnings.append(f"ARN format corrected from '{resource}' to '{corrected}'")
        
        if not result.is_valid:
            result.errors.append(f"Invalid S3 ARN format: {corrected}")
            
    except ValueError as e:
        result.errors.append(str(e))
        result.is_valid = False
    
    return result
