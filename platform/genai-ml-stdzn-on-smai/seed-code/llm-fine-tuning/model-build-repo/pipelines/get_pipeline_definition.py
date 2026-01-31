"""Get the pipeline definition."""

import argparse
import sys

from pipelines._utils import get_pipeline_driver


def main():
    """Main entry point for getting pipeline definition."""
    parser = argparse.ArgumentParser(
        description="Get SageMaker Pipeline definition"
    )
    parser.add_argument(
        "--module-name",
        type=str,
        default="pipelines.llama_finetuning.pipeline",
        help="Python module name for the pipeline",
    )
    parser.add_argument(
        "--kwargs",
        type=str,
        default="{}",
        help="JSON string of keyword arguments for get_pipeline()",
    )
    
    args = parser.parse_args()
    
    # Get pipeline using dynamic import
    pipeline = get_pipeline_driver(args.module_name, args.kwargs)
    
    # Print pipeline definition
    print(pipeline.definition())
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
