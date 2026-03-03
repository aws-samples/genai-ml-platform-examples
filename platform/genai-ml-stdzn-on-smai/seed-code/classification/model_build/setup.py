"""Setup configuration for the bank marketing classification pipeline."""
from setuptools import find_packages, setup

setup(
    name="bank-marketing-pipeline",
    version="1.0.0",
    description="SageMaker Pipeline for Bank Marketing Classification",
    packages=find_packages(where="ml_pipelines"),
    package_dir={"": "ml_pipelines"},
    python_requires=">=3.10",
    install_requires=[
        "sagemaker>=2.257.0",
        "boto3",
        "awswrangler",
    ],
    entry_points={
        "console_scripts": [
            "run-pipeline=run_pipeline:main",
            "get-pipeline=get_pipeline_definition:main",
        ],
    },
)
