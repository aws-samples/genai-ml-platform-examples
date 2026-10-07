"""Configuration module for the drift monitoring pipeline.

Loads configuration from config.yaml and .env file overrides.
Exposes all configuration constants as module-level variables.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this file: src/config/config.py)
# ---------------------------------------------------------------------------
_CONFIG_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CONFIG_DIR.parent.parent

# Load .env (environment-specific overrides take precedence)
load_dotenv(_PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Load config.yaml (central defaults)
# ---------------------------------------------------------------------------
_CONFIG_YAML_PATH = _CONFIG_DIR / "config.yaml"
_yaml_cfg: dict = {}
if _CONFIG_YAML_PATH.exists():
    with open(_CONFIG_YAML_PATH, "r") as _f:
        _yaml_cfg = yaml.safe_load(_f) or {}


def _get(yaml_section: str, yaml_key: str, env_var: str, default=None):
    """Return env-var override → YAML value → default, in that priority.

    Empty values (empty string / whitespace) are treated as "not set" so the
    next source in the priority chain is used. This prevents blank placeholders
    in config.yaml or the environment from masking derived account-agnostic
    defaults (e.g. S3 bucket/path constants resolving to "").
    """
    env_val = os.environ.get(env_var)
    if env_val is not None and env_val.strip() != "":
        return env_val
    section = _yaml_cfg.get(yaml_section, {})
    if isinstance(section, dict) and yaml_key in section:
        yaml_val = section[yaml_key]
        if not (isinstance(yaml_val, str) and yaml_val.strip() == ""):
            return yaml_val
    return default


# ===========================================================================
# NOTE (history): earlier versions of this file tagged constants with
# `🔁 SYNC: lambda_drift_monitor.py` because a scheduled drift-monitor Lambda
# read the same values via env vars. That Lambda and its deploy script have
# been REMOVED — lab5 monitoring now runs entirely inside the notebooks
# (see lab5-monitoring/DELETION_CANDIDATES.md). config.py (backed by
# config.yaml / .env / stack outputs) is the single source of truth; the
# remaining `🔁 SYNC` comments below are historical and refer to deleted code.
# ===========================================================================


# ===================================================================
# AWS
# ===================================================================
# Data-plane region. Single source of truth — config.yaml `aws.region`, with
# AWS_REGION / AWS_DEFAULT_REGION env vars allowed to override at runtime.
# Keep the third-arg default in sync with config.yaml so nothing falls back
# to a different region if the yaml fails to load.
AWS_DEFAULT_REGION: str = _get("aws", "region", "AWS_DEFAULT_REGION", "us-west-2")

# QuickSight identity region (where the QuickSight account was first
# activated). Distinct from data-plane region — all QuickSight API calls
# must hit this endpoint regardless of where the data lives.
QUICKSIGHT_IDENTITY_REGION: str = _get(
    "aws", "quicksight_identity_region", "QUICKSIGHT_IDENTITY_REGION", "us-east-1"
)

# ===================================================================
# SageMaker
# ===================================================================
SAGEMAKER_EXEC_ROLE: str = _get(
    "sagemaker", "exec_role", "SAGEMAKER_EXEC_ROLE", ""
)
SERVERLESS_MEMORY_SIZE: int = int(
    _get("sagemaker", "serverless_memory_size", "SERVERLESS_MEMORY_SIZE", "2048")
)
SERVERLESS_MAX_CONCURRENCY: int = int(
    _get("sagemaker", "serverless_max_concurrency", "SERVERLESS_MAX_CONCURRENCY", "5")
)
BATCH_TRANSFORM_INSTANCE: str = _get(
    "sagemaker", "batch_transform_instance", "BATCH_TRANSFORM_INSTANCE", "ml.m5.xlarge"
)
BATCH_TRANSFORM_MAX_CONCURRENT: int = int(
    _get("sagemaker", "batch_transform_max_concurrent", "BATCH_TRANSFORM_MAX_CONCURRENT", "4")
)

# ===================================================================
# MLflow
# ===================================================================
# 🔁 SYNC: lambda_drift_monitor.py:54 — Lambda reads MLFLOW_TRACKING_URI from
# env; no Lambda-side fallback (MLflow run logging is skipped if missing).
MLFLOW_TRACKING_URI: str = _get(
    "mlflow", "tracking_uri", "MLFLOW_TRACKING_URI", ""
)
MLFLOW_EXPERIMENT_NAME: str = _get(
    "mlflow", "experiment_name", "MLFLOW_EXPERIMENT_NAME",
    "bank-marketing-prediction",
)
MLFLOW_INFERENCE_EXPERIMENT_NAME: str = _get(
    "mlflow", "inference_experiment_name", "MLFLOW_INFERENCE_EXPERIMENT_NAME",
    "bank-marketing-prediction",
)
MLFLOW_BATCH_EXPERIMENT_NAME: str = _get(
    "mlflow", "batch_experiment_name", "MLFLOW_BATCH_EXPERIMENT_NAME",
    "bank-marketing-prediction",
)
MLFLOW_MONITORING_EXPERIMENT_NAME: str = _get(
    "mlflow", "monitoring_experiment_name", "MLFLOW_MONITORING_EXPERIMENT_NAME",
    "bank-marketing-prediction",
)
# MLflow registered-model name, also used as the SageMaker Model Package Group
# name. Matches the model registered by Lab 3A (bank-prediction-XGBoostModel).
MLFLOW_MODEL_NAME: str = _get(
    "mlflow", "model_name", "MLFLOW_MODEL_NAME", "bank-prediction-XGBoostModel"
)

# ===================================================================
# Prediction / probability column names (BYO-dataset knobs)
# ===================================================================
# The endpoint's custom inference handler writes each prediction to the
# inference_responses Athena table using these column names. Defaults match
# the reference implementation. Downstream code
# (drift Lambda, dashboards,
# batch transform) reads columns via these constants so BYO users can point them at a differently-named handler
# output without editing every SQL query.
PREDICTION_COLUMN: str = _get(
    "inference", "prediction_column", "PREDICTION_COLUMN", "prediction"
)
PROBABILITY_COLUMN: str = _get(
    "inference", "probability_column", "PROBABILITY_COLUMN", "probability_positive"
)
PROBABILITY_ALT_COLUMN: str = _get(
    "inference", "probability_alt_column", "PROBABILITY_ALT_COLUMN",
    "probability_negative",
)

# ===================================================================
# Training objective override (BYO-dataset knob)
# ===================================================================
# XGBoost objective + num_class overrides. Empty string means "auto-derive
# from schema.target_type()" (see train.py's resolve_xgboost_objective()).
# Explicit override wins over auto-derivation.
XGBOOST_OBJECTIVE: str = _get(
    "training", "objective", "XGBOOST_OBJECTIVE", ""
)
XGBOOST_NUM_CLASS: int = int(
    _get("training", "num_class", "XGBOOST_NUM_CLASS", "0")
)

# ===================================================================
# Athena
# ===================================================================
# 🔁 SYNC: lambda_drift_monitor.py:49 — Lambda fallback: 'ml_monitoring'.
ATHENA_DATABASE: str = _get("athena", "database", "ATHENA_DATABASE", "bank_marketing")
ATHENA_WORKGROUP: str = _get("athena", "workgroup", "ATHENA_WORKGROUP", "primary")
# 🔁 SYNC: lambda_drift_monitor.py:50 — Lambda fallback:
# 's3://ml-monitoring-data-lake/athena-query-results/'. That fallback path
# is wrong on accounts that don't have that bucket — at deploy time
# deploy_lambda_container.sh derives the correct s3://<data-bucket>/...
# from PROJECT_NAME + account ID and overrides via the env var.
ATHENA_OUTPUT_S3: str = _get("athena", "output_s3", "ATHENA_OUTPUT_S3", "")
ATHENA_QUERY_TIMEOUT: int = int(
    _get("athena", "query_timeout", "ATHENA_QUERY_TIMEOUT", "300")
)

ATHENA_TRAINING_TABLE: str = _get(
    "athena", "training_table", "ATHENA_TRAINING_TABLE", "training_data"
)
# 🔁 SYNC: lambda_drift_monitor.py:51 — Lambda fallback: 'evaluation_data'.
ATHENA_EVALUATION_TABLE: str = _get(
    "athena", "evaluation_table", "ATHENA_EVALUATION_TABLE", "evaluation_data"
)
ATHENA_INFERENCE_TABLE: str = _get(
    "athena", "inference_table", "ATHENA_INFERENCE_TABLE", "inference_responses"
)
ATHENA_GROUND_TRUTH_TABLE: str = _get(
    "athena", "ground_truth_table", "ATHENA_GROUND_TRUTH_TABLE", "ground_truth"
)
ATHENA_GROUND_TRUTH_UPDATES_TABLE: str = _get(
    "athena", "ground_truth_updates_table", "ATHENA_GROUND_TRUTH_UPDATES_TABLE",
    "ground_truth_updates",
)
ATHENA_DRIFTED_DATA_TABLE: str = _get(
    "athena", "drifted_data_table", "ATHENA_DRIFTED_DATA_TABLE", "drifted_data"
)
ATHENA_MONITORING_RESPONSES_TABLE: str = _get(
    "athena", "monitoring_responses_table", "ATHENA_MONITORING_RESPONSES_TABLE",
    "monitoring_responses",
)

# ===================================================================
# Project
# ===================================================================
# Used as a name prefix for CFN, IAM roles, S3 buckets, etc. Single source
# of truth — every shell script + CFN reads this via _get / config_shell.py.
PROJECT_NAME: str = _get(
    "project", "name", "PROJECT_NAME", "bank-marketing-prediction"
)

# ===================================================================
# Single source of truth: read runtime values from the deployed workshop
# CloudFormation stack outputs, so resource names are never declared twice.
# The stack is deployed by scripts/deploy-workshop.sh with
# StackName = "${PROJECT_NAME}-workshop" and ProjectName = PROJECT_NAME.
#
# This block must stay ABOVE the S3-paths section: DATA_S3_BUCKET is resolved
# at import time via _stack_data_bucket(), so the helper has to exist first.
# ===================================================================
WORKSHOP_STACK_NAME: str = _get(
    "project", "stack_name", "WORKSHOP_STACK_NAME", ""
) or (f"{PROJECT_NAME}-workshop" if PROJECT_NAME else "")

_STACK_OUTPUTS_CACHE: dict | None = None


def get_stack_outputs(stack_name: str | None = None) -> dict:
    """Return the workshop stack's Outputs as a {key: value} dict.

    Cached after the first successful lookup. Returns {} (and never raises)
    when the stack is not found or credentials are unavailable, so config
    import still succeeds outside a deployed environment.
    """
    global _STACK_OUTPUTS_CACHE
    if _STACK_OUTPUTS_CACHE is not None and stack_name is None:
        return _STACK_OUTPUTS_CACHE
    name = stack_name or WORKSHOP_STACK_NAME
    if not name:
        return {}
    try:
        import boto3

        cfn = boto3.client("cloudformation", region_name=AWS_DEFAULT_REGION)
        stacks = cfn.describe_stacks(StackName=name)["Stacks"]
        outputs = {
            o["OutputKey"]: o["OutputValue"]
            for o in stacks[0].get("Outputs", [])
        }
    except Exception:
        outputs = {}
    if stack_name is None:
        _STACK_OUTPUTS_CACHE = outputs
    return outputs


def resolve_endpoint_name(prefix: str | None = None) -> str:
    """Resolve the live SageMaker endpoint name.

    Priority: explicit ENDPOINT_NAME (config/.env) → the first InService
    endpoint whose name starts with ENDPOINT_NAME_PREFIX (Lab 3A pattern
    bank-marketing-<timestamp>). Returns "" if none is found.
    """
    if ENDPOINT_NAME:
        return ENDPOINT_NAME
    pfx = prefix or ENDPOINT_NAME_PREFIX
    try:
        import boto3

        sm = boto3.client("sagemaker", region_name=AWS_DEFAULT_REGION)
        eps = sm.list_endpoints(SortBy="CreationTime", SortOrder="Descending")[
            "Endpoints"
        ]
        for ep in eps:
            if ep["EndpointName"].startswith(pfx) and ep["EndpointStatus"] == "InService":
                return ep["EndpointName"]
        # Fall back to any InService endpoint.
        for ep in eps:
            if ep["EndpointStatus"] == "InService":
                return ep["EndpointName"]
    except Exception:
        pass
    return ""


def _stack_data_bucket() -> str:
    """Data bucket from the stack's DataBucketName output (authoritative)."""
    return get_stack_outputs().get("DataBucketName", "")


