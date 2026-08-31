"""Step 3 — Governance officer approves the model centrally in the hub.

The governance officer, working with hub credentials, reviews the synced metrics,
evaluation card, and lineage, then promotes the model to production (via an
MLflow lifecycle alias) and sets the Model Package approval status to Approved.
This is the central control point of the topology: every candidate any spoke
registers is reviewed and approved in one place.

This script sets AWS_PROFILE to the hub profile so the MLflow client uses hub
credentials.

Run:
    python scripts/03_govern_in_hub.py
"""

from __future__ import annotations

import json
import os
import time

from _common import STATE_FILE, config, print_banner

cfg = config()
print_banner(cfg, "Step 3: govern centrally in the hub")

os.environ["AWS_PROFILE"] = cfg.hub_profile
os.environ["AWS_DEFAULT_REGION"] = cfg.region

import boto3
import mlflow

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01 and 02 first.")

sm_arn = state["model_package_arn"]
version = state["model_version"]

hub_sm = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region).client(
    "sagemaker"
)
mlflow.set_tracking_uri(cfg.hub_mlflow_app_arn)
client = mlflow.MlflowClient()


def set_lifecycle(name, ver, stage, status):
    alias = f"sagemakerlifecycle-{stage}-{status}"
    for existing in (
        "staging-pending",
        "staging-active",
        "production-pending",
        "production-active",
    ):
        try:
            client.delete_registered_model_alias(name, f"sagemakerlifecycle-{existing}")
        except Exception:  # noqa: BLE001
            pass
    client.set_registered_model_alias(name, alias, ver)
    return alias


def main() -> None:
    alias = set_lifecycle(cfg.model_name, version, "production", "active")
    print(f"[Hub] Set '{alias}'")
    time.sleep(8)

    hub_sm.update_model_package(ModelPackageArn=sm_arn, ModelApprovalStatus="Approved")
    time.sleep(3)
    detail = hub_sm.describe_model_package(ModelPackageName=sm_arn)
    print(f"[Hub] Lifecycle:       {detail.get('ModelLifeCycle')}")
    print(f"[Hub] Approval status: {detail.get('ModelApprovalStatus')}")

    print("\nNext: python scripts/04_deploy_from_spoke.py")


if __name__ == "__main__":
    main()
