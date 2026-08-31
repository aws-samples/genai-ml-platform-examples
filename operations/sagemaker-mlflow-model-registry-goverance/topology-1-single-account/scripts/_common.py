"""Shared configuration and preflight checks for the Topology 1 sample.

Every step script imports ``config()`` from here. Configuration is read from
environment variables so the scripts stay portable across accounts and can run
either inside a SageMaker Studio JupyterLab space or from a laptop.

Required environment variables
------------------------------
MLFLOW_APP_ARN
    ARN of the managed MLflow app with Model Registry sync enabled. This doubles
    as the MLflow tracking URI. Take it from the CloudFormation stack output
    ``MLflowAppArn``.

EXECUTION_ROLE
    SageMaker AI execution role ARN. Take it from the stack output
    ``SageMakerExecutionRoleArn``.

    Why this must be explicit: inside Studio the SDK can discover the role with
    ``get_execution_role()``, but when you run from a laptop that call resolves
    to your *caller* identity (for example, a federated admin role) which
    SageMaker cannot assume for training or hosting. Setting it explicitly makes
    the sample behave identically in both places.

Optional
--------
AWS_DEFAULT_REGION   Region (defaults to the session region).
MODEL_NAME           Registered model name (defaults to ``single-account-governance-demo``).
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
    account_id: str
    execution_role: str
    mlflow_app_arn: str
    model_name: str


def _fail(message: str) -> "None":
    """Print an actionable error and exit non-zero."""
    print(f"\nConfiguration error: {message}\n", file=sys.stderr)
    sys.exit(1)


def config(require_sync: bool = True) -> Config:
    """Resolve configuration from the environment and run preflight checks.

    Set ``require_sync=False`` for steps that do not need the MLflow app to have
    Model Registry sync enabled (for example, cleanup).
    """
    mlflow_app_arn = os.environ.get("MLFLOW_APP_ARN", "").strip()
    execution_role = os.environ.get("EXECUTION_ROLE", "").strip()

    if not mlflow_app_arn:
        _fail(
            "MLFLOW_APP_ARN is not set. Copy the 'MLflowAppArn' output from the "
            "CloudFormation stack and export it:\n"
            "    export MLFLOW_APP_ARN=arn:aws:sagemaker:<region>:<account>:mlflow-app/app-XXXX"
        )
    if not execution_role:
        _fail(
            "EXECUTION_ROLE is not set. Copy the 'SageMakerExecutionRoleArn' output "
            "from the CloudFormation stack and export it:\n"
            "    export EXECUTION_ROLE=arn:aws:iam::<account>:role/<role-name>"
        )

    session = boto3.Session()
    region = session.region_name or os.environ.get("AWS_DEFAULT_REGION", "")
    if not region:
        _fail("No region configured. Set AWS_DEFAULT_REGION or configure your profile.")

    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
    except Exception as exc:  # noqa: BLE001
        _fail(f"Could not resolve AWS credentials: {exc}")

    # Preflight: the MLflow app exists and (optionally) has sync enabled.
    sm = boto3.client("sagemaker", region_name=region)
    try:
        app = sm.describe_mlflow_app(Arn=mlflow_app_arn)
    except Exception as exc:  # noqa: BLE001
        _fail(
            f"Could not describe the MLflow app {mlflow_app_arn}: {exc}\n"
            "Verify the ARN and that your profile targets the right account/region."
        )

    mode = app.get("ModelRegistrationMode")
    if require_sync and mode != "AutoModelRegistrationEnabled":
        _fail(
            f"The MLflow app's ModelRegistrationMode is '{mode}', not "
            "'AutoModelRegistrationEnabled'. Enable it with:\n"
            f"    aws sagemaker update-mlflow-app --arn {mlflow_app_arn} \\\n"
            "        --model-registration-mode AutoModelRegistrationEnabled"
        )

    model_name = os.environ.get("MODEL_NAME", "single-account-governance-demo").strip()

    return Config(
        region=region,
        account_id=account_id,
        execution_role=execution_role,
        mlflow_app_arn=mlflow_app_arn,
        model_name=model_name,
    )


def print_banner(cfg: Config, step: str) -> None:
    print("=" * 72)
    print(f"Topology 1 — Single-account governance :: {step}")
    print("=" * 72)
    print(f"Account:        {cfg.account_id}")
    print(f"Region:         {cfg.region}")
    print(f"MLflow app:     {cfg.mlflow_app_arn}")
    print(f"Execution role: {cfg.execution_role}")
    print(f"Model name:     {cfg.model_name}")
    print("-" * 72)
