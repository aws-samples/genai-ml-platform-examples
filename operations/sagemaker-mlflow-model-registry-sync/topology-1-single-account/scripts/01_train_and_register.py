"""Step 1 — Train, log, and register a candidate model.

Runs a scikit-learn RandomForest regressor as a SageMaker AI Training Job (via
the SDK v3 ``@remote`` decorator), logs real train/test metrics, an evaluation
model card, and an inference specification to the managed MLflow app, then calls
``mlflow.register_model``.

Because the MLflow app has Model Registry sync enabled
(AutoModelRegistrationEnabled), the register call automatically creates a
Model Package Group and version in the SageMaker AI Model Registry — carrying
over the metrics, evaluation results, inference specification, and lineage.

Run:
    python scripts/01_train_and_register.py

Prerequisites: MLFLOW_APP_ARN and EXECUTION_ROLE exported (see scripts/_common.py).
"""

from __future__ import annotations

import json
import time

from _common import STATE_FILE, config, print_banner

cfg = config()
print_banner(cfg, "Step 1: train and register")

from sagemaker.core import image_uris
from sagemaker.core.remote_function import remote

# Resolve the managed scikit-learn serving image for this region. The framework
# version matches the scikit-learn pin in requirements.txt, so the model pickled
# inside the training job unpickles cleanly on the endpoint in Step 3.
SKLEARN_IMAGE = image_uris.retrieve(
    framework="sklearn",
    region=cfg.region,
    version="1.4-2-py312",
    image_scope="inference",
    instance_type="ml.m5.xlarge",
)
print(f"Inference container image: {SKLEARN_IMAGE}")


@remote(
    image_uri=SKLEARN_IMAGE,
    instance_type="ml.m5.xlarge",
    dependencies="./requirements.txt",
    role=cfg.execution_role,
)
def train_and_register(mlflow_app_arn, model_name, experiment_name, image_uri, params):
    """Train, evaluate, log to MLflow, and register. Runs as a Training Job.

    An explicit image_uri is passed to @remote so the training job runs on the
    py312 scikit-learn container. Without it, @remote falls back to a default
    base image that only supports client Python 3.8 and 3.10.
    """
    import os
    import tempfile

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
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    with mlflow.start_run(run_name="candidate-model") as run:
        model = RandomForestRegressor(**params).fit(X_train, y_train)
        signature = infer_signature(X_train, model.predict(X_train))
        mlflow.log_params(params)

        # Real metrics on held-out data — a reviewer sees numbers that describe
        # the model, not placeholders.
        train_rmse = float(np.sqrt(mean_squared_error(y_train, model.predict(X_train))))
        test_rmse = float(np.sqrt(mean_squared_error(y_test, model.predict(X_test))))
        mlflow.log_metric("train_rmse", train_rmse)
        mlflow.log_metric("test_rmse", test_rmse)

        # serialization_format="pickle" produces a plain model.pkl (instead of
        # MLflow's default skops artifact) that the SageMaker scikit-learn
        # serving container can load.
        model_info = mlflow.sklearn.log_model(
            model,
            name="sklearn-model",
            signature=signature,
            input_example=X_train[:3],
            serialization_format="pickle",
        )

        # Evaluation metrics -> surfaced as a model card on the Model Package.
        eval_df = pd.DataFrame(X_test, columns=["f1", "f2", "f3", "f4"])
        eval_df["target"] = y_test
        dataset = mlflow.data.from_pandas(eval_df, name="eval_set", targets="target")
        sagemaker_mlflow.evaluate(model_info, data=dataset, model_type="regressor")

        logged_model = mlflow.MlflowClient().get_logged_model(model_info.model_id)

        # The scikit-learn serving container has no default model loader; it
        # needs a user inference script referenced by SAGEMAKER_PROGRAM. Log
        # one under the model's artifact prefix so the S3Prefix ModelDataSource
        # downloads it to /opt/ml/model/code/ on the endpoint. Logging through
        # MLflow (log_model_artifacts preserves the local directory layout)
        # keeps the artifact store as the single source of truth and needs no
        # direct s3:PutObject permission on the artifact bucket.
        inference_script = (
            "import os\n"
            "import pickle\n\n\n"
            "def model_fn(model_dir):\n"
            '    with open(os.path.join(model_dir, "model.pkl"), "rb") as f:\n'
            "        return pickle.load(f)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "code"))
            with open(os.path.join(tmp, "code", "inference.py"), "w") as f:
                f.write(inference_script)
            mlflow.MlflowClient().log_model_artifacts(model_info.model_id, tmp)

        # Inference specification -> enables direct deployment from the registry.
        inference_spec = {
            "Containers": [
                {
                    "Image": image_uri,
                    "ModelDataSource": {
                        "S3DataSource": {
                            "S3Uri": logged_model.artifact_location + "/",
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
        }
        sagemaker_mlflow.log_inference_specification(
            model_info.model_id, inference_specification=inference_spec
        )

        run_id = run.info.run_id

    mv = mlflow.register_model(f"runs:/{run_id}/sklearn-model", model_name)
    return run_id, mv.version, train_rmse, test_rmse


def main() -> None:
    print("\nSubmitting the training job (this blocks until it completes)...\n")
    run_id, model_version, train_rmse, test_rmse = train_and_register(
        cfg.mlflow_app_arn,
        cfg.model_name,
        "single-account-governance",
        SKLEARN_IMAGE,
        {"n_estimators": 50, "random_state": 42},
    )

    # Resolve the SageMaker Model Package ARN that sync created for this version.
    import mlflow

    mlflow.set_tracking_uri(cfg.mlflow_app_arn)
    time.sleep(5)
    mv = mlflow.MlflowClient().get_model_version(cfg.model_name, model_version)
    sm_arn = mv.tags["sagemaker.model_package_arn"]

    print("\nRegistered and synced:")
    print(f"  MLflow run:            {run_id}")
    print(f"  Registered model:      {cfg.model_name} v{model_version}")
    print(f"  train_rmse:            {train_rmse:.4f}")
    print(f"  test_rmse:             {test_rmse:.4f}")
    print(f"  SageMaker package ARN: {sm_arn}")

    with open(STATE_FILE, "w") as f:
        json.dump(
            {
                "run_id": run_id,
                "model_version": model_version,
                "model_package_arn": sm_arn,
            },
            f,
        )
    print(f"\nSaved state to {STATE_FILE}")
    print("Next: python scripts/02_govern_lifecycle.py")


if __name__ == "__main__":
    main()
