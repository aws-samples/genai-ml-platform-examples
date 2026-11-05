"""Baseline lookup for in-notebook drift monitoring.

Resolves the baseline.json registered with the model that is actually serving
the endpoint, so drift is measured against "what's running now" rather than
"what we built last." Extracted from the (deleted) scheduled drift Lambda so
the lab5d notebook has no dependency on out-of-scope Lambda/EventBridge code.

Resolution chain:

    endpoint -> endpoint config -> variant.ModelName -> describe_model
        -> Containers[].ModelPackageName -> describe_model_package
        -> CustomerMetadataProperties["baseline_s3_uri"] -> baseline.json

Lab 3A registers the model in MLflow and lets the MLflow App's auto-sync create
the SageMaker Model Package. That means two things this module has to cope with:

* The baseline pointer is a **custom metadata property**, not ``ModelMetrics``.
  ``ModelMetrics`` can only be set by ``CreateModelPackage``, and the sync owns
  that call; ``UpdateModelPackage`` accepts ``CustomerMetadataProperties``. The
  legacy ``ModelMetrics`` location is still read first, so packages registered by
  the older repack flow (or by the seed-code pipeline) resolve unchanged.
* The model package group name is the MLflow registered-model name plus a
  SageMaker-generated suffix (``bank-prediction-XGBoostModel-a1b2c3``), so the
  group is matched by prefix rather than by exact name.
"""

import json
import tarfile
import tempfile
from pathlib import Path

import boto3

from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_EVALUATION_TABLE,
    AWS_DEFAULT_REGION,
    ENDPOINT_NAME,
    MLFLOW_MODEL_NAME,
    resolve_endpoint_name,
)

# The SageMaker Model Package Group is named after the MLflow registered model
# (see config.MLFLOW_MODEL_NAME), but the MLflow -> SageMaker auto-sync appends a
# generated suffix, so this is a PREFIX, not an exact name. _resolve_group()
# below turns it into the real group name.
MODEL_PACKAGE_GROUP_PREFIX = MLFLOW_MODEL_NAME
MODEL_PACKAGE_GROUP = MLFLOW_MODEL_NAME  # kept for callers that print it

_sagemaker_client = boto3.client("sagemaker", region_name=AWS_DEFAULT_REGION)
_s3 = boto3.client("s3", region_name=AWS_DEFAULT_REGION)
_BASELINE_CACHE: dict = {}
_MODEL_CACHE: dict = {}

# Artifact file names, in the order the endpoint's inference.py (model_fn) tries
# them — mirrored here so the baseline is scored by the same file the endpoint loads.
_MODEL_FILE_CANDIDATES = (
    # MLflow's xgboost flavor (Lab 3A logs with model_format="json")
    "model.json",
    "model.ubj",
    "model.xgb",
    "model.pkl",
    # Artifacts written directly by a training script / the old repack flow
    "xgboost-model.json",
    "xgboost-model",
)


def _resolve_model_package_arn_from_endpoint(endpoint_name: str):
    """Walk the SageMaker objects to find the ModelPackage backing an endpoint.

    Returns the ARN, or None if any link in the chain is missing (e.g., the
    endpoint serves a Model built directly from artifacts, not a registered
    package).
    """
    try:
        ep = _sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        cfg = _sagemaker_client.describe_endpoint_config(
            EndpointConfigName=ep["EndpointConfigName"]
        )
        variants = cfg.get("ProductionVariants", [])
        if not variants:
            print(f"⚠️ Endpoint {endpoint_name} has no ProductionVariants")
            return None
        model_name = variants[0]["ModelName"]
        model = _sagemaker_client.describe_model(ModelName=model_name)
        for container in model.get("Containers", []) or [model.get("PrimaryContainer", {})]:
            arn = container.get("ModelPackageName")
            if arn:
                return arn
        print(f"⚠️ Model {model_name} was not built from a registered ModelPackage")
        return None
    except Exception as e:
        print(f"⚠️ Could not resolve ModelPackage from endpoint {endpoint_name}: {e}")
        return None


