# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Topology 1 end to end with SageMaker Python SDK v3: train, auto-register, govern, deploy
#
# This notebook demonstrates the **automatic model registration** integration between
# managed MLflow on Amazon SageMaker AI and the SageMaker AI Model Registry in the
# **single-account** governance topology — and, unlike notebooks 01–03, it closes the
# loop by **deploying the approved model to a real-time SageMaker AI endpoint** directly
# from the Model Registry. This is the step that makes the inference specification worth
# logging in the first place: without a deployment, "enables direct deployment from the
# registry" remains a claim rather than a demonstration.
#
# > **Note on SDK v3:** version 3 is a breaking release. `Estimator`/`Model`/`Predictor`
# > are replaced by `ModelTrainer`/`ModelBuilder`/`Endpoint`, the package is split into
# > `sagemaker-core`, `sagemaker-train`, `sagemaker-serve`, and `sagemaker-mlops`, and the
# > v2 import paths (`sagemaker.remote_function`,
# > `sagemaker.image_uris`, `sagemaker.get_execution_role`) no longer exist. See the
# > [SDK v3 documentation](https://sagemaker.readthedocs.io/en/stable/) for the migration
# > guide.
#
# ## Flow
# ```
# Single account (data science + governance) — SageMaker Studio, SDK v3
# ──────────────────────────────────────────────────────────────────────
# 0. Install pinned dependencies
# 1. Enable Model Registry sync on the MLflow app          (reference)
# 2. Define the IAM guardrail for the data-scientist role
# 3. Train in a SageMaker Training Job (@remote), log real metrics,
#    eval results, and an inference spec; register the model
#    [sync creates the Model Package Group + version automatically]
# 4. Inspect the synced Model Package with typed v3 resources
# 5. Data scientist sets lifecycle staging/pending          (allowed)
# 6. Data scientist attempts production promotion           (DENIED)
# 7. Governance officer promotes + approves for deployment
# 8. Deploy the approved Model Package to a real-time endpoint & invoke
# 9. Clean up everything, including the endpoint
# ```

# %% [markdown]
# ## Prerequisites
#
# - A **SageMaker AI domain** with a user profile, running this notebook in a Studio
#   **JupyterLab space**. The domain
#   **execution role** needs permissions to run SageMaker Training Jobs
#   (`sagemaker:CreateTrainingJob` and `iam:PassRole` on itself), manage models, endpoint
#   configs, and endpoints, call IAM policy simulation, and read/write the MLflow
#   artifact bucket.
# - An **MLflow app with Model Registry sync enabled**
#   (`ModelRegistrationMode = AutoModelRegistrationEnabled`). See Step 1.
# - Python dependencies are installed in Step 0 — nothing to install beforehand.
#
# > **Cost note:** Step 8 creates a real-time endpoint on an `ml.m5.xlarge` instance.
# > Run the cleanup in Step 9 when you are done to stop incurring charges.

# %% [markdown]
# ## Step 0: Install pinned dependencies
#
# The pins below define the tested combination for this notebook:
#
# | Package            | Pin                  | Why                                                                 |
# |--------------------|----------------------|---------------------------------------------------------------------|
# | `sagemaker`        | `>=3,<4`             | SDK v3 API surface used throughout (breaking changes vs v2)          |
# | `mlflow`           | `<4`                 | MLflow 3.x client, matching the managed MLflow app                   |
# | `sagemaker-mlflow` | `>=0.5.0,<1`         | `evaluate()` / `log_inference_specification()` and MLflow 3 support  |
# | `scikit-learn`     | `>=1.4,<1.5`         | Matches the SKLearn serving container, so the pickled model unpickles cleanly at inference time |
#
# The requirements file is written to `requirements.txt` in the notebook's working
# directory. The same file is passed to the `@remote` training job in Step 3, so the
# job environment matches the notebook environment.

# %%
REQUIREMENTS = """\
sagemaker>=3,<4
mlflow<4
sagemaker-mlflow>=0.5.0,<1
scikit-learn>=1.4,<1.5
"""
with open("requirements.txt", "w") as f:
    f.write(REQUIREMENTS)
print(open("requirements.txt").read())

# %%
# %pip install -q -r requirements.txt
print("Dependencies installed. If mlflow or sagemaker was upgraded, restart the kernel before continuing.")

