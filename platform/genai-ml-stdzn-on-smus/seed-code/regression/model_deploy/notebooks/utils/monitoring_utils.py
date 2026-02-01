"""
Utility functions for SageMaker Model Monitoring
"""

import boto3
import json
import time
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.model_monitor import DefaultModelMonitor


def run_model_monitor_job(
    region,
    instance_type,
    role,
    data_capture_path,
    statistics_path,
    constraints_path,
    reports_path,
    instance_count=1,
    publish_cloudwatch_metrics='Disabled',
    wait=True,
    logs=True
):
    """
    Run a manual model monitoring job
    
    Args:
        region: AWS region
        instance_type: Instance type for processing job
        role: IAM role ARN
        data_capture_path: S3 path to captured data
        statistics_path: S3 path to baseline statistics
        constraints_path: S3 path to baseline constraints
        reports_path: S3 path for output reports
        instance_count: Number of instances
        publish_cloudwatch_metrics: Whether to publish CloudWatch metrics
        wait: Whether to wait for job completion
        logs: Whether to show logs
    
    Returns:
        Processing job name
    """
    
    # Create monitor instance
    monitor = DefaultModelMonitor(
        role=role,
        instance_count=instance_count,
        instance_type=instance_type,
        volume_size_in_gb=20,
        max_runtime_in_seconds=3600
    )
    
    # Generate unique job name
    job_name = f"manual-monitoring-{int(time.time())}"
    
    # Run the monitoring job
    monitor.run_baseline(
        baseline_dataset=data_capture_path,
        dataset_format={'csv': {'header': False}},
        output_s3_uri=reports_path,
        job_name=job_name,
        wait=wait,
        logs=logs
    )
    
    return job_name


def check_monitoring_violations(violations_s3_path):
    """
    Check for monitoring violations in the output
    
    Args:
        violations_s3_path: S3 path to constraint violations file
    
    Returns:
        List of violations
    """
    
    s3_client = boto3.client('s3')
    
    try:
        # Parse S3 path
        bucket = violations_s3_path.split('/')[2]
        key = '/'.join(violations_s3_path.split('/')[3:])
        
        # Download violations file
        response = s3_client.get_object(Bucket=bucket, Key=key)
        violations_data = json.loads(response['Body'].read().decode('utf-8'))
        
        return violations_data.get('violations', [])
        
    except Exception as e:
        print(f"Error reading violations: {e}")
        return []


def format_violations_report(violations):
    """
    Format violations into a readable report
    
    Args:
        violations: List of violation dictionaries
    
    Returns:
        Formatted string report
    """
    
    if not violations:
        return "✅ No violations detected - data within baseline constraints"
    
    report = f"⚠️ Found {len(violations)} violation(s):\n\n"
    
    for i, violation in enumerate(violations, 1):
        feature = violation.get('feature_name', 'Unknown')
        check_type = violation.get('constraint_check_type', 'Unknown')
        description = violation.get('description', 'No description')
        
        report += f"{i}. Feature: {feature}\n"
        report += f"   Check: {check_type}\n"
        report += f"   Issue: {description}\n\n"
    
    return report
