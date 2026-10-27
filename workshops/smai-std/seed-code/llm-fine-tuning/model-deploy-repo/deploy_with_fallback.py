"""Deploy the latest approved model package to a SageMaker endpoint, falling
back across GPU instance types when a type has no capacity.

This is a boto3 port of the deploy_with_fallback() helper from Lab 3b.
InsufficientInstanceCapacity means AWS has no free instances of that type in
the Region right now; it is not a configuration problem. Instead of waiting on
one type, the script walks the ordered list in deploy-config.json and moves to
the next type on a capacity error. Any other error (including a
ResourceLimitExceeded quota error) stops the deploy, as in Lab 3b.

Run by buildspec.yml in the ModelDeploy CodeBuild project. Required env vars
(set by the SageMaker Project template):
  SOURCE_MODEL_PACKAGE_GROUP_NAME, SAGEMAKER_PROJECT_NAME,
  SAGEMAKER_PROJECT_ID, MODEL_EXECUTION_ROLE_ARN

On success it writes deploy-output.json and exits 0.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

CONFIG_FILE = "deploy-config.json"
OUTPUT_FILE = "deploy-output.json"

# States in which SageMaker is still working on the endpoint.
TRANSITIONAL = ("Creating", "Updating", "SystemUpdating", "RollingBack", "Deleting")


def truncate_name(name, max_length=63):
    """Truncate a name to the SageMaker 63-character limit.

    Ensures the name ends with an alphanumeric character (not a hyphen).
    """
    if len(name) <= max_length:
        return name
    truncated = name[:max_length]
    # Remove trailing hyphens to satisfy SageMaker naming constraints
    truncated = truncated.rstrip('-')
    print(f"Truncated name from {len(name)} to {len(truncated)} chars: {truncated}")
    return truncated


def unique_name(prefix, suffix, max_length=63):
    """Truncate the prefix, never the suffix, so per-attempt names stay unique."""
    room = max_length - len(suffix)
    return prefix[:room].rstrip('-') + suffix


def is_capacity_error(text):
    """Same match as Lab 3b's _is_capacity_error."""
    t = (text or "").lower()
    return ("insufficientinstancecapacity" in t
            or "provision requested ml compute capacity" in t)


def load_config(path=CONFIG_FILE):
    with open(path) as f:
        cfg = json.load(f)
    types = cfg.get("EndpointInstanceTypes") or []
    if not types:
        raise ValueError(f"{path}: EndpointInstanceTypes must list at least one instance type")
    return {
        "EndpointInstanceTypes": types,
        "EndpointInstanceCount": int(cfg.get("EndpointInstanceCount", 1)),
        "Rounds": int(cfg.get("Rounds", 1)),
        "WaitBetweenRoundsSeconds": int(cfg.get("WaitBetweenRoundsSeconds", 60)),
        "PollSeconds": int(cfg.get("PollSeconds", 30)),
    }


def get_primary_container(sm, model_package_group_name):
    """Pick the latest Approved package and build the model's primary container."""
    response = sm.list_model_packages(
        ModelPackageGroupName=model_package_group_name,
        ModelApprovalStatus='Approved',
        SortBy='CreationTime',
        SortOrder='Descending',
        MaxResults=1
    )
    if not response['ModelPackageSummaryList']:
        raise Exception(f"No approved model packages found in {model_package_group_name}")

    model_package_arn = response['ModelPackageSummaryList'][0]['ModelPackageArn']
    print(f"Latest approved model: {model_package_arn}")

    model_package = sm.describe_model_package(ModelPackageName=model_package_arn)

    # Extract container image and model data
    container = model_package['InferenceSpecification']['Containers'][0]
    image_uri = container['Image']

    # Handle both ModelDataUrl (tar.gz) and ModelDataSource (directory)
    model_data_url = container.get('ModelDataUrl', '')
    model_data_source = container.get('ModelDataSource', {})

    print(f"Image URI: {image_uri}")
    print(f"Model Data URL: {model_data_url}")
    print(f"Model Data Source: {model_data_source}")

    primary_container = {"Image": image_uri}

    # Add model data - prefer ModelDataUrl if available
    if model_data_url:
        primary_container["ModelDataUrl"] = model_data_url
    elif model_data_source:
        primary_container["ModelDataSource"] = model_data_source
    else:
        raise Exception("No model data found in container specification")

    # Add environment variables if present (important for Meta models)
    primary_container["Environment"] = dict(container.get('Environment', {}))

    # Set max_model_len to avoid OOM on KV cache allocation
    # The model defaults to 131072 seq len which exceeds GPU memory on 24 GB GPUs
    primary_container["Environment"]["OPTION_MAX_MODEL_LEN"] = "8192"
    primary_container["Environment"]["OPTION_GPU_MEMORY_UTILIZATION"] = "0.95"

    return model_package_arn, primary_container


