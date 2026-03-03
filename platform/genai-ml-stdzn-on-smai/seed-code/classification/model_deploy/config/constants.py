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

import json
import os
from pathlib import Path

# Load configuration from JSON file
config_path = Path(__file__).parent / "deploy_config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

DEFAULT_DEPLOYMENT_REGION = config.get("aws_region")
DEPLOY_ACCOUNT = config.get("deploy_account")
MODEL_PACKAGE_GROUP_NAME = config.get("model_package_group_name")
ARTIFACT_BUCKET = config.get("DataBucketName")
MODEL_BUCKET_ARN = f"arn:aws:s3:::{ARTIFACT_BUCKET}" if ARTIFACT_BUCKET else ""
