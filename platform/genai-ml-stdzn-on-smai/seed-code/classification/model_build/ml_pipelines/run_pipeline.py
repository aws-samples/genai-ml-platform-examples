"""A CLI to create or update and run pipelines."""
import argparse
import json
import sys
import traceback

from ml_pipelines._utils import get_pipeline_driver, convert_struct, get_pipeline_custom_tags


def main():
    """The main harness that creates or updates and runs the pipeline."""
    parser = argparse.ArgumentParser(
        "Creates or updates and runs the pipeline for the pipeline script."
    )

    parser.add_argument(
        "-n",
        "--module-name",
        dest="module_name",
        type=str,
        help="The module name of the pipeline to import.",
    )
    parser.add_argument(
        "-kwargs",
        "--kwargs",
        dest="kwargs",
        default=None,
        help="Dict string of keyword arguments for the pipeline generation (if supported)",
    )
    parser.add_argument(
        "-role-arn",
        "--role-arn",
        dest="role_arn",
        type=str,
        help="The role arn for the pipeline service execution role.",
    )
    parser.add_argument(
        "-description",
        "--description",
        dest="description",
        type=str,
        default=None,
        help="The description of the pipeline.",
    )
    parser.add_argument(
        "-tags",
        "--tags",
        dest="tags",
        default=None,
        help="""List of dict strings of '[{"Key": "string", "Value": "string"}, ..]'""",
    )
    args = parser.parse_args()

    if args.module_name is None or args.role_arn is None:
        parser.print_help()
        sys.exit(2)
    tags = convert_struct(args.tags)

    try:
        # Get kwargs to check for MLflow configuration
        kwargs = convert_struct(args.kwargs)
        mlflow_tracking_uri = kwargs.get('mlflow_tracking_uri')
        mlflow_experiment_name = kwargs.get('mlflow_experiment_name', 'BankMarketingExperiment')
        
        # Create parent MLflow run if tracking URI is provided
        parent_run_id = None
        if mlflow_tracking_uri:
            try:
                import mlflow
                mlflow.set_tracking_uri(mlflow_tracking_uri)
                mlflow.set_experiment(mlflow_experiment_name)
                parent_run = mlflow.start_run(run_name=f"pipeline-{kwargs.get('pipeline_name', 'run')}")
                parent_run_id = parent_run.info.run_id
                print(f"\n###### Created parent MLflow run: {parent_run_id}")
                mlflow.end_run()  # End locally; child runs will nest under this ID
                
                # Add parent run ID to kwargs
                kwargs['mlflow_parent_run_id'] = parent_run_id
                args.kwargs = json.dumps(kwargs)
            except Exception as e:
                print(f"Warning: Failed to create parent MLflow run: {e}")
        
        pipeline = get_pipeline_driver(args.module_name, args.kwargs)
        print("###### Creating/updating a SageMaker Pipeline with the following definition:")
        parsed = json.loads(pipeline.definition())
        print(json.dumps(parsed, indent=2, sort_keys=True))

        all_tags = get_pipeline_custom_tags(args.module_name, args.kwargs, tags)

        upsert_response = pipeline.upsert(
            role_arn=args.role_arn, description=args.description, tags=all_tags
        )
        print("\n###### Created/Updated SageMaker Pipeline: Response received:")
        print(upsert_response)

        # Prepare execution parameters
        execution_params = {}
        if parent_run_id:
            execution_params['MLflowParentRunId'] = parent_run_id
            execution_params['MLflowTrackingUri'] = mlflow_tracking_uri
            execution_params['MLflowExperimentName'] = mlflow_experiment_name

        execution = pipeline.start(parameters=execution_params if execution_params else None)
        print(f"\n###### Execution started with PipelineExecutionArn: {execution.arn}")

        print("Waiting for the execution to finish...")

        execution.wait(max_attempts=120, delay=60)
        
        print("\n#####Execution completed. Execution step details:")

        print(execution.list_steps())
    except Exception as e:
        print(f"Exception: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
