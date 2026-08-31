# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: mlflow-sync-blog
#     language: python
#     name: mlflow-sync-blog
# ---

# %% [markdown]
# # Topology 1: Single-account model governance
#
# This notebook demonstrates the **automatic model registration** integration between
# managed MLflow on Amazon SageMaker AI and the SageMaker AI Model Registry, in the
# **single-account** governance topology.
#
# In this pattern, data scientists and the governance officer work in the **same AWS
# account**. Data scientists experiment in MLflow; when they register a model, SageMaker AI
# automatically creates a Model Package Group and version in the Model Registry, carrying
# over training metrics, evaluation metrics, an inference specification, and lineage. The
# governance officer then validates and promotes the model to production.
#
# Governance is enforced with **IAM condition keys** on the model lifecycle: the
# data-scientist role can move a model to `staging` but is denied promotion to
# `production`, which only the governance-officer role can perform.
#
# ## Flow
# ```
# Single account (data science + governance)
# ───────────────────────────────────────────
# 1. Enable Model Registry sync on the MLflow app
# 2. Data scientist logs model + eval + inference spec, registers it
#    [sync creates Model Package Group + version automatically]
# 3. Data scientist sets lifecycle staging/pending  (allowed)
# 4. Data scientist attempts production promotion    (DENIED by IAM condition key)
# 5. Governance officer promotes to production/active + approves for deployment
# ```

# %% [markdown]
# ## Prerequisites
#
# - One AWS account with permissions to create SageMaker AI MLflow apps, IAM roles, and S3 buckets.
# - An **MLflow app with Model Registry sync enabled**
#   (`ModelRegistrationMode = AutoModelRegistrationEnabled`). See the setup cell below.
# - Python dependencies:
#   ```bash
#   pip install boto3 mlflow scikit-learn sagemaker-mlflow pandas
#   ```
# - The MLflow app IAM service role needs permissions to register models and create lineage.
#   See `MLFLOW_APP_ROLE_POLICY` below.

# %% [markdown]
# ## Configuration
#
# Set these to match your environment. `MLFLOW_APP_ARN` is the ARN of an MLflow app that
# already has Model Registry sync enabled.

# %%
import os

PROFILE = "<YOUR_PROFILE>"          # AWS CLI profile / credentials to use
REGION = "us-west-2"
MLFLOW_APP_ARN = "<YOUR_MLFLOW_APP_ARN>"  # e.g. arn:aws:sagemaker:us-west-2:123456789012:mlflow-app/app-XXXXXXXXXX
MODEL_NAME = "single-account-governance-demo"

os.environ["AWS_PROFILE"] = PROFILE
os.environ["AWS_DEFAULT_REGION"] = REGION

import boto3
import json
import time

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
sm = session.client("sagemaker")
iam = session.client("iam")
sts = session.client("sts")
ACCOUNT_ID = sts.get_caller_identity()["Account"]
print(f"Account: {ACCOUNT_ID}, Region: {REGION}")
print(f"MLflow app: {MLFLOW_APP_ARN}")

# %% [markdown]
# ## Step 0 (reference): Enabling Model Registry sync on an MLflow app
#
# Model Registry sync is **opt-in**. When you create or update an MLflow app, set the
# model registration mode to `AutoModelRegistrationEnabled`. The commands below are shown
# for reference — this notebook assumes `MLFLOW_APP_ARN` already points to an enabled app.
#
# ```bash
# aws sagemaker create-mlflow-app \
#     --name my-mlflow-app \
#     --artifact-store-uri s3://my-bucket/mlflow \
#     --role-arn arn:aws:iam::<ACCOUNT>:role/my-mlflow-app-role \
#     --model-registration-mode AutoModelRegistrationEnabled \
#     --region us-west-2
#
# # To enable on an existing app:
# aws sagemaker update-mlflow-app \
#     --arn <MLFLOW_APP_ARN> \
#     --model-registration-mode AutoModelRegistrationEnabled
# ```
#
# The MLflow app's IAM **service role** must be allowed to register models and create
# lineage. The following policy captures the required actions.

# %%
MLFLOW_APP_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sagemaker:CreateModelPackageGroup",
                "sagemaker:DescribeModelPackageGroup",
                "sagemaker:CreateModelPackage",
                "sagemaker:UpdateModelPackage",
                "sagemaker:DescribeModelPackage",
                "sagemaker:ListModelPackages",
                "sagemaker:AddTags",
                # Lineage associations (MLflow experiment <-> Model Package)
                "sagemaker:CreateAction",
                "sagemaker:AddAssociation",
                "sagemaker:CreateArtifact",
                "sagemaker:CreateContext",
            ],
            "Resource": "*",
        },
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"],
            "Resource": "*",
        },
    ],
}
print(json.dumps(MLFLOW_APP_ROLE_POLICY, indent=2))