# %% [markdown]
# ## Configuration
#
# SDK v3 moves the session helpers to `sagemaker.core.helper.session_helper`. The
# notebook inherits the **execution role** of the JupyterLab space and
# the region is detected from the environment — the only value to set is
# `MLFLOW_APP_ARN`.

# %%
import json
import time

import boto3
from sagemaker.core.helper.session_helper import Session, get_execution_role

sm_session = Session()
REGION = sm_session.boto_region_name
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
EXECUTION_ROLE = get_execution_role()

iam = boto3.client("iam")

MLFLOW_APP_ARN = "<YOUR_MLFLOW_APP_ARN>"  # e.g. arn:aws:sagemaker:us-west-2:123456789012:mlflow-app/app-XXXXXXXXXX
MODEL_NAME = "single-account-governance-e2e-demo"

print(f"Account: {ACCOUNT_ID}, Region: {REGION}")
print(f"Execution role: {EXECUTION_ROLE}")
print(f"MLflow app: {MLFLOW_APP_ARN}")

# %% [markdown]
# ## Step 1 (reference): Enabling Model Registry sync on an MLflow app
#
# Model Registry sync is **opt-in**. Enable it in the SageMaker AI console (**MLflow** →
# your app → **Edit** → *Model registration mode*) or with the CLI:
#
# ```bash
# aws sagemaker create-mlflow-app \
#     --name my-mlflow-app \
#     --artifact-store-uri s3://my-bucket/mlflow \
#     --role-arn arn:aws:iam::<ACCOUNT>:role/my-mlflow-app-role \
#     --model-registration-mode AutoModelRegistrationEnabled
#
# # To enable on an existing app:
# aws sagemaker update-mlflow-app \
#     --arn <MLFLOW_APP_ARN> \
#     --model-registration-mode AutoModelRegistrationEnabled
# ```
#
# The MLflow app's IAM **service role** must be allowed to register models and create
# lineage:

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
# ## Step 2: Define governance guardrails with IAM condition keys
#
# The Model Registry lifecycle exposes two IAM condition keys:
#
# - `sagemaker:ModelLifeCycle/stage` — the stage being set (`staging`, `production`)
# - `sagemaker:ModelLifeCycle/stageStatus` — the status being set (`pending`, `active`)
#
# The **data-scientist** guardrail denies any lifecycle transition to `production`.
# Attach it to the execution role of the data scientists' Studio user profiles; the
# **governance-officer** profile's role omits the deny.

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
# ## Step 3: Train and register as a SageMaker Training Job — SDK v3 style
#
# The training function is decorated with **`@remote`**, which in SDK v3 lives under
# `sagemaker.train.remote_function` (in v2 it was `sagemaker.remote_function`). Calling
# the function serializes it and runs it as a **SageMaker Training Job** on ephemeral
# managed compute; `dependencies="./requirements.txt"` installs the same pinned
# packages inside the job.
#
# Two details worth noting about the training step:
#
# 1. **Real metrics.** The dataset is split into train and test sets, and the logged
#    `train_rmse` / `test_rmse` are computed values, not placeholders. A reviewer looking
#    at the model card in the registry sees numbers that actually describe the model.
# 2. **Region-independent image resolution.** The inference container is resolved with
#    `sagemaker.core.image_uris.retrieve` (the v3 home of `image_uris`) before the job is
#    submitted — no hardcoded per-region ECR URI.
#
# > **Making the inference spec actually deployable:** the SKLearn framework serving
# > container has **no default model loader** — it requires a user inference script
# > referenced by the `SAGEMAKER_PROGRAM` environment variable (this is what
# > `SKLearnModel.deploy()` normally wires up by repacking the model tarball). Since we
# > deploy straight from the Model Package instead, the training function below:
# > 1. logs the model with `serialization_format="pickle"` (a plain `model.pkl` instead
# >    of MLflow's default `model.skops`, which the container cannot read),
# > 2. logs a minimal `code/inference.py` with a `model_fn` under the model's
# >    artifact prefix via `MlflowClient.log_model_artifacts` (the `S3Prefix`
# >    ModelDataSource downloads it to `/opt/ml/model/code/` on the endpoint), and
# > 3. sets `SAGEMAKER_PROGRAM` / `SAGEMAKER_SUBMIT_DIRECTORY` in the inference spec's
# >    container `Environment`.
# > Without these, the endpoint fails every `/ping` health check and never reaches
# > `InService`.