# ===================================================================
# S3 paths
# ===================================================================
def _derive_data_bucket() -> str:
    """Derive the data bucket account-agnostically.

    Priority: DATA_S3_BUCKET env/yaml -> ${PROJECT_NAME}-data-${account_id}-${region}.
    The CFN data bucket follows the convention ``${ProjectName}-data-${AWS::AccountId}-${AWS::Region}``,
    so when no explicit bucket is configured we reconstruct it from PROJECT_NAME, the
    caller's AWS account ID, and the region. This keeps the config valid in any
    account/deployment without hardcoding a bucket name.
    """
    explicit = _get("s3", "bucket", "DATA_S3_BUCKET", "")
    if explicit:
        return explicit

    # Reuse the canonical PROJECT_NAME constant — single source of truth.
    if not PROJECT_NAME:
        return ""
    project_name = PROJECT_NAME

    try:
        import boto3

        account_id = boto3.client(
            "sts", region_name=AWS_DEFAULT_REGION
        ).get_caller_identity()["Account"]
    except Exception:
        return ""

    return f"{project_name}-data-{account_id}-{AWS_DEFAULT_REGION}"


DATA_S3_BUCKET: str = _stack_data_bucket() or _derive_data_bucket()

# Prefer the stack's AthenaDatabase output as the single source of truth, but
# only when the database was NOT explicitly pinned via env/YAML (an explicit
# value always wins, per _get precedence).
if (
    os.environ.get("ATHENA_DATABASE", "").strip() == ""
    and not (_yaml_cfg.get("athena", {}) or {}).get("database")
):
    _stack_db = get_stack_outputs().get("AthenaDatabase", "")
    if _stack_db:
        ATHENA_DATABASE = _stack_db