def _resolve_group(prefix=MODEL_PACKAGE_GROUP_PREFIX):
    """Return the real model package group name for ``prefix``.

    The MLflow auto-sync names the group ``<mlflow model name>-<suffix>``, so an
    exact-name lookup misses it. An exact match is preferred when one exists
    (packages registered before the sync was adopted), then the newest
    prefix match.
    """
    try:
        groups = _sagemaker_client.list_model_package_groups(
            NameContains=prefix, SortBy="CreationTime", SortOrder="Descending"
        ).get("ModelPackageGroupSummaryList", [])
    except Exception as e:  # noqa: BLE001 - a lookup failure must not break the notebook
        print(f"⚠️ list_model_package_groups failed for prefix {prefix}: {e}")
        return prefix

    names = [g["ModelPackageGroupName"] for g in groups]
    if prefix in names:
        return prefix
    for name in names:
        if name.startswith(prefix):
            return name
    return prefix


def _latest_approved_model_package_arn():
    """Fallback for first-ever monitor runs (no endpoint yet)."""
    try:
        resp = _sagemaker_client.list_model_packages(
            ModelPackageGroupName=_resolve_group(),
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=1,
        )
        packages = resp.get("ModelPackageSummaryList", [])
        return packages[0]["ModelPackageArn"] if packages else None
    except Exception as e:
        print(f"⚠️ list_model_packages fallback failed: {e}")
        return None


def load_baseline_from_registry():
    """Return the baseline.json registered with the model serving the endpoint.

    Resolution order:
      1. Endpoint walk (the deployed model — correct answer)
      2. Latest Approved ModelPackage in the resolved group (only valid on
         first-ever monitor runs before any endpoint exists)

    Cached per process. Returns the parsed baseline.json with
    ``model_package_arn`` added, or ``None`` if no baseline can be resolved
    (the caller then falls back to env/config defaults).
    """
    if "value" in _BASELINE_CACHE:
        return _BASELINE_CACHE["value"]

    # Prefer the explicitly configured endpoint; otherwise discover the live
    # bank-marketing-* endpoint (same helper the notebook uses).
    endpoint = ENDPOINT_NAME or resolve_endpoint_name()

    arn = None
    if endpoint:
        arn = _resolve_model_package_arn_from_endpoint(endpoint)
    if not arn:
        if endpoint:
            print(f"  Falling back to latest-Approved lookup in group {_resolve_group()}")
        arn = _latest_approved_model_package_arn()
    if not arn:
        print(
            f"⚠️ No ModelPackage available (endpoint={endpoint or '<unset>'}, "
            f"group={_resolve_group()})"
        )
        _BASELINE_CACHE["value"] = None
        return None

    try:
        pkg = _sagemaker_client.describe_model_package(ModelPackageName=arn)
        # Three accepted locations, oldest first:
        #   ModelMetrics.ModelQuality.Statistics.S3Uri  - CreateModelPackage flow
        #   ModelMetrics.ModelStatistics.S3Uri          - legacy key
        #   CustomerMetadataProperties["baseline_s3_uri"] - MLflow auto-sync flow,
        #       the only writable option once SageMaker owns CreateModelPackage
        metrics = pkg.get("ModelMetrics", {})
        s3_uri = (
            metrics.get("ModelQuality", {}).get("Statistics", {}).get("S3Uri")
            or metrics.get("ModelStatistics", {}).get("S3Uri")
            or pkg.get("CustomerMetadataProperties", {}).get("baseline_s3_uri")
        )
        if not s3_uri:
            print(f"⚠️ ModelPackage {arn} carries no baseline pointer — skipping baseline")
            _BASELINE_CACHE["value"] = None
            return None

        bucket, key = s3_uri.replace("s3://", "").split("/", 1)
        body = _s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        baseline = json.loads(body)
        baseline["model_package_arn"] = arn
        print(
            f"✓ Loaded baseline from {s3_uri}\n"
            f"  ModelPackage:        {arn}\n"
            f"  Baseline ROC-AUC:    {baseline.get('metrics', {}).get('roc_auc', '?')}\n"
            f"  Evaluation table:    {baseline.get('evaluation_table', '?')}"
            f"  (snapshot {baseline.get('evaluation_snapshot_id') or 'live'})"
        )
        _BASELINE_CACHE["value"] = baseline
        return baseline
    except Exception as e:
        print(f"⚠️ Could not load baseline.json for {arn}: {e}")
        _BASELINE_CACHE["value"] = None
        return None


