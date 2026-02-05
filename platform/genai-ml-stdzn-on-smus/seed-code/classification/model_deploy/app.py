# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from aws_cdk import App, Environment
from deploy_endpoint.deploy_endpoint_stack import DeployEndpointStack
from deploy_endpoint.cloudwatch_monitoring_stack import CloudWatchMonitoringStack
from deploy_endpoint.model_quality_monitor_stack import ModelQualityMonitorStack
from config.constants import (
    DEPLOY_ACCOUNT,
    DEFAULT_DEPLOYMENT_REGION,
    AMAZON_DATAZONE_SCOPENAME,
    AMAZON_DATAZONE_PROJECT
)


app = App()

dev_env = Environment(
    account=DEPLOY_ACCOUNT,
    region=DEFAULT_DEPLOYMENT_REGION
)

endpoint_stack = DeployEndpointStack(
    app, 
    f"sagemaker-{AMAZON_DATAZONE_PROJECT}", 
    env=dev_env
)

# Add CloudWatch monitoring stack
cloudwatch_stack = CloudWatchMonitoringStack(
    app,
    f"sagemaker-{AMAZON_DATAZONE_PROJECT}-cloudwatch-monitoring",
    endpoint_name=endpoint_stack.endpoint_name,
    monitoring_config={
        "MODEL_TYPE": "default",
        "monitoring_job_name_prefix": "model-quality-job",
        "schedule_expression": "cron(0 */6 * * ? *)",
        "instance_count": 1,
        "instance_type": "ml.m5.xlarge",
        "max_runtime_seconds": 3600
    },
    env=dev_env
)
cloudwatch_stack.add_dependency(endpoint_stack)

# Add Model Quality monitoring stack
model_quality_stack = ModelQualityMonitorStack(
    app,
    f"sagemaker-{AMAZON_DATAZONE_PROJECT}-model-quality-monitoring",
    endpoint_name=endpoint_stack.endpoint_name,
    env=dev_env
)
model_quality_stack.add_dependency(endpoint_stack)

app.synth()