DATA_S3_PREFIX: str = _get("s3", "prefix", "DATA_S3_PREFIX", "bank-marketing-lab/")

# Derive the Athena query-results location from the data bucket when not set
# explicitly (account-agnostic, matches the CFN lifecycle/Lambda convention
# ``s3://${ProjectName}-data-${AWS::AccountId}/athena-results/``).
if not ATHENA_OUTPUT_S3 and DATA_S3_BUCKET:
    ATHENA_OUTPUT_S3 = f"s3://{DATA_S3_BUCKET}/athena-results/"


def _s3_path(yaml_key: str, env_var: str, suffix: str) -> str:
    """Build S3 path from config or derive from bucket + prefix + suffix."""
    val = _get("s3", yaml_key, env_var, "")
    if val:
        return val
    if DATA_S3_BUCKET:
        return f"s3://{DATA_S3_BUCKET}/{DATA_S3_PREFIX}{suffix}"
    return ""


S3_TRAINING_DATA: str = _s3_path("training_data", "S3_TRAINING_DATA", "training_data/")
S3_GROUND_TRUTH: str = _s3_path("ground_truth", "S3_GROUND_TRUTH", "ground_truth/")
S3_INFERENCE_RESPONSES: str = _s3_path(
    "inference_responses", "S3_INFERENCE_RESPONSES", "inference_responses/"
)
S3_DRIFTED_DATA: str = _s3_path("drifted_data", "S3_DRIFTED_DATA", "drifted_data/")
S3_GROUND_TRUTH_UPDATES: str = _s3_path(
    "ground_truth_updates", "S3_GROUND_TRUTH_UPDATES", "ground_truth_updates/"
)
S3_MODEL_ARTIFACTS: str = _s3_path(
    "model_artifacts", "S3_MODEL_ARTIFACTS", "model_artifacts/"
)
S3_TRAINING_DATA_EXPORT: str = _s3_path(
    "training_data_export", "S3_TRAINING_DATA_EXPORT", "training_data_export/"
)
S3_BATCH_TRANSFORM_INPUT: str = _s3_path(
    "batch_transform_input", "S3_BATCH_TRANSFORM_INPUT", "batch_transform/input/"
)
S3_BATCH_TRANSFORM_OUTPUT: str = _s3_path(
    "batch_transform_output", "S3_BATCH_TRANSFORM_OUTPUT", "batch_transform/output/"
)

