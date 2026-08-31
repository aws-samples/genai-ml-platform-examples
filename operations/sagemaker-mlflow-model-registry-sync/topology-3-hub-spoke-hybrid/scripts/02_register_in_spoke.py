"""Step 2 — Data scientist registers and approves in the spoke's own registry.

Entirely within the spoke account: the data scientist logs a run and registers
against the SPOKE's own MLflow app. Automatic registration syncs the model into
the spoke's local Model Registry — the hub is not touched. The development
account's model owner then approves the model locally. That local approval is the
trigger for the copy to the hub (Step 3).

Run:
    python scripts/02_register_in_spoke.py
"""

from __future__ import annotations

import json
import os
import tempfile
import time

from _common import STATE_FILE, config, print_banner

cfg = config()
print_banner(cfg, "Step 2: register and approve in the spoke")

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

spoke_sm = boto3.Session(profile_name=cfg.spoke_profile, region_name=cfg.region).client(
    "sagemaker"
)


def register_in_spoke() -> tuple[str, int]:
    mlflow.set_tracking_uri(cfg.spoke_mlflow_app_arn)
    mlflow.set_experiment("hybrid-dev")
    print(f"[Spoke] Tracking URI: {mlflow.get_tracking_uri()}")

    params = {"n_estimators": 50, "random_state": 42}
    X, y = make_regression(
        n_samples=500, n_features=4, n_informative=2, noise=0.5, random_state=0
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    with mlflow.start_run(run_name="dev-candidate") as run:
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
    run_id, version = register_in_spoke()
    print(f"[Spoke] Registered {cfg.model_name} v{version} (MLflow run {run_id})")

    time.sleep(5)
    dev_pkg_arn = mlflow.MlflowClient().get_model_version(
        cfg.model_name, version
    ).tags["sagemaker.model_package_arn"]
    print(f"[Spoke] Model Package in the SPOKE registry: {dev_pkg_arn}")

    # Dev owner approves locally — the trigger for promotion to the hub.
    spoke_sm.update_model_package(
        ModelPackageArn=dev_pkg_arn, ModelApprovalStatus="Approved"
    )
    time.sleep(3)
    status = spoke_sm.describe_model_package(ModelPackageName=dev_pkg_arn)[
        "ModelApprovalStatus"
    ]
    print(f"[Spoke] Dev owner approval status: {status}")

    json.dump(
        {"model_version": version, "dev_pkg_arn": dev_pkg_arn}, open(STATE_FILE, "w")
    )
    print(f"\nSaved state to {STATE_FILE}")
    print("Next: python scripts/03_copy_to_hub.py")


if __name__ == "__main__":
    main()
