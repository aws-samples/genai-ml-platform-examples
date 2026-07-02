# Design Document: Config-Driven Compute Selection for SageMaker Pipeline Steps

**Author:** Platform Team  
**Date:** June 2026  
**Status:** Draft  
**Version:** 1.0

---

## 1. Overview

### 1.1 Problem Statement

The current SageMaker pipeline implementation hardcodes compute choices for each pipeline step
(SageMaker Processing with SKLearn for preprocessing/evaluation, SageMaker Training for model
training). Users have no ability to select alternative compute backends (e.g., EMR Serverless
for data preprocessing) without modifying Python pipeline code directly.

### 1.2 Goal

Enable users to configure compute backends for each pipeline step via a JSON configuration file.
The pipeline construction logic will read this config and dynamically assemble the correct
SageMaker Pipeline steps based on user preferences.

### 1.3 Scope

**In scope:**
- Config schema for per-step compute selection
- Factory pattern for step construction in pipeline.py
- Support for SageMaker Processing and EMR Serverless as preprocessing compute options
- Support for SageMaker Training as training compute (extensible to others in future)
- Config validation
- Regression and integration testing plan

**Out of scope:**
- UI/CLI for config generation (users edit JSON directly)
- Auto-provisioning of EMR Serverless applications
- Compute options for the evaluation step (future iteration)

---

## 2. Current Architecture

### 2.1 Directory Structure

```
model_build/
├── config/
│   └── pipeline_config.json          # Current config (metadata only)
├── ml_pipelines/
│   ├── __init__.py
│   ├── _utils.py                     # Dynamic module loading, kwargs conversion
│   ├── run_pipeline.py               # CLI entry point
│   └── training/
│       ├── __init__.py
│       └── pipeline.py               # Pipeline definition (hardcoded compute)
├── source_scripts/
│   ├── preprocessing/
│   │   └── prepare_bank_data/
│   │       ├── main.py               # SKLearn-based preprocessing script
│   │       └── requirements.txt
│   ├── training/
│   │   └── xgboost/
│   │       └── train.py
│   └── evaluate/
│       └── evaluate_xgboost/
│           └── main.py
├── requirements.txt
└── setup.py
```

### 2.2 Current Pipeline Steps

| Step | Compute | Implementation |
|------|---------|---------------|
| PreprocessBankMarketingData | SageMaker Processing (FrameworkProcessor + SKLearn 1.4-2) | `source_scripts/preprocessing/prepare_bank_data/main.py` |
| TrainBankMarketingModel | SageMaker Training (XGBoost 1.7-1) | `source_scripts/training/xgboost/train.py` |
| EvaluateBankMarketingModel | SageMaker Processing (FrameworkProcessor + SKLearn 1.4-2) | `source_scripts/evaluate/evaluate_xgboost/main.py` |
| CheckAccuracyBankMarketingEvaluation | Condition step (no compute) | Inline in pipeline.py |
| RegisterBankMarketingModel | Model registry (no compute) | Inline in pipeline.py |

### 2.3 Current Config File (`pipeline_config.json`)

```json
{
  "aws_region": "us-east-1",
  "sagemaker_project_name": "",
  "sagemaker_pipeline_role_arn": "",
  "glue_database": "bank-classification-db",
  "glue_table": "bank-marketing-data",
  "DataBucketName": "",
  "model_package_group_name": "bank-classification-model-group",
  "mlflow_tracking_uri": "",
  "mlflow_experiment_name": "bank-classification-experiment"
}
```

### 2.4 Current Data Flow

```
Glue Catalog (bank-marketing-data)
    │
    ▼
[Preprocessing - SageMaker Processing]
    │
    ├── s3://.../train/train.csv
    ├── s3://.../validation/validation.csv
    ├── s3://.../test/test.csv
    └── s3://.../mlflow/parent_run_id.txt
            │
            ▼
[Training - SageMaker Training]
    │
    └── s3://.../model.tar.gz
            │
            ▼
[Evaluation - SageMaker Processing]
    │
    └── evaluation.json
            │
            ▼
[Condition: accuracy >= 0.7] ──► [Register Model]
```

---

## 3. Proposed Design

### 3.1 Enhanced Config Schema

The `pipeline_config.json` will be extended with a `steps` section that allows per-step
compute configuration. Existing top-level fields remain unchanged for backward compatibility.