# ===================================================================
# SQS
# ===================================================================
# SQS_QUEUE_URL is set at endpoint-deploy time (notebook 2 resolves the URL
# from CFN's InferenceLoggerQueue and passes it into the container env).
# Empty by default — the inference handler skips Athena logging if unset.
SQS_QUEUE_URL: str = _get("sqs", "inference_queue_url", "SQS_QUEUE_URL", "")
MONITORING_SQS_QUEUE_NAME: str = _get(
    "sqs", "monitoring_queue_name", "MONITORING_SQS_QUEUE_NAME",
    "bank-marketing-monitoring-results",
)
# 🔁 SYNC: lambda_drift_monitor.py:55 — Lambda fallback: '' (empty string).
# When empty, the Lambda computes drift results but skips SQS dispatch, so
# the monitoring-writer Lambda never persists them. deploy_lambda_container.sh
# resolves the URL from `aws sqs get-queue-url` at deploy time and bakes it
# into the Lambda env, so the empty fallback is the "misconfigured" path.
MONITORING_SQS_QUEUE_URL: str = _get(
    "sqs", "monitoring_queue_url", "MONITORING_SQS_QUEUE_URL", ""
)

# ===================================================================
# Inference logging
# ===================================================================
# Master switch — when false, the inference handler returns predictions but
# does NOT send to SQS. Used at endpoint-deploy time as a container env var.
ENABLE_ATHENA_LOGGING: bool = (
    _get("inference_logging", "enable_athena_logging", "ENABLE_ATHENA_LOGGING", "true")
    .lower() in ("true", "1", "yes")
)

