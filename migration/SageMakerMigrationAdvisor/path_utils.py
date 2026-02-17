"""
Path utilities for handling diagram storage in different environments
Supports both local development and ECS/Fargate deployments
"""

import os
import logging

logger = logging.getLogger(__name__)


def get_diagram_folder() -> str:
    """
    Get the appropriate diagram folder path based on the environment.
    
    Returns:
        str: Absolute path to the diagram folder
        
    Logic:
    - ECS/Fargate: Use /tmp/generated-diagrams (writable)
    - Local: Use script_dir/generated-diagrams (persistent)
    """
    # Check if running in AWS environment (ECS/Fargate/Lambda)
    is_aws_env = os.environ.get('AWS_EXECUTION_ENV') or os.environ.get('ECS_CONTAINER_METADATA_URI')
    
    if is_aws_env:
        # Running in AWS - use /tmp which is writable
        diagram_folder = '/tmp/generated-diagrams'
        logger.info(f"AWS environment detected - using /tmp for diagrams: {diagram_folder}")
    else:
        # Running locally - use script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        diagram_folder = os.path.join(script_dir, 'generated-diagrams')
        logger.info(f"Local environment detected - using script directory: {diagram_folder}")
    
    # Ensure folder exists
    try:
        os.makedirs(diagram_folder, exist_ok=True)
        logger.info(f"Diagram folder ready: {diagram_folder}")
    except Exception as e:
        logger.error(f"Failed to create diagram folder: {e}")
        # Fallback to /tmp if script directory is not writable
        if not is_aws_env:
            logger.warning("Script directory not writable, falling back to /tmp")
            diagram_folder = '/tmp/generated-diagrams'
            os.makedirs(diagram_folder, exist_ok=True)
    
    return diagram_folder


def get_workspace_dir() -> str:
    """
    Get the appropriate workspace directory for diagram generation.
    
    Returns:
        str: Absolute path to the workspace directory
        
    Logic:
    - ECS/Fargate: Use /tmp (writable)
    - Local: Use script directory (persistent)
    """
    # Check if running in AWS environment
    is_aws_env = os.environ.get('AWS_EXECUTION_ENV') or os.environ.get('ECS_CONTAINER_METADATA_URI')
    
    if is_aws_env:
        workspace_dir = '/tmp'
        logger.info(f"AWS environment detected - using /tmp as workspace: {workspace_dir}")
    else:
        workspace_dir = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Local environment detected - using script directory as workspace: {workspace_dir}")
    
    return workspace_dir


def is_aws_environment() -> bool:
    """
    Check if running in AWS environment (ECS/Fargate/Lambda).
    
    Returns:
        bool: True if running in AWS, False otherwise
    """
    return bool(os.environ.get('AWS_EXECUTION_ENV') or os.environ.get('ECS_CONTAINER_METADATA_URI'))
