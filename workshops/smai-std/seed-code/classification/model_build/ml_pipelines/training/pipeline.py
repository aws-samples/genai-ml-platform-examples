# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""SageMaker Pipeline: bank-marketing XGBoost build, from the Lab 2 Iceberg tables.

    Preprocess -> Train -> Repack -> Evaluate -> (accuracy gate) -> Register

The pipeline consumes the Iceberg tables Lab 2 published and produces a model
package whose artifact carries the same custom inference handler the Lab 3A
notebook deploys, so a model built by CI/CD and a model built by hand serve
identical responses and are monitored by Lab 5 identically.

Three design points worth knowing before editing:

1.  THE FEATURE LIST IS RESOLVED AT DEFINITION TIME, not in the containers.
    ``config/dataset_schema.yaml`` is read here (in the GitHub Actions runner)
    and the resulting order is passed to the steps as a ``--features`` argument.
    The step containers therefore need neither PyYAML nor the schema file.

2.  THE EVALUATION OUTPUT DESTINATION IS PINNED to the workshop data bucket.
    ``baseline.json`` has to be referenced as ``ModelMetrics`` at definition
    time, which means its S3 URI cannot be a step property resolved later. The
    pipeline execution ID keeps each run's baseline immutable and distinct.

3.  REPACKING IS AN EXPLICIT STEP, not SDK magic. See
    ``source_scripts/inference/repack.py`` for why.