# ===================================================================
# Inference confidence thresholds
# ===================================================================
HIGH_CONFIDENCE_THRESHOLD: float = float(
    _get("inference", "high_confidence_threshold", "HIGH_CONFIDENCE_THRESHOLD", "0.9")
)
LOW_CONFIDENCE_LOWER: float = float(
    _get("inference", "low_confidence_lower", "LOW_CONFIDENCE_LOWER", "0.4")
)
LOW_CONFIDENCE_UPPER: float = float(
    _get("inference", "low_confidence_upper", "LOW_CONFIDENCE_UPPER", "0.6")
)

# ===================================================================
# Lambda
# ===================================================================
LAMBDA_EXEC_ROLE: str = _get("lambda", "exec_role", "LAMBDA_EXEC_ROLE", "")

# ===================================================================
# Data file paths
# ===================================================================
DATA_DIR: Path = _PROJECT_ROOT / "data"

# Local CSV paths (used only by upload_data_to_s3.py and download_dataset.py)
CSV_TRAINING_DATA: Path = _PROJECT_ROOT / _get(
    "data", "csv_training_data", "CSV_TRAINING_DATA",
    "data/bank_marketing_predictions_final.csv",
)
CSV_GROUND_TRUTH: Path = _PROJECT_ROOT / _get(
    "data", "csv_ground_truth", "CSV_GROUND_TRUTH",
    "data/ground_truth.csv",
)
CSV_DRIFTED_DATA: Path = _PROJECT_ROOT / _get(
    "data", "csv_drifted_data", "CSV_DRIFTED_DATA",
    "data/drifted_data.csv",
)

# S3 data paths — pipeline and Athena code should use these
_s3_data_base = f"s3://{DATA_S3_BUCKET}/{DATA_S3_PREFIX}data" if DATA_S3_BUCKET else ""

S3_CSV_TRAINING_DATA: str = _get(
    "data", "s3_training_data", "S3_TRAINING_DATA",
    f"{_s3_data_base}/bank_marketing_predictions_final.csv" if _s3_data_base else "",
)
S3_CSV_GROUND_TRUTH: str = _get(
    "data", "s3_ground_truth", "S3_GROUND_TRUTH",
    f"{_s3_data_base}/ground_truth.csv" if _s3_data_base else "",
)
S3_CSV_DRIFTED_DATA: str = _get(
    "data", "s3_drifted_data", "S3_DRIFTED_DATA",
    f"{_s3_data_base}/drifted_data.csv" if _s3_data_base else "",
)

# ===================================================================
# Training
# ===================================================================
RANDOM_STATE: int = int(_get("training", "random_state", "RANDOM_STATE", "42"))

