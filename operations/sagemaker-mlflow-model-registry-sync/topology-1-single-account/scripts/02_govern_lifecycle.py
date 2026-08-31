"""Step 2 — Govern the model lifecycle with IAM condition keys.

Demonstrates the governance boundary in the single-account topology, where the
boundary is the IAM role rather than the account:

  1. A data scientist moves the model to staging (allowed).
  2. A production promotion from the data-scientist role is denied by an IAM
     condition key on the lifecycle stage.
  3. The governance officer promotes to production and approves for deployment.

The lifecycle stage is driven by MLflow aliases with the naming convention
``sagemakerlifecycle-{stage}-{status}``. Setting such an alias updates the
SageMaker AI Model Package lifecycle automatically.

The production-denial in step 2 is shown with an IAM policy simulation against
the data scientist's actual guardrail policy, so the sample is self-contained
and does not require assuming a second role. See the README for the two IAM
condition keys and how to attach the guardrail to real Studio user profiles.

Run:
    python scripts/02_govern_lifecycle.py
"""

from __future__ import annotations

import json
import time

import boto3
import mlflow
from sagemaker.core.resources import ModelPackage

from _common import STATE_FILE, config, print_banner

cfg = config()
print_banner(cfg, "Step 2: govern lifecycle")

try:
    state = json.load(open(STATE_FILE))
except FileNotFoundError:
    raise SystemExit("State file not found. Run 01_train_and_register.py first.")

model_version = state["model_version"]
sm_arn = state["model_package_arn"]

mlflow.set_tracking_uri(cfg.mlflow_app_arn)
mlflow_client = mlflow.MlflowClient()
iam = boto3.client("iam")

# The data scientist's guardrail: deny any lifecycle transition to production.
# Attach this to the execution role of the data scientists' Studio user
# profiles. The governance-officer profile's role omits it.
DATA_SCIENTIST_DENY_PRODUCTION = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyProductionPromotion",
            "Effect": "Deny",
            "Action": "sagemaker:UpdateModelPackage",
            "Resource": "*",
            "Condition": {
                "StringEquals": {"sagemaker:ModelLifeCycle/stage": "production"}
            },
        }
    ],
}

model_package = ModelPackage.get(model_package_name=sm_arn)
# Workaround: DescribeModelPackage does not return ModelPackageName for versioned
# packages, so get() leaves model_package_name unset, which breaks refresh().
# The API accepts an ARN in that field, so backfill it.
model_package.model_package_name = model_package.model_package_arn


def set_lifecycle(name, version, stage, status):
    """Set a lifecycle alias, removing any existing lifecycle alias first."""
    alias = f"sagemakerlifecycle-{stage}-{status}"
    for existing in (
        "staging-pending",
        "staging-active",
        "production-pending",
        "production-active",
    ):
        try:
            mlflow_client.delete_registered_model_alias(
                name, f"sagemakerlifecycle-{existing}"
            )
        except Exception:  # noqa: BLE001
            pass
    mlflow_client.set_registered_model_alias(name, alias, version)
    return alias


def main() -> None:
    # 1. Data scientist -> staging (allowed).
    alias = set_lifecycle(cfg.model_name, model_version, "staging", "pending")
    time.sleep(8)
    model_package.refresh()
    print(f"\n[1] Data scientist set '{alias}' (allowed).")
    print(f"    Lifecycle: {model_package.model_life_cycle}")

    # 2. Production promotion denied by the guardrail (policy simulation).
    sim = iam.simulate_custom_policy(
        PolicyInputList=[json.dumps(DATA_SCIENTIST_DENY_PRODUCTION)],
        ActionNames=["sagemaker:UpdateModelPackage"],
        ContextEntries=[
            {
                "ContextKeyName": "sagemaker:ModelLifeCycle/stage",
                "ContextKeyValues": ["production"],
                "ContextKeyType": "string",
            }
        ],
    )
    decision = sim["EvaluationResults"][0]["EvalDecision"]
    print(f"\n[2] Data-scientist production promotion -> IAM decision: {decision}")
    assert decision == "explicitDeny", "Expected the guardrail to deny production"
    print("    Guardrail verified: data scientists cannot promote to production.")

    # 3. Governance officer -> production + approve for deployment.
    alias = set_lifecycle(cfg.model_name, model_version, "production", "active")
    time.sleep(8)
    model_package.update(model_approval_status="Approved")
    time.sleep(3)
    model_package.refresh()
    print(f"\n[3] Governance officer set '{alias}' and approved for deployment.")
    print(f"    Lifecycle:        {model_package.model_life_cycle}")
    print(f"    Approval status:  {model_package.model_approval_status}")

    print("\nNext: python scripts/03_deploy_and_invoke.py")


if __name__ == "__main__":
    main()
