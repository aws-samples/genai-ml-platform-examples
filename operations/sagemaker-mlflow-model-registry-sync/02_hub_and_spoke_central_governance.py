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
# # Topology 2: Hub-and-spoke central model governance
#
# This notebook demonstrates centralized model governance using **automatic model
# registration** from managed MLflow on Amazon SageMaker AI, combined with **AWS Resource
# Access Manager (AWS RAM)** cross-account sharing.
#
# The MLflow app and the central Model Registry live in a **hub** account. The hub shares
# the MLflow app with a **spoke** (development) account. Data scientists in the spoke
# register candidate models against the shared MLflow app; automatic model registration
# creates the corresponding Model Package Group and version **in the hub** account. The
# governance officer validates and approves models centrally in the hub.
#
# This builds on the pattern described in
# [Centralize model governance with SageMaker Model Registry and AWS RAM sharing](https://aws.amazon.com/blogs/machine-learning/centralize-model-governance-with-sagemaker-model-registry-resource-access-manager-sharing/).
#
# ## Flow
# ```
# Hub account                                Spoke (development) account
# ─────────────                              ───────────────────────────
# 1. RAM share MLflow app ─────────────────> Accept invitation
# 2.                                         Register model on the shared app
#    [automatic model registration creates the Model Package Group in the hub]
# 3. RAM share Model Package Group ────────> Accept invitation
# 4. Governance officer reviews & approves   Describe / list the shared group
# ```

# %% [markdown]
# ## Prerequisites
#
# - **Two AWS accounts**: a hub (owns the MLflow app and the central Model Registry) and a
#   spoke (development). They do **not** need to be in the same AWS Organization; this
#   notebook uses external principals with invitation acceptance.
# - AWS CLI profiles for both accounts with administrative access.
# - An **MLflow app with Model Registry sync enabled** in the hub (see notebook 01, Step 0).
# - The hub artifact S3 bucket needs a **cross-account bucket policy** so the spoke can
#   read and write model artifacts (see Step 1).
# - Python dependencies: `pip install boto3 mlflow scikit-learn sagemaker-mlflow pandas`

# %% [markdown]
# ## Configuration

# %%
import boto3
import json
import time
import os

HUB_PROFILE = "<YOUR_HUB_PROFILE>"
HUB_ACCOUNT_ID = "<HUB_ACCOUNT_ID>"          # e.g. 111111111111

SPOKE_PROFILE = "<YOUR_SPOKE_PROFILE>"
SPOKE_ACCOUNT_ID = "<SPOKE_ACCOUNT_ID>"      # e.g. 222222222222

REGION = "us-west-2"
MLFLOW_APP_ARN = "<HUB_MLFLOW_APP_ARN>"      # the HUB app, e.g. arn:aws:sagemaker:us-west-2:111111111111:mlflow-app/app-XXXXXXXXXX
HUB_ARTIFACT_BUCKET = "<HUB_ARTIFACT_BUCKET>"  # the hub MLflow app's S3 artifact bucket
MODEL_NAME = "hub-spoke-central-demo"

hub_session = boto3.Session(profile_name=HUB_PROFILE, region_name=REGION)
spoke_session = boto3.Session(profile_name=SPOKE_PROFILE, region_name=REGION)

hub_ram = hub_session.client("ram")
hub_sm = hub_session.client("sagemaker")
hub_s3 = hub_session.client("s3")
spoke_ram = spoke_session.client("ram")
spoke_sm = spoke_session.client("sagemaker")

print("Configuration loaded.")


# %%
def accept_pending_invitation(ram_client, sender_account_id, name_contains=None, retries=6):
    """Find and accept a pending RAM invitation from a given sender. Idempotent."""
    for attempt in range(retries):
        invs = ram_client.get_resource_share_invitations()["resourceShareInvitations"]
        pending = [
            i for i in invs
            if i["status"] == "PENDING" and i["senderAccountId"] == sender_account_id
            and (name_contains is None or name_contains in i.get("resourceShareName", ""))
        ]
        if pending:
            arn = pending[0]["resourceShareInvitationArn"]
            ram_client.accept_resource_share_invitation(resourceShareInvitationArn=arn)
            return f"accepted: {arn}"
        time.sleep(5)
    return "no pending invitation found (may already be accepted)"