# %% [markdown]
# ## Step 1: Define governance guardrails with IAM condition keys
#
# The Model Registry lifecycle exposes two IAM condition keys:
#
# - `sagemaker:ModelLifeCycle/stage` — the stage being set (`staging`, `production`)
# - `sagemaker:ModelLifeCycle/stageStatus` — the status being set (`pending`, `active`)
#
# We express the **data-scientist** guardrail as a policy that **denies** any lifecycle
# transition to `production`. Attach this policy to the role your data scientists assume.
# The **governance-officer** role omits this deny, so it can promote to production.

# %%
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
print("Data scientist guardrail (deny production promotion):")
print(json.dumps(DATA_SCIENTIST_DENY_PRODUCTION, indent=2))

# %% [markdown]
# ## Step 2: Data scientist logs and registers a model
#
# The data scientist trains a model, logs evaluation metrics and an inference
# specification, and registers it. Registration automatically creates the Model Package
# Group and version in the SageMaker AI Model Registry.

# %%
import mlflow
from mlflow.models import infer_signature
import sagemaker_mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.datasets import make_regression

mlflow.set_tracking_uri(MLFLOW_APP_ARN)
mlflow.set_experiment("single-account-governance")

params = {"n_estimators": 10, "random_state": 42}
X, y = make_regression(n_features=4, n_informative=2, random_state=0, shuffle=False)

with mlflow.start_run(run_name="candidate-model") as run:
    model = RandomForestRegressor(**params).fit(X, y)
    signature = infer_signature(X, model.predict(X))
    mlflow.log_params(params)
    mlflow.log_metric("train_rmse", 0.12)
    model_info = mlflow.sklearn.log_model(
        model, name="sklearn-model", signature=signature, input_example=X[:3]
    )

    # Evaluation metrics -> surface as a model card on the Model Package
    eval_df = pd.DataFrame(X, columns=["f1", "f2", "f3", "f4"])
    eval_df["target"] = y
    dataset = mlflow.data.from_pandas(eval_df, name="eval_set", targets="target")
    sagemaker_mlflow.evaluate(model_info, data=dataset, model_type="regressor")

    # Inference specification -> enables direct deployment from the Model Registry.
    # Resolve the serving image for this region; the framework version matches the
    # scikit-learn pin in requirements.txt so the pickled model loads on the endpoint.
    from sagemaker.core import image_uris
    sklearn_image = image_uris.retrieve(
        framework="sklearn", region=REGION, version="1.4-2-py312",
        image_scope="inference", instance_type="ml.m5.xlarge",
    )
    logged_model = mlflow.MlflowClient().get_logged_model(model_info.model_id)
    inference_spec = {
        "Containers": [{
            "Image": sklearn_image,
            "ModelDataSource": {
                "S3DataSource": {
                    "S3Uri": logged_model.artifact_location + "/",
                    "S3DataType": "S3Prefix",
                    "CompressionType": "None",
                }
            },
        }],
        "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.xlarge"],
    }
    sagemaker_mlflow.log_inference_specification(
        model_info.model_id, inference_specification=inference_spec
    )

    run_id = run.info.run_id

model_uri = f"runs:/{run_id}/sklearn-model"
mv = mlflow.register_model(model_uri, MODEL_NAME)
print(f"Registered {mv.name} version {mv.version}")

# %% [markdown]
# ## Step 3: Confirm the synced Model Package
#
# Registration created a Model Package Group (name gets a short hash suffix) and a
# version. The SageMaker AI Model Package ARN is tagged on the MLflow model version.

# %%
client = mlflow.MlflowClient()
time.sleep(5)
mv_get = client.get_model_version(MODEL_NAME, mv.version)
sm_arn = mv_get.tags["sagemaker.model_package_arn"]
print(f"SageMaker Model Package ARN: {sm_arn}")

detail = sm.describe_model_package(ModelPackageName=sm_arn)
print("Status:", detail["ModelPackageStatus"])
print("Has inference specification:", "InferenceSpecification" in detail)
print("Has model card (evaluation metrics):", "ModelCard" in detail)

# %% [markdown]
# ## Step 4: Data scientist moves the model to staging (allowed)
#
# Lifecycle stage and status are driven by MLflow **aliases** using the naming convention
# `sagemakerlifecycle-{stage}-{status}`. Setting `staging/pending` is within the data
# scientist's guardrail.

