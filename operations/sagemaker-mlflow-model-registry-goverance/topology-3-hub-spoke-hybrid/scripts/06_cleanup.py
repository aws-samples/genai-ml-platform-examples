"""Step 6 — Clean up across both accounts.

Spoke: the local Model Package + group, the MLflow registered model.
Hub:   the copied Model Package, and (optionally) the destination group and its
       RAM share.

By default the hub destination group and its RAM share are LEFT in place, since
they are one-time hub setup meant to be reused across many dev cycles. Pass
--remove-hub-group to delete them too.

Run:
    python scripts/06_cleanup.py [--remove-hub-group]
"""

from __future__ import annotations

import json
import os
import sys
import time

import boto3

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 6: cleanup")

remove_hub_group = "--remove-hub-group" in sys.argv

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found — nothing to clean up.")

hub = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region)
spoke = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
hub_sm, hub_ram = hub.client("sagemaker"), hub.client("ram")
spoke_sm = spoke.client("sagemaker")


def _try(label, fn):
    try:
        fn()
        print(f"  deleted {label}")
    except Exception as exc:  # noqa: BLE001
        print(f"  skip {label}: {exc}")


def _empty_and_delete_group(sm, group):
    for p in sm.list_model_packages(ModelPackageGroupName=group).get(
        "ModelPackageSummaryList", []
    ):
        _try(
            p["ModelPackageArn"],
            lambda a=p["ModelPackageArn"]: sm.delete_model_package(ModelPackageName=a),
        )
    for _ in range(12):
        if not sm.list_model_packages(ModelPackageGroupName=group).get(
            "ModelPackageSummaryList", []
        ):
            break
        time.sleep(5)


def main() -> None:
    # Spoke: delete the endpoint deployed in Step 5 (bills per instance-hour).
    ep = state.get("spoke_endpoint_name")
    if ep:
        print("Spoke: deleting hosting resources...")
        _try(f"endpoint {ep}", lambda: spoke_sm.delete_endpoint(EndpointName=ep))
        _try(
            f"endpoint-config {state.get('spoke_endpoint_config_name')}",
            lambda: spoke_sm.delete_endpoint_config(
                EndpointConfigName=state["spoke_endpoint_config_name"]
            ),
        )
        _try(
            f"model {state.get('spoke_model_name_resource')}",
            lambda: spoke_sm.delete_model(ModelName=state["spoke_model_name_resource"]),
        )

    # Hub: delete the copied package (leave the destination group by default).
    hub_pkg = state.get("hub_pkg_arn")
    if hub_pkg:
        print("Hub: deleting the copied Model Package...")
        _try(hub_pkg, lambda: hub_sm.delete_model_package(ModelPackageName=hub_pkg))

    if remove_hub_group:
        print("Hub: removing destination group and RAM share...")
        _empty_and_delete_group(hub_sm, cfg.hub_dest_mpg)
        _try(
            f"group {cfg.hub_dest_mpg}",
            lambda: hub_sm.delete_model_package_group(
                ModelPackageGroupName=cfg.hub_dest_mpg
            ),
        )
        for s in hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]:
            if s["name"] == "hybrid-dest-mpg-share" and s["status"] in (
                "ACTIVE",
                "PENDING",
            ):
                _try(
                    s["name"],
                    lambda a=s["resourceShareArn"]: hub_ram.delete_resource_share(
                        resourceShareArn=a
                    ),
                )

    # Spoke: delete the local package + group.
    dev_pkg = state.get("dev_pkg_arn")
    if dev_pkg:
        print("Spoke: deleting the local Model Package and group...")
        try:
            group = spoke_sm.describe_model_package(ModelPackageName=dev_pkg)[
                "ModelPackageGroupName"
            ]
        except Exception:  # noqa: BLE001
            group = None
        if group:
            _empty_and_delete_group(spoke_sm, group)
            _try(
                f"group {group}",
                lambda: spoke_sm.delete_model_package_group(
                    ModelPackageGroupName=group
                ),
            )

    # Spoke: MLflow registered model.
    print("Spoke: deleting the MLflow registered model...")
    os.environ["AWS_PROFILE"] = cfg.spoke_profile
    import mlflow

    mlflow.set_tracking_uri(cfg.spoke_mlflow_app_arn)
    _try(
        f"registered model {cfg.model_name}",
        lambda: mlflow.MlflowClient().delete_registered_model(cfg.model_name),
    )

    print("\nDone.", "Hub destination group left in place (use --remove-hub-group to delete)."
          if not remove_hub_group else "Hub destination group removed.")
    print("Delete the CloudFormation stacks to remove domains, apps, and roles.")


if __name__ == "__main__":
    main()