# %% [markdown]
# ## Step 1: Allow the spoke to use the hub artifact bucket
#
# Model artifacts are stored in the hub's S3 bucket. For the spoke to upload artifacts
# during registration, add a cross-account bucket policy granting the spoke account access.

# %%
bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "CrossAccountSpokeAccess",
        "Effect": "Allow",
        "Principal": {"AWS": f"arn:aws:iam::{SPOKE_ACCOUNT_ID}:root"},
        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"],
        "Resource": [
            f"arn:aws:s3:::{HUB_ARTIFACT_BUCKET}",
            f"arn:aws:s3:::{HUB_ARTIFACT_BUCKET}/*",
        ],
    }],
}
hub_s3.put_bucket_policy(Bucket=HUB_ARTIFACT_BUCKET, Policy=json.dumps(bucket_policy))
print(f"Cross-account bucket policy applied to s3://{HUB_ARTIFACT_BUCKET}")

# %% [markdown]
# ## Step 2: Hub shares the MLflow app with the spoke
#
# The hub creates a RAM resource share for the MLflow app and the spoke accepts it. Using
# `allowExternalPrincipals=True` lets the share work even when the accounts are not in the
# same AWS Organization.

# %%
existing = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
app_share = next((s for s in existing if s["name"] == "mlflow-app-blog-share"
                  and s["status"] in ("ACTIVE", "PENDING")), None)
if app_share:
    print(f"MLflow app share already exists: {app_share['resourceShareArn']}")
else:
    resp = hub_ram.create_resource_share(
        name="mlflow-app-blog-share",
        resourceArns=[MLFLOW_APP_ARN],
        principals=[SPOKE_ACCOUNT_ID],
        allowExternalPrincipals=True,
    )
    print(f"Created MLflow app share: {resp['resourceShare']['resourceShareArn']}")

time.sleep(5)
print(accept_pending_invitation(spoke_ram, HUB_ACCOUNT_ID, name_contains="mlflow-app-blog-share"))

# %% [markdown]
# ## Step 3: Spoke registers a candidate model on the shared MLflow app
#
# Using **spoke credentials**, the data scientist logs a run and registers a model on the
# hub's MLflow app. Automatic model registration creates the Model Package Group and
# version in the hub account, synchronously with the register call.

# %%
os.environ["AWS_PROFILE"] = SPOKE_PROFILE
os.environ["AWS_DEFAULT_REGION"] = REGION

import mlflow
from mlflow.models import infer_signature
import sagemaker_mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.datasets import make_regression

mlflow.set_tracking_uri(MLFLOW_APP_ARN)
mlflow.set_experiment("hub-spoke-central")
print(f"[Spoke] Tracking URI: {mlflow.get_tracking_uri()}")

params = {"n_estimators": 10, "random_state": 42}
X, y = make_regression(n_features=4, n_informative=2, random_state=0, shuffle=False)

with mlflow.start_run(run_name="spoke-candidate") as run:
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
print(f"[Spoke] Registered {mv.name} version {mv.version}")

client = mlflow.MlflowClient()
time.sleep(5)
sm_arn = client.get_model_version(MODEL_NAME, mv.version).tags["sagemaker.model_package_arn"]
print(f"[Hub] Model Package created in hub account: {sm_arn}")

# %% [markdown]
# ## Step 4: Locate the synced Model Package Group in the hub
#
# Automatic model registration appends a short hash suffix to the group name
# (`model-name` becomes `model-name-<hash>`), so we discover it by prefix in the hub.

# %%
resp = hub_sm.list_model_package_groups(NameContains=MODEL_NAME)
mpgs = sorted(resp.get("ModelPackageGroupSummaryList", []),
              key=lambda x: x["CreationTime"], reverse=True)
mpg_arn = mpgs[0]["ModelPackageGroupArn"]
mpg_name = mpgs[0]["ModelPackageGroupName"]
print(f"[Hub] Model Package Group: {mpg_name}")
print(f"[Hub] ARN: {mpg_arn}")

# %% [markdown]
# ## Step 5: Hub shares the Model Package Group back to the spoke
#
# The hub attaches a resource policy to the group and creates a RAM share using the
# `AllowDeploy` managed permission, which lets the spoke describe and deploy the shared
# models. The spoke accepts the invitation.

