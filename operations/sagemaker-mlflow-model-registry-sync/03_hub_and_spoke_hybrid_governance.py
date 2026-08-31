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
# # Topology 3: Hub-and-spoke hybrid model governance
#
# Some regulated organizations treat the hub as a production-grade account and do **not**
# want data scientists writing into it directly. This notebook demonstrates the hybrid
# pattern for those cases.
#
# Each development account runs its **own** MLflow app with **automatic model
# registration** enabled, syncing candidate models into a **development** Model Registry
# (the same mechanism as notebook 01, but local to the dev account). When a model is
# approved in the development registry, an approval-triggered workflow **copies** the Model
# Package into the **hub** Model Registry cross-account. Data scientists never write to the
# hub; only the approved artifact crosses the boundary.
#
# ## Flow
# ```
# Dev (spoke) account                          Hub account
# ───────────────────                          ───────────
# 1. Register model on the dev MLflow app
#    [automatic model registration -> DEV Model Registry]
# 2. Dev owner approves in the dev registry
# 3. Approval-triggered workflow reads the
#    approved package and copies it ──────────> Hub Model Registry (shared dest group)
# 4.                                            Governance officer validates & approves
# ```

# %% [markdown]
# ## Prerequisites
#
# - **Two AWS accounts**: a development (spoke) account and a hub account.
# - Each development account has its **own MLflow app with Model Registry sync enabled**
#   and a development Model Registry.
# - The hub exposes a **destination Model Package Group** shared to the dev account via AWS
#   RAM, with a resource policy allowing the dev account to call `CreateModelPackage`
#   (see Step 0).
# - Python dependencies: `pip install boto3 mlflow scikit-learn sagemaker-mlflow pandas`

# %% [markdown]
# ## Configuration

# %%
import boto3
import json
import time
import os

DEV_PROFILE = "<YOUR_DEV_PROFILE>"
DEV_ACCOUNT_ID = "<DEV_ACCOUNT_ID>"          # e.g. 222222222222
HUB_PROFILE = "<YOUR_HUB_PROFILE>"
HUB_ACCOUNT_ID = "<HUB_ACCOUNT_ID>"          # e.g. 111111111111
REGION = "us-west-2"

DEV_MLFLOW_APP_ARN = "<DEV_MLFLOW_APP_ARN>"  # the DEV account's own app, e.g. arn:aws:sagemaker:us-west-2:222222222222:mlflow-app/app-XXXXXXXXXX
HUB_DEST_MPG = "hub-central-registry-from-dev"
HUB_DEST_MPG_ARN = f"arn:aws:sagemaker:{REGION}:{HUB_ACCOUNT_ID}:model-package-group/{HUB_DEST_MPG}"
MODEL_NAME = "hybrid-dev-candidate"

dev_session = boto3.Session(profile_name=DEV_PROFILE, region_name=REGION)
hub_session = boto3.Session(profile_name=HUB_PROFILE, region_name=REGION)
dev_sm = dev_session.client("sagemaker")
hub_sm = hub_session.client("sagemaker")
print("Configuration loaded.")

# %% [markdown]
# ## Step 0 (reference): Hub exposes a destination group to the dev account
#
# The hub administrator creates a destination Model Package Group, attaches a resource
# policy that lets the dev account write into it, and shares it via AWS RAM. This is a
# one-time setup performed by the hub, shown here for reference.
#
# ```python
# # (hub credentials)
# hub_sm.create_model_package_group(ModelPackageGroupName=HUB_DEST_MPG)
# hub_sm.put_model_package_group_policy(
#     ModelPackageGroupName=HUB_DEST_MPG,
#     ResourcePolicy=json.dumps({
#         "Version": "2012-10-17",
#         "Statement": [{
#             "Sid": "DevCopyIn",
#             "Effect": "Allow",
#             "Principal": {"AWS": f"arn:aws:iam::{DEV_ACCOUNT_ID}:root"},
#             "Action": [
#                 "sagemaker:DescribeModelPackageGroup", "sagemaker:CreateModelPackage",
#                 "sagemaker:DescribeModelPackage", "sagemaker:ListModelPackages",
#                 "sagemaker:UpdateModelPackage",
#             ],
#             "Resource": [HUB_DEST_MPG_ARN, HUB_DEST_MPG_ARN.replace("model-package-group", "model-package") + "/*"],
#         }],
#     }),
# )
# # RAM share HUB_DEST_MPG_ARN to DEV_ACCOUNT_ID with the AllowDeploy managed permission,
# # then the dev account accepts the invitation.
# ```

# %% [markdown]
# ## Step 1: Data scientist registers a model in the development account
#
# Using dev credentials against the dev MLflow app, the data scientist logs and registers
# a candidate. Automatic model registration syncs it into the **development** Model
# Registry — entirely within the dev account.

# %%
os.environ["AWS_PROFILE"] = DEV_PROFILE
os.environ["AWS_DEFAULT_REGION"] = REGION

import mlflow
from mlflow.models import infer_signature
import sagemaker_mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.datasets import make_regression

mlflow.set_tracking_uri(DEV_MLFLOW_APP_ARN)
mlflow.set_experiment("hybrid-dev")
print(f"[Dev] Tracking URI: {mlflow.get_tracking_uri()}")

