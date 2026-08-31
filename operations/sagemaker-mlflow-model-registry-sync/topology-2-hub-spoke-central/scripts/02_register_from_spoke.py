"""Step 2 — Spoke registers a candidate model on the shared MLflow app.

Using spoke credentials, a data scientist logs a run and registers a model on
the *hub's* MLflow app. Because the hub app has Model Registry sync enabled,
automatic registration creates the Model Package Group and version in the HUB
account, synchronously with the register call.

The hub then attaches a resource policy to the new group and RAM-shares it back
to the spoke with the AllowDeploy managed permission, so the spoke can describe
and deploy the shared model (Step 4).

This script sets AWS_PROFILE to the spoke profile so the MLflow client and its
underlying boto3 session use spoke credentials.

Run:
    python scripts/02_register_from_spoke.py
"""

from __future__ import annotations

import json
import os
import tempfile
import time

from _common import STATE_FILE, accept_pending_invitation, config, print_banner

cfg = config()
print_banner(cfg, "Step 2: register from the spoke")

# The MLflow client and its boto3 session must use SPOKE credentials.
os.environ["AWS_PROFILE"] = cfg.spoke_profile
os.environ["AWS_DEFAULT_REGION"] = cfg.region

import boto3
import mlflow
import numpy as np
import pandas as pd
import sagemaker_mlflow
from mlflow.models import infer_signature
from sklearn.datasets import make_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

SKLEARN_IMAGE = (
    f"246618743249.dkr.ecr.{cfg.region}.amazonaws.com/"
    "sagemaker-scikit-learn:1.4-2-py312-cpu-py3"
)


def register_from_spoke() -> tuple[str, int]:
    mlflow.set_tracking_uri(cfg.hub_mlflow_app_arn)
    mlflow.set_experiment("hub-spoke-central")
    print(f"[Spoke] Tracking URI: {mlflow.get_tracking_uri()}")

    params = {"n_estimators": 50, "random_state": 42}
    X, y = make_regression(
        n_samples=500, n_features=4, n_informative=2, noise=0.5, random_state=0
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    with mlflow.start_run(run_name="spoke-candidate") as run:
        model = RandomForestRegressor(**params).fit(X_train, y_train)
        signature = infer_signature(X_train, model.predict(X_train))
        mlflow.log_params(params)
        mlflow.log_metric(
            "train_rmse", float(np.sqrt(mean_squared_error(y_train, model.predict(X_train))))
        )
        mlflow.log_metric(
            "test_rmse", float(np.sqrt(mean_squared_error(y_test, model.predict(X_test))))
        )
        model_info = mlflow.sklearn.log_model(
            model,
            name="sklearn-model",
            signature=signature,
            input_example=X_train[:3],
            serialization_format="pickle",
        )

        eval_df = pd.DataFrame(X_test, columns=["f1", "f2", "f3", "f4"])
        eval_df["target"] = y_test
        dataset = mlflow.data.from_pandas(eval_df, name="eval_set", targets="target")
        sagemaker_mlflow.evaluate(model_info, data=dataset, model_type="regressor")

        logged_model = mlflow.MlflowClient().get_logged_model(model_info.model_id)

        # Log the inference script under the model's artifact prefix through
        # MLflow — log_model_artifacts preserves the local directory layout, so
        # code/inference.py lands where the S3Prefix ModelDataSource expects it
        # (see Topology 1 for why the scikit-learn serving container needs it).
        inference_script = (
            "import os\n"
            "import pickle\n\n\n"
            "def model_fn(model_dir):\n"
            '    with open(os.path.join(model_dir, "model.pkl"), "rb") as f:\n'
            "        return pickle.load(f)\n"
        )
        loc = logged_model.artifact_location
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "code"))
            with open(os.path.join(tmp, "code", "inference.py"), "w") as f:
                f.write(inference_script)
            mlflow.MlflowClient().log_model_artifacts(model_info.model_id, tmp)

        sagemaker_mlflow.log_inference_specification(
            model_info.model_id,
            inference_specification={
                "Containers": [
                    {
                        "Image": SKLEARN_IMAGE,
                        "ModelDataSource": {
                            "S3DataSource": {
                                "S3Uri": loc + "/",
                                "S3DataType": "S3Prefix",
                                "CompressionType": "None",
                            }
                        },
                        "Environment": {
                            "SAGEMAKER_PROGRAM": "inference.py",
                            "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                        },
                    }
                ],
                "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.xlarge"],
            },
        )
        run_id = run.info.run_id

    mv = mlflow.register_model(f"runs:/{run_id}/sklearn-model", cfg.model_name)
    return run_id, int(mv.version)