```json
{
  "aws_region": "us-east-1",
  "sagemaker_project_name": "",
  "sagemaker_pipeline_role_arn": "",
  "glue_database": "bank-classification-db",
  "glue_table": "bank-marketing-data",
  "DataBucketName": "",
  "model_package_group_name": "bank-classification-model-group",
  "mlflow_tracking_uri": "",
  "mlflow_experiment_name": "bank-classification-experiment",

  "steps": {
    "preprocessing": {
      "compute": "sagemaker_processing",
      "sagemaker_processing": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1,
        "framework": "sklearn",
        "framework_version": "1.4-2",
        "volume_size_gb": 30
      },
      "emr_serverless": {
        "application_id": "00abcdef12345678",
        "execution_role_arn": "arn:aws:iam::123456789012:role/EMRServerlessRole",
        "release_label": "emr-7.1.0",
        "spark_submit_params": {
          "spark.executor.memory": "4g",
          "spark.executor.cores": "4",
          "spark.driver.memory": "2g"
        },
        "entry_point": "source_scripts/preprocessing/prepare_bank_data_spark/main.py"
      }
    },
    "training": {
      "compute": "sagemaker_training",
      "sagemaker_training": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1,
        "framework": "xgboost",
        "framework_version": "1.7-1",
        "volume_size_gb": 30,
        "hyperparameters": {
          "max_depth": 5,
          "eta": 0.2,
          "gamma": 4,
          "min_child_weight": 6,
          "subsample": 0.8,
          "num_round": 100,
          "objective": "binary:logistic"
        }
      }
    },
    "evaluation": {
      "compute": "sagemaker_processing",
      "sagemaker_processing": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1,
        "framework": "sklearn",
        "framework_version": "1.4-2",
        "volume_size_gb": 30
      }
    }
  }
}
```

### 3.2 Config Schema Specification

#### Top-Level Fields (unchanged)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| aws_region | string | Yes | AWS region |
| sagemaker_project_name | string | Yes | SageMaker project name |
| sagemaker_pipeline_role_arn | string | Yes | IAM role ARN for pipeline execution |
| glue_database | string | Yes | Glue catalog database name |
| glue_table | string | Yes | Glue catalog table name |
| DataBucketName | string | Yes | S3 bucket for artifacts |
| model_package_group_name | string | Yes | Model package group name |
| mlflow_tracking_uri | string | No | MLflow tracking server URI |
| mlflow_experiment_name | string | No | MLflow experiment name |
| steps | object | No | Per-step compute config (defaults to current behavior if absent) |

#### `steps.preprocessing` Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| compute | enum | Yes | One of: `sagemaker_processing`, `emr_serverless` |
| sagemaker_processing | object | Conditional | Required when compute = `sagemaker_processing` |
| emr_serverless | object | Conditional | Required when compute = `emr_serverless` |

#### `steps.preprocessing.sagemaker_processing` Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| instance_type | string | No | ml.m5.xlarge | SageMaker instance type |
| instance_count | int | No | 1 | Number of instances |
| framework | string | No | sklearn | Framework (sklearn, spark) |
| framework_version | string | No | 1.4-2 | Framework version |
| volume_size_gb | int | No | 30 | EBS volume size in GB |

#### `steps.preprocessing.emr_serverless` Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| application_id | string | Yes | — | Pre-created EMR Serverless application ID |
| execution_role_arn | string | Yes | — | IAM role for EMR Serverless job |
| release_label | string | No | emr-7.1.0 | EMR release label |
| spark_submit_params | object | No | {} | Spark configuration key-value pairs |
| entry_point | string | No | (auto-resolved) | Path to PySpark entry script |

#### `steps.training` Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| compute | enum | Yes | Currently only: `sagemaker_training` |
| sagemaker_training | object | Conditional | Required when compute = `sagemaker_training` |

#### `steps.training.sagemaker_training` Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| instance_type | string | No | ml.m5.xlarge | Training instance type |
| instance_count | int | No | 1 | Number of training instances |
| framework | string | No | xgboost | Training framework |
| framework_version | string | No | 1.7-1 | Framework version |
| volume_size_gb | int | No | 30 | EBS volume size |
| hyperparameters | object | No | (current defaults) | Model hyperparameters |

### 3.3 Backward Compatibility

- If `steps` key is **absent**, pipeline uses current hardcoded behavior (no breaking change)
- If `steps` key is **present but a step is missing**, that step uses defaults
- Existing top-level config fields remain unchanged

---

## 4. Implementation Plan

### 4.1 New Directory Structure

```
model_build/
├── config/
│   ├── pipeline_config.json              # Enhanced with "steps" section
│   └── pipeline_config_schema.json       # JSON Schema for validation
├── ml_pipelines/
│   ├── __init__.py
│   ├── _utils.py                         # Existing utility functions
│   ├── _config.py                        # NEW: Config loader + validator
│   ├── _step_factory.py                  # NEW: Factory for building steps
│   ├── run_pipeline.py                   # Updated to pass config to pipeline
│   └── training/
│       ├── __init__.py
│       └── pipeline.py                   # Refactored to use factory
├── source_scripts/
│   ├── preprocessing/
│   │   ├── prepare_bank_data/            # Existing: SageMaker Processing script
│   │   │   ├── main.py
│   │   │   └── requirements.txt
│   │   └── prepare_bank_data_spark/      # NEW: PySpark equivalent for EMR
│   │       ├── main.py
│   │       └── requirements.txt
│   ├── training/
│   │   └── xgboost/
│   │       └── train.py
│   └── evaluate/
│       └── evaluate_xgboost/
│           └── main.py
├── tests/                                # NEW: Test suite
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_step_factory.py
│   │   └── test_pipeline_construction.py
│   └── integration/
│       ├── test_sagemaker_processing_step.py
│       ├── test_emr_serverless_step.py
│       └── test_end_to_end_pipeline.py
├── requirements.txt
└── setup.py
```

