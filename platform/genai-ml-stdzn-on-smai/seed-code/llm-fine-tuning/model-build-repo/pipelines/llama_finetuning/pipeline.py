from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.model_step import ModelStep
from sagemaker.workflow.functions import Join
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.pytorch.processing import PyTorchProcessor
from sagemaker.model import Model
from sagemaker.workflow.pipeline_context import PipelineSession
import mlflow
from .config import Config


def get_pipeline(
    region=None,
    role=None,
    default_bucket=None,
    pipeline_name=None,
    model_package_group_name=None,
    base_job_prefix=None,
    sagemaker_project_name=None,
):
    """
    Get a SageMaker Pipeline instance.
    
    Args:
        region: AWS region
        role: SageMaker execution role ARN
        default_bucket: S3 bucket for pipeline artifacts
        pipeline_name: Name of the pipeline
        model_package_group_name: Model package group name for registry
        base_job_prefix: Prefix for SageMaker jobs
        sagemaker_project_name: SageMaker project name
    
    Returns:
        Pipeline instance
    """
    # Load config from file - config file is mandatory
    config = Config.from_file("configs/dev-config.json")
    
    # Override with provided parameters only if not already set in config
    print(f"Config SAGEMAKER_ROLE from file: {config.SAGEMAKER_ROLE}")
    print(f"Role parameter from CloudFormation: {role}")
    
    if role and not config.SAGEMAKER_ROLE:
        config.SAGEMAKER_ROLE = role
        print(f"Using CloudFormation role (config was empty)")
    else:
        print(f"Using config file role: {config.SAGEMAKER_ROLE}")
    
    if default_bucket:
        config.S3_BUCKET = default_bucket
    if pipeline_name:
        config.PIPELINE_NAME = pipeline_name
    if model_package_group_name:
        config.MODEL_PACKAGE_GROUP_NAME = model_package_group_name
    if region:
        config.AWS_REGION = region
    
    print(f"Final SAGEMAKER_ROLE being used: {config.SAGEMAKER_ROLE}")
    
    # Set up MLflow if configured
    if hasattr(config, 'MLFLOW_TRACKING_ARN') and config.MLFLOW_TRACKING_ARN:
        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_ARN)
    
    # Create pipeline session
    pipeline_session = PipelineSession()
    
    # Use PyTorchProcessor for CPU instance support
    pytorch_processor = PyTorchProcessor(
        framework_version='2.1',
        role=config.SAGEMAKER_ROLE,
        instance_type=config.PROCESSING_INSTANCE_TYPE,
        instance_count=config.PROCESSING_INSTANCE_COUNT,
        py_version='py310',
        sagemaker_session=pipeline_session,
        env={
            "MLFLOW_TRACKING_ARN": config.MLFLOW_TRACKING_ARN,
            "MLFLOW_EXPERIMENT_NAME": f"{config.PIPELINE_NAME}-experiment"
        }
    )
    
    # Preprocessing step using PyTorch processor
    preprocessing_step = ProcessingStep(
        name="PreprocessDollyDataset",
        step_args=pytorch_processor.run(
            code="pipelines/llama_finetuning/steps/preprocess.py",
            inputs=[],  # Dolly dataset downloaded in processing
            outputs=[
                ProcessingOutput(
                    output_name="train",
                    source="/opt/ml/processing/train",
                    destination=config.TRAIN_DATA
                ),
                ProcessingOutput(
                    output_name="test",
                    source="/opt/ml/processing/test",
                    destination=config.TEST_DATA
                )
            ],
            arguments=["--task", "preprocessing"]
        )
    )
    

    
    # Training step - defined after base transform to show they're independent
    training_step = TrainingStep(
        name="FineTuneLlama",
        estimator=JumpStartEstimator(
            model_id=config.MODEL_ID,
            instance_type=config.TRAINING_INSTANCE_TYPE,
            instance_count=1,
            role=config.SAGEMAKER_ROLE,
            disable_output_compression=False,  # Ensure model.tar.gz is created
            environment={
                "accept_eula": "true",
                "MLFLOW_TRACKING_ARN": config.MLFLOW_TRACKING_ARN,
                "MLFLOW_EXPERIMENT_NAME": f"{config.PIPELINE_NAME}-experiment"
            },
            hyperparameters={
                "epochs": config.EPOCHS,
                "instruction_tuned": config.INSTRUCTION_TUNED,
                "max_input_length": config.MAX_INPUT_LENGTH,
            },
            sagemaker_session=pipeline_session,
        ),
        inputs={
            "training": preprocessing_step.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri
        },
        depends_on=[preprocessing_step]
    )
    
    # Create model for registration
    # Training outputs model.tar.gz which can be used directly for registration
    
    # Get the correct inference image URI for the model
    from sagemaker import image_uris
    inference_image_uri = image_uris.retrieve(
        region=config.AWS_REGION,
        framework=None,
        image_scope="inference",
        model_id=config.MODEL_ID,
        model_version=config.MODEL_VERSION,
        instance_type="ml.g5.2xlarge"
    )
    
    # Use model artifacts from training step
    # Training outputs model.tar.gz, so use the S3 URI directly
    model_data_uri = training_step.properties.ModelArtifacts.S3ModelArtifacts
    
    finetuned_model = Model(
        image_uri=inference_image_uri,
        model_data=model_data_uri,
        role=config.SAGEMAKER_ROLE,
        sagemaker_session=pipeline_session,
    )
    
    # Registration step using ModelStep
    register_step = ModelStep(
        name="RegisterLlamaModel",
        step_args=finetuned_model.register(
            content_types=["application/json"],
            response_types=["application/json"],
            # List of supported GPU instance types for LLaMA inference
            inference_instances=[
                "ml.g5.xlarge",
                "ml.g5.2xlarge", 
                "ml.g5.4xlarge",
                "ml.g5.12xlarge",
                "ml.p3.2xlarge",
                "ml.p3.8xlarge"
            ],
            transform_instances=[
                "ml.g5.xlarge",
                "ml.g5.2xlarge",
                "ml.g5.4xlarge",
                "ml.g5.12xlarge"
            ],
            model_package_group_name=model_package_group_name,
            approval_status="PendingManualApproval",
        ),
        depends_on=[training_step]
    )
    
    pipeline = Pipeline(
        name=pipeline_name,
        steps=[
            preprocessing_step,
            training_step,
            register_step
        ]
    )
    
    return pipeline