# Target column name and feature list are dataset-shape concerns, not
# infrastructure config — they live in src/config/dataset_schema.yaml and
# are read via src.config.schema.target_column() / schema.feature_names().
# config.py deliberately does not re-export them, to keep exactly one
# source of truth per concept.

_training_cfg = _yaml_cfg.get("training", {}) if isinstance(
    _yaml_cfg.get("training"), dict
) else {}

XGBOOST_PARAMS: dict = _training_cfg.get("xgboost_params") or {
    "max_depth": 4,
    "learning_rate": 0.05,
    "num_boost_round": 200,
    "min_child_weight": 10,
    "early_stopping_rounds": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "eval_metric": "auc",
}

# ===================================================================
# Drift thresholds (used by monitor_model_performance.py)
# ===================================================================
# The daily drift Lambda reads its own thresholds from env vars
# (DATA_DRIFT_THRESHOLD, KS_PVALUE_THRESHOLD, MODEL_DRIFT_THRESHOLD,
#  DATA_DRIFT_LOOKBACK_DAYS, MODEL_DRIFT_LOOKBACK_DAYS) — not from this file.
_drift_cfg = _yaml_cfg.get("drift_thresholds", {}) if isinstance(
    _yaml_cfg.get("drift_thresholds"), dict
) else {}

MIN_ROC_AUC_THRESHOLD: float = float(
    _drift_cfg.get("min_roc_auc", os.environ.get("MIN_ROC_AUC_THRESHOLD", "0.85"))
)
# 🔁 SYNC: lambda_drift_monitor.py:58 — Lambda fallback: 0.2. Data-drift
# threshold: fraction of features whose distribution must shift (Evidently
# DataDriftPreset) before alerting. Used by notebook 3 cells 56 (CloudWatch
# alarms) and 62 (alert config).
DATA_DRIFT_THRESHOLD: float = float(
    _drift_cfg.get("data_drift", os.environ.get("DATA_DRIFT_THRESHOLD", "0.20"))
)
# 🔁 SYNC: lambda_drift_monitor.py:60 — Lambda fallback: 0.05. Model-drift
# threshold: relative ROC-AUC degradation vs baseline.
MODEL_DRIFT_THRESHOLD: float = float(
    _drift_cfg.get("model_drift", os.environ.get("MODEL_DRIFT_THRESHOLD", "0.05"))
)

# EventBridge schedule for the drift-monitor Lambda.
_drift_mon_cfg = _yaml_cfg.get("drift_monitor", {}) if isinstance(
    _yaml_cfg.get("drift_monitor"), dict
) else {}
DRIFT_MONITOR_SCHEDULE: str = _drift_mon_cfg.get(
    "schedule", os.environ.get("DRIFT_MONITOR_SCHEDULE", "cron(0 2 * * ? *)")
)

# ===================================================================
# Resource names — single source of truth for everything CFN, the deploy
# scripts, the delete scripts, the notebooks, and the Lambdas reference.
# Each constant below is THE place to change a name; shell scripts read
# them via `python -m src.config.config_shell` (no shell-side defaults).
# ===================================================================
# The endpoint is created at runtime by Lab 3A (name pattern
# bank-marketing-<timestamp>), NOT by CloudFormation. Leave ENDPOINT_NAME empty
# to auto-discover the live InService endpoint whose name starts with
# ENDPOINT_NAME_PREFIX (see resolve_endpoint_name() below).
ENDPOINT_NAME: str = _get(
    "endpoint", "name", "ENDPOINT_NAME", ""
)
ENDPOINT_NAME_PREFIX: str = _get(
    "endpoint", "name_prefix", "ENDPOINT_NAME_PREFIX", "bank-marketing"
)
# ===================================================================
# SLATED FOR DELETION — drift-plane resource names (Lambda/EventBridge/SNS/
# CloudWatch/ECR). These belong to the out-of-scope scheduled drift plane
# (see lab5-monitoring/DELETION_CANDIDATES.md). Nothing in the in-notebook
# monitoring path uses them; delete together with the drift Lambda/CFN.
# ===================================================================
DRIFT_LAMBDA_NAME: str = _get(
    "drift_monitor", "lambda_name", "DRIFT_LAMBDA_NAME",
    "bank-marketing-drift-monitor",
)
MONITORING_WRITER_LAMBDA_NAME: str = _get(
    "monitoring_writer", "lambda_name", "MONITORING_WRITER_LAMBDA_NAME",
    "bank-marketing-monitoring-results-writer",
)
EVENTBRIDGE_RULE_NAME: str = _get(
    "drift_monitor", "eventbridge_rule_name", "EVENTBRIDGE_RULE_NAME",
    "bank-marketing-drift-check",
)
SNS_TOPIC_NAME: str = _get(
    "drift_monitor", "sns_topic_name", "SNS_TOPIC_NAME",
    "bank-marketing-monitoring-drift-alerts",
)
CLOUDWATCH_DASHBOARD_NAME: str = _get(
    "drift_monitor", "cloudwatch_dashboard_name", "CLOUDWATCH_DASHBOARD_NAME",
    "BankMarketing-DriftMonitoring",
)
ECR_REPO_NAME: str = _get(
    "drift_monitor", "ecr_repo_name", "ECR_REPO_NAME",
    DRIFT_LAMBDA_NAME,   # convention: ECR repo matches Lambda name
)

