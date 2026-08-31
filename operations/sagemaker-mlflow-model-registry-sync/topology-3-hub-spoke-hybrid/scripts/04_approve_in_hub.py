"""Step 4 — Governance officer re-validates and approves in the hub.

The governance officer, working with hub credentials, sees the copied package in
the hub registry — with the provenance metadata pointing back to its dev source —
validates it, and approves it for deployment. The hub stayed isolated from
day-to-day development: only the approved artifact crossed the boundary, and the
hub made its own independent approval decision.

Run:
    python scripts/04_approve_in_hub.py
"""

from __future__ import annotations

import json
import time

import boto3

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 4: re-validate and approve in the hub")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01-03 first.")

hub_pkg_arn = state.get("hub_pkg_arn")
if not hub_pkg_arn:
    raise SystemExit("No hub package ARN in state. Run 03_copy_to_hub.py first.")

hub_sm = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region).client(
    "sagemaker"
)


def main() -> None:
    detail = hub_sm.describe_model_package(ModelPackageName=hub_pkg_arn)
    print(f"[Hub] Package status:   {detail['ModelPackageStatus']}")
    print(f"[Hub] Source metadata:  {detail.get('CustomerMetadataProperties')}")
    print(f"[Hub] Has inference spec: {'InferenceSpecification' in detail}")

    hub_sm.update_model_package(
        ModelPackageArn=hub_pkg_arn, ModelApprovalStatus="Approved"
    )
    time.sleep(3)
    status = hub_sm.describe_model_package(ModelPackageName=hub_pkg_arn)[
        "ModelApprovalStatus"
    ]
    print(f"[Hub] Approval status:  {status}")

    print("\nNext: python scripts/05_deploy_from_spoke.py")


if __name__ == "__main__":
    main()
