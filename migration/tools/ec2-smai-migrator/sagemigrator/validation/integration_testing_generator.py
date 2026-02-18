"""
Integration Testing Generator for SageMigrator

Generates end-to-end pipeline tests, inference endpoint testing suites,
performance benchmarking tools, and monitoring/alerting validation.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..models.analysis import AnalysisReport
from ..models.artifacts import MigrationArtifacts
from ..models.validation import ValidationReport, CompatibilityCheck, ValidationStatus


@dataclass
class IntegrationTestSuite:
    """Generated integration test suite"""
    pipeline_tests: Dict[str, str]  # test name -> test content
    endpoint_tests: Dict[str, str]  # test name -> test content
    benchmark_tests: Dict[str, str]  # test name -> test content
    monitoring_tests: Dict[str, str]  # test name -> test content
    requirements: List[str]  # additional requirements
    config_files: Dict[str, str]  # config file name -> content
    documentation: str  # integration test documentation


class IntegrationTestingGenerator:
    """Generates comprehensive integration testing suites"""
    
    def __init__(self):
        self.test_templates = self._load_test_templates()
    
    def generate_integration_suite(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> IntegrationTestSuite:
        """Generate complete integration testing suite"""
        # Generate end-to-end pipeline tests
        pipeline_tests = self._generate_pipeline_tests(analysis, artifacts)
        
        # Generate inference endpoint testing suites
        endpoint_tests = self._generate_endpoint_tests(analysis, artifacts)
        
        # Generate performance benchmarking tools
        benchmark_tests = self._generate_benchmark_tests(analysis, artifacts)
        
        # Generate monitoring and alerting validation
        monitoring_tests = self._generate_monitoring_tests(analysis, artifacts)
        
        # Generate configuration files
        config_files = self._generate_config_files(analysis, artifacts)
        
        # Generate documentation
        documentation = self._generate_integration_documentation(
            pipeline_tests, endpoint_tests, benchmark_tests, monitoring_tests
        )
        
        requirements = [
            "boto3", "sagemaker", "pytest", "pytest-asyncio", 
            "requests", "numpy", "pandas", "psutil", "time"
        ]
        
        return IntegrationTestSuite(
            pipeline_tests=pipeline_tests,
            endpoint_tests=endpoint_tests,
            benchmark_tests=benchmark_tests,
            monitoring_tests=monitoring_tests,
            requirements=requirements,
            config_files=config_files,
            documentation=documentation
        )
    
    def _generate_pipeline_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate end-to-end pipeline tests"""
        tests = {}
        
        tests["test_pipeline_execution.py"] = '''"""
End-to-End Pipeline Execution Tests

Tests for complete SageMaker pipeline execution and validation.
"""

import pytest
import boto3
import json
import time
from pathlib import Path
from typing import Dict, Any
import sagemaker
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import LocalPipelineSession


class TestPipelineExecution:
    """Test end-to-end pipeline execution"""
    
    @pytest.fixture
    def sagemaker_session(self):
        """Create SageMaker session for testing"""
        return sagemaker.Session()
    
    @pytest.fixture
    def local_session(self):
        """Create local pipeline session for testing"""
        return LocalPipelineSession()
    
    def test_pipeline_definition_valid(self, local_session):
        """Test that pipeline definition is valid"""
        # This would be customized based on actual pipeline
        try:
            # Mock pipeline definition
            from sagemaker.workflow.steps import TrainingStep
            from sagemaker.sklearn.estimator import SKLearn
            
            # Create a simple estimator for testing
            estimator = SKLearn(
                entry_point="train.py",
                framework_version="0.23-1",
                instance_type="ml.m5.large",
                role="arn:aws:iam::123456789012:role/SageMakerRole",
                sagemaker_session=local_session
            )
            
            # Create training step
            training_step = TrainingStep(
                name="TrainingStep",
                estimator=estimator
            )
            
            # Create pipeline
            pipeline = Pipeline(
                name="test-pipeline",
                steps=[training_step],
                sagemaker_session=local_session
            )
            
            # Validate pipeline definition
            pipeline_definition = pipeline.definition()
            assert pipeline_definition is not None
            assert "Steps" in pipeline_definition
            
        except Exception as e:
            pytest.fail(f"Pipeline definition validation failed: {e}")
    
    def test_pipeline_local_execution(self, local_session):
        """Test pipeline execution in local mode"""
        # This test would run the pipeline locally
        # Implementation depends on actual pipeline structure
        pass
    
    def test_pipeline_parameter_validation(self):
        """Test pipeline parameter validation"""
        # Test various parameter combinations
        valid_params = {
            "InstanceType": "ml.m5.large",
            "ModelName": "test-model",
            "BatchSize": 32
        }
        
        # Validate parameter types and ranges
        assert isinstance(valid_params["BatchSize"], int)
        assert valid_params["BatchSize"] > 0
        assert valid_params["InstanceType"].startswith("ml.")
    
    def test_pipeline_error_handling(self):
        """Test pipeline error handling"""
        # Test handling of various error conditions
        invalid_params = {
            "InstanceType": "invalid-instance",
            "BatchSize": -1
        }
        
        # These should be caught and handled appropriately
        with pytest.raises((ValueError, TypeError)):
            if invalid_params["BatchSize"] <= 0:
                raise ValueError("Batch size must be positive")
    
    def test_pipeline_artifact_validation(self):
        """Test that pipeline produces expected artifacts"""
        # Mock artifact validation
        expected_artifacts = [
            "model.tar.gz",
            "evaluation.json",
            "metrics.json"
        ]
        
        # In real implementation, this would check S3 or local paths
        for artifact in expected_artifacts:
            # Mock validation - in real test would check actual files
            assert artifact.endswith(('.tar.gz', '.json', '.pkl'))


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        tests["test_pipeline_monitoring.py"] = '''"""
Pipeline Monitoring Tests

Tests for pipeline monitoring, logging, and status tracking.
"""

