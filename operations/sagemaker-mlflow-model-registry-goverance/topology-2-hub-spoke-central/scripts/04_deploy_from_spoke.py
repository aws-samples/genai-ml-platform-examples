"""Step 4 — Spoke deploys the shared, approved model.

Using spoke credentials, deploy the hub-owned Model Package (shared back via AWS
RAM with the AllowDeploy permission) to a real-time endpoint in the spoke, and
invoke it. The Model references the hub Model Package by ARN; SageMaker resolves
the container image and model data from the package's inference specification.

Cross-account artifact access — the piece the RAM share does NOT cover:
  The model artifacts live in the HUB's S3 artifact store. For the spoke
  endpoint to pull them, access is required on BOTH sides:
    * Resource side: the hub bucket policy grants the spoke account s3:GetObject
      (applied in Step 1).
    * Identity side: the spoke execution role needs s3:GetObject on the hub
      bucket. AmazonSageMakerFullAccess grants S3 access to buckets whose name
      contains "sagemaker", which covers sagemaker-<region>-<hub-account>. If you
      scope the spoke role more tightly, add the hub bucket explicitly.

Cost note: creates an ml.m5.xlarge endpoint. Run Step 5 to tear it down.

Run:
    python scripts/04_deploy_from_spoke.py
"""

from __future__ import annotations

import json
import os
import time

# The SDK v3 typed-resource control-plane client builds its own botocore session
# and resolves credentials from the ambient environment (the session= argument
# only reaches the runtime/metrics clients). Every Step 4 operation runs in the
# spoke, so force the spoke profile before importing the SDK — mirroring how
# steps 02/03 set AWS_PROFILE for their MLflow clients.
os.environ["AWS_PROFILE"] = os.environ.get("SPOKE_PROFILE", "").strip()

import boto3
from sagemaker.core.resources import Endpoint, EndpointConfig, Model
from sagemaker.core.shapes import ContainerDefinition, ProductionVariant

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 4: deploy from the spoke")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01-03 first.")

sm_arn = state["model_package_arn"]

# All SDK v3 resource calls in this step run with SPOKE credentials. The SDK v3
# typed resources take a boto3 session directly (session param is a boto3
# Session), so pass spoke_boto rather than a sagemaker helper Session wrapper.
spoke_boto = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
spoke_sm = spoke_boto.client("sagemaker")
sm_session = spoke_boto


def main() -> None:
    # Governance gate: the spoke only deploys an Approved package. The spoke can
    # read the hub package's approval status through the RAM share (by full ARN).
    detail = spoke_sm.describe_model_package(ModelPackageName=sm_arn)
    approval = detail.get("ModelApprovalStatus")
    if approval != "Approved":
        raise SystemExit(
            f"Model Package approval status is '{approval}', not 'Approved'. "
            "Run 03_govern_in_hub.py to approve it in the hub first."
        )
    print(f"Shared Model Package is Approved: {sm_arn}")

    suffix = time.strftime("%Y%m%d-%H%M%S")
    resource_name = f"{cfg.model_name}-{suffix}"

    Model.create(
        model_name=resource_name,
        primary_container=ContainerDefinition(model_package_name=sm_arn),
        execution_role_arn=cfg.spoke_execution_role,
        session=sm_session,
    )
    print(f"Created model:           {resource_name}")

    EndpointConfig.create(
        endpoint_config_name=resource_name,
        production_variants=[
            ProductionVariant(
                variant_name="AllTraffic",
                model_name=resource_name,
                initial_instance_count=1,
                instance_type="ml.m5.xlarge",
            )
        ],
        session=sm_session,
    )
    print(f"Created endpoint config: {resource_name}")

    endpoint = Endpoint.create(
        endpoint_name=resource_name,
        endpoint_config_name=resource_name,
        session=sm_session,
    )
    print(f"Creating endpoint {resource_name} in the spoke (a few minutes)...")
    endpoint.wait_for_status("InService")
    print("Endpoint is InService.")

    response = endpoint.invoke(
        body="0.5,-1.2,0.3,0.8\n1.1,0.4,-0.7,0.2",
        content_type="text/csv",
        accept="application/json",
    )
    print("Prediction:", response.body.read().decode())

    state["endpoint_name"] = resource_name
    state["model_name_resource"] = resource_name
    state["endpoint_config_name"] = resource_name
    json.dump(state, open(STATE_FILE, "w"))
    print(f"\nSaved endpoint name to {STATE_FILE}")
    print("Next: python scripts/05_cleanup.py")


if __name__ == "__main__":
    main()
