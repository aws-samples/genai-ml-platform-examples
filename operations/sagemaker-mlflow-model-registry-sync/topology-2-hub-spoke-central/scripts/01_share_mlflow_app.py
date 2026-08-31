"""Step 1 — Hub shares the MLflow app with the spoke.

Two setup actions, both performed with hub credentials except the invitation
acceptance (spoke):

  1. Attach a cross-account bucket policy to the hub's MLflow artifact store so
     the spoke can write model artifacts during registration (Step 2) and read
     them at deploy time (Step 4).
  2. Create an AWS RAM resource share for the MLflow app and have the spoke
     accept it. allowExternalPrincipals=True lets the share work even when the
     accounts are not in the same AWS Organization.

Run:
    python scripts/01_share_mlflow_app.py
"""

from __future__ import annotations

import json
import time

import boto3

from _common import accept_pending_invitation, config, print_banner

cfg = config()
print_banner(cfg, "Step 1: share the MLflow app")

hub = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region)
spoke = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region)
hub_s3, hub_ram, spoke_ram = hub.client("s3"), hub.client("ram"), spoke.client("ram")


def main() -> None:
    # 1. Cross-account bucket policy on the hub artifact store.
    bucket = cfg.hub_artifact_bucket
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CrossAccountSpokeAccess",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{cfg.spoke_account_id}:root"},
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                ],
            }
        ],
    }
    hub_s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(bucket_policy))
    print(f"[1] Cross-account bucket policy applied to s3://{bucket}")

    # 2. RAM-share the MLflow app.
    existing = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
    share = next(
        (
            s
            for s in existing
            if s["name"] == "mlflow-app-central-share"
            and s["status"] in ("ACTIVE", "PENDING")
        ),
        None,
    )
    if share:
        print(f"[2] MLflow app share already exists: {share['resourceShareArn']}")
    else:
        resp = hub_ram.create_resource_share(
            name="mlflow-app-central-share",
            resourceArns=[cfg.hub_mlflow_app_arn],
            principals=[cfg.spoke_account_id],
            allowExternalPrincipals=True,
        )
        print(f"[2] Created MLflow app share: {resp['resourceShare']['resourceShareArn']}")

    time.sleep(5)
    print("[2]", accept_pending_invitation(
        spoke_ram, cfg.hub_account_id, name_contains="mlflow-app-central-share"
    ))

    print("\nNext: python scripts/02_register_from_spoke.py")


if __name__ == "__main__":
    main()