def main() -> None:
    run_id, version = register_from_spoke()
    print(f"[Spoke] Registered {cfg.model_name} v{version} (MLflow run {run_id})")

    client = mlflow.MlflowClient()
    time.sleep(5)
    sm_arn = client.get_model_version(cfg.model_name, version).tags[
        "sagemaker.model_package_arn"
    ]
    print(f"[Hub] Model Package created in the hub account: {sm_arn}")

    # Hub discovers the synced group (hash suffix) and shares it back.
    hub = boto3.Session(profile_name=cfg.hub_profile, region_name=cfg.region)
    hub_sm, hub_ram = hub.client("sagemaker"), hub.client("ram")
    spoke_ram = boto3.Session(
        profile_name=cfg.spoke_profile, region_name=cfg.region
    ).client("ram")

    groups = []
    for attempt in range(6):
        groups = sorted(
            hub_sm.list_model_package_groups(NameContains=cfg.model_name).get(
                "ModelPackageGroupSummaryList", []
            ),
            key=lambda x: x["CreationTime"],
            reverse=True,
        )
        if groups:
            break
        print(f"  Waiting for the synced group to appear in the hub ({attempt + 1}/6)...")
        time.sleep(5)
    if not groups:
        raise SystemExit(
            f"No Model Package Group containing '{cfg.model_name}' found in the hub. "
            "The sync may not have completed — wait a moment and re-run this step."
        )
    mpg_arn = groups[0]["ModelPackageGroupArn"]
    mpg_name = groups[0]["ModelPackageGroupName"]
    print(f"[Hub] Model Package Group: {mpg_name}")

    hub_sm.put_model_package_group_policy(
        ModelPackageGroupName=mpg_name,
        ResourcePolicy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "CrossAccountMPGAccess",
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{cfg.spoke_account_id}:root"},
                        "Action": [
                            "sagemaker:DescribeModelPackageGroup",
                            "sagemaker:DescribeModelPackage",
                            "sagemaker:ListModelPackages",
                            "sagemaker:CreateModel",
                        ],
                        "Resource": [
                            mpg_arn,
                            f"arn:aws:sagemaker:{cfg.region}:{cfg.hub_account_id}:model-package/{mpg_name}/*",
                        ],
                    }
                ],
            }
        ),
    )
    print(f"[Hub] Resource policy attached to {mpg_name}")

    existing = hub_ram.get_resource_shares(resourceOwner="SELF")["resourceShares"]
    share_name = f"mpg-central-share-{mpg_name}"
    if any(
        s["name"] == share_name and s["status"] in ("ACTIVE", "PENDING")
        for s in existing
    ):
        print("[Hub] Group share already exists")
    else:
        resp = hub_ram.create_resource_share(
            name=share_name,
            resourceArns=[mpg_arn],
            principals=[cfg.spoke_account_id],
            allowExternalPrincipals=True,
            permissionArns=[
                "arn:aws:ram::aws:permission/AWSRAMPermissionSageMakerModelPackageGroupAllowDeploy"
            ],
        )
        print(f"[Hub] Created group share: {resp['resourceShare']['resourceShareArn']}")

    time.sleep(10)
    print("[Spoke]", accept_pending_invitation(
        spoke_ram, cfg.hub_account_id, name_contains=share_name
    ))

    json.dump(
        {"model_version": version, "model_package_arn": sm_arn, "mpg_name": mpg_name},
        open(STATE_FILE, "w"),
    )
    print(f"\nSaved state to {STATE_FILE}")
    print("Next: python scripts/03_govern_in_hub.py")


if __name__ == "__main__":
    main()