### 4.2 Module: `_config.py` (Config Loader & Validator)

**Purpose:** Load `pipeline_config.json`, validate against schema, provide typed access.

```python
"""Config loader and validator for pipeline configuration."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


# Default values matching current hardcoded behavior
DEFAULTS = {
    "preprocessing": {
        "compute": "sagemaker_processing",
        "sagemaker_processing": {
            "instance_type": "ml.m5.xlarge",
            "instance_count": 1,
            "framework": "sklearn",
            "framework_version": "1.4-2",
            "volume_size_gb": 30,
        },
    },
    "training": {
        "compute": "sagemaker_training",
        "sagemaker_training": {
            "instance_type": "ml.m5.xlarge",
            "instance_count": 1,
            "framework": "xgboost",
            "framework_version": "1.7-1",
            "volume_size_gb": 30,
            "hyperparameters": {
                "max_depth": 5,
                "eta": 0.2,
                "gamma": 4,
                "min_child_weight": 6,
                "subsample": 0.8,
                "num_round": 100,
                "objective": "binary:logistic",
            },
        },
    },
    "evaluation": {
        "compute": "sagemaker_processing",
        "sagemaker_processing": {
            "instance_type": "ml.m5.xlarge",
            "instance_count": 1,
            "framework": "sklearn",
            "framework_version": "1.4-2",
            "volume_size_gb": 30,
        },
    },
}

VALID_COMPUTE_OPTIONS = {
    "preprocessing": ["sagemaker_processing", "emr_serverless"],
    "training": ["sagemaker_training"],
    "evaluation": ["sagemaker_processing"],
}


@dataclass
class StepConfig:
    """Configuration for a single pipeline step."""
    compute: str
    params: Dict[str, Any]


@dataclass
class PipelineConfig:
    """Full pipeline configuration."""
    aws_region: str
    sagemaker_project_name: str
    sagemaker_pipeline_role_arn: str
    glue_database: str
    glue_table: str
    data_bucket_name: str
    model_package_group_name: str
    mlflow_tracking_uri: str = ""
    mlflow_experiment_name: str = "BankMarketingExperiment"
    preprocessing: StepConfig = None
    training: StepConfig = None
    evaluation: StepConfig = None


def load_pipeline_config(config_path: str) -> PipelineConfig:
    """Load and validate pipeline configuration from JSON file."""
    with open(config_path, "r") as f:
        raw = json.load(f)

    # Build step configs with defaults
    steps = raw.get("steps", {})
    step_configs = {}
    for step_name, defaults in DEFAULTS.items():
        step_raw = steps.get(step_name, defaults)
        compute = step_raw.get("compute", defaults["compute"])

        # Validate compute option
        if compute not in VALID_COMPUTE_OPTIONS[step_name]:
            raise ValueError(
                f"Invalid compute '{compute}' for step '{step_name}'. "
                f"Valid options: {VALID_COMPUTE_OPTIONS[step_name]}"
            )

        # Validate required fields for compute type
        if compute not in step_raw:
            raise ValueError(
                f"Missing config section '{compute}' for step '{step_name}'"
            )

        params = {**defaults.get(compute, {}), **step_raw.get(compute, {})}
        step_configs[step_name] = StepConfig(compute=compute, params=params)

    return PipelineConfig(
        aws_region=raw["aws_region"],
        sagemaker_project_name=raw.get("sagemaker_project_name", ""),
        sagemaker_pipeline_role_arn=raw.get("sagemaker_pipeline_role_arn", ""),
        glue_database=raw["glue_database"],
        glue_table=raw["glue_table"],
        data_bucket_name=raw.get("DataBucketName", ""),
        model_package_group_name=raw.get("model_package_group_name", ""),
        mlflow_tracking_uri=raw.get("mlflow_tracking_uri", ""),
        mlflow_experiment_name=raw.get("mlflow_experiment_name", "BankMarketingExperiment"),
        preprocessing=step_configs["preprocessing"],
        training=step_configs["training"],
        evaluation=step_configs["evaluation"],
    )
```

### 4.3 Module: `_step_factory.py` (Step Factory)

**Purpose:** Given a `StepConfig`, construct the appropriate SageMaker Pipeline step.