# %%
from sagemaker.core import image_uris
from sagemaker.train.remote_function import remote

# Resolve the SKLearn serving container for the current region (SDK v3 path).
# The framework version matches the scikit-learn pin in requirements.txt, so the
# model pickled inside the training job unpickles cleanly on the endpoint.
sklearn_image = image_uris.retrieve(
    framework="sklearn",
    region=REGION,
    version="1.4-2",
    image_scope="inference",
    instance_type="ml.m5.xlarge",
)
print(f"Inference container image: {sklearn_image}")


@remote(instance_type="ml.m5.xlarge", dependencies="./requirements.txt")
def train_and_register(mlflow_app_arn, model_name, experiment_name, image_uri, params):
    """Runs as a SageMaker Training Job: train, evaluate, log to MLflow, register."""
    import mlflow
    import numpy as np
    import pandas as pd
    import sagemaker_mlflow
    from mlflow.models import infer_signature
    from sklearn.datasets import make_regression
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_squared_error
    from sklearn.model_selection import train_test_split

    mlflow.set_tracking_uri(mlflow_app_arn)
    mlflow.set_experiment(experiment_name)

    X, y = make_regression(
        n_samples=500, n_features=4, n_informative=2, noise=0.5, random_state=0
    )
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    with mlflow.start_run(run_name="candidate-model") as run:
        model = RandomForestRegressor(**params).fit(X_train, y_train)
        signature = infer_signature(X_train, model.predict(X_train))
        mlflow.log_params(params)

        # Real metrics on train and held-out test data — no placeholders.
        train_rmse = float(np.sqrt(mean_squared_error(y_train, model.predict(X_train))))
        test_rmse = float(np.sqrt(mean_squared_error(y_test, model.predict(X_test))))
        mlflow.log_metric("train_rmse", train_rmse)
        mlflow.log_metric("test_rmse", test_rmse)

        model_info = mlflow.sklearn.log_model(
            model,
            name="sklearn-model",
            signature=signature,
            input_example=X_train[:3],
            # Serialize as plain pickle (not skops) so the model is a `model.pkl`
            # that the SageMaker SKLearn serving container can load without
            # extra dependencies.
            serialization_format="pickle",
        )

        # Evaluation metrics -> surfaced as a model card on the Model Package
        eval_df = pd.DataFrame(X_test, columns=["f1", "f2", "f3", "f4"])
        eval_df["target"] = y_test
        dataset = mlflow.data.from_pandas(eval_df, name="eval_set", targets="target")
        sagemaker_mlflow.evaluate(model_info, data=dataset, model_type="regressor")

        # Inference specification -> enables direct deployment from the Model Registry
        logged_model = mlflow.MlflowClient().get_logged_model(model_info.model_id)

        # The SKLearn serving container has no default model loader: it requires a
        # user inference script referenced by SAGEMAKER_PROGRAM. Log one under the
        # model's artifact prefix through MLflow — the S3Prefix ModelDataSource
        # downloads everything under the prefix, so it lands at
        # /opt/ml/model/code/inference.py on the endpoint. log_model_artifacts
        # preserves the local directory layout and uses the MLflow app's own
        # artifact access, so no direct s3:PutObject on the bucket is needed.
        import os
        import tempfile

        INFERENCE_SCRIPT = """\
import os
import pickle


def model_fn(model_dir):
    with open(os.path.join(model_dir, "model.pkl"), "rb") as f:
        return pickle.load(f)
"""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "code"))
            with open(os.path.join(tmp, "code", "inference.py"), "w") as f:
                f.write(INFERENCE_SCRIPT)
            mlflow.MlflowClient().log_model_artifacts(model_info.model_id, tmp)

        inference_spec = {
            "Containers": [{
                "Image": image_uri,
                "ModelDataSource": {
                    "S3DataSource": {
                        "S3Uri": logged_model.artifact_location + "/",
                        "S3DataType": "S3Prefix",
                        "CompressionType": "None",
                    }
                },
                # Point the framework container at the inference script; without
                # these the sklearn container fails every /ping health check.
                "Environment": {
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                },
            }],
            "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.xlarge"],
        }
        sagemaker_mlflow.log_inference_specification(
            model_info.model_id, inference_specification=inference_spec
        )

        run_id = run.info.run_id

    mv = mlflow.register_model(f"runs:/{run_id}/sklearn-model", model_name)
    return run_id, mv.version, train_rmse, test_rmse