# %%
mpg_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "CrossAccountMPGAccess",
        "Effect": "Allow",
        "Principal": {"AWS": f"arn:aws:iam::{SPOKE_ACCOUNT_ID}:root"},
        "Action": [
            "sagemaker:DescribeModelPackageGroup",
            "sagemaker:DescribeModelPackage",
            "sagemaker:ListModelPackages",
            "sagemaker:CreateModelPackage",
            "sagemaker:UpdateModelPackage",
            "sagemaker:CreateModel",
        ],
        "Resource": [
            mpg_arn,
            f"arn:aws:sagemaker:{REGION}:{HUB_ACCOUNT_ID}:model-package/{mpg_name}/*",
        ],
    }],
}
hub_sm.put_model_package_group_policy(
    ModelPackageGroupName=mpg_name, ResourcePolicy=json.dumps(mpg_policy)
)
print(f"[Hub] Resource policy attached to {mpg_name}")

existing = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
mpg_share = next((s for s in existing if s["name"] == f"mpg-blog-share-{mpg_name}"
                  and s["status"] in ("ACTIVE", "PENDING")), None)
if mpg_share:
    print(f"[Hub] MPG share already exists: {mpg_share['resourceShareArn']}")
else:
    resp = hub_ram.create_resource_share(
        name=f"mpg-blog-share-{mpg_name}",
        resourceArns=[mpg_arn],
        principals=[SPOKE_ACCOUNT_ID],
        allowExternalPrincipals=True,
        permissionArns=["arn:aws:ram::aws:permission/AWSRAMPermissionSageMakerModelPackageGroupAllowDeploy"],
    )
    print(f"[Hub] Created MPG share: {resp['resourceShare']['resourceShareArn']}")

time.sleep(10)
print(accept_pending_invitation(spoke_ram, HUB_ACCOUNT_ID, name_contains=f"mpg-blog-share-{mpg_name}"))

# %% [markdown]
# ## Step 6: Verify the spoke can access the shared Model Package Group
#
# From spoke credentials, describe and list the shared group. Cross-account access
# requires the **full ARN** of the group, not just its name.

# %%
print(f"[Spoke] Describing shared group: {mpg_arn}")
desc = spoke_sm.describe_model_package_group(ModelPackageGroupName=mpg_arn)
print("  Name:", desc["ModelPackageGroupName"])
print("  Status:", desc["ModelPackageGroupStatus"])

pkgs = spoke_sm.list_model_packages(ModelPackageGroupName=mpg_arn)
for p in pkgs.get("ModelPackageSummaryList", []):
    print("  Package:", p["ModelPackageArn"], "approval:", p.get("ModelApprovalStatus"))
print("Spoke can access the shared Model Package Group via RAM.")

# %% [markdown]
# ## Step 7: Governance officer approves the model centrally in the hub
#
# The governance officer, working in the hub, reviews the synced training metrics,
# evaluation model card, and lineage, then promotes the model to production and approves
# it for deployment. Lifecycle stage is driven by an MLflow alias; approval status enables
# one-click deployment.

# %%
def set_lifecycle(name, version, stage, status):
    alias = f"sagemakerlifecycle-{stage}-{status}"
    for existing in ("staging-pending", "staging-active", "production-pending", "production-active"):
        try:
            client.delete_registered_model_alias(name, f"sagemakerlifecycle-{existing}")
        except Exception:
            pass
    client.set_registered_model_alias(name, alias, version)
    return alias

set_lifecycle(MODEL_NAME, mv.version, "production", "active")
time.sleep(8)
hub_sm.update_model_package(ModelPackageArn=sm_arn, ModelApprovalStatus="Approved")
time.sleep(3)
detail = hub_sm.describe_model_package(ModelPackageName=sm_arn)
print("[Hub] ModelLifeCycle:", detail.get("ModelLifeCycle"))
print("[Hub] ModelApprovalStatus:", detail.get("ModelApprovalStatus"))

# %% [markdown]
# ## Summary
#
# The spoke's data scientists never left MLflow, yet every candidate model they registered
# appeared automatically in the hub's central Model Registry with its training metrics,
# evaluation model card, inference specification, and lineage. The governance officer
# reviews and approves centrally in the hub, and the approved model is shared back to the
# spoke for deployment. This gives a single, authoritative view of candidate models across
# development teams while keeping experimentation self-service.