```python
"""Factory module for constructing SageMaker Pipeline steps based on config."""

from typing import Dict, Any, Tuple
import sagemaker
from sagemaker.processing import FrameworkProcessor, ProcessingInput, ProcessingOutput
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.emr_step import EMRStep, EMRStepConfig
from sagemaker.workflow.parameters import ParameterString, ParameterInteger

from ml_pipelines._config import StepConfig


class StepFactory:
    """Constructs SageMaker Pipeline steps from config."""

    def __init__(self, session, role, default_bucket, base_job_prefix,
                 bucket_kms_id=None, env_vars=None):
        self.session = session
        self.role = role
        self.default_bucket = default_bucket
        self.base_job_prefix = base_job_prefix
        self.bucket_kms_id = bucket_kms_id
        self.env_vars = env_vars or {}

    def build_preprocessing_step(
        self, step_config: StepConfig, glue_database, glue_table
    ) -> Tuple[Any, Dict[str, str]]:
        """
        Build the preprocessing step based on compute config.

        Returns:
            Tuple of (step, output_paths) where output_paths maps
            logical names to S3 URI property references.
        """
        if step_config.compute == "sagemaker_processing":
            return self._build_sm_processing_preprocessing(
                step_config.params, glue_database, glue_table
            )
        elif step_config.compute == "emr_serverless":
            return self._build_emr_preprocessing(
                step_config.params, glue_database, glue_table
            )
        else:
            raise ValueError(f"Unsupported preprocessing compute: {step_config.compute}")

    def _build_sm_processing_preprocessing(self, params, glue_database, glue_table):
        """Build SageMaker Processing preprocessing step (current behavior)."""
        processor = FrameworkProcessor(
            estimator_cls=sagemaker.sklearn.estimator.SKLearn,
            framework_version=params.get("framework_version", "1.4-2"),
            instance_type=params.get("instance_type", "ml.m5.xlarge"),
            instance_count=params.get("instance_count", 1),
            base_job_name=f"{self.base_job_prefix}/sklearn-preprocess",
            sagemaker_session=self.session,
            role=self.role,
            output_kms_key=self.bucket_kms_id,
            env=self.env_vars,
            volume_size_in_gb=params.get("volume_size_gb", 30),
        )

        step_args = processor.run(
            outputs=[
                ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
                ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation"),
                ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
                ProcessingOutput(output_name="mlflow", source="/opt/ml/processing/mlflow"),
            ],
            code="main.py",
            source_dir="source_scripts/preprocessing/prepare_bank_data",
            arguments=["--database-name", glue_database, "--table-name", glue_table],
        )

        step = ProcessingStep(name="PreprocessBankMarketingData", step_args=step_args)
        return step

    def _build_emr_preprocessing(self, params, glue_database, glue_table):
        """Build EMR Serverless preprocessing step."""
        from sagemaker.workflow.emr_step import EMRStep, EMRStepConfig

        # S3 output base path
        output_base = f"s3://{self.default_bucket}/{self.base_job_prefix}/preprocessing"

        spark_config = params.get("spark_submit_params", {})
        spark_conf_list = [
            f"--conf {k}={v}" for k, v in spark_config.items()
        ]

        emr_step_config = EMRStepConfig(
            jar="command-runner.jar",
            args=[
                "spark-submit",
                "--deploy-mode", "cluster",
                *spark_conf_list,
                params.get("entry_point",
                           "source_scripts/preprocessing/prepare_bank_data_spark/main.py"),
                "--database-name", glue_database,
                "--table-name", glue_table,
                "--output-path", output_base,
            ],
        )

        step = EMRStep(
            name="PreprocessBankMarketingData",
            cluster_id=params["application_id"],
            step_config=emr_step_config,
            display_name="Preprocess with EMR Serverless",
        )
        return step

    def build_training_step(self, step_config: StepConfig, preprocess_step):
        """Build the training step based on compute config."""
        if step_config.compute == "sagemaker_training":
            return self._build_sm_training(step_config.params, preprocess_step)
        else:
            raise ValueError(f"Unsupported training compute: {step_config.compute}")

    def _build_sm_training(self, params, preprocess_step):
        """Build SageMaker Training step (current behavior)."""
        from sagemaker.xgboost.estimator import XGBoost
        from sagemaker.inputs import TrainingInput

        model_path = f"s3://{self.default_bucket}/{self.base_job_prefix}/BankMarketingTrain"
        hyperparameters = params.get("hyperparameters", {})

        xgb_train = XGBoost(
            entry_point="train.py",
            source_dir="source_scripts/training/xgboost",
            framework_version=params.get("framework_version", "1.7-1"),
            instance_type=params.get("instance_type", "ml.m5.xlarge"),
            instance_count=params.get("instance_count", 1),
            output_path=model_path,
            base_job_name=f"{self.base_job_prefix}/bank-marketing-train",
            sagemaker_session=self.session,
            role=self.role,
            output_kms_key=self.bucket_kms_id,
            hyperparameters=hyperparameters,
            environment=self.env_vars,
            volume_size=params.get("volume_size_gb", 30),
        )

        step = TrainingStep(
            name="TrainBankMarketingModel",
            estimator=xgb_train,
            inputs={
                "train": TrainingInput(
                    s3_data=preprocess_step.properties.ProcessingOutputConfig
                        .Outputs["train"].S3Output.S3Uri,
                    content_type="text/csv",
                ),
                "validation": TrainingInput(
                    s3_data=preprocess_step.properties.ProcessingOutputConfig
                        .Outputs["validation"].S3Output.S3Uri,
                    content_type="text/csv",
                ),
                "mlflow": TrainingInput(
                    s3_data=preprocess_step.properties.ProcessingOutputConfig
                        .Outputs["mlflow"].S3Output.S3Uri,
                    content_type="text/plain",
                ),
            },
        )
        return step, xgb_train
```

