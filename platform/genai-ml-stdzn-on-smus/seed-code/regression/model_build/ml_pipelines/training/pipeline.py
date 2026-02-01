def get_pipeline(
    region,
    role=None,
    default_bucket=None,
    model_package_group_name="AbalonePackageGroup",
    pipeline_name="AbalonePipeline",
    base_job_prefix="Abalone",
    bucket_kms_id=None,
    sagemaker_session=None,
    glue_database_name=None,
    glue_table_name=None,
):
    """Gets a SageMaker ML Pipeline instance working with on abalone data.

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
    
    # Create a ScriptProcessor for data preprocessing with requirements.txt
    script_processor = ScriptProcessor(
        image_uri=sagemaker.image_uris.retrieve(
            framework="sklearn",
            region=region,
            version="1.0-1",
            py_version="py3",
            instance_type="ml.m5.xlarge",
        ),
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/requirements-preprocess",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )
    
    # Processing step using AWS Data Wrangler with requirements.txt
    step_process = ProcessingStep(
        name="PreprocessAbaloneData",
        processor=script_processor,
        inputs=[
            # Add requirements.txt as an input
            ProcessingInput(
                source=f"s3://{default_bucket}/SMUSMLOPS/requirements-preprocess/input/dependencies/",
                destination="/opt/ml/processing/input/requirements",
                input_name="requirements"
            )
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
        ],
        code="source_scripts/preprocessing/prepare_abalone_data/main.py",
        job_arguments=[
            "--database-name", glue_database,
            "--table-name", glue_table
        ],
    )

    # training step for generating model artifacts
    model_path = f"s3://{default_bucket}/{base_job_prefix}/AbaloneTrain"

    image_uri = sagemaker.image_uris.retrieve(
        framework="xgboost",
        region=region,
        version="1.0-1",
        py_version="py3",
        instance_type="ml.m5.xlarge",
    )

    xgb_train = Estimator(
        image_uri=image_uri,
        instance_type=training_instance_type,
        instance_count=1,
        output_path=model_path,
        base_job_name=f"{base_job_prefix}/abalone-train",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )
    xgb_train.set_hyperparameters(
        objective="reg:linear",
        num_round=50,
        max_depth=5,
        eta=0.2,
        gamma=4,
        min_child_weight=6,
        subsample=0.7,
        silent=0,
    )
    step_train = TrainingStep(
        name="TrainAbaloneModel",
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
        },
    )

    # processing step for evaluation
    script_eval = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}/script-abalone-eval",
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )
    evaluation_report = PropertyFile(
        name="AbaloneEvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )
    step_eval = ProcessingStep(
        name="EvaluateAbaloneModel",
        processor=script_eval,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
            ),
        ],
        outputs=[
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
        ],
        code="source_scripts/evaluate/evaluate_xgboost/main.py",
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
        name="RegisterAbaloneModel",
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
    cond_lte = ConditionLessThanOrEqualTo(
        left=JsonGet(
            step_name=step_eval.name, property_file=evaluation_report, json_path="regression_metrics.mse.value"
        ),
        right=6.0,
    )
    step_cond = ConditionStep(
        name="CheckMSEAbaloneEvaluation",
        conditions=[cond_lte],
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
        ],
        steps=[step_process, step_train, step_eval, step_cond],
        sagemaker_session=sagemaker_session,
    )
    return pipeline