def describe_or_none(sm, endpoint_name):
    try:
        return sm.describe_endpoint(EndpointName=endpoint_name)
    except ClientError as e:
        if "could not find" in str(e).lower():
            return None
        raise


def wait_until_settled(sm, endpoint_name, poll_seconds):
    """Poll until the endpoint leaves a transitional state. Returns the last
    describe_endpoint response, or None if the endpoint no longer exists."""
    while True:
        desc = describe_or_none(sm, endpoint_name)
        if desc is None or desc["EndpointStatus"] not in TRANSITIONAL:
            return desc
        print(f"  ... {endpoint_name} is {desc['EndpointStatus']}")
        time.sleep(poll_seconds)


def delete_endpoint_and_wait(sm, endpoint_name, poll_seconds):
    print(f"  deleting endpoint {endpoint_name}")
    try:
        sm.delete_endpoint(EndpointName=endpoint_name)
    except ClientError as e:
        if "could not find" not in str(e).lower():
            raise
    while describe_or_none(sm, endpoint_name) is not None:
        time.sleep(poll_seconds)
    print(f"  endpoint {endpoint_name} deleted")


def delete_quietly(fn, **kwargs):
    """Best-effort cleanup, like Lab 3b's _cleanup_endpoint."""
    try:
        fn(**kwargs)
    except Exception as e:  # noqa: BLE001 - cleanup must never mask the real outcome
        print(f"  (cleanup skipped: {str(e)[:150]})")


def cleanup_previous(sm, old_config_name, new_config_name, new_model_name):
    """After a successful update, delete the endpoint config and model the
    endpoint used before. CloudFormation did this when it owned the endpoint."""
    if not old_config_name or old_config_name == new_config_name:
        return
    try:
        old = sm.describe_endpoint_config(EndpointConfigName=old_config_name)
    except ClientError:
        old = {"ProductionVariants": []}
    delete_quietly(sm.delete_endpoint_config, EndpointConfigName=old_config_name)
    for variant in old.get("ProductionVariants", []):
        model = variant.get("ModelName")
        if model and model != new_model_name:
            delete_quietly(sm.delete_model, ModelName=model)