### 4.4 Refactored `pipeline.py`

The existing `get_pipeline()` function will be refactored to:
1. Accept a `config_path` parameter (or load from default location)
2. Use `_config.load_pipeline_config()` to parse config
3. Delegate step construction to `StepFactory`
4. Preserve all existing behavior when `steps` section is absent

**Key change pattern:**

```python
def get_pipeline(region, role=None, default_bucket=None, config_path=None, **kwargs):
    """Gets a SageMaker ML Pipeline instance.

    If config_path is provided, reads step configuration from file.
    Otherwise falls back to existing hardcoded behavior for backward compatibility.
    """
    from ml_pipelines._config import load_pipeline_config

    # Load config
    if config_path:
        config = load_pipeline_config(config_path)
    else:
        config = None  # Use legacy behavior

    # ... session setup ...

    if config and config.preprocessing:
        factory = StepFactory(session=sagemaker_session, role=role, ...)
        step_process = factory.build_preprocessing_step(
            config.preprocessing, glue_database, glue_table
        )
        step_train, estimator = factory.build_training_step(
            config.training, step_process
        )
    else:
        # Legacy hardcoded path (existing code unchanged)
        ...
```

### 4.5 EMR Serverless Preprocessing Script

A PySpark equivalent of `prepare_bank_data/main.py` must be created at:

`source_scripts/preprocessing/prepare_bank_data_spark/main.py`

**Requirements:**
- Same input contract: read from Glue catalog (database + table)
- Same output contract: write train/validation/test CSVs to S3
- Same transformations: imputation, scaling, one-hot encoding, train/val/test split
- MLflow logging (optional, via PySpark MLflow integration)

**Key differences from SageMaker Processing version:**
- Uses PySpark DataFrames instead of pandas
- Uses Spark ML Pipeline instead of sklearn Pipeline
- Reads/writes directly to S3 (no `/opt/ml/processing/` paths)
- Output paths provided as command-line arguments

### 4.6 Output Path Normalization

The critical integration point is how downstream steps reference preprocessing outputs.

| Compute | How outputs are exposed |
|---------|------------------------|
| SageMaker Processing | `step.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri` |
| EMR Serverless | Fixed S3 paths defined in config (e.g., `s3://bucket/prefix/train/`) |

**Solution:** Introduce a `StepOutputResolver` that abstracts output path retrieval:

```python
class StepOutputResolver:
    """Resolves output S3 paths regardless of compute backend."""

    def __init__(self, step, compute_type, output_base=None):
        self.step = step
        self.compute_type = compute_type
        self.output_base = output_base

    def get_output_uri(self, output_name: str):
        if self.compute_type == "sagemaker_processing":
            return (self.step.properties
                    .ProcessingOutputConfig.Outputs[output_name]
                    .S3Output.S3Uri)
        elif self.compute_type == "emr_serverless":
            # EMR writes to known S3 paths
            return f"{self.output_base}/{output_name}/"
        else:
            raise ValueError(f"Unknown compute type: {self.compute_type}")
```

---

## 5. Sequence Diagrams

### 5.1 Pipeline Construction Flow (New)

```
User                  run_pipeline.py         _config.py        _step_factory.py      pipeline.py
 │                         │                      │                    │                    │
 │─── run with config ────►│                      │                    │                    │
 │                         │── load_pipeline_config()──►│              │                    │
 │                         │◄── PipelineConfig ────────│              │                    │
 │                         │                      │                    │                    │
 │                         │── get_pipeline(config=...) ──────────────────────────────────►│
 │                         │                      │                    │                    │
 │                         │                      │    ◄── build_preprocessing_step() ─────│
 │                         │                      │    │                                    │
 │                         │                      │    │─── check compute type              │
 │                         │                      │    │─── dispatch to builder             │
 │                         │                      │    │──► return step ────────────────────►│
 │                         │                      │                    │                    │
 │                         │                      │    ◄── build_training_step() ───────────│
 │                         │                      │    │──► return step ────────────────────►│
 │                         │                      │                    │                    │
 │                         │◄── Pipeline ──────────────────────────────────────────────────│
 │                         │                      │                    │                    │
 │◄── execution ARN ───────│                      │                    │                    │
```

### 5.2 Data Flow with EMR Serverless Preprocessing

