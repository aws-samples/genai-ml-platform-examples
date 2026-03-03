def get_pipeline(
    region,
    role=None,
    default_bucket=None,
    model_package_group_name="BankMarketingPackageGroup",
    pipeline_name="BankMarketingPipeline",
    base_job_prefix="BankMarketing",
    bucket_kms_id=None,
    sagemaker_session=None,
    sagemaker_project_arn=None,
    glue_database_name=None,
    glue_table_name=None,
    mlflow_tracking_uri=None,
    mlflow_experiment_name="BankMarketingExperiment",
):
    """Gets a SageMaker ML Pipeline instance working with bank marketing data.

    Args:
        region: AWS region to create and run the pipeline.
        role: IAM role to create and run steps and pipeline.
        default_bucket: the bucket to use for storing the artifacts

    Returns:
        an instance of a pipeline
    """
    import boto3
    import sagemaker
    import sagemaker.session
    
    from sagemaker.estimator import Estimator
    from sagemaker.inputs import TrainingInput
    from sagemaker.model_metrics import (
        MetricsSource,
        ModelMetrics,
    )
    from sagemaker.processing import (
        FrameworkProcessor,
        ProcessingInput,
        ProcessingOutput,
        ScriptProcessor,
    )
    from sagemaker.sklearn.processing import SKLearnProcessor
    from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
    from sagemaker.workflow.condition_step import (
        ConditionStep,
    )
    from sagemaker.workflow.functions import (
        JsonGet,
    )
    from sagemaker.workflow.parameters import (
        ParameterInteger,
        ParameterString,
    )
    from sagemaker.workflow.pipeline import Pipeline
    from sagemaker.workflow.properties import PropertyFile
    from sagemaker.workflow.steps import (
        ProcessingStep,
        TrainingStep,
    )
    from sagemaker.workflow.step_collections import RegisterModel
    from sagemaker.workflow.pipeline_context import PipelineSession
    
    # Ensure we have a PipelineSession (required for step_args pattern)
    if sagemaker_session is None or not isinstance(sagemaker_session, PipelineSession):
        sagemaker_session = PipelineSession(default_bucket=default_bucket)
    
    # Parameters for pipeline execution
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge"
    )
    processing_instance_count = ParameterInteger(
        name="ProcessingInstanceCount", default_value=1
    )
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.xlarge"
    )
    model_approval_status = ParameterString(
        name="ModelApprovalStatus", default_value="PendingManualApproval"
    )
    glue_database = ParameterString(
        name="GlueDatabase", default_value=glue_database_name
    )
    glue_table = ParameterString(
        name="GlueTable", default_value=glue_table_name
    )
    mlflow_tracking_uri_param = ParameterString(
        name="MLflowTrackingUri", default_value=mlflow_tracking_uri or ""
    )
    mlflow_experiment_name_param = ParameterString(
        name="MLflowExperimentName", default_value=mlflow_experiment_name or "BankMarketingExperiment"
    )
    mlflow_parent_run_id = ParameterString(
        name="MLflowParentRunId", default_value=""
    )
    
    # Create FrameworkProcessor for data preprocessing (supports source_dir + requirements.txt)
    sklearn_processor = FrameworkProcessor(
        estimator_cls=sagemaker.sklearn.estimator.SKLearn,
        framework_version="1.4-2",
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/sklearn-preprocess",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        env={
            "MLFLOW_TRACKING_URI": mlflow_tracking_uri_param,
            "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name_param,
            "MLFLOW_PARENT_RUN_ID": mlflow_parent_run_id
        }
    )
    
    # Processing step using AWS Data Wrangler with requirements.txt
    step_process_args = sklearn_processor.run(
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
            ProcessingOutput(output_name="mlflow", source="/opt/ml/processing/mlflow"),
        ],
        code="main.py",
        source_dir="source_scripts/preprocessing/prepare_bank_data",
        arguments=[
            "--database-name", glue_database,
            "--table-name", glue_table
        ],
    )
    step_process = ProcessingStep(
        name="PreprocessBankMarketingData",
        step_args=step_process_args,
    )

    # training step for generating model artifacts using script-mode XGBoost with MLflow
    model_path = f"s3://{default_bucket}/{base_job_prefix}/BankMarketingTrain"

    from sagemaker.xgboost.estimator import XGBoost

    xgb_train = XGBoost(
        entry_point="train.py",
        source_dir="source_scripts/training/xgboost",
        framework_version="1.7-1",
        instance_type=training_instance_type,
        instance_count=1,
        output_path=model_path,
        base_job_name=f"{base_job_prefix}/bank-marketing-train",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        hyperparameters={
            "max_depth": 5,
            "eta": 0.2,
            "gamma": 4,
            "min_child_weight": 6,
            "subsample": 0.8,
            "num_round": 100,
            "objective": "binary:logistic",
        },
        environment={
            "MLFLOW_TRACKING_URI": mlflow_tracking_uri_param,
            "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name_param,
            "MLFLOW_PARENT_RUN_ID": mlflow_parent_run_id,
        },
    )
    step_train = TrainingStep(
        name="TrainBankMarketingModel",
        estimator=xgb_train,
        inputs={
            "train": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
            "validation": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["validation"].S3Output.S3Uri,
                content_type="text/csv",
            ),
            "mlflow": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["mlflow"].S3Output.S3Uri,
                content_type="text/plain",
            ),
        },
    )

    # FrameworkProcessor for evaluation (supports source_dir + requirements.txt)
    sklearn_eval = FrameworkProcessor(
        estimator_cls=sagemaker.sklearn.estimator.SKLearn,
        framework_version="1.4-2",
        instance_type=processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}/sklearn-eval",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
        env={
            "MLFLOW_TRACKING_URI": mlflow_tracking_uri_param,
            "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name_param,
            "MLFLOW_PARENT_RUN_ID": mlflow_parent_run_id
        }
    )
    evaluation_report = PropertyFile(
        name="BankMarketingEvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )
    step_eval_args = sklearn_eval.run(
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["mlflow"].S3Output.S3Uri,
                destination="/opt/ml/processing/mlflow",
            ),
        ],
        outputs=[
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
        ],
        code="main.py",
        source_dir="source_scripts/evaluate/evaluate_xgboost",
    )
    step_eval = ProcessingStep(
        name="EvaluateBankMarketingModel",
        step_args=step_eval_args,
        property_files=[evaluation_report],
    )

    # register model step that will be conditionally executed
    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri="{}/evaluation.json".format(
                step_eval.arguments["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"]
            ),
            content_type="application/json",
        )
    )

    step_register = RegisterModel(
        name="RegisterBankMarketingModel",
        estimator=xgb_train,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["text/csv"],
        response_types=["text/csv"],
        inference_instances=["ml.t2.medium", "ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=model_package_group_name,
        approval_status=model_approval_status,
        model_metrics=model_metrics,
    )

    # condition step for evaluating model quality and branching execution
    from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
    
    cond_gte = ConditionGreaterThanOrEqualTo(
        left=JsonGet(
            step_name=step_eval.name, property_file=evaluation_report, json_path="classification_metrics.accuracy.value"
        ),
        right=0.7,
    )
    step_cond = ConditionStep(
        name="CheckAccuracyBankMarketingEvaluation",
        conditions=[cond_gte],
        if_steps=[step_register],
        else_steps=[],
    )

    # Create pipeline
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type,
            processing_instance_count,
            training_instance_type,
            model_approval_status,
            glue_database,
            glue_table,
            mlflow_tracking_uri_param,
            mlflow_experiment_name_param,
            mlflow_parent_run_id,
        ],
        steps=[step_process, step_train, step_eval, step_cond],
        sagemaker_session=sagemaker_session,
    )
    return pipeline


def get_pipeline_custom_tags(tags, region, sagemaker_project_arn):
    """Get custom tags for the pipeline.
    
    Args:
        tags: Existing tags
        region: AWS region
        sagemaker_project_arn: SageMaker project ARN
        
    Returns:
        Combined tags
    """
    try:
        # Check if project-name tag already exists
        existing_keys = {tag.get("Key") for tag in tags}
        
        project_name = sagemaker_project_arn.split("/")[-1] if sagemaker_project_arn else ""
        custom_tags = []
        
        if project_name and "sagemaker:project-name" not in existing_keys:
            custom_tags.append({"Key": "sagemaker:project-name", "Value": project_name})
        
        return custom_tags + tags
    except Exception:
        return tags
