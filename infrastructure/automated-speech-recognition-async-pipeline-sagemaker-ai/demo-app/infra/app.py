#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.backend_stack import BackendStack
from infra.frontend_stack import FrontendStack
import json

# Load config file
with open("./configs/configs.json", "r") as f:
    configs = json.load(f)

app = cdk.App()
BackendStack(app, "VoiceDemoBackend",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=configs.get('region', os.environ.get("CDK_DEFAULT_REGION"))),
    configs=configs
)

FrontendStack(app, "VoiceDemoFrontend",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=configs.get('region', os.environ.get("CDK_DEFAULT_REGION"))),
    configs=configs
)

app.synth()