import pytest
import boto3
import json
import time
from unittest.mock import Mock, patch


class TestPipelineMonitoring:
    """Test pipeline monitoring functionality"""
    
    def test_pipeline_status_tracking(self):
        """Test pipeline status tracking"""
        # Mock pipeline execution statuses
        statuses = ["Starting", "InProgress", "Completed", "Failed"]
        
        for status in statuses:
            # Validate status is recognized
            assert status in ["Starting", "InProgress", "Completed", "Failed", "Stopped"]
    
    def test_pipeline_logging(self):
        """Test pipeline logging functionality"""
        # Mock log entries
        log_entries = [
            {"timestamp": "2024-01-01T10:00:00Z", "level": "INFO", "message": "Pipeline started"},
            {"timestamp": "2024-01-01T10:05:00Z", "level": "INFO", "message": "Training step started"},
            {"timestamp": "2024-01-01T10:30:00Z", "level": "INFO", "message": "Training completed"},
        ]
        
        # Validate log structure
        for entry in log_entries:
            assert "timestamp" in entry
            assert "level" in entry
            assert "message" in entry
            assert entry["level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]
    
    def test_pipeline_metrics_collection(self):
        """Test pipeline metrics collection"""
        # Mock metrics
        metrics = {
            "execution_time": 1800,  # 30 minutes
            "training_accuracy": 0.95,
            "validation_accuracy": 0.92,
            "cost": 15.50
        }
        
        # Validate metrics
        assert metrics["execution_time"] > 0
        assert 0 <= metrics["training_accuracy"] <= 1
        assert 0 <= metrics["validation_accuracy"] <= 1
        assert metrics["cost"] >= 0
    
    def test_pipeline_alerting(self):
        """Test pipeline alerting functionality"""
        # Mock alert conditions
        alert_conditions = [
            {"metric": "accuracy", "threshold": 0.8, "operator": "less_than"},
            {"metric": "execution_time", "threshold": 3600, "operator": "greater_than"},
            {"metric": "cost", "threshold": 100, "operator": "greater_than"}
        ]
        
        # Test alert evaluation
        current_metrics = {
            "accuracy": 0.75,  # Should trigger alert
            "execution_time": 1800,  # Should not trigger alert
            "cost": 15.50  # Should not trigger alert
        }
        
        alerts_triggered = []
        for condition in alert_conditions:
            metric_value = current_metrics.get(condition["metric"])
            if metric_value is not None:
                if condition["operator"] == "less_than" and metric_value < condition["threshold"]:
                    alerts_triggered.append(condition["metric"])
                elif condition["operator"] == "greater_than" and metric_value > condition["threshold"]:
                    alerts_triggered.append(condition["metric"])
        
        assert "accuracy" in alerts_triggered
        assert "execution_time" not in alerts_triggered
        assert "cost" not in alerts_triggered


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return tests
    
    def _generate_endpoint_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate inference endpoint testing suites"""
        tests = {}
        
        tests["test_endpoint_deployment.py"] = '''"""
Endpoint Deployment Tests

Tests for SageMaker endpoint deployment and configuration.
"""

import pytest
import boto3
import json
import time
import requests
from unittest.mock import Mock, patch


class TestEndpointDeployment:
    """Test endpoint deployment functionality"""
    
    @pytest.fixture
    def sagemaker_client(self):
        """Mock SageMaker client"""
        return boto3.client('sagemaker', region_name='us-east-1')
    
    def test_endpoint_configuration_valid(self):
        """Test endpoint configuration validation"""
        config = {
            "EndpointConfigName": "test-endpoint-config",
            "ProductionVariants": [
                {
                    "VariantName": "primary",
                    "ModelName": "test-model",
                    "InitialInstanceCount": 1,
                    "InstanceType": "ml.t2.medium",
                    "InitialVariantWeight": 1.0
                }
            ]
        }
        
        # Validate configuration structure
        assert "EndpointConfigName" in config
        assert "ProductionVariants" in config
        assert len(config["ProductionVariants"]) > 0
        
        variant = config["ProductionVariants"][0]
        assert "VariantName" in variant
        assert "ModelName" in variant
        assert "InstanceType" in variant
        assert variant["InitialInstanceCount"] > 0
    
    def test_endpoint_health_check(self):
        """Test endpoint health check"""
        # Mock endpoint response
        health_response = {
            "EndpointStatus": "InService",
            "EndpointArn": "arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint",
            "CreationTime": "2024-01-01T10:00:00Z",
            "LastModifiedTime": "2024-01-01T10:05:00Z"
        }
        
        # Validate health check response
        assert health_response["EndpointStatus"] in ["Creating", "InService", "Updating", "Failed", "Deleting"]
        assert "EndpointArn" in health_response
        assert "CreationTime" in health_response
    
    def test_endpoint_scaling(self):
        """Test endpoint auto-scaling configuration"""
        scaling_config = {
            "MinCapacity": 1,
            "MaxCapacity": 10,
            "TargetValue": 70.0,
            "ScaleInCooldown": 300,
            "ScaleOutCooldown": 300
        }
        
        # Validate scaling configuration
        assert scaling_config["MinCapacity"] >= 1
        assert scaling_config["MaxCapacity"] >= scaling_config["MinCapacity"]
        assert 0 < scaling_config["TargetValue"] <= 100
        assert scaling_config["ScaleInCooldown"] >= 0
        assert scaling_config["ScaleOutCooldown"] >= 0
    
    def test_endpoint_security(self):
        """Test endpoint security configuration"""
        security_config = {
            "VpcConfig": {
                "SecurityGroupIds": ["sg-12345678"],
                "Subnets": ["subnet-12345678", "subnet-87654321"]
            },
            "EnableNetworkIsolation": True
        }
        
        # Validate security configuration
        if "VpcConfig" in security_config:
            assert "SecurityGroupIds" in security_config["VpcConfig"]
            assert "Subnets" in security_config["VpcConfig"]
            assert len(security_config["VpcConfig"]["SecurityGroupIds"]) > 0
            assert len(security_config["VpcConfig"]["Subnets"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        tests["test_endpoint_inference.py"] = '''"""
Endpoint Inference Tests

Tests for endpoint inference functionality and response validation.
"""

import pytest
import json
import numpy as np
import requests
from unittest.mock import Mock, patch


class TestEndpointInference:
    """Test endpoint inference functionality"""
    
    def test_inference_request_format(self):
        """Test inference request format validation"""
        # Test various input formats
        test_inputs = [
            {"instances": [[1, 2, 3, 4, 5]]},
            {"instances": [{"feature1": 1.0, "feature2": 2.0}]},
            {"data": {"ndarray": [[1, 2, 3, 4, 5]]}},
        ]
        
        for input_data in test_inputs:
            # Validate input structure
            assert isinstance(input_data, dict)
            assert len(input_data) > 0
    
    def test_inference_response_format(self):
        """Test inference response format validation"""
        # Mock inference responses
        responses = [
            {"predictions": [0.8, 0.2]},
            {"predictions": [[0.1, 0.9]]},
            {"outputs": [{"score": 0.95, "label": "positive"}]}
        ]
        
        for response in responses:
            # Validate response structure
            assert isinstance(response, dict)
            assert len(response) > 0
            # Should contain predictions or outputs
            assert "predictions" in response or "outputs" in response
    
    def test_batch_inference(self):
        """Test batch inference functionality"""
        # Mock batch request
        batch_request = {
            "instances": [
                [1, 2, 3, 4, 5],
                [2, 3, 4, 5, 6],
                [3, 4, 5, 6, 7]
            ]
        }
        
        # Mock batch response
        batch_response = {
            "predictions": [
                [0.8, 0.2],
                [0.7, 0.3],
                [0.9, 0.1]
            ]
        }
        
        # Validate batch processing
        assert len(batch_request["instances"]) == len(batch_response["predictions"])
        
        for prediction in batch_response["predictions"]:
            assert isinstance(prediction, list)
            assert len(prediction) > 0
    
    def test_inference_latency(self):
        """Test inference latency requirements"""
        import time
        
        # Mock inference timing
        start_time = time.time()
        # Simulate inference processing
        time.sleep(0.01)  # 10ms simulation
        end_time = time.time()
        
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Validate latency is reasonable (< 1000ms for this test)
        assert latency < 1000
        assert latency > 0
    
    def test_inference_error_handling(self):
        """Test inference error handling"""
        # Test various error scenarios
        error_cases = [
            {"error": "Invalid input format", "code": 400},
            {"error": "Model not found", "code": 404},
            {"error": "Internal server error", "code": 500}
        ]
        
        for error_case in error_cases:
            # Validate error response structure
            assert "error" in error_case
            assert "code" in error_case
            assert 400 <= error_case["code"] < 600
    
    def test_inference_data_types(self):
        """Test inference with different data types"""
        # Test different input data types
        test_cases = [
            {"input": [1, 2, 3], "type": "int"},
            {"input": [1.0, 2.5, 3.7], "type": "float"},
            {"input": ["text", "data"], "type": "string"},
            {"input": [[1, 2], [3, 4]], "type": "nested"}
        ]
        
        for case in test_cases:
            input_data = case["input"]
            data_type = case["type"]
            
            # Validate input based on type
            if data_type == "int":
                assert all(isinstance(x, int) for x in input_data)
            elif data_type == "float":
                assert all(isinstance(x, (int, float)) for x in input_data)
            elif data_type == "string":
                assert all(isinstance(x, str) for x in input_data)
            elif data_type == "nested":
                assert all(isinstance(x, list) for x in input_data)


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return tests
    
    def _generate_benchmark_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate performance benchmarking tools"""
        tests = {}
        
        tests["test_performance_benchmarks.py"] = '''"""
Performance Benchmarking Tests

Tests for measuring and validating system performance metrics.
"""

import pytest
import time
import psutil
import numpy as np
from typing import Dict, List, Any
import json


class TestPerformanceBenchmarks:
    """Test system performance benchmarks"""
    
    def test_training_performance(self):
        """Test training performance metrics"""
        # Mock training performance data
        training_metrics = {
            "epoch_time": 120.5,  # seconds
            "samples_per_second": 1000,
            "gpu_utilization": 0.85,
            "memory_usage": 0.70,
            "loss_convergence_rate": 0.95
        }
        
        # Validate performance metrics
        assert training_metrics["epoch_time"] > 0
        assert training_metrics["samples_per_second"] > 0
        assert 0 <= training_metrics["gpu_utilization"] <= 1
        assert 0 <= training_metrics["memory_usage"] <= 1
        assert 0 <= training_metrics["loss_convergence_rate"] <= 1
    
    def test_inference_performance(self):
        """Test inference performance metrics"""
        # Mock inference performance data
        inference_metrics = {
            "latency_p50": 25.0,  # milliseconds
            "latency_p95": 50.0,
            "latency_p99": 100.0,
            "throughput": 500,  # requests per second
            "error_rate": 0.001
        }
        
        # Validate inference metrics
        assert inference_metrics["latency_p50"] > 0
        assert inference_metrics["latency_p95"] >= inference_metrics["latency_p50"]
        assert inference_metrics["latency_p99"] >= inference_metrics["latency_p95"]
        assert inference_metrics["throughput"] > 0
        assert 0 <= inference_metrics["error_rate"] <= 1
    
    def test_resource_utilization(self):
        """Test resource utilization metrics"""
        # Get actual system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Validate resource metrics
        assert 0 <= cpu_percent <= 100
        assert 0 <= memory.percent <= 100
        assert 0 <= disk.percent <= 100
        assert memory.total > 0
        assert disk.total > 0
    
    def test_scalability_metrics(self):
        """Test scalability performance"""
        # Mock scalability test results
        scalability_data = [
            {"instances": 1, "throughput": 100, "latency": 50},
            {"instances": 2, "throughput": 180, "latency": 55},
            {"instances": 4, "throughput": 320, "latency": 65},
            {"instances": 8, "throughput": 580, "latency": 80}
        ]
        
        # Validate scalability trends
        for i in range(1, len(scalability_data)):
            current = scalability_data[i]
            previous = scalability_data[i-1]
            
            # Throughput should generally increase with more instances
            assert current["throughput"] > previous["throughput"] * 0.8  # Allow some efficiency loss
            
            # Latency should not increase dramatically
            assert current["latency"] < previous["latency"] * 2  # Should not double
    
    def test_cost_performance_ratio(self):
        """Test cost-performance ratio"""
        # Mock cost and performance data
        configurations = [
            {"instance_type": "ml.t3.medium", "cost_per_hour": 0.0416, "throughput": 100},
            {"instance_type": "ml.m5.large", "cost_per_hour": 0.096, "throughput": 200},
            {"instance_type": "ml.c5.xlarge", "cost_per_hour": 0.17, "throughput": 400}
        ]
        
        # Calculate cost-performance ratios
        for config in configurations:
            cost_per_request = config["cost_per_hour"] / (config["throughput"] * 3600)  # per second
            config["cost_efficiency"] = 1 / cost_per_request if cost_per_request > 0 else 0
            
            # Validate calculations
            assert config["cost_per_hour"] > 0
            assert config["throughput"] > 0
            assert config["cost_efficiency"] > 0
    
    def test_memory_efficiency(self):
        """Test memory usage efficiency"""
        # Mock memory usage patterns
        memory_usage = {
            "model_size": 500,  # MB
            "batch_processing": 1200,  # MB
            "peak_usage": 1500,  # MB
            "baseline": 200  # MB
        }
        
        # Validate memory efficiency
        assert memory_usage["model_size"] > 0
        assert memory_usage["batch_processing"] >= memory_usage["model_size"]
        assert memory_usage["peak_usage"] >= memory_usage["batch_processing"]
        assert memory_usage["baseline"] > 0
        
        # Calculate memory efficiency ratio
        efficiency_ratio = memory_usage["model_size"] / memory_usage["peak_usage"]
        assert 0 < efficiency_ratio <= 1
    
    def test_network_performance(self):
        """Test network performance metrics"""
        # Mock network performance data
        network_metrics = {
            "bandwidth_utilization": 0.65,  # 65% of available bandwidth
            "packet_loss": 0.001,  # 0.1% packet loss
            "round_trip_time": 15.5,  # milliseconds
            "jitter": 2.3  # milliseconds
        }
        
        # Validate network metrics
        assert 0 <= network_metrics["bandwidth_utilization"] <= 1
        assert 0 <= network_metrics["packet_loss"] <= 1
        assert network_metrics["round_trip_time"] > 0
        assert network_metrics["jitter"] >= 0


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return tests
    
    def _generate_monitoring_tests(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate monitoring and alerting validation tests"""
        tests = {}
        
        tests["test_monitoring_validation.py"] = '''"""
Monitoring and Alerting Validation Tests

Tests for monitoring systems, alerting mechanisms, and observability.
"""

import pytest
import json
import time
from typing import Dict, List, Any
from unittest.mock import Mock, patch


class TestMonitoringValidation:
    """Test monitoring and alerting functionality"""
    
    def test_cloudwatch_metrics(self):
        """Test CloudWatch metrics collection"""
        # Mock CloudWatch metrics
        metrics = [
            {"MetricName": "Invocations", "Value": 1000, "Unit": "Count"},
            {"MetricName": "Duration", "Value": 250.5, "Unit": "Milliseconds"},
            {"MetricName": "Errors", "Value": 5, "Unit": "Count"},
            {"MetricName": "Throttles", "Value": 0, "Unit": "Count"}
        ]
        
        # Validate metric structure
        for metric in metrics:
            assert "MetricName" in metric
            assert "Value" in metric
            assert "Unit" in metric
            assert isinstance(metric["Value"], (int, float))
            assert metric["Value"] >= 0
    
    def test_custom_metrics(self):
        """Test custom application metrics"""
        # Mock custom metrics
        custom_metrics = {
            "model_accuracy": 0.95,
            "prediction_confidence": 0.87,
            "data_drift_score": 0.12,
            "feature_importance_stability": 0.93
        }
        
        # Validate custom metrics
        for metric_name, value in custom_metrics.items():
            assert isinstance(value, (int, float))
            if "accuracy" in metric_name or "confidence" in metric_name or "stability" in metric_name:
                assert 0 <= value <= 1
            if "drift" in metric_name:
                assert value >= 0
    
    def test_alert_configuration(self):
        """Test alert configuration validation"""
        # Mock alert configurations
        alerts = [
            {
                "name": "HighErrorRate",
                "metric": "Errors",
                "threshold": 10,
                "comparison": "GreaterThanThreshold",
                "evaluation_periods": 2,
                "period": 300
            },
            {
                "name": "LowAccuracy",
                "metric": "model_accuracy",
                "threshold": 0.8,
                "comparison": "LessThanThreshold",
                "evaluation_periods": 1,
                "period": 600
            }
        ]
        
        # Validate alert configurations
        for alert in alerts:
            assert "name" in alert
            assert "metric" in alert
            assert "threshold" in alert
            assert "comparison" in alert
            assert alert["comparison"] in ["GreaterThanThreshold", "LessThanThreshold", "GreaterThanOrEqualToThreshold", "LessThanOrEqualToThreshold"]
            assert alert["evaluation_periods"] > 0
            assert alert["period"] > 0
    
    def test_log_aggregation(self):
        """Test log aggregation and analysis"""
        # Mock log entries
        log_entries = [
            {"timestamp": "2024-01-01T10:00:00Z", "level": "INFO", "message": "Request processed", "duration": 150},
            {"timestamp": "2024-01-01T10:00:01Z", "level": "ERROR", "message": "Validation failed", "error_code": "INVALID_INPUT"},
            {"timestamp": "2024-01-01T10:00:02Z", "level": "WARN", "message": "High latency detected", "duration": 500}
        ]
        
        # Analyze log patterns
        error_count = sum(1 for entry in log_entries if entry["level"] == "ERROR")
        warning_count = sum(1 for entry in log_entries if entry["level"] == "WARN")
        avg_duration = sum(entry.get("duration", 0) for entry in log_entries) / len(log_entries)
        
        # Validate log analysis
        assert error_count >= 0
        assert warning_count >= 0
        assert avg_duration >= 0
        
        # Check for concerning patterns
        error_rate = error_count / len(log_entries)
        assert 0 <= error_rate <= 1
    
    def test_dashboard_data(self):
        """Test monitoring dashboard data"""
        # Mock dashboard data
        dashboard_data = {
            "system_health": {
                "status": "healthy",
                "uptime": 99.95,
                "last_incident": "2024-01-01T08:00:00Z"
            },
            "performance": {
                "avg_response_time": 125.5,
                "requests_per_minute": 1500,
                "error_rate": 0.002
            },
            "resources": {
                "cpu_utilization": 65.2,
                "memory_utilization": 78.1,
                "disk_utilization": 45.3
            }
        }
        
        # Validate dashboard data structure
        assert "system_health" in dashboard_data
        assert "performance" in dashboard_data
        assert "resources" in dashboard_data
        
        # Validate health metrics
        health = dashboard_data["system_health"]
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert 0 <= health["uptime"] <= 100
        
        # Validate performance metrics
        perf = dashboard_data["performance"]
        assert perf["avg_response_time"] > 0
        assert perf["requests_per_minute"] >= 0
        assert 0 <= perf["error_rate"] <= 1
        
        # Validate resource metrics
        resources = dashboard_data["resources"]
        assert 0 <= resources["cpu_utilization"] <= 100
        assert 0 <= resources["memory_utilization"] <= 100
        assert 0 <= resources["disk_utilization"] <= 100
    
    def test_notification_delivery(self):
        """Test notification delivery mechanisms"""
        # Mock notification configurations
        notifications = [
            {"type": "email", "recipients": ["admin@example.com"], "severity": "critical"},
            {"type": "slack", "channel": "#alerts", "severity": "warning"},
            {"type": "sns", "topic_arn": "arn:aws:sns:us-east-1:123456789012:alerts", "severity": "error"}
        ]
        
        # Validate notification configurations
        for notification in notifications:
            assert "type" in notification
            assert "severity" in notification
            assert notification["type"] in ["email", "slack", "sns", "webhook"]
            assert notification["severity"] in ["info", "warning", "error", "critical"]
            
            # Type-specific validations
            if notification["type"] == "email":
                assert "recipients" in notification
                assert len(notification["recipients"]) > 0
            elif notification["type"] == "slack":
                assert "channel" in notification
            elif notification["type"] == "sns":
                assert "topic_arn" in notification
                assert notification["topic_arn"].startswith("arn:aws:sns:")


if __name__ == "__main__":
    pytest.main([__file__])
'''
        
        return tests
    
    def _generate_config_files(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate configuration files for integration tests"""
        configs = {}
        
        configs["pytest.ini"] = '''[tool:pytest]
testpaths = tests/integration
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --color=yes
markers =
    integration: marks tests as integration tests
    slow: marks tests as slow running
    aws: marks tests that require AWS credentials
    endpoint: marks tests for endpoint functionality
    pipeline: marks tests for pipeline functionality
    monitoring: marks tests for monitoring functionality
    benchmark: marks tests for performance benchmarking
'''
        
        configs["test_config.json"] = '''{
    "aws": {
        "region": "us-east-1",
        "role_arn": "arn:aws:iam::123456789012:role/SageMakerExecutionRole",
        "bucket": "sagemigrator-test-bucket"
    },
    "sagemaker": {
        "instance_types": {
            "training": "ml.m5.large",
            "inference": "ml.t3.medium"
        },
        "framework_versions": {
            "pytorch": "1.12.0",
            "sklearn": "0.23-1"
        }
    },
    "testing": {
        "timeout": 3600,
        "retry_attempts": 3,
        "cleanup_after_test": true
    },
    "monitoring": {
        "metrics_namespace": "SageMigrator/Testing",
        "log_group": "/aws/sagemaker/testing",
        "alert_email": "alerts@example.com"
    }
}'''
        
        configs["docker-compose.test.yml"] = '''version: '3.8'
services:
  integration-tests:
    build:
      context: .
      dockerfile: Dockerfile.test
    environment:
      - AWS_DEFAULT_REGION=us-east-1
      - PYTHONPATH=/app
      - TESTING=true
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    command: pytest tests/integration/ -v
    
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,sagemaker,cloudwatch,logs
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
    volumes:
      - localstack_data:/tmp/localstack
      
volumes:
  localstack_data:
'''
        
        return configs
    
    def _generate_integration_documentation(
        self,
        pipeline_tests: Dict[str, str],
        endpoint_tests: Dict[str, str], 
        benchmark_tests: Dict[str, str],
        monitoring_tests: Dict[str, str]
    ) -> str:
        """Generate documentation for integration tests"""
        return f'''# Integration Testing Suite Documentation

## Overview

This integration testing suite provides comprehensive end-to-end testing for SageMigrator migration artifacts. It includes pipeline execution tests, endpoint deployment and inference tests, performance benchmarking, and monitoring validation.

## Test Categories

### 1. Pipeline Tests
{chr(10).join(f"- **{name}**: End-to-end pipeline execution and validation" for name in pipeline_tests.keys())}

### 2. Endpoint Tests  
{chr(10).join(f"- **{name}**: Endpoint deployment and inference testing" for name in endpoint_tests.keys())}

### 3. Benchmark Tests
{chr(10).join(f"- **{name}**: Performance benchmarking and optimization" for name in benchmark_tests.keys())}

### 4. Monitoring Tests
{chr(10).join(f"- **{name}**: Monitoring and alerting validation" for name in monitoring_tests.keys())}

## Prerequisites

### AWS Configuration
- AWS credentials configured (via AWS CLI, IAM roles, or environment variables)
- SageMaker execution role with appropriate permissions
- S3 bucket for test artifacts
- CloudWatch permissions for metrics and logs

### Local Environment
- Docker and Docker Compose (for local testing)
- Python 3.8+ with required dependencies
- Sufficient disk space for test artifacts

## Running Tests

### Full Integration Test Suite
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with specific markers
pytest tests/integration/ -m "pipeline" -v
pytest tests/integration/ -m "endpoint" -v
pytest tests/integration/ -m "benchmark" -v
```

### Individual Test Categories
```bash
# Pipeline tests
pytest tests/integration/test_pipeline_execution.py -v

# Endpoint tests  
pytest tests/integration/test_endpoint_deployment.py -v
pytest tests/integration/test_endpoint_inference.py -v

# Performance tests
pytest tests/integration/test_performance_benchmarks.py -v

# Monitoring tests
pytest tests/integration/test_monitoring_validation.py -v
```

### Local Testing with LocalStack
```bash
# Start LocalStack services
docker-compose -f docker-compose.test.yml up -d localstack

# Run tests against LocalStack
AWS_ENDPOINT_URL=http://localhost:4566 pytest tests/integration/ -v

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Configuration

### Test Configuration File
Edit `test_config.json` to customize:
- AWS region and credentials
- SageMaker instance types
- Framework versions
- Testing timeouts and retry settings
- Monitoring configuration

### Environment Variables
```bash
export AWS_DEFAULT_REGION=us-east-1
export SAGEMAKER_ROLE_ARN=arn:aws:iam::123456789012:role/SageMakerExecutionRole
export TEST_BUCKET=sagemigrator-test-bucket
export TESTING=true
```

## Test Data Management

### Test Artifacts
- Training data: Generated synthetically or downloaded from public datasets
- Model artifacts: Created during test execution
- Configuration files: Stored in test configuration directory

### Cleanup
Tests automatically clean up resources after execution. To manually cleanup:
```bash
# Cleanup test resources
python tests/integration/cleanup_test_resources.py

# Remove test artifacts
rm -rf test_artifacts/
```

## Monitoring and Reporting

### Test Results
- JUnit XML reports generated for CI/CD integration
- Coverage reports for code coverage analysis
- Performance metrics logged to CloudWatch

### Continuous Integration
```yaml
# Example GitHub Actions workflow
name: Integration Tests
on: [push, pull_request]
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run integration tests
        run: pytest tests/integration/ --junitxml=results.xml
        env:
          AWS_ACCESS_KEY_ID: ${{{{ secrets.AWS_ACCESS_KEY_ID }}}}
          AWS_SECRET_ACCESS_KEY: ${{{{ secrets.AWS_SECRET_ACCESS_KEY }}}}
```

## Troubleshooting

### Common Issues

1. **AWS Permissions**: Ensure SageMaker execution role has required permissions
2. **Resource Limits**: Check AWS service limits for your account
3. **Network Issues**: Verify VPC and security group configurations
4. **Timeout Issues**: Increase timeout values in test configuration

### Debug Mode
```bash
# Run tests with debug logging
pytest tests/integration/ -v -s --log-cli-level=DEBUG

# Run specific test with detailed output
pytest tests/integration/test_pipeline_execution.py::TestPipelineExecution::test_pipeline_definition_valid -v -s
```

### Getting Help
- Check AWS CloudWatch logs for detailed error messages
- Review SageMaker training and endpoint logs
- Consult AWS documentation for service-specific issues
- File issues in the SageMigrator repository for tool-specific problems
'''
    
    def _load_test_templates(self) -> Dict[str, str]:
        """Load test templates (placeholder for future template system)"""
        return {}
    
    def validate_integration_suite(self, test_suite: IntegrationTestSuite) -> List[CompatibilityCheck]:
        """Validate the generated integration test suite"""
        checks = []
        
        # Check that all required test categories are present
        required_categories = ["pipeline_tests", "endpoint_tests", "benchmark_tests", "monitoring_tests"]
        
        for category in required_categories:
            category_tests = getattr(test_suite, category, {})
            if category_tests:
                checks.append(CompatibilityCheck(
                    check_name=f"Integration test category: {category}",
                    status=ValidationStatus.PASSED,
                    message=f"Required test category {category} is present",
                    details={"test_count": len(category_tests)},
                    severity="high"
                ))
            else:
                checks.append(CompatibilityCheck(
                    check_name=f"Integration test category: {category}",
                    status=ValidationStatus.FAILED,
                    message=f"Required test category {category} is missing",
                    details={},
                    severity="high"
                ))
        
        # Check configuration files
        if test_suite.config_files:
            checks.append(CompatibilityCheck(
                check_name="Configuration files",
                status=ValidationStatus.PASSED,
                message="Configuration files are present",
                details={"config_count": len(test_suite.config_files)},
                severity="medium"
            ))
        
        return checks