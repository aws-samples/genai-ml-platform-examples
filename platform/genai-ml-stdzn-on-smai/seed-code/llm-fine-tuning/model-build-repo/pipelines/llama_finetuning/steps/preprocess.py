#!/usr/bin/env python3
"""
Preprocessing step for Dolly dataset.
This script downloads and preprocesses the Dolly dataset for fine-tuning.
"""

import argparse
import os
import json
import logging
import subprocess
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Install datasets library first if not available
try:
    import datasets
except ImportError:
    logger.info("Installing datasets library...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "--timeout=300",
        "--retries=5",
        "datasets",
        "-q"
    ])
    import datasets

# Install MLflow after datasets
try:
    import mlflow
except ImportError:
    logger.info("Installing MLflow with SageMaker plugin...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "--timeout=300",
        "--retries=5",
        "mlflow",
        "sagemaker-mlflow",
        "-q"
    ])
    import mlflow

def preprocess():
    """Preprocess the Dolly dataset for fine-tuning"""
    logger.info("Starting data preprocessing...")
    
    # Set up MLflow tracking for SageMaker (matching Lab 2/3 notebook approach)
    # Use ARN directly - SageMaker SDK handles authentication automatically
    mlflow_tracking_arn = os.getenv("MLFLOW_TRACKING_ARN")
    
    if mlflow_tracking_arn:
        logger.info(f"Setting MLflow tracking URI to ARN: {mlflow_tracking_arn}")
        mlflow.set_tracking_uri(mlflow_tracking_arn)
    else:
        logger.warning("No MLFLOW_TRACKING_ARN found, MLflow tracking disabled")
    
    # Set experiment name
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "llama-finetuning-pipeline")
    mlflow.set_experiment(experiment_name)
    
    # Start MLflow run for preprocessing
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with mlflow.start_run(run_name=f"preprocessing-{timestamp}"):
        logger.info(f"Started MLflow run: preprocessing-{timestamp}")
        
        return _preprocess_data()

def _preprocess_data():
    """Internal function to handle the actual preprocessing logic"""
    from datasets import load_dataset
    
    # Create output directories (using /opt/ml/processing for ProcessingStep)
    os.makedirs("/opt/ml/processing/train", exist_ok=True)
    os.makedirs("/opt/ml/processing/test", exist_ok=True)
    
    # Load dataset
    logger.info("Loading Dolly dataset...")
    try:
        # Add more detailed logging
        logger.info("Attempting to download databricks/databricks-dolly-15k dataset...")
        dolly_dataset = load_dataset("databricks/databricks-dolly-15k", split="train")
        logger.info(f"✓ Successfully loaded {len(dolly_dataset)} samples")
        
        # Log sample data structure
        if len(dolly_dataset) > 0:
            sample = dolly_dataset[0]
            logger.info(f"Sample data keys: {list(sample.keys())}")
            logger.info(f"Sample categories available: {set(dolly_dataset['category'])}")
            
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise
    
    # Filter for summarization tasks (exactly like Lab 2 notebook)
    logger.info("Filtering for summarization tasks...")
    try:
        summarization_dataset = dolly_dataset.filter(lambda example: example["category"] == "summarization")
        logger.info(f"Found {len(summarization_dataset)} summarization samples")
        
        if len(summarization_dataset) == 0:
            logger.warning("No summarization samples found, using all data")
            summarization_dataset = dolly_dataset
        else:
            # Remove the category column (important step from notebook)
            summarization_dataset = summarization_dataset.remove_columns("category")
            logger.info("Removed 'category' column from dataset")
            
    except Exception as e:
        logger.error(f"Failed to filter dataset: {e}")
        logger.info("Using full dataset instead")
        summarization_dataset = dolly_dataset
    
    # Split into train/test (exactly like Lab 2 notebook)
    logger.info("Splitting into train/test sets...")
    try:
        train_and_test_dataset = summarization_dataset.train_test_split(test_size=0.1)
        logger.info("Dataset split completed successfully")
        
        # Log dataset statistics to MLflow
        mlflow.log_param("dataset_name", "databricks-dolly-15k")
        mlflow.log_param("task_filter", "summarization")
        mlflow.log_param("test_size", 0.1)
        mlflow.log_metric("total_samples", len(summarization_dataset))
        mlflow.log_metric("train_samples", len(train_and_test_dataset["train"]))
        mlflow.log_metric("test_samples", len(train_and_test_dataset["test"]))
        
    except Exception as e:
        logger.error(f"Failed to split dataset: {e}")
        raise
    
    # Create instruction template for fine-tuning (matches Lab 2 notebook)
    template = {
        "prompt": "Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Input:\n{context}\n\n",
        "completion": " {response}"
    }
    
    # Save training data (matches Lab 2 notebook)
    logger.info("Saving training data...")
    train_and_test_dataset["train"].to_json("/opt/ml/processing/train/train.jsonl")
    logger.info(f"Saved {len(train_and_test_dataset['train'])} training samples")
    
    # Save test data (matches Lab 2 notebook)
    logger.info("Saving test data...")
    train_and_test_dataset["test"].to_json("/opt/ml/processing/test/test.jsonl")
    logger.info(f"Saved {len(train_and_test_dataset['test'])} test samples")
    
    # Create batch transform input format
    # Format: {"id": 0, "text_inputs": "prompt + instruction + context"}
    logger.info("Creating batch transform input file...")
    batch_inputs = []
    for idx, row in enumerate(train_and_test_dataset["test"]):
        prompt_text = template["prompt"].format(
            instruction=row["instruction"],
            context=row["context"]
        )
        batch_input = {
            "id": idx,
            "text_inputs": prompt_text
        }
        batch_inputs.append(batch_input)
    
    # Save batch transform input
    with open("/opt/ml/processing/test/batch_input.jsonl", "w") as f:
        for entry in batch_inputs:
            f.write(json.dumps(entry) + "\n")
    logger.info(f"Saved {len(batch_inputs)} batch transform inputs")
    
    # Save template (matches Lab 2 notebook)
    logger.info("Saving template...")
    with open("/opt/ml/processing/train/template.json", "w") as f:
        json.dump(template, f, indent=2)
    logger.info("Template saved successfully")
    
    logger.info("Preprocessing completed successfully!")
    
    # Log statistics and verify files
    logger.info(f"Training samples: {len(train_and_test_dataset['train'])}")
    logger.info(f"Test samples: {len(train_and_test_dataset['test'])}")
    
    # Verify files were created
    train_file = "/opt/ml/processing/train/train.jsonl"
    test_file = "/opt/ml/processing/test/test.jsonl"
    template_file = "/opt/ml/processing/train/template.json"
    
    for file_path in [train_file, test_file, template_file]:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            logger.info(f"✓ {file_path} created successfully ({size} bytes)")
            # Log file sizes to MLflow
            file_name = os.path.basename(file_path)
            mlflow.log_metric(f"{file_name}_size_bytes", size)
        else:
            logger.error(f"✗ {file_path} was not created!")
            raise FileNotFoundError(f"Expected output file not found: {file_path}")
    
    # Log template as artifact
    mlflow.log_dict(template, "preprocessing/template.json")
    logger.info("Logged template to MLflow")


if __name__ == "__main__":
    logger.info("Starting preprocessing.")
    
    parser = argparse.ArgumentParser(description="Preprocess Dolly dataset for LLaMA fine-tuning")
    parser.add_argument("--task", type=str, default="preprocessing", help="Task type")
    args = parser.parse_args()
    
    try:
        logger.info("Starting Dolly Dataset Preprocessing")
        preprocess()
        logger.info("Preprocessing completed successfully")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        exit(1)