```
Glue Catalog (bank-marketing-data)
    │
    ▼
[EMR Serverless - PySpark Job]
    │   (reads from Glue catalog, writes to S3 directly)
    │
    ├── s3://{bucket}/{prefix}/preprocessing/train/
    ├── s3://{bucket}/{prefix}/preprocessing/validation/
    ├── s3://{bucket}/{prefix}/preprocessing/test/
    └── s3://{bucket}/{prefix}/preprocessing/mlflow/
            │
            ▼   (StepOutputResolver normalizes paths)
            │
[Training - SageMaker Training]  ← same as before
    │
    └── s3://.../model.tar.gz
            │
            ▼
[Evaluation - SageMaker Processing]  ← same as before
    │
    └── evaluation.json
```

---

## 6. Dependencies & Prerequisites

### 6.1 SDK Requirements

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| sagemaker | >= 2.200.0 | EMRStep support in Pipelines |
| boto3 | >= 1.28.0 | EMR Serverless API |
| jsonschema | >= 4.0.0 | Config validation (new dependency) |

Update `requirements.txt`:
```
sagemaker>=2.200.0
boto3
jsonschema>=4.0.0
```

### 6.2 Infrastructure Prerequisites (for EMR Serverless option)

Before a user can select `emr_serverless` as a compute option, the following must exist:

1. **EMR Serverless Application** — pre-created with appropriate release label
2. **IAM Execution Role** — with permissions for:
   - Glue catalog access (GetDatabase, GetTable, GetPartitions)
   - S3 read/write to data bucket
   - CloudWatch Logs (for EMR job logs)
3. **S3 Output Location** — the data bucket must be accessible from EMR Serverless
4. **Network Configuration** — EMR Serverless application must have network access
   to Glue catalog and S3

### 6.3 IAM Permissions

The SageMaker Pipeline execution role needs additional permissions when EMR Serverless is used:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "emr-serverless:StartJobRun",
        "emr-serverless:GetJobRun",
        "emr-serverless:CancelJobRun"
      ],
      "Resource": "arn:aws:emr-serverless:*:*:/applications/*"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "<EMR_SERVERLESS_EXECUTION_ROLE_ARN>",
      "Condition": {
        "StringLike": {
          "iam:PassedToService": "emr-serverless.amazonaws.com"
        }
      }
    }
  ]
}
```

---

## 7. Implementation Tasks (Ordered)

### Phase 1: Foundation (Config & Validation)

| # | Task | Estimated Effort | Files Modified/Created |
|---|------|-----------------|----------------------|
| 1.1 | Create `_config.py` with config loader and validator | 1 day | `ml_pipelines/_config.py` (new) |
| 1.2 | Create JSON Schema for pipeline config | 0.5 day | `config/pipeline_config_schema.json` (new) |
| 1.3 | Write unit tests for config loading (valid, invalid, missing steps, defaults) | 0.5 day | `tests/unit/test_config.py` (new) |
| 1.4 | Update `pipeline_config.json` with `steps` section | 0.5 day | `config/pipeline_config.json` |

### Phase 2: Factory Layer

| # | Task | Estimated Effort | Files Modified/Created |
|---|------|-----------------|----------------------|
| 2.1 | Create `_step_factory.py` with SageMaker Processing builder | 1 day | `ml_pipelines/_step_factory.py` (new) |
| 2.2 | Add EMR Serverless builder to factory | 1 day | `ml_pipelines/_step_factory.py` |
| 2.3 | Create `StepOutputResolver` for path normalization | 0.5 day | `ml_pipelines/_step_factory.py` |
| 2.4 | Write unit tests for step factory (mock SageMaker SDK) | 1 day | `tests/unit/test_step_factory.py` (new) |

### Phase 3: Pipeline Integration

| # | Task | Estimated Effort | Files Modified/Created |
|---|------|-----------------|----------------------|
| 3.1 | Refactor `pipeline.py` to accept config and use factory | 1.5 days | `ml_pipelines/training/pipeline.py` |
| 3.2 | Update `run_pipeline.py` to pass config path | 0.5 day | `ml_pipelines/run_pipeline.py` |
| 3.3 | Update `_utils.py` to support config_path in kwargs | 0.5 day | `ml_pipelines/_utils.py` |
| 3.4 | Write unit tests for pipeline construction (both compute paths) | 1 day | `tests/unit/test_pipeline_construction.py` (new) |

### Phase 4: EMR Serverless Script

| # | Task | Estimated Effort | Files Modified/Created |
|---|------|-----------------|----------------------|
| 4.1 | Create PySpark preprocessing script (`prepare_bank_data_spark/main.py`) | 2 days | `source_scripts/preprocessing/prepare_bank_data_spark/main.py` (new) |
| 4.2 | Verify PySpark script produces identical outputs to SKLearn version | 1 day | Manual validation + `tests/integration/test_emr_serverless_step.py` |

### Phase 5: Integration & Regression Testing

| # | Task | Estimated Effort | Files Modified/Created |
|---|------|-----------------|----------------------|
| 5.1 | Integration test: pipeline creation with SageMaker Processing (existing path) | 1 day | `tests/integration/test_sagemaker_processing_step.py` |
| 5.2 | Integration test: pipeline creation with EMR Serverless | 1 day | `tests/integration/test_emr_serverless_step.py` |
| 5.3 | End-to-end regression: run full pipeline with default config | 1 day | `tests/integration/test_end_to_end_pipeline.py` |
| 5.4 | End-to-end test: run full pipeline with EMR Serverless config | 1 day | `tests/integration/test_end_to_end_pipeline.py` |
| 5.5 | Documentation update (README) | 0.5 day | `README.md` |

**Total estimated effort: ~15 developer-days**

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Scope:** Test config loading, validation, factory dispatch, and pipeline construction
without calling AWS APIs.

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_load_valid_config_full` | Load config with all steps specified | PipelineConfig populated correctly |
| `test_load_config_no_steps_section` | Load config without `steps` key | Defaults applied for all steps |
| `test_load_config_partial_steps` | Only `preprocessing` specified | Preprocessing from config, others default |
| `test_invalid_compute_option` | Set compute to "spark_on_k8s" | Raises ValueError |
| `test_missing_required_emr_fields` | EMR config without application_id | Raises ValueError |
| `test_factory_dispatches_sm_processing` | compute = sagemaker_processing | Calls SM Processing builder |
| `test_factory_dispatches_emr` | compute = emr_serverless | Calls EMR builder |
| `test_pipeline_definition_valid_json` | Construct pipeline, check definition() | Valid JSON, correct step names |
| `test_backward_compat_no_config` | Call get_pipeline without config_path | Pipeline matches current behavior exactly |