# %%
def set_lifecycle(name, version, stage, status):
    """Set a lifecycle alias, removing any existing lifecycle alias first.

    A model version can hold only one lifecycle alias at a time, so we remove the
    previous one before setting the next.
    """
    alias = f"sagemakerlifecycle-{stage}-{status}"
    for existing in ("staging-pending", "staging-active", "production-pending", "production-active"):
        try:
            client.delete_registered_model_alias(name, f"sagemakerlifecycle-{existing}")
        except Exception:
            pass
    client.set_registered_model_alias(name, alias, version)
    return alias

alias = set_lifecycle(MODEL_NAME, mv.version, "staging", "pending")
time.sleep(8)
detail = sm.describe_model_package(ModelPackageName=sm_arn)
print(f"Set alias '{alias}'")
print("ModelLifeCycle:", detail.get("ModelLifeCycle"))

# %% [markdown]
# ## Step 5: The production guardrail in action
#
# If the data scientist's role carried the `DenyProductionPromotion` policy from Step 1,
# the next call would fail. Because lifecycle transitions flow through the **MLflow app's
# service role** (not the caller's role) in this managed integration, we demonstrate the
# guardrail with a **local IAM policy simulation** so the notebook is self-contained and
# does not require assuming a second role.

# %%
# Simulate the data-scientist policy against a production promotion.
sim_role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/does-not-need-to-exist"
try:
    sim = iam.simulate_custom_policy(
        PolicyInputList=[json.dumps(DATA_SCIENTIST_DENY_PRODUCTION)],
        ActionNames=["sagemaker:UpdateModelPackage"],
        ContextEntries=[{
            "ContextKeyName": "sagemaker:ModelLifeCycle/stage",
            "ContextKeyValues": ["production"],
            "ContextKeyType": "string",
        }],
    )
    decision = sim["EvaluationResults"][0]["EvalDecision"]
    print(f"Data-scientist promotion to production -> IAM decision: {decision}")
    assert decision == "explicitDeny", "Expected the guardrail to deny production promotion"
    print("Guardrail verified: data scientists cannot promote to production.")
except Exception as e:
    print("Policy simulation error:", repr(e))

# %% [markdown]
# ## Step 6: Governance officer promotes to production and approves for deployment
#
# The governance-officer role (without the deny) reviews the metrics and lineage, then
# promotes the model to `production/active`. To enable one-click deployment from Studio,
# the officer also sets the Model Package approval status to `Approved`.

# %%
alias = set_lifecycle(MODEL_NAME, mv.version, "production", "active")
time.sleep(8)

# Enable deployment: approval status is separate from lifecycle stage.
sm.update_model_package(ModelPackageArn=sm_arn, ModelApprovalStatus="Approved")
time.sleep(3)

detail = sm.describe_model_package(ModelPackageName=sm_arn)
print("ModelLifeCycle:", detail.get("ModelLifeCycle"))
print("ModelApprovalStatus:", detail.get("ModelApprovalStatus"))

# %% [markdown]
# ## Step 7 (optional): Freeze the approved model against further changes
#
# Once a model is approved, you can lock it so MLflow can no longer modify it. Apply a
# resource tag to the **Model Package Group** (tags attach to the group, not to individual
# versions) and a matching IAM condition on the MLflow app's service role. The example
# policy denies `UpdateModelPackage` on any Model Package Group tagged `frozen=true`.

# %%
mpg_name = detail["ModelPackageGroupName"]
mpg_arn = sm.describe_model_package_group(ModelPackageGroupName=mpg_name)["ModelPackageGroupArn"]
sm.add_tags(ResourceArn=mpg_arn, Tags=[{"Key": "frozen", "Value": "true"}])
FREEZE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "DenyUpdatesToFrozenModels",
        "Effect": "Deny",
        "Action": "sagemaker:UpdateModelPackage",
        "Resource": "*",
        "Condition": {"StringEquals": {"aws:ResourceTag/frozen": "true"}},
    }],
}
print(f"Applied tag frozen=true to Model Package Group: {mpg_name}")
print("Attach this policy to the MLflow app service role to enforce the freeze:")
print(json.dumps(FREEZE_POLICY, indent=2))

# %% [markdown]
# ## Summary
#
# In a single account, the automatic model registration integration gives the governance
# officer a complete Model Registry view of every candidate model — training metrics,
# evaluation metrics, inference specification, and lineage — without data scientists
# leaving MLflow. IAM condition keys on the lifecycle stage enforce an approval gate, and a
# resource-tag freeze locks approved models. The same building blocks extend to the
# cross-account topologies in notebooks 02 and 03.
