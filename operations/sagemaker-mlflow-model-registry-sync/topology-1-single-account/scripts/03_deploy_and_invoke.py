"""Step 3 — Deploy the approved model from the registry and invoke it.

This is where the inference specification logged in Step 1 pays off. Because the
Model Package carries a container image and model data location, it is directly
deployable — no repacking, no separate model upload. The deployment uses SDK v3
typed resources (Model, EndpointConfig, Endpoint), which mirror the SageMaker AI
API and are exactly what a CI/CD pipeline runs when an approval event fires.

The script refuses to deploy a package that is not Approved, mirroring the
governance gate.

Cost note: this creates a real-time endpoint on an ml.m5.xlarge instance. Run
scripts/04_cleanup.py when you are done to stop incurring charges.

Run:
    python scripts/03_deploy_and_invoke.py
"""

from __future__ import annotations

import json
import time

import boto3
from sagemaker.core.resources import Endpoint, EndpointConfig, Model
from sagemaker.core.shapes import ContainerDefinition, ProductionVariant

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 3: deploy and invoke")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01 and 02 first.")

sm_arn = state["model_package_arn"]
sm = boto3.client("sagemaker", region_name=cfg.region)


def main() -> None:
    # Governance gate: only deploy an Approved package.
    detail = sm.describe_model_package(ModelPackageName=sm_arn)
    approval = detail.get("ModelApprovalStatus")
    if approval != "Approved":
        raise SystemExit(
            f"Model Package approval status is '{approval}', not 'Approved'. "
            "Run 02_govern_lifecycle.py to approve it before deploying."
        )
    print(f"Model Package is Approved: {sm_arn}")

    suffix = time.strftime("%Y%m%d-%H%M%S")
    resource_name = f"{cfg.model_name}-{suffix}"

    Model.create(
        model_name=resource_name,
        primary_container=ContainerDefinition(model_package_name=sm_arn),
        execution_role_arn=cfg.execution_role,
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
    )
    print(f"Created endpoint config: {resource_name}")

    endpoint = Endpoint.create(
        endpoint_name=resource_name,
        endpoint_config_name=resource_name,
    )
    print(f"Creating endpoint {resource_name} (a few minutes)...")
    endpoint.wait_for_status("InService")
    print("Endpoint is InService.")

    # Invoke with a CSV payload (four features, matching the training data).
    response = endpoint.invoke(
        body="0.5,-1.2,0.3,0.8\n1.1,0.4,-0.7,0.2",
        content_type="text/csv",
        accept="application/json",
    )
    print("Prediction:", response.body.read().decode())

    state["endpoint_name"] = resource_name
    state["model_name_resource"] = resource_name
    state["endpoint_config_name"] = resource_name
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    print(f"\nSaved endpoint name to {STATE_FILE}")
    print("Next: python scripts/04_cleanup.py  (deletes the endpoint and registry entries)")


if __name__ == "__main__":
    main()