# ===================================================================
# Monitoring lookback windows (used by notebook 2 + monitor_model_performance.py)
# ===================================================================
# 🔁 SYNC: lambda_drift_monitor.py:64-65 — note the Lambda reads SHORTER
# env-var names (`DATA_DRIFT_LOOKBACK_DAYS`, `MODEL_DRIFT_LOOKBACK_DAYS`)
# with fallbacks of 7 and 30 respectively. The constants below use longer
# `MONITORING_*` names so notebook code can use different windows than the
# scheduled Lambda. deploy_lambda_container.sh sets the SHORT-name env vars
# to whatever value you want the Lambda to use (currently '1' for testing).
# Keep both pairs aligned conceptually; the numeric values can intentionally
# differ between notebook (longer history) and Lambda (daily delta).
MONITORING_DATA_DRIFT_LOOKBACK_DAYS: int = int(
    os.environ.get("MONITORING_DATA_DRIFT_LOOKBACK_DAYS", "7")
)
MONITORING_MODEL_DRIFT_LOOKBACK_DAYS: int = int(
    os.environ.get("MONITORING_MODEL_DRIFT_LOOKBACK_DAYS", "30")
)

# ---------------------------------------------------------------------------
# Lambda env vars WITHOUT a config.py counterpart (intentionally)
# ---------------------------------------------------------------------------
# The drift-monitor Lambda reads a few env vars that have no corresponding
# constant here. They fall into two buckets:
#
#  (a) Lambda-only operational knobs — not interesting to the rest of the
#      project. If you need to tune one, change deploy_lambda_container.sh
#      or edit the Lambda env directly in the console:
#         KS_PVALUE_THRESHOLD   (lambda_drift_monitor.py:59, fallback 0.05)
#         MIN_SAMPLES           (lambda_drift_monitor.py:61, fallback 100)
#         BASELINE_ROC_AUC      (lambda_drift_monitor.py:563, fallback 0.92)
#
#  (b) Values resolved at deploy time, not at config-load time. Lives in
#      deploy_lambda_container.sh because the value depends on what AWS
#      returned just now:
#         SNS_TOPIC_ARN         (created by deploy script, ARN passed in)
#         MODEL_VERSION         (resolved from latest approved MPG package)
#         MLFLOW_TRACKING_URI   (looked up via list-mlflow-tracking-servers)
#         ATHENA_OUTPUT_S3      (derived from PROJECT_NAME + account ID)
#         MONITORING_SQS_QUEUE_URL  (looked up via sqs get-queue-url)
#
# Both buckets are deliberately NOT 🔁 SYNC-tagged: there is no second
# source of truth to keep aligned.