**Mocking strategy:**
- Mock `sagemaker.session.PipelineSession` to avoid AWS calls
- Mock `boto3.client` for EMR Serverless interactions
- Use `sagemaker.workflow.pipeline.Pipeline.definition()` to verify structure

### 8.2 Integration Tests

**Scope:** Test actual pipeline creation (upsert) in an AWS account. These require
AWS credentials and a configured environment.

| Test Case | Description | Environment | Expected Result |
|-----------|-------------|-------------|-----------------|
| `test_sm_processing_pipeline_upsert` | Create pipeline with SM Processing preprocessing | Dev account | Pipeline upsert succeeds, definition contains ProcessingStep |
| `test_emr_pipeline_upsert` | Create pipeline with EMR Serverless preprocessing | Dev account with EMR app | Pipeline upsert succeeds, definition contains EMRStep |
| `test_sm_processing_pipeline_execution` | Execute pipeline end-to-end with SM Processing | Dev account | All steps succeed, model registered |
| `test_emr_pipeline_execution` | Execute pipeline end-to-end with EMR Serverless | Dev account with EMR app | All steps succeed, model registered |
| `test_output_parity` | Compare outputs from SM Processing vs EMR Serverless runs | Dev account | Train/val/test splits are equivalent (same schema, similar distributions) |

### 8.3 Regression Tests

**Purpose:** Ensure existing functionality is not broken by the refactor.

| Test Case | Description | Pass Criteria |
|-----------|-------------|---------------|
| `test_default_config_produces_same_pipeline` | Compare pipeline JSON before and after refactor | Pipeline `definition()` JSON is structurally identical |
| `test_run_pipeline_cli_unchanged` | Run `run_pipeline.py` with same args as before | Same exit code, same pipeline ARN pattern |
| `test_mlflow_integration_preserved` | Run pipeline with MLflow tracking | Parent/child runs created correctly |
| `test_existing_preprocessing_script` | Run SM Processing step in isolation | Same outputs as current production |
| `test_hyperparameters_passed_correctly` | Check training step has correct hyperparameters from config | HP values match config |
| `test_condition_step_logic_unchanged` | Verify accuracy threshold gating still works | Model registered only when accuracy >= 0.7 |

### 8.4 Test Execution Commands

```bash
# Unit tests (no AWS access needed)
pytest tests/unit/ -v --tb=short

# Integration tests (requires AWS credentials + dev account)
pytest tests/integration/ -v --tb=short -m "not slow"

# Full end-to-end (takes ~30min per run)
pytest tests/integration/test_end_to_end_pipeline.py -v --tb=long -m "slow"

# Regression only
pytest tests/ -v -k "regression or backward_compat"
```

---

## 9. Risk Analysis & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| EMR Serverless step not fully supported in SageMaker Pipelines SDK version used | High | Medium | Verify with SDK >= 2.200.0. Fallback: use `CallbackStep` with Lambda to orchestrate EMR job. |
| PySpark preprocessing produces different results than SKLearn | High | Medium | Output parity test with tolerance bounds. Document acceptable numerical differences from floating-point handling. |
| Config validation misses edge cases | Medium | Low | Use JSON Schema + runtime validation. Add integration tests with malformed configs. |
| Pipeline execution role lacks EMR permissions | Medium | High | Document required IAM permissions. Provide CloudFormation/Terraform snippet for role updates. |
| Breaking change for existing users | High | Low | `steps` section is optional; absence triggers legacy code path. No existing config files break. |
| EMR Serverless cold start latency | Low | High | Document that first EMR run may be slower. Not a correctness issue. |

---

## 10. Future Extensibility