"""

import importlib.util
import json
import pathlib

import sagemaker
import sagemaker.session
from sagemaker.image_uris import retrieve as retrieve_image_uri
from sagemaker.model import Model
from sagemaker.model_card import ModelPackageModelCard
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import FrameworkProcessor, ProcessingInput, ProcessingOutput
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.execution_variables import ExecutionVariables
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.model_step import ModelStep
from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.xgboost.estimator import XGBoost

# Both the training and the serving image are pinned to the same XGBoost
# version. The booster is serialized by the training container and deserialized
# by the serving container, so a skew between them is a load failure at deploy
# time, long after this pipeline has reported success.
XGBOOST_VERSION = "1.7-1"
SKLEARN_FRAMEWORK_VERSION = "1.4-2"

# Training metric copied onto the model card. train.py evaluates on the
# validation channel with eval_metric=auc, so the training job always reports it.
MODEL_CARD_TRAINING_METRIC = "validation:auc"


class _PipelineModelPackageModelCard(ModelPackageModelCard):
    """Model package card whose content is resolved when the pipeline runs.

    ``ModelPackageModelCard`` json.dumps its content at definition time, which
    would freeze step properties (training job ARN, final metric) into literal
    ``{"Get": ...}`` text. Handing the request a ``Join`` instead lets SageMaker
    substitute the runtime values when the register step executes.
    """

    def __init__(self, content_join, model_card_status="Draft"):
        super().__init__(model_card_content=None, model_card_status=model_card_status)
        self._content_join = content_join

    def _create_request_args(self):
        return {"ModelCardStatus": self.model_card_status, "Content": self._content_join}


def _training_model_card(step_train, hyperparameters, training_image, dataset_uris,
                         model_artifact_dir):
    """Build the model card that fills Studio's Train tab for this version.

    SageMaker only derives a card on its own when the registered ModelDataUrl is
    a training job's output. This pipeline registers the REPACKED artifact (a
    processing job output), so without an explicit card Studio shows
    "No training job" and loses the metrics/hyperparameters view.
    """
    def quoted(value):
        return ['"', value, '"']

    hyper_parameters = json.dumps(
        [{"name": k, "value": str(v)} for k, v in sorted(hyperparameters.items())]
    )
    parts = [
        '{"training_details": {"training_job_details": {',
        '"training_arn": ', *quoted(step_train.properties.TrainingJobArn), ', ',
        '"training_metrics": [{"name": ', json.dumps(MODEL_CARD_TRAINING_METRIC),
        ', "value": ',
        step_train.properties.FinalMetricDataList[MODEL_CARD_TRAINING_METRIC].Value,
        '}], ',
        '"hyper_parameters": ', hyper_parameters, ', ',
        '"training_environment": {"container_image": [', json.dumps(training_image), ']}, ',
        '"training_datasets": [',
    ]
    for i, uri in enumerate(dataset_uris):
        parts += ([", "] if i else []) + quoted(uri)
    # Flat Join: the artifact path is spelled out here rather than nesting the
    # repacked_model_data Join inside this one.
    parts += [']}}, "model_overview": {"model_artifact": ["', model_artifact_dir,
              '/model.tar.gz"]}}']
    return _PipelineModelPackageModelCard(Join(on="", values=parts))


def _load_schema():
    """Load ml_pipelines/schema.py.

    ``run_pipeline.py`` imports this module as ``training.pipeline`` -- i.e.
    ``training`` is a TOP-LEVEL package, because sys.path[0] is ``ml_pipelines/``.
    So a relative import (``from .. import _dataset_schema``) cannot work, and
    ``from ml_pipelines import _dataset_schema`` only works while the repo root
    happens to be on PYTHONPATH. Import it idiomatically when that holds, and
    fall back to loading it by path so the pipeline definition never depends on
    how the caller set PYTHONPATH.

    (The module is deliberately NOT called ``schema`` -- see its docstring: that
    name shadows the PyPI ``schema`` package sagemaker.clarify imports.)
    """
    try:
        from ml_pipelines import _dataset_schema  # noqa: F401
        return _dataset_schema
    except ImportError:
        path = pathlib.Path(__file__).resolve().parent.parent / "_dataset_schema.py"
        spec = importlib.util.spec_from_file_location("ml_pipelines_dataset_schema", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def get_pipeline(
    region,
    role=None,
    default_bucket=None,
    data_bucket=None,
    model_package_group_name="bank-classification-model-group",
    pipeline_name="BankMarketingPipeline",
    base_job_prefix="BankMarketing",
    bucket_kms_id=None,
    sagemaker_session=None,
    sagemaker_project_arn=None,
    athena_database=None,
    training_table="training_data",
    evaluation_table="evaluation_data",
    mlflow_tracking_uri=None,
    mlflow_experiment_name="BankMarketingExperiment",
    code_commit_sha="",
    accuracy_threshold=0.7,
    validation_fraction=0.1,
):
    """Build the bank-marketing training pipeline.

    Args:
        region: AWS region.
        role: IAM role the pipeline steps assume.
        default_bucket: artifact bucket for pipeline-managed outputs.
        data_bucket: workshop data bucket. baseline.json is written here so
            Lab 5 can read it; falls back to default_bucket when unset.
        athena_database: Glue database holding the Lab 2 Iceberg tables.
        training_table / evaluation_table: the Lab 2 Iceberg tables.
        code_commit_sha: commit that produced this model, recorded in
            baseline.json (GITHUB_SHA in CI).
        accuracy_threshold: minimum accuracy required to register.
        validation_fraction: slice of training_data held back for validation.

    Returns:
        A configured sagemaker.workflow.pipeline.Pipeline.
    """
    schema = _load_schema()
    features = schema.feature_names()
    feature_list = ",".join(features)
    target_column = schema.target_column()

    if not athena_database:
        raise ValueError(
            "athena_database is required -- it is the Glue database holding the "
            "Lab 2 Iceberg tables (e.g. 'bank_marketing'). Set "
            "\"athena_database\" in config/pipeline_config.json."
        )

    # baseline.json goes to the workshop data bucket: that is the bucket Lab 5's
    # monitoring code is scoped to read, and keeping it off the throwaway
    # pipeline-artifact bucket means the baseline outlives the pipeline.
    data_bucket = data_bucket or default_bucket

    # The step_args pattern below requires a PipelineSession, which defers the
    # job-description calls instead of launching them.
    if sagemaker_session is None or not isinstance(sagemaker_session, PipelineSession):
        sagemaker_session = PipelineSession(default_bucket=default_bucket)

    # ---------------------------------------------------------------- parameters
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge")
    processing_instance_count = ParameterInteger(
        name="ProcessingInstanceCount", default_value=1)
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.xlarge")
    model_approval_status = ParameterString(
        name="ModelApprovalStatus", default_value="PendingManualApproval")
    athena_database_param = ParameterString(
        name="AthenaDatabase", default_value=athena_database)
    training_table_param = ParameterString(
        name="TrainingTable", default_value=training_table)
    evaluation_table_param = ParameterString(
        name="EvaluationTable", default_value=evaluation_table)
    validation_fraction_param = ParameterFloat(
        name="ValidationFraction", default_value=validation_fraction)
    accuracy_threshold_param = ParameterFloat(
        name="AccuracyThreshold", default_value=accuracy_threshold)
    mlflow_tracking_uri_param = ParameterString(
        name="MLflowTrackingUri", default_value=mlflow_tracking_uri or "")
    mlflow_experiment_name_param = ParameterString(
        name="MLflowExperimentName",
        default_value=mlflow_experiment_name or "BankMarketingExperiment")
    mlflow_parent_run_id = ParameterString(name="MLflowParentRunId", default_value="")

    mlflow_env = {
        "MLFLOW_TRACKING_URI": mlflow_tracking_uri_param,
        "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name_param,
        "MLFLOW_PARENT_RUN_ID": mlflow_parent_run_id,
    }

    # ------------------------------------------------------- 1. preprocess step
    # Reads the Iceberg tables through pinned snapshots and materializes
    # target-first, header-less CSVs. No feature engineering: Lab 2 already
    # label-encoded everything to DOUBLE.
    sklearn_processor = FrameworkProcessor(
        estimator_cls=SKLearn,
        framework_version=SKLEARN_FRAMEWORK_VERSION,
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/iceberg-preprocess",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        env=mlflow_env,
    )
    step_process_args = sklearn_processor.run(
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
            ProcessingOutput(output_name="lineage", source="/opt/ml/processing/lineage"),
            ProcessingOutput(output_name="mlflow", source="/opt/ml/processing/mlflow"),
        ],
        code="main.py",
        source_dir="source_scripts/preprocessing/prepare_bank_data",
        arguments=[
            "--database", athena_database_param,
            "--training-table", training_table_param,
            "--evaluation-table", evaluation_table_param,
            "--features", feature_list,
            "--target-column", target_column,
            "--validation-fraction", validation_fraction_param.to_string(),
        ],
    )
    step_process = ProcessingStep(
        name="PreprocessBankMarketingData",
        step_args=step_process_args,
    )
    process_outputs = step_process.properties.ProcessingOutputConfig.Outputs

    # ------------------------------------------------------------ 2. train step
    model_path = f"s3://{default_bucket}/{base_job_prefix}/BankMarketingTrain"
    train_hyperparameters = {
        "max_depth": 5,
        "eta": 0.2,
        "gamma": 4,
        "min_child_weight": 6,
        "subsample": 0.8,
        "num_round": 100,
        "objective": "binary:logistic",
    }
    xgb_train = XGBoost(
        entry_point="train.py",
        source_dir="source_scripts/training/xgboost",
        framework_version=XGBOOST_VERSION,
        instance_type=training_instance_type,
        instance_count=1,
        output_path=model_path,
        base_job_name=f"{base_job_prefix}/bank-marketing-train",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        hyperparameters=train_hyperparameters,
        environment=mlflow_env,
    )
    step_train = TrainingStep(
        name="TrainBankMarketingModel",
        estimator=xgb_train,
        inputs={
            "train": sagemaker.inputs.TrainingInput(
                s3_data=process_outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
            "validation": sagemaker.inputs.TrainingInput(
                s3_data=process_outputs["validation"].S3Output.S3Uri,
                content_type="text/csv",
            ),
            "mlflow": sagemaker.inputs.TrainingInput(
                s3_data=process_outputs["mlflow"].S3Output.S3Uri,
                content_type="text/plain",
            ),
        },
    )

    # ----------------------------------------------------------- 3. repack step
    # Bakes code/inference.py and feature_names.json into the model tarball so
    # the artifact is self-contained and script mode can find the handler.
    repack_processor = FrameworkProcessor(
        estimator_cls=SKLearn,
        framework_version=SKLEARN_FRAMEWORK_VERSION,
        instance_type=processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}/repack-model",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )
    step_repack_args = repack_processor.run(
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/input/model",
            ),
        ],
        outputs=[
            ProcessingOutput(output_name="repacked", source="/opt/ml/processing/output/model"),
        ],
        code="repack.py",
        source_dir="source_scripts/inference",
        arguments=["--features", feature_list],
    )
    step_repack = ProcessingStep(name="RepackBankMarketingModel", step_args=step_repack_args)

    # The registered artifact is the REPACKED one. model_data must point at the
    # object, not the directory the processing output writes into.
    repacked_model_data = Join(
        on="/",
        values=[
            step_repack.properties.ProcessingOutputConfig.Outputs["repacked"].S3Output.S3Uri,
            "model.tar.gz",
        ],
    )

    # --------------------------------------------------------- 4. evaluate step
    # Pin the output location: baseline.json's URI is needed at DEFINITION time
    # for ModelMetrics, so it cannot be a runtime step property. The execution ID
    # keeps each run's baseline immutable, which matters because a model package
    # version's metrics must keep describing the artifact it was registered with.
    baseline_prefix_parts = [
        "s3:/", data_bucket, "model-baselines", ExecutionVariables.PIPELINE_EXECUTION_ID,
    ]
    evaluation_destination = Join(on="/", values=baseline_prefix_parts)
    baseline_s3_uri = Join(on="/", values=baseline_prefix_parts + ["baseline.json"])

    sklearn_eval = FrameworkProcessor(
        estimator_cls=SKLearn,
        framework_version=SKLEARN_FRAMEWORK_VERSION,
        instance_type=processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}/evaluate-model",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        env=mlflow_env,
    )
    evaluation_report = PropertyFile(
        name="BankMarketingEvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )
    step_eval_args = sklearn_eval.run(
        inputs=[
            # Score the artifact that will actually be served, not the raw
            # training output.
            ProcessingInput(
                source=step_repack.properties.ProcessingOutputConfig.Outputs[
                    "repacked"].S3Output.S3Uri,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=process_outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
            ),
            ProcessingInput(
                source=process_outputs["lineage"].S3Output.S3Uri,
                destination="/opt/ml/processing/lineage",
            ),
            ProcessingInput(
                source=process_outputs["mlflow"].S3Output.S3Uri,
                destination="/opt/ml/processing/mlflow",
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                source="/opt/ml/processing/evaluation",
                destination=evaluation_destination,
            ),
        ],
        code="main.py",
        source_dir="source_scripts/evaluate/evaluate_xgboost",
        arguments=[
            "--training-job-name", step_train.properties.TrainingJobName,
            "--model-package-group", model_package_group_name,
            "--feature-schema-version", str(schema.FEATURE_SCHEMA_VERSION),
            "--code-commit-sha", code_commit_sha,
        ],
    )
    step_eval = ProcessingStep(
        name="EvaluateBankMarketingModel",
        step_args=step_eval_args,
        property_files=[evaluation_report],
    )

    # --------------------------------------------------------- 5. register step
    inference_image = retrieve_image_uri(
        framework="xgboost",
        region=region,
        version=XGBOOST_VERSION,
        image_scope="inference",
    )

    # Script-mode flags live on the model package itself, so ANY deployment of
    # this package runs code/inference.py -- not only one that remembers to set
    # them. The deploy repo sets them again alongside the capture configuration.
    model = Model(
        image_uri=inference_image,
        model_data=repacked_model_data,
        role=role,
        sagemaker_session=sagemaker_session,
        env={
            "SAGEMAKER_PROGRAM": "inference.py",
            "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
        },
    )

    # The link Lab 5 follows: describe_model_package ->
    # ModelMetrics.ModelQuality.Statistics.S3Uri -> baseline.json.
    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=baseline_s3_uri,
            content_type="application/json",
        )
    )

    # Fills Studio's Train tab (training job, metric, hyperparameters, image).
    model_card = _training_model_card(
        step_train=step_train,
        hyperparameters=train_hyperparameters,
        training_image=retrieve_image_uri(
            framework="xgboost",
            region=region,
            version=XGBOOST_VERSION,
            image_scope="training",
        ),
        dataset_uris=[
            process_outputs["train"].S3Output.S3Uri,
            process_outputs["validation"].S3Output.S3Uri,
        ],
        model_artifact_dir=step_repack.properties.ProcessingOutputConfig.Outputs[
            "repacked"].S3Output.S3Uri,
    )

    register_args = model.register(
        content_types=["application/json", "text/csv"],
        response_types=["application/json"],
        model_package_group_name=model_package_group_name,
        approval_status=model_approval_status,
        model_metrics=model_metrics,
        model_card=model_card,
        description=(
            "XGBoost bank-marketing model with the shared custom inference "
            "handler, trained on the Lab 2 Iceberg tables."
        ),
        customer_metadata_properties={
            k: v for k, v in {
                "feature_schema_version": str(schema.FEATURE_SCHEMA_VERSION),
                "code_commit_sha": code_commit_sha,
            }.items() if v
        },
    )
    step_register = ModelStep(name="RegisterBankMarketingModel", step_args=register_args)

    # ------------------------------------------------------- 6. condition + wire
    step_cond = ConditionStep(
        name="CheckAccuracyBankMarketingEvaluation",
        conditions=[
            ConditionGreaterThanOrEqualTo(
                left=JsonGet(
                    step_name=step_eval.name,
                    property_file=evaluation_report,
                    json_path="classification_metrics.accuracy.value",
                ),
                right=accuracy_threshold_param,
            )
        ],
        if_steps=[step_register],
        else_steps=[],
    )

    return Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type,
            processing_instance_count,
            training_instance_type,
            model_approval_status,
            athena_database_param,
            training_table_param,
            evaluation_table_param,
            validation_fraction_param,
            accuracy_threshold_param,
            mlflow_tracking_uri_param,
            mlflow_experiment_name_param,
            mlflow_parent_run_id,
        ],
        steps=[step_process, step_train, step_repack, step_eval, step_cond],
        sagemaker_session=sagemaker_session,
    )


def get_pipeline_custom_tags(tags, region, sagemaker_project_arn):
    """Add the SageMaker project tag when it is not already present."""
    try:
        existing_keys = {tag.get("Key") for tag in tags}
        project_name = sagemaker_project_arn.split("/")[-1] if sagemaker_project_arn else ""
        custom_tags = []
        if project_name and "sagemaker:project-name" not in existing_keys:
            custom_tags.append({"Key": "sagemaker:project-name", "Value": project_name})
        return custom_tags + tags
    except Exception:
        return tags