params = {"n_estimators": 10, "random_state": 42}
X, y = make_regression(n_features=4, n_informative=2, random_state=0, shuffle=False)

with mlflow.start_run(run_name="dev-candidate") as run:
    model = RandomForestRegressor(**params).fit(X, y)
    signature = infer_signature(X, model.predict(X))
    mlflow.log_params(params)
    mlflow.log_metric("train_rmse", 0.12)
    model_info = mlflow.sklearn.log_model(
        model, name="sklearn-model", signature=signature, input_example=X[:3]
    )

    eval_df = pd.DataFrame(X, columns=["f1", "f2", "f3", "f4"])
    eval_df["target"] = y
    dataset = mlflow.data.from_pandas(eval_df, name="eval_set", targets="target")
    sagemaker_mlflow.evaluate(model_info, data=dataset, model_type="regressor")

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
            "ModelDataSource": {"S3DataSource": {
                "S3Uri": logged_model.artifact_location + "/",
                "S3DataType": "S3Prefix", "CompressionType": "None"}},
        }],
        "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.xlarge"],
    }
    sagemaker_mlflow.log_inference_specification(model_info.model_id, inference_specification=inference_spec)
    run_id = run.info.run_id

mv = mlflow.register_model(f"runs:/{run_id}/sklearn-model", MODEL_NAME)
client = mlflow.MlflowClient()
time.sleep(5)
dev_pkg_arn = client.get_model_version(MODEL_NAME, mv.version).tags["sagemaker.model_package_arn"]
print(f"[Dev] Registered {mv.name} v{mv.version}")
print(f"[Dev] Model Package in DEV registry: {dev_pkg_arn}")

# %% [markdown]
# ## Step 2: Dev owner approves the model in the development registry
#
# The development account's model owner reviews the candidate and approves it locally. This
# approval is the trigger for promotion to the hub. In production you would drive the next
# step from an Amazon EventBridge rule on the Model Package state change; here we perform it
# inline.

# %%
dev_sm.update_model_package(ModelPackageArn=dev_pkg_arn, ModelApprovalStatus="Approved")
time.sleep(3)
dev_detail = dev_sm.describe_model_package(ModelPackageName=dev_pkg_arn)
print("[Dev] Approval status:", dev_detail["ModelApprovalStatus"])

# %% [markdown]
# ## Step 3: Approval-triggered workflow copies the model into the hub
#
# The workflow reads the approved package from the dev registry and calls
# `CreateModelPackage` against the **hub's shared destination group** using dev
# credentials. Because the hub granted the dev account `CreateModelPackage` on that group,
# the copy lands in the hub registry without the data scientist ever writing to the hub
# directly. The copied package carries the inference specification and the metadata linking
# it back to its source.

# %%
def copy_package_to_hub(source_arn, dest_mpg_arn):
    """Copy an approved dev Model Package into the hub destination group (cross-account)."""
    src = dev_sm.describe_model_package(ModelPackageName=source_arn)
    kwargs = {
        "ModelPackageGroupName": dest_mpg_arn,
        "ModelPackageDescription": f"Copied from dev registry {source_arn}",
        "ModelApprovalStatus": "PendingManualApproval",  # hub governance re-validates
        "CustomerMetadataProperties": {
            "source_model_package_arn": source_arn,
            "source_account": DEV_ACCOUNT_ID,
        },
    }
    if "InferenceSpecification" in src:
        kwargs["InferenceSpecification"] = src["InferenceSpecification"]
    return dev_sm.create_model_package(**kwargs)["ModelPackageArn"]

hub_pkg_arn = copy_package_to_hub(dev_pkg_arn, HUB_DEST_MPG_ARN)
print(f"[Hub] Copied into hub registry: {hub_pkg_arn}")

# %% [markdown]
# ## Step 4: Governance officer validates and approves in the hub
#
# The governance officer, working with hub credentials, sees the copied package in the hub
# registry (with a pointer back to its dev source), validates it, and approves it for
# deployment.

# %%
hub_detail = hub_sm.describe_model_package(ModelPackageName=hub_pkg_arn)
print("[Hub] Package status:", hub_detail["ModelPackageStatus"])
print("[Hub] Source metadata:", hub_detail.get("CustomerMetadataProperties"))
print("[Hub] Has inference specification:", "InferenceSpecification" in hub_detail)

hub_sm.update_model_package(ModelPackageArn=hub_pkg_arn, ModelApprovalStatus="Approved")
time.sleep(3)
hub_detail = hub_sm.describe_model_package(ModelPackageName=hub_pkg_arn)
print("[Hub] Approval status:", hub_detail["ModelApprovalStatus"])

# %% [markdown]
# ## Summary
#
# In the hybrid topology, each development account keeps a self-contained loop: MLflow
# experimentation and automatic model registration into a **development** Model Registry,
# with no write access to the hub. Only when a model is approved locally does a workflow
# copy it into the hub registry, preserving the inference specification and a link back to
# the source package. This satisfies regulated environments that require the hub to stay
# isolated from day-to-day development activity while still giving governance officers a
# central place to validate and approve production candidates.
