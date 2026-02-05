"""
Model Quality Monitoring Stack for drift detection
"""
from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_s3 as s3,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    RemovalPolicy
)
from constructs import Construct
from dataclasses import dataclass
from pathlib import Path
from yamldataclassconfig import create_file_path_field
from config.config_mux import StageYamlDataClassConfig


@dataclass
class MonitoringConfig(StageYamlDataClassConfig):
    """Model monitoring configuration from YAML"""
    enable_data_capture: bool = True
    data_capture_percentage: int = 100
    drift_threshold: float = 0.1
    baseline_job_name_prefix: str = "baseline-job"
    monitoring_job_name_prefix: str = "model-quality-job"
    schedule_expression: str = "cron(0 */6 * * ? *)"
    instance_count: int = 1
    instance_type: str = "ml.m5.xlarge"
    max_runtime_seconds: int = 3600

    FILE_PATH: Path = create_file_path_field(
        "monitoring-config.yml", path_is_absolute=True
    )


class ModelQualityMonitorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, endpoint_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.endpoint_name = endpoint_name
        self.config = MonitoringConfig()
        self.config.load_for_stack(self)
        self.environment_name = construct_id.split('-')[1]  # Extract the project ID part
        
        # Create S3 bucket for monitoring artifacts
        self.monitoring_bucket = self.create_monitoring_bucket()
        
        # Create IAM role for monitoring jobs
        self.monitoring_role = self.create_monitoring_role()
        
        # Enable data capture on endpoint
        self.enable_data_capture()
        
        # Create baseline job
        self.create_baseline_job()
        
        # Create monitoring schedule
        self.create_monitoring_schedule()
        
        # Create drift detection alarms
        self.create_drift_alarms()
        
        # Create monitoring Lambda for custom metrics
        self.create_monitoring_lambda()
    
    def create_monitoring_bucket(self):
        """Create S3 bucket for model monitoring artifacts"""
        bucket = s3.Bucket(
            self,
            "ModelMonitoringBucket",
            bucket_name=f"sagemaker-model-monitor-{self.account}-{self.region}-{self.environment_name}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldMonitoringData",
                    enabled=True,
                    expiration=Duration.days(90),  # Keep monitoring data for 90 days
                    noncurrent_version_expiration=Duration.days(30)
                )
            ]
        )
        
        return bucket
    
    def create_monitoring_role(self):
        """Create IAM role for SageMaker Model Monitor"""
        role = iam.Role(
            self,
            "ModelMonitoringRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ],
            inline_policies={
                "ModelMonitoringPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                self.monitoring_bucket.bucket_arn,
                                f"{self.monitoring_bucket.bucket_arn}/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "cloudwatch:PutMetricData",
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sagemaker:DescribeEndpoint",
                                "sagemaker:DescribeEndpointConfig",
                                "sagemaker:DescribeModel"
                            ],
                            resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:*"]
                        )
                    ]
                )
            }
        )
        
        return role
    
    def enable_data_capture(self):
        """Enable data capture on the SageMaker endpoint"""
        # Note: This would typically be done during endpoint creation
        # For existing endpoints, you'd need to update the endpoint config
        
        data_capture_config = {
            "EnableCapture": True,
            "InitialSamplingPercentage": self.config.data_capture_percentage,
            "DestinationS3Uri": f"s3://{self.monitoring_bucket.bucket_name}/data-capture",
            "CaptureOptions": [
                {"CaptureMode": "Input"},
                {"CaptureMode": "Output"}
            ],
            "CaptureContentTypeHeader": {
                "CsvContentTypes": ["text/csv"],
                "JsonContentTypes": ["application/json"]
            }
        }
        
        # Store config for reference (actual implementation would update endpoint)
        self.data_capture_config = data_capture_config
    
    def create_baseline_job(self):
        """Create baseline processing job for model monitoring"""
        baseline_job = sagemaker.CfnDataQualityJobDefinition(
            self,
            "BaselineJob",
            job_definition_name=f"{self.config.baseline_job_name_prefix}-{self.endpoint_name}",
            data_quality_app_specification=sagemaker.CfnDataQualityJobDefinition.DataQualityAppSpecificationProperty(
                image_uri=f"159807026194.dkr.ecr.{self.region}.amazonaws.com/sagemaker-model-monitor-analyzer"
            ),
            data_quality_job_input=sagemaker.CfnDataQualityJobDefinition.DataQualityJobInputProperty(
                endpoint_input=sagemaker.CfnDataQualityJobDefinition.EndpointInputProperty(
                    endpoint_name=self.endpoint_name,
                    local_path="/opt/ml/processing/input/endpoint"
                )
            ),
            data_quality_job_output_config=sagemaker.CfnDataQualityJobDefinition.MonitoringOutputConfigProperty(
                monitoring_outputs=[
                    sagemaker.CfnDataQualityJobDefinition.MonitoringOutputProperty(
                        s3_output=sagemaker.CfnDataQualityJobDefinition.S3OutputProperty(
                            s3_uri=f"s3://{self.monitoring_bucket.bucket_name}/baseline/constraints",
                            local_path="/opt/ml/processing/output"
                        )
                    )
                ]
            ),
            job_resources=sagemaker.CfnDataQualityJobDefinition.MonitoringResourcesProperty(
                cluster_config=sagemaker.CfnDataQualityJobDefinition.ClusterConfigProperty(
                    instance_count=self.config.instance_count,
                    instance_type=self.config.instance_type,
                    volume_size_in_gb=30
                )
            ),
            role_arn=self.monitoring_role.role_arn,
            stopping_condition=sagemaker.CfnDataQualityJobDefinition.StoppingConditionProperty(
                max_runtime_in_seconds=self.config.max_runtime_seconds
            )
        )
        
        return baseline_job
    
    def create_monitoring_schedule(self):
        """Create monitoring schedule for continuous drift detection"""
        monitoring_schedule = sagemaker.CfnMonitoringSchedule(
            self,
            "ModelQualityMonitoringSchedule",
            monitoring_schedule_name=f"{self.config.monitoring_job_name_prefix}-{self.endpoint_name}",
            monitoring_schedule_config=sagemaker.CfnMonitoringSchedule.MonitoringScheduleConfigProperty(
                schedule_config=sagemaker.CfnMonitoringSchedule.ScheduleConfigProperty(
                    schedule_expression=self.config.schedule_expression
                ),
                monitoring_job_definition=sagemaker.CfnMonitoringSchedule.MonitoringJobDefinitionProperty(
                    monitoring_app_specification=sagemaker.CfnMonitoringSchedule.MonitoringAppSpecificationProperty(
                        image_uri=f"159807026194.dkr.ecr.{self.region}.amazonaws.com/sagemaker-model-monitor-analyzer"
                    ),
                    monitoring_inputs=[
                        sagemaker.CfnMonitoringSchedule.MonitoringInputProperty(
                            endpoint_input=sagemaker.CfnMonitoringSchedule.EndpointInputProperty(
                                endpoint_name=self.endpoint_name,
                                local_path="/opt/ml/processing/input/endpoint"
                            )
                        )
                    ],
                    monitoring_output_config=sagemaker.CfnMonitoringSchedule.MonitoringOutputConfigProperty(
                        monitoring_outputs=[
                            sagemaker.CfnMonitoringSchedule.MonitoringOutputProperty(
                                s3_output=sagemaker.CfnMonitoringSchedule.S3OutputProperty(
                                    s3_uri=f"s3://{self.monitoring_bucket.bucket_name}/model-monitor-reports",
                                    local_path="/opt/ml/processing/output"
                                )
                            )
                        ]
                    ),
                    monitoring_resources=sagemaker.CfnMonitoringSchedule.MonitoringResourcesProperty(
                        cluster_config=sagemaker.CfnMonitoringSchedule.ClusterConfigProperty(
                            instance_count=self.config.instance_count,
                            instance_type=self.config.instance_type,
                            volume_size_in_gb=30
                        )
                    ),
                    role_arn=self.monitoring_role.role_arn,
                    stopping_condition=sagemaker.CfnMonitoringSchedule.StoppingConditionProperty(
                        max_runtime_in_seconds=self.config.max_runtime_seconds
                    ),
                    baseline_config=sagemaker.CfnMonitoringSchedule.BaselineConfigProperty(
                        constraints_resource=sagemaker.CfnMonitoringSchedule.ConstraintsResourceProperty(
                            s3_uri=f"s3://{self.monitoring_bucket.bucket_name}/baseline/constraints/constraints.json"
                        ),
                        statistics_resource=sagemaker.CfnMonitoringSchedule.StatisticsResourceProperty(
                            s3_uri=f"s3://{self.monitoring_bucket.bucket_name}/baseline/statistics/statistics.json"
                        )
                    )
                )
            )
        )
        
        return monitoring_schedule
    
    def create_drift_alarms(self):
        """Create CloudWatch alarms for drift detection"""
        # Get SNS topic from monitoring stack
        alarm_topic = sns.Topic.from_topic_arn(
            self,
            "ImportedAlarmTopic",
            f"arn:aws:sns:{self.region}:{self.account}:{self.environment_name}-sagemaker-alarms"
        )
        
        # Data Quality Drift Alarm
        data_drift_alarm = cloudwatch.Alarm(
            self,
            "DataQualityDriftAlarm",
            alarm_name=f"{self.endpoint_name}-data-quality-drift",
            alarm_description="Data quality drift detected in model monitoring",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker/ModelMonitor",
                metric_name="DataQualityViolations",
                dimensions_map={
                    "EndpointName": self.endpoint_name,
                    "MonitoringSchedule": f"{self.config.monitoring_job_name_prefix}-{self.endpoint_name}"
                },
                statistic="Sum",
                period=Duration.hours(1)
            ),
            threshold=1,  # Any violations trigger alarm
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        data_drift_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
        
        # Model Quality Drift Alarm
        model_drift_alarm = cloudwatch.Alarm(
            self,
            "ModelQualityDriftAlarm", 
            alarm_name=f"{self.endpoint_name}-model-quality-drift",
            alarm_description="Model quality drift detected in monitoring",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker/ModelMonitor",
                metric_name="ModelQualityViolations",
                dimensions_map={
                    "EndpointName": self.endpoint_name,
                    "MonitoringSchedule": f"{self.config.monitoring_job_name_prefix}-{self.endpoint_name}"
                },
                statistic="Sum",
                period=Duration.hours(1)
            ),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        model_drift_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))
    
    def create_monitoring_lambda(self):
        """Create Lambda function for custom monitoring metrics"""
        monitoring_lambda = _lambda.Function(
            self,
            "ModelMonitoringLambda",
            function_name=f"{self.endpoint_name}-model-monitor",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            timeout=Duration.minutes(5),
            environment={
                "ENDPOINT_NAME": self.endpoint_name,
                "MONITORING_BUCKET": self.monitoring_bucket.bucket_name,
                "ENVIRONMENT": self.environment_name
            },
            role=iam.Role(
                self,
                "MonitoringLambdaRole",
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
                ],
                inline_policies={
                    "MonitoringPolicy": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "s3:GetObject",
                                    "s3:ListBucket",
                                    "cloudwatch:PutMetricData",
                                    "sagemaker:DescribeMonitoringSchedule",
                                    "sagemaker:ListMonitoringExecutions"
                                ],
                                resources=["*"]
                            )
                        ]
                    )
                }
            ),
            code=_lambda.Code.from_inline(f"""
import json
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    endpoint_name = os.environ['ENDPOINT_NAME']
    bucket_name = os.environ['MONITORING_BUCKET']
    environment = os.environ['ENVIRONMENT']
    
    s3 = boto3.client('s3')
    cloudwatch = boto3.client('cloudwatch')
    sagemaker = boto3.client('sagemaker')
    
    try:
        # Check for recent monitoring violations
        monitoring_schedule = f"{{os.environ['ENDPOINT_NAME'].replace('endpoint', 'quality-monitor')}}"
        
        # List recent monitoring executions
        response = sagemaker.list_monitoring_executions(
            MonitoringScheduleName=monitoring_schedule,
            MaxResults=5,
            SortBy='CreationTime',
            SortOrder='Descending'
        )
        
        violations_count = 0
        latest_execution_status = 'Unknown'
        
        if response['MonitoringExecutionSummaries']:
            latest_execution = response['MonitoringExecutionSummaries'][0]
            latest_execution_status = latest_execution['MonitoringExecutionStatus']
            
            # Check for violations in S3
            try:
                violations_key = f"model-monitor-reports/violations.json"
                violations_obj = s3.get_object(Bucket=bucket_name, Key=violations_key)
                violations_data = json.loads(violations_obj['Body'].read())
                violations_count = len(violations_data.get('violations', []))
            except:
                violations_count = 0
        
        # Publish custom metrics
        cloudwatch.put_metric_data(
            Namespace='SageMaker/ModelMonitor/Custom',
            MetricData=[
                {{
                    'MetricName': 'MonitoringExecutionStatus',
                    'Dimensions': [
                        {{'Name': 'EndpointName', 'Value': endpoint_name}},
                        {{'Name': 'Environment', 'Value': environment}}
                    ],
                    'Value': 1 if latest_execution_status == 'Completed' else 0,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }},
                {{
                    'MetricName': 'ViolationsDetected',
                    'Dimensions': [
                        {{'Name': 'EndpointName', 'Value': endpoint_name}},
                        {{'Name': 'Environment', 'Value': environment}}
                    ],
                    'Value': violations_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }}
            ]
        )
        
        return {{
            'statusCode': 200,
            'body': json.dumps({{
                'endpoint': endpoint_name,
                'violations_count': violations_count,
                'execution_status': latest_execution_status,
                'timestamp': datetime.utcnow().isoformat()
            }})
        }}
        
    except Exception as e:
        print(f"Error in monitoring Lambda: {{str(e)}}")
        return {{
            'statusCode': 500,
            'body': json.dumps({{'error': str(e)}})
        }}
""")
        )
        
        # Schedule Lambda to run every hour
        monitoring_rule = events.Rule(
            self,
            "ModelMonitoringSchedule",
            rule_name=f"{self.endpoint_name[:40]}-monitor-schedule",
            schedule=events.Schedule.rate(Duration.hours(1)),
            description="Check model monitoring status and publish custom metrics"
        )
        monitoring_rule.add_target(targets.LambdaFunction(monitoring_lambda))
        
        return monitoring_lambda
