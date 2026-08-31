"""Step 4 — Clean up all resources created by the sample.

Deletes, in order: the endpoint (bills per instance-hour, so first), the
endpoint config, the model, every Model Package in the synced group, the group
itself, and the MLflow registered model.

Run:
    python scripts/04_cleanup.py

The MLflow app, Studio domain, and execution role are provisioned by the
CloudFormation stack — delete the stack to remove those.
"""

from __future__ import annotations

import json

import boto3
import mlflow

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 4: cleanup")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found — nothing to clean up.")

sm = boto3.client("sagemaker", region_name=cfg.region)


def _try(label, fn):
    try:
        fn()
        print(f"  deleted {label}")
    except Exception as exc:  # noqa: BLE001
        print(f"  skip {label}: {exc}")


def main() -> None:
    endpoint_name = state.get("endpoint_name")
    if endpoint_name:
        print("Deleting hosting resources...")
        _try(f"endpoint {endpoint_name}", lambda: sm.delete_endpoint(EndpointName=endpoint_name))
        _try(
            f"endpoint-config {state.get('endpoint_config_name')}",
            lambda: sm.delete_endpoint_config(
                EndpointConfigName=state["endpoint_config_name"]
            ),
        )
        _try(
            f"model {state.get('model_name_resource')}",
            lambda: sm.delete_model(ModelName=state["model_name_resource"]),
        )

    sm_arn = state.get("model_package_arn")
    if sm_arn:
        # group name is between 'model-package-group/' ... but we stored the
        # package ARN; derive the group from the package detail.
        print("Deleting registry entries...")
        try:
            group = sm.describe_model_package(ModelPackageName=sm_arn)[
                "ModelPackageGroupName"
            ]
        except Exception:  # noqa: BLE001
            group = None
        if group:
            pkgs = sm.list_model_packages(ModelPackageGroupName=group).get(
                "ModelPackageSummaryList", []
            )
            for p in pkgs:
                _try(
                    p["ModelPackageArn"],
                    lambda a=p["ModelPackageArn"]: sm.delete_model_package(
                        ModelPackageName=a
                    ),
                )
            # Model package deletion is eventually consistent — wait until the
            # group is empty before deleting it, otherwise the group delete
            # fails with "still contains Model Packages".
            import time

            for _ in range(12):
                remaining = sm.list_model_packages(
                    ModelPackageGroupName=group
                ).get("ModelPackageSummaryList", [])
                if not remaining:
                    break
                time.sleep(5)
            _try(
                f"group {group}",
                lambda: sm.delete_model_package_group(ModelPackageGroupName=group),
            )

    print("Deleting MLflow registered model...")
    mlflow.set_tracking_uri(cfg.mlflow_app_arn)
    _try(
        f"registered model {cfg.model_name}",
        lambda: mlflow.MlflowClient().delete_registered_model(cfg.model_name),
    )

    print("\nDone. To remove the domain, MLflow app, and role, delete the CFN stack.")


if __name__ == "__main__":
    main()
