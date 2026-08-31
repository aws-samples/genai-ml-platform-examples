"""Step 1 — Hub exposes a destination group to the spoke.

The hub administrator creates a destination Model Package Group, attaches a
resource policy that lets the spoke account write into it, and RAM-shares it to
the spoke with the AllowRegister managed permission (the permission designed for
registering new model versions into a shared group). The spoke accepts.

This is a one-time hub-side setup. Data scientists never write to the hub
directly; only the approval-triggered copy (Step 3) does, into this group.

Run:
    python scripts/01_hub_setup.py
"""

from __future__ import annotations

import json
import time

import boto3

from _common import accept_pending_invitation, config, print_banner

cfg = config(require_sync=False)
print_banner(cfg, "Step 1: hub exposes the destination group")

hub = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region)
spoke = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
hub_sm, hub_ram, spoke_ram = hub.client("sagemaker"), hub.client("ram"), spoke.client("ram")


def main() -> None:
    # 1. Create the destination group (idempotent).
    try:
        hub_sm.create_model_package_group(ModelPackageGroupName=cfg.hub_dest_mpg)
        print(f"[Hub] Created destination group {cfg.hub_dest_mpg}")
    except hub_sm.exceptions.ClientError as exc:
        if "already exists" in str(exc):
            print(f"[Hub] Destination group {cfg.hub_dest_mpg} already exists")
        else:
            raise

    # 2. Resource policy: allow the spoke account to copy packages into the group.
    pkg_arn_glob = cfg.hub_dest_mpg_arn.replace(
        "model-package-group", "model-package"
    ) + "/*"
    hub_sm.put_model_package_group_policy(
        ModelPackageGroupName=cfg.hub_dest_mpg,
        ResourcePolicy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DevCopyIn",
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{cfg.spoke_account_id}:root"},
                        "Action": [
                            "sagemaker:DescribeModelPackageGroup",
                            "sagemaker:CreateModelPackage",
                            "sagemaker:DescribeModelPackage",
                            "sagemaker:ListModelPackages",
                            "sagemaker:UpdateModelPackage",
                        ],
                        "Resource": [cfg.hub_dest_mpg_arn, pkg_arn_glob],
                    }
                ],
            }
        ),
    )
    print("[Hub] Resource policy attached (spoke may CreateModelPackage into the group)")

    # 3. RAM-share the group with the AllowRegister managed permission.
    existing = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
    if any(
        s["name"] == "hybrid-dest-mpg-share" and s["status"] in ("ACTIVE", "PENDING")
        for s in existing
    ):
        print("[Hub] RAM share already exists")
    else:
        resp = hub_ram.create_resource_share(
            name="hybrid-dest-mpg-share",
            resourceArns=[cfg.hub_dest_mpg_arn],
            principals=[cfg.spoke_account_id],
            allowExternalPrincipals=True,
            permissionArns=[
                "arn:aws:ram::aws:permission/AWSRAMPermissionSageMakerModelPackageGroupAllowRegister"
            ],
        )
        print(f"[Hub] Created RAM share: {resp['resourceShare']['resourceShareArn']}")

    time.sleep(8)
    print("[Spoke]", accept_pending_invitation(
        spoke_ram, cfg.hub_account_id, name_contains="hybrid-dest-mpg-share"
    ))

    print("\nNext: python scripts/02_register_in_spoke.py")


if __name__ == "__main__":
    main()
