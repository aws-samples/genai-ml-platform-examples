"""
CloudWatch Dashboard for SageMaker Endpoint Monitoring
"""
from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from config.constants import DEPLOY_ACCOUNT, DEFAULT_DEPLOYMENT_REGION

# Healthcheck configuration constants
ALARM_THRESHOLDS = {
    "dev": {
        "error_rate_percent": 10.0,
        "latency_ms": 15000,
        "cpu_percent": 85.0,
        "memory_percent": 90.0,
        "healthcheck_success_rate": 0.7
    },
    "staging": {
        "error_rate_percent": 7.0,
        "latency_ms": 12000,
        "cpu_percent": 80.0,
        "memory_percent": 85.0,
        "healthcheck_success_rate": 0.8
    },
    "production": {
        "error_rate_percent": 5.0,
        "latency_ms": 10000,
        "cpu_percent": 75.0,
        "memory_percent": 80.0,
        "healthcheck_success_rate": 0.9
    }
}

HEALTHCHECK_SCHEDULE = {
    "dev": 10,      # Every 10 minutes
    "staging": 5,   # Every 5 minutes
    "production": 2 # Every 2 minutes
}

HEALTHCHECK_PAYLOADS = {
    "default": {
        "instances": [[1.0, 2.0, 3.0, 4.0]]
    }
}


class CloudWatchMonitoringStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, endpoint_name: str, monitoring_config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.endpoint_name = endpoint_name
        self.monitoring_config = monitoring_config
        self.environment_name = construct_id.split('-')[-1]
        
        # Create SNS topic for alerts
        self.alarm_topic = self.create_alarm_topic()
        
        # Create CloudWatch Dashboard
        self.create_sagemaker_dashboard()
        
        # Create CloudWatch Alarms
        self.create_sagemaker_alarms()
        
        # Create healthcheck Lambda
        self.create_healthcheck_lambda()
    
    def create_sagemaker_dashboard(self):
        """Create comprehensive SageMaker monitoring dashboard"""
        
        dashboard = cloudwatch.Dashboard(
            self,
            "SageMakerDashboard",
            dashboard_name=f"{self.environment_name}-sagemaker-dashboard",
            period_override=cloudwatch.PeriodOverride.AUTO,
            start="-PT24H"  # Force update by adding start parameter
        )
        
        # Row 1: Invocation Metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Endpoint Invocations",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocations",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Invocations Per Instance",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="InvocationsPerInstance",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            )
        )
        
        # Row 2: Latency Metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Model Latency",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="ModelLatency",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Overhead Latency",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="OverheadLatency",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            )
        )
        
        # Row 3: Error Metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="4XX Errors",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocation4XXErrors",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="5XX Errors",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocation5XXErrors",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                ],
                width=12,
                height=6
            )
        )
        
        # Row 4: Resource Utilization
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="CPU Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="CPUUtilization",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Memory Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="MemoryUtilization",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Disk Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="DiskUtilization",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=8,
                height=6
            )
        )
        
        # Row 5: Summary Stats
        dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Total Invocations (24h)",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocations",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Sum",
                        period=Duration.hours(24)
                    )
                ],
                width=6,
                height=6
            ),
            cloudwatch.SingleValueWidget(
                title="Average Latency (1h)",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="ModelLatency",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.hours(1)
                    )
                ],
                width=6,
                height=6
            ),
            cloudwatch.SingleValueWidget(
                title="Error Rate (1h)",
                metrics=[
                    cloudwatch.MathExpression(
                        expression="(m1 + m2) / m3 * 100",
                        using_metrics={
                            "m1": cloudwatch.Metric(
                                namespace="AWS/SageMaker",
                                metric_name="Invocation4XXErrors",
                                dimensions_map={
                                    "EndpointName": self.endpoint_name,
                                    "VariantName": "AllTraffic"
                                },
                                statistic="Sum",
                                period=Duration.hours(1)
                            ),
                            "m2": cloudwatch.Metric(
                                namespace="AWS/SageMaker",
                                metric_name="Invocation5XXErrors",
                                dimensions_map={
                                    "EndpointName": self.endpoint_name,
                                    "VariantName": "AllTraffic"
                                },
                                statistic="Sum",
                                period=Duration.hours(1)
                            ),
                            "m3": cloudwatch.Metric(
                                namespace="AWS/SageMaker",
                                metric_name="Invocations",
                                dimensions_map={
                                    "EndpointName": self.endpoint_name,
                                    "VariantName": "AllTraffic"
                                },
                                statistic="Sum",
                                period=Duration.hours(1)
                            )
                        },
                        label="Error Rate %"
                    )
                ],
                width=6,
                height=6
            ),
            cloudwatch.SingleValueWidget(
                title="Current CPU Usage",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="CPUUtilization",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(5)
                    )
                ],
                width=6,
                height=6
            )
        )
        
        # Row 6: Model Quality Monitoring
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Model Quality Violations",
                left=[
                    cloudwatch.Metric(
                        namespace="SageMaker/ModelMonitor/Custom",
                        metric_name="ViolationsDetected",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "Environment": self.environment_name
                        },
                        statistic="Sum",
                        period=Duration.hours(1)
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Monitoring Execution Status",
                left=[
                    cloudwatch.Metric(
                        namespace="SageMaker/ModelMonitor/Custom",
                        metric_name="MonitoringExecutionStatus",
                        dimensions_map={
                            "EndpointName": self.endpoint_name,
                            "Environment": self.environment_name
                        },
                        statistic="Average",
                        period=Duration.hours(1)
                    )
                ],
                width=12,
                height=6
            )
        )
    
    def create_alarm_topic(self):
        """Create SNS topic for alarm notifications"""
        return sns.Topic(
            self,
            "SageMakerAlarmTopic",
            topic_name=f"{self.environment_name}-sagemaker-alarms",
            display_name="SageMaker Endpoint Alarms"
        )
    
    def create_sagemaker_alarms(self):
        """Create comprehensive CloudWatch alarms for SageMaker endpoint"""
        
        # Get environment-specific thresholds
        thresholds = ALARM_THRESHOLDS.get(self.environment_name, ALARM_THRESHOLDS["dev"])
        
        # High Error Rate Alarm
        error_rate_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            alarm_name=f"{self.endpoint_name}-high-error-rate",
            alarm_description="High error rate detected on SageMaker endpoint",
            metric=cloudwatch.MathExpression(
                expression="(m1 + m2) / m3 * 100",
                using_metrics={
                    "m1": cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocation4XXErrors",
                        dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                        statistic="Sum",
                        period=Duration.minutes(5)
                    ),
                    "m2": cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocation5XXErrors",
                        dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                        statistic="Sum",
                        period=Duration.minutes(5)
                    ),
                    "m3": cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocations",
                        dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                }
            ),
            threshold=thresholds["error_rate_percent"],
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        error_rate_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
        
        # High Latency Alarm
        latency_alarm = cloudwatch.Alarm(
            self,
            "HighLatencyAlarm",
            alarm_name=f"{self.endpoint_name}-high-latency",
            alarm_description="High latency detected on SageMaker endpoint",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="ModelLatency",
                dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=thresholds["latency_ms"],
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        latency_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
        
        # High CPU Utilization Alarm
        cpu_alarm = cloudwatch.Alarm(
            self,
            "HighCPUAlarm",
            alarm_name=f"{self.endpoint_name}-high-cpu",
            alarm_description="High CPU utilization on SageMaker endpoint",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="CPUUtilization",
                dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=thresholds["cpu_percent"],
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        cpu_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
        
        # High Memory Utilization Alarm
        memory_alarm = cloudwatch.Alarm(
            self,
            "HighMemoryAlarm",
            alarm_name=f"{self.endpoint_name}-high-memory",
            alarm_description="High memory utilization on SageMaker endpoint",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="MemoryUtilization",
                dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=thresholds["memory_percent"],
            evaluation_periods=3,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        memory_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
        
        # No Invocations Alarm (Endpoint not receiving traffic)
        no_invocations_alarm = cloudwatch.Alarm(
            self,
            "NoInvocationsAlarm",
            alarm_name=f"{self.endpoint_name}-no-invocations",
            alarm_description="No invocations detected on SageMaker endpoint",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="Invocations",
                dimensions_map={"EndpointName": self.endpoint_name, "VariantName": "AllTraffic"},
                statistic="Sum",
                period=Duration.minutes(15)
            ),
            threshold=1,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING
        )
        no_invocations_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
    
    def create_healthcheck_lambda(self):
        """Create Lambda function for endpoint healthchecks"""
        
        # Get environment-specific configuration
        thresholds = ALARM_THRESHOLDS.get(self.environment_name, ALARM_THRESHOLDS["dev"])
        schedule_minutes = HEALTHCHECK_SCHEDULE.get(self.environment_name, 5)
        
        # IAM role for healthcheck Lambda
        healthcheck_role = iam.Role(
            self,
            "HealthcheckLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "SageMakerInvokePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["sagemaker:InvokeEndpoint"],
                            resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/{self.endpoint_name}"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["cloudwatch:PutMetricData"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Healthcheck Lambda function
        healthcheck_lambda = _lambda.Function(
            self,
            "HealthcheckLambda",
            function_name=f"{self.endpoint_name}-healthcheck",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            role=healthcheck_role,
            timeout=Duration.seconds(30),
            environment={
                "ENDPOINT_NAME": self.endpoint_name,
                "ENVIRONMENT": self.environment_name,
                "MODEL_TYPE": self.monitoring_config.get('MODEL_TYPE', 'default')
            },
            code=_lambda.Code.from_inline(f"""
import json
import boto3
import time
import os
from datetime import datetime

# Healthcheck payloads by model type
HEALTHCHECK_PAYLOADS = {HEALTHCHECK_PAYLOADS}

def lambda_handler(event, context):
    endpoint_name = os.environ['ENDPOINT_NAME']
    environment = os.environ['ENVIRONMENT']
    model_type = os.environ.get('MODEL_TYPE', 'default')
    
    sagemaker_runtime = boto3.client('sagemaker-runtime')
    cloudwatch = boto3.client('cloudwatch')
    
    # Get appropriate payload for model type
    sample_payload = HEALTHCHECK_PAYLOADS.get(model_type, HEALTHCHECK_PAYLOADS['default'])
    
    try:
        start_time = time.time()
        
        # Invoke endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps(sample_payload)
        )
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Check if response is valid
        result = json.loads(response['Body'].read().decode())
        
        # Publish custom metrics
        cloudwatch.put_metric_data(
            Namespace='SageMaker/HealthCheck',
            MetricData=[
                {{
                    'MetricName': 'HealthCheckLatency',
                    'Dimensions': [
                        {{'Name': 'EndpointName', 'Value': endpoint_name}},
                        {{'Name': 'Environment', 'Value': environment}}
                    ],
                    'Value': latency,
                    'Unit': 'Milliseconds',
                    'Timestamp': datetime.utcnow()
                }},
                {{
                    'MetricName': 'HealthCheckSuccess',
                    'Dimensions': [
                        {{'Name': 'EndpointName', 'Value': endpoint_name}},
                        {{'Name': 'Environment', 'Value': environment}}
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }}
            ]
        )
        
        return {{
            'statusCode': 200,
            'body': json.dumps({{
                'status': 'healthy',
                'latency_ms': latency,
                'endpoint': endpoint_name,
                'model_type': model_type,
                'timestamp': datetime.utcnow().isoformat()
            }})
        }}
        
    except Exception as e:
        # Publish failure metric
        cloudwatch.put_metric_data(
            Namespace='SageMaker/HealthCheck',
            MetricData=[
                {{
                    'MetricName': 'HealthCheckSuccess',
                    'Dimensions': [
                        {{'Name': 'EndpointName', 'Value': endpoint_name}},
                        {{'Name': 'Environment', 'Value': environment}}
                    ],
                    'Value': 0,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }}
            ]
        )
        
        return {{
            'statusCode': 500,
            'body': json.dumps({{
                'status': 'unhealthy',
                'error': str(e),
                'endpoint': endpoint_name,
                'model_type': model_type,
                'timestamp': datetime.utcnow().isoformat()
            }})
        }}
""")
        )
        
        # Schedule healthcheck based on environment
        healthcheck_rule = events.Rule(
            self,
            "HealthcheckSchedule",
            rule_name=f"{self.endpoint_name}-healthcheck-schedule",
            schedule=events.Schedule.rate(Duration.minutes(schedule_minutes)),
            description=f"Scheduled healthcheck for SageMaker endpoint (every {schedule_minutes} min)"
        )
        healthcheck_rule.add_target(targets.LambdaFunction(healthcheck_lambda))
        
        # Create alarm for healthcheck failures
        healthcheck_alarm = cloudwatch.Alarm(
            self,
            "HealthcheckFailureAlarm",
            alarm_name=f"{self.endpoint_name}-healthcheck-failure",
            alarm_description="SageMaker endpoint healthcheck failures",
            metric=cloudwatch.Metric(
                namespace="SageMaker/HealthCheck",
                metric_name="HealthCheckSuccess",
                dimensions_map={
                    "EndpointName": self.endpoint_name,
                    "Environment": self.environment_name
                },
                statistic="Average",
                period=Duration.minutes(10)
            ),
            threshold=thresholds["healthcheck_success_rate"],
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING
        )
        healthcheck_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
        
        return healthcheck_lambda
