"""Step 3 — Approval-triggered copy of the model into the hub.

Reads the approved package from the spoke registry and calls CreateModelPackage
against the hub's shared destination group, using spoke credentials. Because the
hub granted the spoke CreateModelPackage on that group (Step 1), the copy lands
in the hub registry without the data scientist ever writing to the hub directly.

Only the approved *package* crosses the account boundary. The copy:
  * carries the inference specification,
  * records CustomerMetadataProperties pointing back to the source package and
    account (provenance, since native lineage does not cross accounts), and
  * lands as PendingManualApproval so the hub re-validates independently.

In production you would drive this from an Amazon EventBridge rule on the spoke
Model Package state change to Approved, rather than calling it inline.

Run:
    python scripts/03_copy_to_hub.py
"""

from __future__ import annotations

import json

import boto3

from _common import STATE_FILE, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 3: copy the approved model into the hub")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run steps 01 and 02 first.")

dev_pkg_arn = state["dev_pkg_arn"]

# The copy is performed with SPOKE credentials, writing into the hub group.
spoke_sm = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region).client(
    "sagemaker"
)


def main() -> None:
    src = spoke_sm.describe_model_package(ModelPackageName=dev_pkg_arn)
    if src.get("ModelApprovalStatus") != "Approved":
        raise SystemExit(
            "The source package is not Approved in the spoke. Run 02 first."
        )

    kwargs = {
        "ModelPackageGroupName": cfg.hub_dest_mpg_arn,  # hub's shared group (full ARN)
        "ModelPackageDescription": f"Copied from dev registry {dev_pkg_arn}",
        "ModelApprovalStatus": "PendingManualApproval",  # hub re-validates
        "CustomerMetadataProperties": {
            "source_model_package_arn": dev_pkg_arn,
            "source_account": cfg.spoke_account_id,
        },
    }
    if "InferenceSpecification" in src:
        kwargs["InferenceSpecification"] = src["InferenceSpecification"]

    hub_pkg_arn = spoke_sm.create_model_package(**kwargs)["ModelPackageArn"]
    print(f"[Hub] Copied into hub registry: {hub_pkg_arn}")
    print("      (PendingManualApproval — the hub re-validates independently)")

    state["hub_pkg_arn"] = hub_pkg_arn
    json.dump(state, open(STATE_FILE, "w"))
    print(f"\nSaved state to {STATE_FILE}")
    print("Next: python scripts/04_approve_in_hub.py")


if __name__ == "__main__":
    main()