# ===================================================================
# Ground-truth simulation (dev/test only — see notebook 2 Section 4)
# ===================================================================
# These knobs let notebook 2 inject controlled drift into the ground-truth
# simulator so the monitoring pipeline can be exercised end-to-end. In
# production, ground truth comes from operational investigation feeds; these
# constants are unused.
GROUND_TRUTH_SIM_ACCURACY: float = float(
    os.environ.get("GROUND_TRUTH_SIM_ACCURACY", "0.85")
)
# Two knobs reduce the simulator's "effective accuracy":
#   effective_accuracy = base - feature_drift_impact - model_drift_magnitude
# Set either > 0 to inject errors. Floored at 0.5 inside the simulator.
GROUND_TRUTH_SIM_FEATURE_DRIFT_IMPACT: float = float(
    os.environ.get("GROUND_TRUTH_SIM_FEATURE_DRIFT_IMPACT", "0.0")
)
GROUND_TRUTH_SIM_MODEL_DRIFT_MAG: float = float(
    os.environ.get("GROUND_TRUTH_SIM_MODEL_DRIFT_MAG", "0.0")
)

# ===================================================================
# Drift dataset generation
# ===================================================================
_drift_gen_cfg = _yaml_cfg.get("drift_generation", {}) if isinstance(
    _yaml_cfg.get("drift_generation"), dict
) else {}

DRIFT_GEN_DEFAULT_CONFIG: dict = _drift_gen_cfg.get("default_drift", {})
DRIFT_GEN_NUM_SAMPLES: int = int(_drift_gen_cfg.get("num_samples", "5000"))
DRIFT_GEN_RANDOM_STATE: int = int(_drift_gen_cfg.get("random_state", "123"))

# ===================================================================
# QuickSight (used by lab5e-governance-dashboard.ipynb)
# ===================================================================
# These IDs and display names are constants of the deployed dashboard, not
# tunables — they live here as plain literals (no YAML mirror).
QUICKSIGHT_DATASOURCE_ID: str = "bank-marketing-governance-athena-datasource"
QUICKSIGHT_DATASOURCE_NAME: str = "Bank Marketing Governance - Athena"
QUICKSIGHT_INFERENCE_DATASET_ID: str = "bank-marketing-governance-inference-dataset"
QUICKSIGHT_INFERENCE_DATASET_NAME: str = "Bank Marketing Governance - Inference Monitoring"
QUICKSIGHT_DRIFT_DATASET_ID: str = "bank-marketing-governance-drift-dataset"
QUICKSIGHT_DRIFT_DATASET_NAME: str = "Bank Marketing Governance - Drift Monitoring"
QUICKSIGHT_FEATURE_DRIFT_DATASET_ID: str = "bank-marketing-governance-feature-drift-dataset"
QUICKSIGHT_FEATURE_DRIFT_DATASET_NAME: str = "Bank Marketing Governance - Feature Drift Analysis"
# Feature-level (per-feature) drift dataset, backed by the Athena view
# `feature_drift_detail` (created at dashboard-build time — see
# create_governance_dashboard.create_feature_drift_detail_view()).
QUICKSIGHT_FEATURE_LEVEL_DATASET_ID: str = "bank-marketing-governance-feature-level-dataset"
QUICKSIGHT_FEATURE_LEVEL_DATASET_NAME: str = "Bank Marketing Governance - Feature Level Drift"
# Prediction-accuracy timeline dataset (CustomSql join of inference_responses
# + ground_truth_updates).
QUICKSIGHT_ACCURACY_DATASET_ID: str = "bank-marketing-governance-inference-dataset-accuracy"
QUICKSIGHT_ACCURACY_DATASET_NAME: str = "Prediction Accuracy Timeline"
QUICKSIGHT_ANALYSIS_ID: str = "bank-marketing-governance-analysis"
QUICKSIGHT_ANALYSIS_NAME: str = "Bank Marketing Governance"
QUICKSIGHT_DASHBOARD_ID: str = "bank-marketing-governance-dashboard"
QUICKSIGHT_DASHBOARD_NAME: str = "Bank Marketing Governance"
QUICKSIGHT_SERVICE_ROLE_NAME: str = "aws-quicksight-service-role-v0"

# Inline policies the workshop attaches to the (account-global) QuickSight
# service role, declared in templates/2-iam.yaml. Project-scoped so multiple
# projects can share aws-quicksight-service-role-v0 without a policy-name
# collision. Must stay in sync with the PolicyName values in 2-iam.yaml.
QUICKSIGHT_S3_POLICY_NAME: str = f"{PROJECT_NAME}-QuickSightS3DataLakeAccess"
QUICKSIGHT_ATHENA_POLICY_NAME: str = f"{PROJECT_NAME}-QuickSightAthenaAccess"