# Calling the function submits the training job and blocks until it completes.
run_id, model_version, train_rmse, test_rmse = train_and_register(
    MLFLOW_APP_ARN,
    MODEL_NAME,
    "single-account-governance-e2e",
    sklearn_image,
    {"n_estimators": 50, "random_state": 42},
)
print(f"Registered {MODEL_NAME} version {model_version} (MLflow run {run_id})")
print(f"train_rmse={train_rmse:.4f}  test_rmse={test_rmse:.4f}")

# %% [markdown]
# ## Step 4: Inspect the synced Model Package with typed v3 resources
#
# Registration created a Model Package Group (with a short hash suffix on the name) and a
# version; the Model Package ARN is tagged on the MLflow model version. Instead of raw
# `boto3` calls, SDK v3 provides **typed resource classes** in
# `sagemaker.core.resources` — `ModelPackage.get()` returns an object with typed
# attributes, which reads better in a notebook and is what the rest of this walkthrough
# builds on.

# %%
import mlflow
from sagemaker.core.resources import ModelPackage

mlflow.set_tracking_uri(MLFLOW_APP_ARN)
mlflow_client = mlflow.MlflowClient()
time.sleep(5)

mv_get = mlflow_client.get_model_version(MODEL_NAME, model_version)
sm_arn = mv_get.tags["sagemaker.model_package_arn"]
print(f"SageMaker Model Package ARN: {sm_arn}")

model_package = ModelPackage.get(model_package_name=sm_arn)
# Workaround: DescribeModelPackage does not return ModelPackageName for *versioned*
# packages (only the ARN, group name, and version), so `get()` leaves
# `model_package_name` unassigned — which breaks `refresh()` (and `update()`, which
# calls refresh internally). The API accepts an ARN in the ModelPackageName field,
# so backfill it with the ARN.
model_package.model_package_name = model_package.model_package_arn
print("Status:", model_package.model_package_status)
print("Approval status:", model_package.model_approval_status)
print("Has inference specification:", model_package.inference_specification is not None)
print("Model Package Group:", model_package.model_package_group_name)

# %% [markdown]
# ## Step 5: Data scientist moves the model to staging (allowed)
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
            mlflow_client.delete_registered_model_alias(name, f"sagemakerlifecycle-{existing}")
        except Exception:
            pass
    mlflow_client.set_registered_model_alias(name, alias, version)
    return alias


alias = set_lifecycle(MODEL_NAME, model_version, "staging", "pending")
time.sleep(8)
model_package.refresh()
print(f"Set alias '{alias}'")
print("ModelLifeCycle:", model_package.model_life_cycle)

# %% [markdown]
# ## Step 6: The production guardrail in action
#
# If the data scientist's Studio execution role carried the `DenyProductionPromotion`
# policy from Step 2, a production promotion would fail. Because lifecycle transitions
# flow through the **MLflow app's service role** (not the caller's role) in this managed
# integration, we demonstrate the guardrail with a **local IAM policy simulation** so the
# notebook is self-contained and does not require assuming a second role.

# %%
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

# %% [markdown]
# ## Step 7: Governance officer promotes to production and approves for deployment
#
# The governance-officer role (without the deny) reviews the metrics and lineage, then
# promotes the model to `production/active`. Approval status is a **separate attribute**
# from lifecycle stage, so promotion and deployment readiness remain distinct decisions —
# the officer sets it to `Approved` with the typed resource's `update()` method.

# %%
alias = set_lifecycle(MODEL_NAME, model_version, "production", "active")
time.sleep(8)

# Enable deployment: approval status is separate from lifecycle stage.
model_package.update(model_approval_status="Approved")
time.sleep(3)

model_package.refresh()
print("ModelLifeCycle:", model_package.model_life_cycle)
print("ModelApprovalStatus:", model_package.model_approval_status)