This design is intentionally extensible for additional compute options:

| Future Compute Option | Pipeline Step | Effort |
|----------------------|---------------|--------|
| AWS Glue (Spark) | Processing/preprocessing | Add `glue_job` config + factory builder |
| Amazon EKS (custom containers) | Training | Add `eks_training` config + `TrainingStep` with custom image |
| AWS Step Functions (nested) | Any | Add `stepfunctions` config for complex orchestration |
| SageMaker Processing with Spark | Preprocessing | Add `sagemaker_spark` variant using SparkProcessor |

To add a new compute option:
1. Add the enum value to `VALID_COMPUTE_OPTIONS` in `_config.py`
2. Add the config schema section
3. Implement a builder method in `StepFactory`
4. Create the corresponding execution script under `source_scripts/`
5. Add tests

---

## 11. Open Questions

| # | Question | Decision Needed By | Owner |
|---|----------|-------------------|-------|
| 1 | Should hyperparameters live in the config file or remain in code? | Phase 2 | Platform Team |
| 2 | Do we need a "dry-run" mode that validates config and prints pipeline JSON without executing? | Phase 3 | Developer |
| 3 | Should EMR Serverless application be auto-created if `application_id` is empty? | Phase 4 | Architect |
| 4 | What tolerance is acceptable for output parity between SKLearn and PySpark? | Phase 4 | Data Science |
| 5 | Should the evaluation step also support EMR Serverless in this iteration? | Phase 1 | Product Owner |

---

## 12. Appendix

### A. Example Config: SageMaker Processing (Default/Current Behavior)

```json
{
  "aws_region": "us-east-1",
  "sagemaker_project_name": "bank-classification",
  "sagemaker_pipeline_role_arn": "arn:aws:iam::123456789012:role/SageMakerPipelineRole",
  "glue_database": "bank-classification-db",
  "glue_table": "bank-marketing-data",
  "DataBucketName": "my-ml-bucket",
  "model_package_group_name": "bank-classification-model-group",
  "mlflow_tracking_uri": "http://mlflow.example.com:5000",
  "mlflow_experiment_name": "bank-classification-experiment",
  "steps": {
    "preprocessing": {
      "compute": "sagemaker_processing",
      "sagemaker_processing": {
        "instance_type": "ml.m5.2xlarge",
        "instance_count": 1,
        "framework": "sklearn",
        "framework_version": "1.4-2"
      }
    },
    "training": {
      "compute": "sagemaker_training",
      "sagemaker_training": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1,
        "framework": "xgboost",
        "framework_version": "1.7-1",
        "hyperparameters": {
          "max_depth": 5,
          "eta": 0.2,
          "num_round": 100,
          "objective": "binary:logistic"
        }
      }
    },
    "evaluation": {
      "compute": "sagemaker_processing",
      "sagemaker_processing": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1
      }
    }
  }
}
```

### B. Example Config: EMR Serverless Preprocessing

```json
{
  "aws_region": "us-east-1",
  "sagemaker_project_name": "bank-classification",
  "sagemaker_pipeline_role_arn": "arn:aws:iam::123456789012:role/SageMakerPipelineRole",
  "glue_database": "bank-classification-db",
  "glue_table": "bank-marketing-data",
  "DataBucketName": "my-ml-bucket",
  "model_package_group_name": "bank-classification-model-group",
  "mlflow_tracking_uri": "",
  "mlflow_experiment_name": "bank-classification-experiment",
  "steps": {
    "preprocessing": {
      "compute": "emr_serverless",
      "emr_serverless": {
        "application_id": "00f5t2k3v4nm0z09",
        "execution_role_arn": "arn:aws:iam::123456789012:role/EMRServerlessExecutionRole",
        "release_label": "emr-7.1.0",
        "spark_submit_params": {
          "spark.executor.memory": "8g",
          "spark.executor.cores": "4",
          "spark.driver.memory": "4g",
          "spark.dynamicAllocation.enabled": "true"
        }
      }
    },
    "training": {
      "compute": "sagemaker_training",
      "sagemaker_training": {
        "instance_type": "ml.m5.2xlarge",
        "instance_count": 1,
        "framework": "xgboost",
        "framework_version": "1.7-1"
      }
    },
    "evaluation": {
      "compute": "sagemaker_processing",
      "sagemaker_processing": {
        "instance_type": "ml.m5.xlarge",
        "instance_count": 1
      }
    }
  }
}
```

### C. Migration Guide for Existing Users

1. **No action required** — existing `pipeline_config.json` without `steps` key continues to work
2. **To adopt:** Add `steps` section to config file. Start with `sagemaker_processing` to validate, then switch to `emr_serverless`
3. **To switch preprocessing to EMR Serverless:**
   - Create EMR Serverless application (or use existing)
   - Update IAM roles with EMR permissions
   - Set `steps.preprocessing.compute` to `emr_serverless`
   - Fill in `application_id` and `execution_role_arn`
   - Run pipeline — verify outputs match expected schema