def deploy_with_fallback(sm, endpoint_name, model_name, config_prefix, cfg, tags):
    """Try each instance type in order, falling back on capacity errors.

    Returns (instance_type, endpoint_config_name) once the endpoint is
    InService on the new config. Raises RuntimeError on a non-capacity
    failure or when every type is exhausted.
    """
    instance_types = cfg["EndpointInstanceTypes"]
    rounds = cfg["Rounds"]
    poll = cfg["PollSeconds"]
    last = None
    attempt = 0

    for rnd in range(rounds):
        for it in instance_types:
            attempt += 1
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
            short_type = it.replace("ml.", "").replace(".", "-")
            config_name = unique_name(config_prefix, f"-{short_type}-{attempt}-{stamp}")
            print(f"[attempt] {it} -> {endpoint_name} (config {config_name})")

            sm.create_endpoint_config(
                EndpointConfigName=config_name,
                ProductionVariants=[{
                    "VariantName": "AllTraffic",
                    "ModelName": model_name,
                    "InstanceType": it,
                    "InitialInstanceCount": cfg["EndpointInstanceCount"],
                    "InitialVariantWeight": 1.0,
                }],
                Tags=tags,
            )

            # Wait out any in-flight change, and clear a Failed endpoint, so the
            # stable name can be reused.
            existing = wait_until_settled(sm, endpoint_name, poll)
            if existing is not None and existing["EndpointStatus"] == "Failed":
                print(f"  existing endpoint is Failed: {existing.get('FailureReason', '')[:150]}")
                delete_endpoint_and_wait(sm, endpoint_name, poll)
                existing = None
            previous_config = existing["EndpointConfigName"] if existing else None

            try:
                if existing:
                    print(f"  updating existing endpoint (currently on {previous_config})")
                    sm.update_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)
                else:
                    sm.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name, Tags=tags)
            except ClientError as e:
                last = str(e)
                if is_capacity_error(last):
                    print(f"  capacity error on {it}; trying next. {last[:150]}")
                    delete_quietly(sm.delete_endpoint_config, EndpointConfigName=config_name)
                    continue
                raise

            desc = wait_until_settled(sm, endpoint_name, poll)
            if desc is None:
                raise RuntimeError(f"Endpoint {endpoint_name} disappeared while deploying on {it}")
            status = desc["EndpointStatus"]
            if status == "InService" and desc.get("EndpointConfigName") == config_name:
                print(f"  [ok] InService on {it}: {endpoint_name}")
                cleanup_previous(sm, previous_config, config_name, model_name)
                return it, config_name

            # A failed create leaves the endpoint Failed. A failed update rolls
            # back: the endpoint is InService again, but on the old config.
            reason = desc.get("FailureReason", "")
            last = reason or status
            print(f"  {status} on {it} (config {desc.get('EndpointConfigName')}): {reason[:150]}")
            if not is_capacity_error(reason):
                raise RuntimeError(f"Deploy failed on {it} (non-capacity): {last}")
            if status == "Failed":
                delete_endpoint_and_wait(sm, endpoint_name, poll)
            delete_quietly(sm.delete_endpoint_config, EndpointConfigName=config_name)

        if rnd + 1 < rounds:
            wait = cfg["WaitBetweenRoundsSeconds"]
            print(f"[round {rnd + 1}] all types short on capacity; waiting {wait}s...")
            time.sleep(wait)

    raise RuntimeError(
        f"No capacity on any of {instance_types} after {rounds} round(s). Last: {last}")


def main():
    project_name = os.environ['SAGEMAKER_PROJECT_NAME']
    project_id = os.environ['SAGEMAKER_PROJECT_ID']
    model_package_group_name = os.environ['SOURCE_MODEL_PACKAGE_GROUP_NAME']
    model_execution_role = os.environ['MODEL_EXECUTION_ROLE_ARN']

    cfg = load_config()
    print(f"Model Package Group: {model_package_group_name}")
    print(f"Instance types, in order: {cfg['EndpointInstanceTypes']}")

    # Timestamp for unique resource names (format: YYYYMMDD-HHMMSS)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    print(f"Deployment timestamp: {timestamp}")

    tags = [
        {"Key": "sagemaker:project-name", "Value": project_name},
        {"Key": "sagemaker:project-id", "Value": project_id},
        {"Key": "sagemaker:deployment-timestamp", "Value": timestamp},
        {"Key": "sagemaker:deployment-stage", "Value": "prod"},
    ]

    sm = boto3.client('sagemaker')
    model_package_arn, primary_container = get_primary_container(sm, model_package_group_name)

    # The endpoint name is stable: test/buildspec.yml and the README look for it.
    endpoint_name = truncate_name(f"{project_name}-{project_id}")
    model_name = truncate_name(f"{project_name}-{project_id}-model-{timestamp}")

    # Create the model once; every attempt reuses it.
    sm.create_model(
        ModelName=model_name,
        PrimaryContainer=primary_container,
        ExecutionRoleArn=model_execution_role,
        Tags=tags,
    )
    print(f"✓ Created model {model_name}")

    instance_type, config_name = deploy_with_fallback(
        sm, endpoint_name, model_name, f"{project_name}-{project_id}-config", cfg, tags)

    output = {
        "EndpointName": endpoint_name,
        "InstanceType": instance_type,
        "EndpointConfigName": config_name,
        "ModelName": model_name,
        "ModelPackageArn": model_package_arn,
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"✓ Wrote {OUTPUT_FILE}: {json.dumps(output)}")
    print("✓ Deployment completed successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"✗ Deployment failed: {e}", file=sys.stderr)
        raise
