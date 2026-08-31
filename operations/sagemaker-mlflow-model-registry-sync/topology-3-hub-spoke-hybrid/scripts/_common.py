"""Shared configuration and preflight checks for the Topology 3 sample.

Topology 3 (hub-and-spoke, hybrid governance) spans two accounts, but unlike
Topology 2 each development account runs its OWN MLflow app and registry:

  * spoke — development account with its own MLflow app (sync enabled) and a
            local Model Registry. Data scientists never write to the hub.
  * hub   — owns a destination Model Package Group. Approved models are COPIED
            into it cross-account; the hub re-validates before approving.

Required environment variables
------------------------------
HUB_PROFILE            AWS CLI profile for the hub account.
SPOKE_PROFILE          AWS CLI profile for the spoke (development) account.
SPOKE_MLFLOW_APP_ARN   ARN of the SPOKE's own MLflow app (sync enabled). Doubles
                       as the MLflow tracking URI. Stack output ``MLflowAppArn``
                       in the spoke.
AWS_DEFAULT_REGION     Region where the CloudFormation stacks are deployed.

Optional
--------
MODEL_NAME             Registered model name (defaults to hybrid-dev-candidate).
HUB_DEST_MPG           Hub destination group name (defaults to
                       hub-central-registry-from-dev).
SPOKE_EXECUTION_ROLE   Spoke execution role ARN, used as the endpoint execution
                       role when deploying the spoke-local approved package in
                       Step 5. Stack output ``SageMakerExecutionRoleArn`` in the
                       spoke. Required only for Step 5.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import boto3

STATE_FILE = os.path.join(os.path.dirname(__file__), ".sample_state.json")


@dataclass
class Config:
    region: str
    hub_profile: str
    spoke_profile: str
    hub_account_id: str
    spoke_account_id: str
    spoke_mlflow_app_arn: str
    model_name: str
    hub_dest_mpg: str
    spoke_execution_role: str

    @property
    def hub_dest_mpg_arn(self) -> str:
        return (
            f"arn:aws:sagemaker:{self.region}:{self.hub_account_id}"
            f":model-package-group/{self.hub_dest_mpg}"
        )

    @property
    def spoke_artifact_bucket(self) -> str:
        return f"sagemaker-{self.region}-{self.spoke_account_id}"


def _fail(message: str) -> None:
    print(f"\nConfiguration error: {message}\n", file=sys.stderr)
    sys.exit(1)


def config(require_sync: bool = True) -> Config:
    hub_profile = os.environ.get("HUB_PROFILE", "").strip()
    spoke_profile = os.environ.get("SPOKE_PROFILE", "").strip()
    spoke_mlflow_app_arn = os.environ.get("SPOKE_MLFLOW_APP_ARN", "").strip()
    region = os.environ.get("AWS_DEFAULT_REGION", "").strip()

    if not region:
        _fail(
            "AWS_DEFAULT_REGION is not set. Use the region where you deployed the "
            "CloudFormation stacks:\n"
            "    export AWS_DEFAULT_REGION=us-west-2"
        )
    if not hub_profile or not spoke_profile:
        _fail(
            "HUB_PROFILE and SPOKE_PROFILE must both be set:\n"
            "    export HUB_PROFILE=mlops-hub\n"
            "    export SPOKE_PROFILE=mlops-dev"
        )
    if not spoke_mlflow_app_arn:
        _fail(
            "SPOKE_MLFLOW_APP_ARN is not set. Use the 'MLflowAppArn' output from "
            "the SPOKE CloudFormation stack (Topology 3 uses the spoke's own app):\n"
            "    export SPOKE_MLFLOW_APP_ARN=arn:aws:sagemaker:<region>:<spoke>:mlflow-app/app-XXXX"
        )

    try:
        hub_account_id = boto3.Session(profile_name=hub_profile).client(
            "sts"
        ).get_caller_identity()["Account"]
        spoke_account_id = boto3.Session(profile_name=spoke_profile).client(
            "sts"
        ).get_caller_identity()["Account"]
    except Exception as exc:  # noqa: BLE001
        _fail(f"Could not resolve credentials for one of the profiles: {exc}")

    # Preflight: the spoke MLflow app exists and (optionally) has sync enabled.
    spoke_sm = boto3.Session(profile_name=spoke_profile, region_name=region).client(
        "sagemaker"
    )
    try:
        app = spoke_sm.describe_mlflow_app(Arn=spoke_mlflow_app_arn)
    except Exception as exc:  # noqa: BLE001
        _fail(f"Could not describe the spoke MLflow app {spoke_mlflow_app_arn}: {exc}")

    mode = app.get("ModelRegistrationMode")
    if require_sync and mode != "AutoModelRegistrationEnabled":
        _fail(
            f"The spoke MLflow app's ModelRegistrationMode is '{mode}', not "
            "'AutoModelRegistrationEnabled'. Enable it with:\n"
            f"    aws sagemaker update-mlflow-app --arn {spoke_mlflow_app_arn} \\\n"
            "        --model-registration-mode AutoModelRegistrationEnabled "
            "--profile $SPOKE_PROFILE"
        )

    return Config(
        region=region,
        hub_profile=hub_profile,
        spoke_profile=spoke_profile,
        hub_account_id=hub_account_id,
        spoke_account_id=spoke_account_id,
        spoke_mlflow_app_arn=spoke_mlflow_app_arn,
        model_name=os.environ.get("MODEL_NAME", "hybrid-dev-candidate").strip(),
        hub_dest_mpg=os.environ.get(
            "HUB_DEST_MPG", "hub-central-registry-from-dev"
        ).strip(),
        spoke_execution_role=os.environ.get("SPOKE_EXECUTION_ROLE", "").strip(),
    )


def print_banner(cfg: Config, step: str) -> None:
    print("=" * 72)
    print(f"Topology 3 — Hub-and-spoke hybrid governance :: {step}")
    print("=" * 72)
    print(f"Hub account:      {cfg.hub_account_id}  (profile {cfg.hub_profile})")
    print(f"Spoke account:    {cfg.spoke_account_id}  (profile {cfg.spoke_profile})")
    print(f"Region:           {cfg.region}")
    print(f"Spoke MLflow app: {cfg.spoke_mlflow_app_arn}")
    print(f"Hub dest group:   {cfg.hub_dest_mpg}")
    print(f"Model name:       {cfg.model_name}")
    print("-" * 72)


def accept_pending_invitation(ram_client, sender_account_id, name_contains=None, retries=6):
    """Find and accept a pending RAM invitation from a sender. Idempotent."""
    import time

    for _ in range(retries):
        invs = ram_client.get_resource_share_invitations()["resourceShareInvitations"]
        pending = [
            i
            for i in invs
            if i["status"] == "PENDING"
            and i["senderAccountId"] == sender_account_id
            and (name_contains is None or name_contains in i.get("resourceShareName", ""))
        ]
        if pending:
            arn = pending[0]["resourceShareInvitationArn"]
            ram_client.accept_resource_share_invitation(resourceShareInvitationArn=arn)
            return f"accepted: {arn}"
        time.sleep(5)
    return "no pending invitation found (may already be accepted)"
