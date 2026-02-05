"""Runs the SageMaker Pipeline with Glue Catalog integration."""
import argparse
import json
import logging
import os
import sys

import boto3
import sagemaker
import sagemaker.session

from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.parameters import ParameterString

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-name", type=str, required=True)
    parser.add_argument("--role-arn", type=str, required=True)
    parser.add_argument("--tags", type=str, default=None)
    parser.add_argument("--kwargs", type=str, default=None)
    parser.add_argument("--pipeline-name", type=str, default=None)
    parser.add_argument("--log-level", type=str, default=None)
    args = parser.parse_args()

    if args.log_level is not None:
        level = logging.getLevelName(args.log_level.upper())
        logger.setLevel(level)

    tags = json.loads(args.tags) if args.tags is not None else []

    try:
        module = __import__(args.module_name, fromlist=["get_pipeline"])
        get_pipeline = getattr(module, "get_pipeline")
    except Exception as e:
        logger.error(f"Failed to import the module {args.module_name}: {e}")
        sys.exit(1)

    kwargs = json.loads(args.kwargs) if args.kwargs is not None else {}

    logger.info("Getting pipeline")
    pipeline = get_pipeline(**kwargs)

    if args.pipeline_name is not None:
        pipeline.name = args.pipeline_name

    logger.info(f"Creating/updating pipeline: {pipeline.name}")
    pipeline.upsert(role_arn=args.role_arn, tags=tags)

    logger.info("Starting pipeline execution")
    pipeline.start()

    logger.info(f"Pipeline {pipeline.name} successfully created/updated and started")


if __name__ == "__main__":
    main()
