"""Run the SageMaker Pipeline."""

import argparse
import json
import sys

from pipelines._utils import get_pipeline_driver, get_pipeline_custom_tags


def main():
    """Main entry point for running the pipeline."""
    parser = argparse.ArgumentParser(
        description="Create/Update and run SageMaker Pipeline"
    )
    parser.add_argument(
        "--module-name",
        type=str,
        default="pipelines.llama_finetuning.pipeline",
        help="Python module name for the pipeline",
    )
    parser.add_argument(
        "--role-arn",
        type=str,
        required=True,
        help="SageMaker execution role ARN",
    )
    parser.add_argument(
        "--tags",
        type=str,
        default="[]",
        help="JSON string of tags to apply to pipeline",
    )
    parser.add_argument(
        "--kwargs",
        type=str,
        default="{}",
        help="JSON string of keyword arguments for get_pipeline()",
    )
    
    args = parser.parse_args()
    
    # Parse tags
    tags = json.loads(args.tags)
    
    print(f"Creating/Updating pipeline from module: {args.module_name}")
    print(f"Pipeline kwargs: {args.kwargs}")
    
    # Get pipeline using dynamic import
    pipeline = get_pipeline_driver(args.module_name, args.kwargs)
    
    print(f"Pipeline name: {pipeline.name}")
    
    # Get custom tags if defined
    tags = get_pipeline_custom_tags(args.module_name, args.kwargs, tags)
    
    # Upsert pipeline (create or update)
    print("Upserting pipeline...")
    pipeline.upsert(
        role_arn=args.role_arn,
        tags=tags
    )
    print(f"✓ Pipeline upserted: {pipeline.name}")
    
    # Start pipeline execution
    print("Starting pipeline execution...")
    execution = pipeline.start()
    print(f"✓ Pipeline execution started: {execution.arn}")
    
    # Print execution details
    print(f"\nExecution details:")
    print(f"  ARN: {execution.arn}")
    print(f"  Status: {execution.describe()['PipelineExecutionStatus']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