def load_registered_model(model_package_arn):
    """Download and load the model artifact registered on a ModelPackage.

    Returns the loaded xgboost object (Booster, or whatever a .pkl unpickles to).
    Cached per process — the artifact is a few hundred KB but the S3 round trip
    plus untar is not free.
    """
    if model_package_arn in _MODEL_CACHE:
        return _MODEL_CACHE[model_package_arn]

    import xgboost as xgb

    pkg = _sagemaker_client.describe_model_package(ModelPackageName=model_package_arn)
    container = pkg["InferenceSpecification"]["Containers"][0]
    workdir = Path(tempfile.mkdtemp(prefix="baseline-model-"))

    if container.get("ModelDataUrl"):
        # Single compressed artifact (repack flow / seed-code pipeline).
        url = container["ModelDataUrl"]
        bucket, key = url.replace("s3://", "").split("/", 1)
        archive = workdir / "model.tar.gz"
        _s3.download_file(bucket, key, str(archive))
        with tarfile.open(archive) as tf:
            tf.extractall(workdir)
    else:
        # Uncompressed S3 prefix: the MLflow artifact store the endpoint serves
        # from (Lab 3A). Pull the top-level files; the model is one of them.
        source = container["ModelDataSource"]["S3DataSource"]
        url = source["S3Uri"]
        bucket, prefix = url.replace("s3://", "").split("/", 1)
        paginator = _s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                rel = obj["Key"][len(prefix):].lstrip("/")
                if not rel or rel.endswith("/"):
                    continue
                dest = workdir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                _s3.download_file(bucket, obj["Key"], str(dest))

    path = next((workdir / n for n in _MODEL_FILE_CANDIDATES if (workdir / n).exists()), None)
    if path is None:
        raise FileNotFoundError(f"No model file in {url} (looked for {_MODEL_FILE_CANDIDATES})")

    if path.suffix == ".pkl":
        import pickle

        with open(path, "rb") as f:
            model = pickle.load(f)
    else:
        model = xgb.Booster()
        model.load_model(str(path))

    print(f"✓ Loaded registered model artifact: {url} ({path.name})")
    _MODEL_CACHE[model_package_arn] = model
    return model


def score_evaluation_baseline(
    baseline,
    athena_client,
    feature_names,
    target_column,
    threshold=0.5,
    limit=None,
):
    """Score the held-out evaluation set with the registered model.

    This is the baseline half of the model-drift comparison: the (label,
    prediction) pairs the model produced on data it never trained on.

    Why re-score instead of reading `evaluation_data.prediction`? That column is
    written NULL by Lab 2 and nothing backfills it, so a query filtering on
    `prediction IS NOT NULL` returns zero rows. Re-scoring the exact evaluation
    snapshot pinned in baseline.json with the exact artifact the endpoint serves
    reproduces the ROC-AUC recorded in baseline.json to the last digit (the
    printed comparison below is the proof), and it needs no write access to the
    table.

    Returns a DataFrame with columns target / prediction / probability.
    """
    import pandas as pd
    from sklearn.metrics import roc_auc_score

    table = baseline.get("evaluation_table") or ATHENA_EVALUATION_TABLE
    snapshot = baseline.get("evaluation_snapshot_id") or ""
    source = (
        f"{ATHENA_DATABASE}.{table} FOR VERSION AS OF {snapshot}"
        if snapshot
        else f"{ATHENA_DATABASE}.{table}"
    )
    sql = (
        f"SELECT {', '.join(feature_names)}, {target_column}\n"
        f"FROM {source}\n"
        f"WHERE {target_column} IS NOT NULL"
    )
    if limit:
        sql += f"\nLIMIT {limit}"

    df = athena_client.execute_query(sql)
    X = df[feature_names].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = df[target_column].astype(bool).astype(int)

    model = load_registered_model(baseline["model_package_arn"])
    try:
        import xgboost as xgb

        proba = model.predict(xgb.DMatrix(X.values, feature_names=list(feature_names)))
    except AttributeError:
        # A pickled sklearn-API estimator rather than a raw Booster.
        proba = model.predict_proba(X.values)[:, 1]

    scored = pd.DataFrame(
        {
            "target": y.values,
            "prediction": (proba > threshold).astype(int),
            "probability": proba,
        }
    )

    recorded = baseline.get("metrics", {}).get("roc_auc")
    reproduced = roc_auc_score(scored["target"], scored["probability"])
    print(
        f"  Re-scored {len(scored):,} held-out rows from {source}\n"
        f"  ROC-AUC reproduced: {reproduced:.6f}"
        + (f"  (baseline.json recorded {recorded:.6f})" if recorded else "")
    )
    return scored