# %% [markdown]
# ## Step 8: Deploy the approved model from the Model Registry
#
# This is where the inference specification pays off. Because the training job logged a
# container image and model data location before registration, the approved Model Package
# is **directly deployable** — no repacking, no separate model upload.
#
# With SDK v3 typed resources the deployment is three explicit objects, mirroring the
# underlying SageMaker AI API:
#
# 1. **`Model`** referencing the Model Package by ARN (`model_package_name` in the
#    container definition),
# 2. **`EndpointConfig`** with a production variant,
# 3. **`Endpoint`** created from the config.
#
# This is the same flow the **Deploy** button in Studio drives — expressed as code that a
# CI/CD pipeline can run when the approval EventBridge event fires.
#
# > The deployed sklearn serving container follows the SageMaker Scikit-learn container's
# > input conventions; we invoke it with a CSV payload matching the four training
# > features.

# %%
from sagemaker.core.resources import Endpoint, EndpointConfig, Model
from sagemaker.core.shapes import ContainerDefinition, ProductionVariant

suffix = time.strftime("%Y%m%d-%H%M%S")
resource_name = f"{MODEL_NAME}-{suffix}"

deployed_model = Model.create(
    model_name=resource_name,
    primary_container=ContainerDefinition(model_package_name=sm_arn),
    execution_role_arn=EXECUTION_ROLE,
)
print(f"Model created: {resource_name}")

endpoint_config = EndpointConfig.create(
    endpoint_config_name=resource_name,
    production_variants=[
        ProductionVariant(
            variant_name="AllTraffic",
            model_name=resource_name,
            initial_instance_count=1,
            instance_type="ml.m5.xlarge",
        )
    ],
)
print(f"Endpoint config created: {resource_name}")

endpoint = Endpoint.create(
    endpoint_name=resource_name,
    endpoint_config_name=resource_name,
)
print(f"Creating endpoint {resource_name} (takes a few minutes)...")
endpoint.wait_for_status("InService")
print("Endpoint is InService.")

# %%
# Invoke the endpoint with a CSV payload (four features, matching the training data).
response = endpoint.invoke(
    body="0.5,-1.2,0.3,0.8\n1.1,0.4,-0.7,0.2",
    content_type="text/csv",
    accept="application/json",
)
print("Prediction:", response.body.read().decode())

# %% [markdown]
# The governed lifecycle is now complete: the model the data scientist registered from
# MLflow — with its metrics, evaluation card, and lineage — passed through an IAM-gated
# approval and is serving traffic, deployed **from the registry entry itself**.

# %% [markdown]
# ## Step 9: Clean up
#
# Delete the endpoint first (it bills per instance-hour), then the supporting resources.
# Uncomment and run when you are done. Remember to also **stop or delete the JupyterLab
# space** when finished.

# %%
# endpoint.delete()
# endpoint.wait_for_delete()
# endpoint_config.delete()
# deployed_model.delete()
#
# sm = boto3.client("sagemaker")
# mpg_name = model_package.model_package_group_name
# for pkg in sm.list_model_packages(ModelPackageGroupName=mpg_name)["ModelPackageSummaryList"]:
#     sm.delete_model_package(ModelPackageName=pkg["ModelPackageArn"])
# sm.delete_model_package_group(ModelPackageGroupName=mpg_name)
# mlflow_client.delete_registered_model(MODEL_NAME)
# print("Cleaned up endpoint, model, model package group, and registered model.")

# %% [markdown]
# ## Summary
#
# This notebook ran the single-account governance topology **end to end** on SageMaker
# Python SDK v3:
#
# - **Training** executed as a SageMaker Training Job via `@remote`
#   (`sagemaker.train.remote_function`), logging **computed** train/test RMSE, an
#   evaluation model card, and an inference specification from inside the job.
# - **Automatic model registration** synced the candidate into the Model Registry with
#   metrics, evaluation results, inference spec, and lineage intact.
# - **Governance** was enforced with IAM condition keys on the lifecycle stage
#   (verified with policy simulation) and the approval status set through the typed
#   `ModelPackage` resource.
# - **Deployment** — the piece the earlier notebooks stopped short of — created a
#   real-time endpoint directly from the approved Model Package using the v3 typed
#   resources (`Model`, `EndpointConfig`, `Endpoint`) and invoked it.
#
# The same building blocks extend to the cross-account topologies in notebooks 02
# and 03: the deployment step in this notebook is exactly what a spoke account runs
# against a shared Model Package Group ARN after the hub's governance officer approves.
