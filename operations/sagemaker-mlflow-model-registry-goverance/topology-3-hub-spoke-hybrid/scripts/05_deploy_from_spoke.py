"""Step 5 — Deploy the approved model in the spoke.

In this hybrid topology the spoke owns the model end-to-end: it trained the
model, registered it in its OWN Model Registry, and approved it locally. So the
spoke also deploys it — entirely within its own account. The model artifacts
already live in the spoke's S3 artifact store, so there is NO cross-account
artifact access: the spoke reads its own bucket with its own execution role.

The hub copy (Steps 3-4) is a governance/audit record — a central inventory of
approved models with independent hub sign-off. It is deliberately NOT the
deployment source, which keeps the hub free of any runtime dependency on the
spoke (the isolation goal of this topology). Deployment is gated by the SPOKE's
own local approval (Step 2).

The script refuses to deploy a package that is not Approved in the spoke,
mirroring the local governance gate.

Cost note: creates an ml.m5.xlarge endpoint in the spoke. Run Step 6 to tear it
down.

Run:
    python scripts/05_deploy_from_spoke.py

Requires SPOKE_EXECUTION_ROLE (the spoke stack's SageMakerExecutionRoleArn
output).
"""

from __future__ import annotations

import json
import os
import time

# The SDK v3 typed-resource control-plane client builds its own botocore session
# and resolves credentials from the ambient environment (the session= argument
# only reaches the runtime/metrics clients). Every deploy operation here runs in
# the spoke, so force the spoke profile before importing the SDK — mirroring how
# the register/govern steps set AWS_PROFILE for their MLflow clients.
os.environ["AWS_PROFILE"] = os.environ.get("SPOKE_PROFILE", "").strip()

import boto3
from sagemaker.core.resources import Endpoint, EndpointConfig, Model
from sagemaker.core.shapes import ContainerDefinition, ProductionVariant

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 5: deploy from the spoke")

if not cfg.spoke_execution_role:
    raise SystemExit(
        "SPOKE_EXECUTION_ROLE is not set. Use the spoke stack's "
        "'SageMakerExecutionRoleArn' output:\n"
        "    export SPOKE_EXECUTION_ROLE=arn:aws:iam::<spoke>:role/<role-name>"
    )

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01-04 first.")

# Deploy the SPOKE's own approved package (not the hub copy). The artifacts it
# references are in the spoke's bucket, so no cross-account access is needed.
dev_pkg_arn = state.get("dev_pkg_arn")
if not dev_pkg_arn:
    raise SystemExit("No spoke package ARN in state. Run 02_register_in_spoke.py first.")

spoke_boto = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
spoke_sm = spoke_boto.client("sagemaker")
sm_session = spoke_boto


def main() -> None:
    # Governance gate: the spoke only deploys a package it approved locally.
    detail = spoke_sm.describe_model_package(ModelPackageName=dev_pkg_arn)
    approval = detail.get("ModelApprovalStatus")
    if approval != "Approved":
        raise SystemExit(
            f"Spoke Model Package approval status is '{approval}', not 'Approved'. "
            "Run 02_register_in_spoke.py to approve it locally first."
        )
    print(f"Spoke Model Package is Approved: {dev_pkg_arn}")

    suffix = time.strftime("%Y%m%d-%H%M%S")
    resource_name = f"{cfg.model_name}-spoke-{suffix}"

    Model.create(
        model_name=resource_name,
        primary_container=ContainerDefinition(model_package_name=dev_pkg_arn),
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

    state["spoke_endpoint_name"] = resource_name
    state["spoke_model_name_resource"] = resource_name
    state["spoke_endpoint_config_name"] = resource_name
    json.dump(state, open(STATE_FILE, "w"))
    print(f"\nSaved endpoint name to {STATE_FILE}")
    print("Next: python scripts/06_cleanup.py")


if __name__ == "__main__":
    main()
