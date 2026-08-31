"""Step 5 — Clean up all resources across both accounts.

Spoke: endpoint, endpoint config, model.
Hub:   RAM shares (app + group), the cross-account bucket policy, Model Packages,
       group, MLflow registered model.

The CloudFormation-provisioned infrastructure (domains, MLflow apps, roles) is
left in place — delete the stacks to remove those.

Run:
    python scripts/05_cleanup.py
"""

from __future__ import annotations

import json
import os
import time

import boto3

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 5: cleanup")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found — nothing to clean up.")

hub = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region)
spoke = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
hub_sm, hub_ram = hub.client("sagemaker"), hub.client("ram")
hub_s3 = hub.client("s3")
spoke_sm = spoke.client("sagemaker")


def _try(label, fn):
    try:
        fn()
        print(f"  deleted {label}")
    except Exception as exc:  # noqa: BLE001
        print(f"  skip {label}: {exc}")


def main() -> None:
    # Spoke hosting resources.
    ep = state.get("endpoint_name")
    if ep:
        print("Spoke: deleting hosting resources...")
        _try(f"endpoint {ep}", lambda: spoke_sm.delete_endpoint(EndpointName=ep))
        _try(
            f"endpoint-config {state.get('endpoint_config_name')}",
            lambda: spoke_sm.delete_endpoint_config(
                EndpointConfigName=state["endpoint_config_name"]
            ),
        )
        _try(
            f"model {state.get('model_name_resource')}",
            lambda: spoke_sm.delete_model(ModelName=state["model_name_resource"]),
        )

    # Hub bucket policy: revoke the spoke's cross-account access granted in Step 1.
    print("Hub: removing the cross-account bucket policy...")
    _try(
        f"bucket policy on {cfg.hub_artifact_bucket}",
        lambda: hub_s3.delete_bucket_policy(Bucket=cfg.hub_artifact_bucket),
    )

    # Hub RAM shares.
    print("Hub: deleting RAM shares...")
    shares = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
    for s in shares:
        if s["status"] in ("ACTIVE", "PENDING") and (
            s["name"] == "mlflow-app-central-share"
            or s["name"].startswith("mpg-central-share-")
        ):
            _try(
                s["name"],
                lambda a=s["resourceShareArn"]: hub_ram.delete_resource_share(
                    resourceShareArn=a
                ),
            )

    # Hub registry entries.
    sm_arn = state.get("model_package_arn")
    mpg = state.get("mpg_name")
    if mpg:
        print("Hub: deleting registry entries...")
        for p in hub_sm.list_model_packages(ModelPackageGroupName=mpg).get(
            "ModelPackageSummaryList", []
        ):
            _try(
                p["ModelPackageArn"],
                lambda a=p["ModelPackageArn"]: hub_sm.delete_model_package(
                    ModelPackageName=a
                ),
            )
        for _ in range(12):
            if not hub_sm.list_model_packages(ModelPackageGroupName=mpg).get(
                "ModelPackageSummaryList", []
            ):
                break
            time.sleep(5)
        _try(
            f"group {mpg}",
            lambda: hub_sm.delete_model_package_group(ModelPackageGroupName=mpg),
        )

    # Hub MLflow registered model.
    print("Hub: deleting MLflow registered model...")
    os.environ["AWS_PROFILE"] = cfg.hub_profile
    import mlflow

    mlflow.set_tracking_uri(cfg.hub_mlflow_app_arn)
    _try(
        f"registered model {cfg.model_name}",
        lambda: mlflow.MlflowClient().delete_registered_model(cfg.model_name),
    )

    print("\nDone. Delete the CloudFormation stacks to remove domains, apps, and roles.")


if __name__ == "__main__":
    main()
