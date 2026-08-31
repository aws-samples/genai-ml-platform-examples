"""Shared configuration and preflight checks for the Topology 2 sample.

Topology 2 (hub-and-spoke, central governance) spans two accounts:

  * hub   — owns the managed MLflow app and the central Model Registry
  * spoke — a development account whose data scientists register models

Configuration is read from environment variables so the scripts stay portable.

Required environment variables
------------------------------
HUB_PROFILE            AWS CLI profile for the hub account.
SPOKE_PROFILE          AWS CLI profile for the spoke (development) account.
HUB_MLFLOW_APP_ARN     ARN of the hub's MLflow app (sync enabled). Doubles as the
                       MLflow tracking URI. Stack output ``MLflowAppArn`` in the hub.
SPOKE_EXECUTION_ROLE   Spoke execution role ARN, used as the endpoint execution
                       role in Step 4. Stack output ``SageMakerExecutionRoleArn``
                       in the spoke.
AWS_DEFAULT_REGION     Region where the CloudFormation stacks are deployed.

Optional
--------
MODEL_NAME             Registered model name (defaults to hub-spoke-central-demo).
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
    hub_mlflow_app_arn: str
    spoke_execution_role: str
    model_name: str

    @property
    def hub_artifact_bucket(self) -> str:
        return f"sagemaker-{self.region}-{self.hub_account_id}"


def _fail(message: str) -> None:
    print(f"\nConfiguration error: {message}\n", file=sys.stderr)
    sys.exit(1)


def config(require_sync: bool = True) -> Config:
    hub_profile = os.environ.get("HUB_PROFILE", "").strip()
    spoke_profile = os.environ.get("SPOKE_PROFILE", "").strip()
    hub_mlflow_app_arn = os.environ.get("HUB_MLFLOW_APP_ARN", "").strip()
    spoke_execution_role = os.environ.get("SPOKE_EXECUTION_ROLE", "").strip()
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
    if not hub_mlflow_app_arn:
        _fail(
            "HUB_MLFLOW_APP_ARN is not set. Use the 'MLflowAppArn' output from the "
            "hub CloudFormation stack:\n"
            "    export HUB_MLFLOW_APP_ARN=arn:aws:sagemaker:<region>:<hub>:mlflow-app/app-XXXX"
        )
    if not spoke_execution_role:
        _fail(
            "SPOKE_EXECUTION_ROLE is not set. Use the 'SageMakerExecutionRoleArn' "
            "output from the spoke CloudFormation stack:\n"
            "    export SPOKE_EXECUTION_ROLE=arn:aws:iam::<spoke>:role/<role-name>"
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

    # Preflight: the hub MLflow app exists and (optionally) has sync enabled.
    hub_sm = boto3.Session(profile_name=hub_profile, region_name=region).client(
        "sagemaker"
    )
    try:
        app = hub_sm.describe_mlflow_app(Arn=hub_mlflow_app_arn)
    except Exception as exc:  # noqa: BLE001
        _fail(f"Could not describe the hub MLflow app {hub_mlflow_app_arn}: {exc}")

    mode = app.get("ModelRegistrationMode")
    if require_sync and mode != "AutoModelRegistrationEnabled":
        _fail(
            f"The hub MLflow app's ModelRegistrationMode is '{mode}', not "
            "'AutoModelRegistrationEnabled'. Enable it with:\n"
            f"    aws sagemaker update-mlflow-app --arn {hub_mlflow_app_arn} \\\n"
            "        --model-registration-mode AutoModelRegistrationEnabled "
            "--profile $HUB_PROFILE"
        )

    return Config(
        region=region,
        hub_profile=hub_profile,
        spoke_profile=spoke_profile,
        hub_account_id=hub_account_id,
        spoke_account_id=spoke_account_id,
        hub_mlflow_app_arn=hub_mlflow_app_arn,
        spoke_execution_role=spoke_execution_role,
        model_name=os.environ.get("MODEL_NAME", "hub-spoke-central-demo").strip(),
    )


def print_banner(cfg: Config, step: str) -> None:
    print("=" * 72)
    print(f"Topology 2 — Hub-and-spoke central governance :: {step}")
    print("=" * 72)
    print(f"Hub account:    {cfg.hub_account_id}  (profile {cfg.hub_profile})")
    print(f"Spoke account:  {cfg.spoke_account_id}  (profile {cfg.spoke_profile})")
    print(f"Region:         {cfg.region}")
    print(f"Hub MLflow app: {cfg.hub_mlflow_app_arn}")
    print(f"Model name:     {cfg.model_name}")
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
