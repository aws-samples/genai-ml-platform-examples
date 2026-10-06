# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Resolve the container environment for the bank-marketing endpoint.

The model artifact registered by the build pipeline carries a custom inference
handler at ``code/inference.py``. Two mechanisms have to be switched on for it to
actually serve:

1.  SCRIPT MODE. ``SAGEMAKER_PROGRAM`` and ``SAGEMAKER_SUBMIT_DIRECTORY`` tell the
    stock XGBoost container to run our handler. WITHOUT THEM the container
    silently ignores ``code/inference.py`` and serves a bare CSV of
    probabilities -- a wrong response shape and no inference capture, with no
    error anywhere to explain it.

2.  INFERENCE CAPTURE. The handler publishes one message per prediction to the
    SQS queue provisioned by ``templates/4-inference-capture.yaml``, which a
    Lambda drains into the Iceberg ``inference_responses`` table that Lab 5
    analyses. The handler discovers nothing on its own: every value arrives as a
    container environment variable.

``FEATURE_NAMES`` is read out of the model package's own ``baseline.json``
rather than from a vendored copy of the dataset schema. That is deliberate: it
cannot drift from the artifact being deployed, because it came from it.

Everything here degrades rather than fails. If the queue is missing or the
baseline is unreadable, the endpoint still deploys and serves predictions --
capture is simply disabled, which is recoverable, whereas a failed deployment
blocks the lab.
"""

import json
from urllib.parse import urlparse

import boto3

# Matches the Lab 3A notebook so both endpoints behave identically.
SCRIPT_MODE_ENV = {
    "SAGEMAKER_PROGRAM": "inference.py",
    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
}

CAPTURE_QUEUE_SUFFIX = "-inference-capture"


def resolve_project_name(explicit_name, data_bucket, account, region):
    """Return the workshop ProjectName that prefixes the capture queue.

    Prefers an explicit value from deploy_config.json. Otherwise derives it from
    the data bucket, which the workshop names
    ``{ProjectName}-data-{account}-{region}`` -- the same derivation Lab 3A uses.
    """
    if explicit_name:
        return explicit_name
    if not data_bucket:
        return ""
    return data_bucket.replace(f"-data-{account}-{region}", "")


def resolve_capture_queue(project_name, region):
    """Look up the capture queue. Returns (queue_url, queue_arn), ('', '') if absent."""
    if not project_name:
        print("Inference capture: no project name resolved, cannot locate the queue.")
        return "", ""

    queue_name = f"{project_name}{CAPTURE_QUEUE_SUFFIX}"
    sqs = boto3.client("sqs", region_name=region)
    try:
        queue_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    except Exception as e:  # QueueDoesNotExist, AccessDenied, ...
        print(
            f"Inference capture: queue '{queue_name}' not resolved ({type(e).__name__}). "
            "The endpoint will deploy with capture DISABLED. Deploy the "
            "4-inference-capture stack, or set project_name in deploy_config.json."
        )
        return "", ""

    try:
        queue_arn = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )["Attributes"]["QueueArn"]
    except Exception as e:
        print(f"Inference capture: could not read the queue ARN ({type(e).__name__}).")
        return queue_url, ""

    print(f"Inference capture: resolved {queue_url}")
    return queue_url, queue_arn


def load_baseline_for_package(model_package_arn, region):
    """Return the baseline.json attached to a model package, or {}.

    Follows the same chain Lab 5 uses:
      describe_model_package -> ModelMetrics.ModelQuality.Statistics.S3Uri
    """
    try:
        sm = boto3.client("sagemaker", region_name=region)
        package = sm.describe_model_package(ModelPackageName=model_package_arn)
    except Exception as e:
        print(f"Could not describe model package ({type(e).__name__}: {e})")
        return {}

    metrics = package.get("ModelMetrics", {})
    s3_uri = (
        metrics.get("ModelQuality", {}).get("Statistics", {}).get("S3Uri")
        or metrics.get("ModelStatistics", {}).get("S3Uri")
        or package.get("CustomerMetadataProperties", {}).get("baseline_s3_uri")
    )
    if not s3_uri:
        print(
            f"Model package {model_package_arn} carries no baseline pointer. "
            "FEATURE_NAMES will be omitted; the handler will fall back to the "
            "feature_names.json baked into the artifact."
        )
        return {}

    try:
        parsed = urlparse(s3_uri)
        body = boto3.client("s3", region_name=region).get_object(
            Bucket=parsed.netloc, Key=parsed.path.lstrip("/")
        )["Body"].read()
        baseline = json.loads(body)
        print(f"Loaded baseline.json from {s3_uri}")
        return baseline
    except Exception as e:
        print(f"Could not read {s3_uri} ({type(e).__name__}: {e})")
        return {}


def model_package_version(model_package_arn, region):
    """Return the registry version of a model package as a string, or ''."""
    try:
        sm = boto3.client("sagemaker", region_name=region)
        version = sm.describe_model_package(
            ModelPackageName=model_package_arn).get("ModelPackageVersion")
        return str(version) if version is not None else ""
    except Exception as e:
        print(f"Could not resolve the model package version ({type(e).__name__}).")
        return ""


def build_container_environment(
    endpoint_name,
    region,
    model_package_arn,
    data_bucket,
    account,
    explicit_project_name="",
    enable_capture=True,
):
    """Build the endpoint container environment.

    Returns (environment_dict, queue_arn). queue_arn is '' when capture is off,
    which is the caller's signal not to attach the SQS IAM statement.
    """
    environment = dict(SCRIPT_MODE_ENV)
    # boto3-created models do not get SAGEMAKER_REGION injected the way the SDK's
    # .deploy() does, so set both explicitly.
    environment["SAGEMAKER_REGION"] = region
    environment["AWS_REGION"] = region
    environment["ENDPOINT_NAME"] = endpoint_name

    if not enable_capture:
        print("Inference capture: disabled by deploy_config.json.")
        environment["ENABLE_INFERENCE_CAPTURE"] = "false"
        return environment, ""

    project_name = resolve_project_name(explicit_project_name, data_bucket, account, region)
    queue_url, queue_arn = resolve_capture_queue(project_name, region)

    baseline = load_baseline_for_package(model_package_arn, region)
    feature_schema = baseline.get("feature_schema") or []
    if feature_schema:
        # Lets the handler name the columns of a positional text/csv request, so
        # captured rows carry named features that match the training baseline.
        environment["FEATURE_NAMES"] = ",".join(feature_schema)

    mlflow_run_id = baseline.get("mlflow_run_id")
    if mlflow_run_id:
        environment["MLFLOW_RUN_ID"] = mlflow_run_id

    version = model_package_version(model_package_arn, region)
    if version:
        # Matches Lab 3A's 'v<version>' so captured predictions from either path
        # join back to the model package that owns the baseline.
        environment["MODEL_VERSION"] = f"v{version}"

    environment["ENABLE_INFERENCE_CAPTURE"] = "true" if queue_url else "false"
    if queue_url:
        environment["SQS_QUEUE_URL"] = queue_url

    print("Container environment:")
    for key in sorted(environment):
        print(f"  {key} = {environment[key]}")

    return environment, queue_arn
