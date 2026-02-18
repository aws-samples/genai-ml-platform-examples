"""
SageMaker SDK v3 Generator Component.

Converts training scripts to SageMaker-compatible format using current SDK v3 syntax and patterns.
"""

import ast
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from ..models.analysis import AnalysisReport, PatternAnalysis
from ..utils.exceptions import SageMigratorError


@dataclass
class EstimatorConfig:
    """Configuration for SageMaker estimator generation."""
    framework: str
    framework_version: str
    python_version: str
    instance_type: str
    instance_count: int
    entry_point: str
    source_dir: str
    hyperparameters: Dict[str, str]
    role: str
    use_spot_instances: bool = False
    max_run: int = 86400  # 24 hours default


@dataclass
class PipelineConfig:
    """Configuration for SageMaker pipeline generation."""
    pipeline_name: str
    role: str
    bucket: str
    prefix: str
    use_local_session: bool = True


class SDKv3Generator:
    """
    Generates SageMaker SDK v3 compatible training scripts and pipeline definitions.
    
    This component converts EC2/local training code to SageMaker-compatible format,
    implementing current SDK v3 patterns and best practices.
    """
    
    def __init__(self):
        self.supported_frameworks = {
            'pytorch': {
                'versions': ['2.0.1', '2.1.0', '2.2.0'],
                'python_versions': ['py310', 'py311'],
                'default_version': '2.1.0',
                'default_python': 'py310'
            },
            'tensorflow': {
                'versions': ['2.13.0', '2.14.0', '2.15.0'],
                'python_versions': ['py310', 'py311'],
                'default_version': '2.13.0',
                'default_python': 'py310'
            },
            'sklearn': {
                'versions': ['1.2-1', '1.3-1'],
                'python_versions': ['py310', 'py311'],
                'default_version': '1.2-1',
                'default_python': 'py310'
            }
        }
        
        self.instance_types = {
            'training': [
                'ml.m5.large', 'ml.m5.xlarge', 'ml.m5.2xlarge', 'ml.m5.4xlarge',
                'ml.c5.xlarge', 'ml.c5.2xlarge', 'ml.c5.4xlarge',
                'ml.p3.2xlarge', 'ml.p3.8xlarge', 'ml.p3.16xlarge',
                'ml.g4dn.xlarge', 'ml.g4dn.2xlarge', 'ml.g4dn.4xlarge'
            ],
            'inference': [
                'ml.t2.medium', 'ml.t2.large', 'ml.m5.large', 'ml.m5.xlarge',
                'ml.c5.large', 'ml.c5.xlarge', 'ml.c5.2xlarge',
                'ml.g4dn.xlarge', 'ml.g4dn.2xlarge'
            ]
        }

    def generate_training_script(self, source_code: str, analysis: AnalysisReport) -> str:
        """
        Convert source training code to SageMaker-compatible format.
        
        Args:
            source_code: Original training script content
            analysis: Code analysis results
            
        Returns:
            SageMaker-compatible training script
        """
        try:
            # Parse the source code
            tree = ast.parse(source_code)
            
            # Generate SageMaker-compatible script
            sagemaker_script = self._convert_to_sagemaker_format(tree, analysis)
            
            return sagemaker_script
            
        except SyntaxError as e:
            raise SageBridgeError(f"Failed to parse source code: {e}")
        except Exception as e:
            raise SageBridgeError(f"Failed to generate training script: {e}")

    def generate_estimator_config(self, analysis: AnalysisReport) -> EstimatorConfig:
        """
        Generate SageMaker estimator configuration based on analysis.
        
        Args:
            analysis: Code analysis results
            
        Returns:
            Estimator configuration
        """
        # Detect framework from dependencies
        all_packages = analysis.dependencies.compatible_packages + analysis.dependencies.problematic_packages
        framework = self._detect_framework(all_packages)
        
        # Get framework configuration
        framework_config = self.supported_frameworks.get(framework, self.supported_frameworks['pytorch'])
        
        # Select appropriate instance type based on detected patterns
        instance_type = self._select_instance_type(analysis.patterns)
        
        return EstimatorConfig(
            framework=framework,
            framework_version=framework_config['default_version'],
            python_version=framework_config['default_python'],
            instance_type=instance_type,
            instance_count=self._determine_instance_count(analysis.patterns),
            entry_point='train.py',
            source_dir='code',
            hyperparameters=self._extract_hyperparameters(analysis),
            role='${aws:iam::role/SageMakerExecutionRole}',  # Placeholder for CloudFormation
            use_spot_instances=True,  # Cost optimization
            max_run=86400
        )

    def generate_pipeline_definition(self, estimator_config: EstimatorConfig, 
                                   pipeline_config: PipelineConfig) -> str:
        """
        Generate SageMaker pipeline definition using SDK v3 patterns.
        
        Args:
            estimator_config: Estimator configuration
            pipeline_config: Pipeline configuration
            
        Returns:
            Pipeline definition code
        """
        pipeline_code = f'''"""
SageMaker Pipeline Definition - Generated by SageBridge
"""

import boto3
from sagemaker import get_execution_role
from sagemaker.pytorch import PyTorch
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import TrainingStep
from sagemaker.workflow.pipeline_context import LocalPipelineSession
from sagemaker.inputs import TrainingInput
from sagemaker.workflow.parameters import ParameterString, ParameterInteger


def create_pipeline(
    role: str = None,
    bucket: str = "{pipeline_config.bucket}",
    prefix: str = "{pipeline_config.prefix}",
    use_local: bool = {str(pipeline_config.use_local_session).lower()}
) -> Pipeline:
    """
    Create SageMaker pipeline for training and evaluation.
    
    Args:
        role: SageMaker execution role ARN
        bucket: S3 bucket for data and artifacts
        prefix: S3 prefix for organization
        use_local: Whether to use LocalPipelineSession for testing
        
    Returns:
        Configured SageMaker pipeline
    """
    
    # Use LocalPipelineSession for local testing
    if use_local:
        session = LocalPipelineSession()
    else:
        session = None
    
    # Get execution role
    if role is None:
        try:
            role = get_execution_role()
        except Exception:
            # Fallback for local development
            role = "arn:aws:iam::{{AWS::AccountId}}:role/SageMakerExecutionRole"
    
    # Define pipeline parameters
    input_data = ParameterString(
        name="InputData",
        default_value=f"s3://{{bucket}}/{{prefix}}/data"
    )
    
    instance_count = ParameterInteger(
        name="InstanceCount",
        default_value={estimator_config.instance_count}
    )
    
    instance_type = ParameterString(
        name="InstanceType", 
        default_value="{estimator_config.instance_type}"
    )
    
    # Create estimator with SDK v3 patterns
    estimator = PyTorch(
        entry_point="{estimator_config.entry_point}",
        source_dir="{estimator_config.source_dir}",
        role=role,
        instance_type=instance_type,
        instance_count=instance_count,
        framework_version="{estimator_config.framework_version}",
        py_version="{estimator_config.python_version}",
        hyperparameters={estimator_config.hyperparameters},
        use_spot_instances={str(estimator_config.use_spot_instances).lower()},
        max_run={estimator_config.max_run},
        session=session,
        # SDK v3 specific configurations
        keep_alive_period_in_seconds=300,  # For warm pools
        container_log_level=20,  # INFO level logging
        disable_profiler=False,
        enable_network_isolation=False,
        encrypt_inter_container_traffic=True  # Security best practice
    )
    
    # Define training step
    training_step = TrainingStep(
        name="TrainingStep",
        estimator=estimator,
        inputs={{
            "training": TrainingInput(
                s3_data=input_data,
                content_type="application/x-parquet"  # Optimized format
            )
        }}
    )
    
    # Create pipeline
    pipeline = Pipeline(
        name="{pipeline_config.pipeline_name}",
        parameters=[input_data, instance_count, instance_type],
        steps=[training_step],
        session=session
    )
    
    return pipeline


def execute_pipeline_locally():
    """Execute pipeline using LocalPipelineSession for testing."""
    pipeline = create_pipeline(use_local=True)
    
    try:
        execution = pipeline.start()
        execution.wait()
        print(f"Pipeline execution completed: {{execution.arn}}")
        return execution
    except Exception as e:
        print(f"Pipeline execution failed: {{e}}")
        raise


if __name__ == "__main__":
    # For local testing
    execute_pipeline_locally()
'''
        
        return pipeline_code

    def _convert_to_sagemaker_format(self, tree: ast.AST, analysis: AnalysisReport) -> str:
        """Convert AST to SageMaker-compatible training script."""
        
        # Basic template for SageMaker training script
        sagemaker_template = '''"""
SageMaker Training Script - Generated by SageBridge
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

# SageMaker specific imports
import sagemaker
from sagemaker.session import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse SageMaker training job arguments."""
    parser = argparse.ArgumentParser()
    
    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAINING'))
    parser.add_argument('--test', type=str, default=os.environ.get('SM_CHANNEL_TESTING'))
    parser.add_argument('--output-data-dir', type=str, default=os.environ.get('SM_OUTPUT_DATA_DIR'))
    
    # Hyperparameters
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--learning-rate', type=float, default=0.001)
    
    return parser.parse_args()


def load_data(data_dir: str):
    """Load training data from SageMaker input channels."""
    logger.info(f"Loading data from {data_dir}")
    
    # Implementation will be customized based on original code
    # This is a placeholder that will be replaced with actual data loading logic
    pass


def create_model():
    """Create and return the model."""
    # Model definition will be extracted from original code
    # This is a placeholder that will be replaced with actual model creation
    pass


def train_model(model, train_data, args):
    """Train the model."""
    logger.info("Starting model training...")
    
    # Training logic will be extracted from original code
    # This is a placeholder that will be replaced with actual training logic
    pass


def save_model(model, model_dir: str):
    """Save model in SageMaker format."""
    logger.info(f"Saving model to {model_dir}")
    
    # Save both state_dict and TorchScript versions for compatibility
    # This will be implemented by TorchScriptHandler
    pass


def main():
    """Main training function."""
    args = parse_args()
    
    logger.info("Starting SageMaker training job")
    logger.info(f"Arguments: {args}")
    
    # Load data
    train_data = load_data(args.train)
    
    # Create model
    model = create_model()
    
    # Train model
    trained_model = train_model(model, train_data, args)
    
    # Save model
    save_model(trained_model, args.model_dir)
    
    logger.info("Training completed successfully")


if __name__ == "__main__":
    main()
'''
        
        return sagemaker_template

    def _detect_framework(self, packages: List[str]) -> str:
        """Detect ML framework from package dependencies."""
        for package in packages:
            if 'torch' in package.lower():
                return 'pytorch'
            elif 'tensorflow' in package.lower() or 'tf' in package.lower():
                return 'tensorflow'
            elif 'sklearn' in package.lower() or 'scikit-learn' in package.lower():
                return 'sklearn'
        
        # Default to PyTorch if no framework detected
        return 'pytorch'

    def _select_instance_type(self, patterns: PatternAnalysis) -> str:
        """Select appropriate instance type based on detected patterns."""
        # Check for distributed training (implies need for more resources)
        if patterns.distributed_training:
            return 'ml.p3.2xlarge'  # GPU instance for distributed training
        
        # Check if any training patterns suggest compute-intensive workload
        compute_intensive_patterns = ['deep_learning', 'neural_network', 'cnn', 'rnn', 'transformer']
        if any(pattern in ' '.join(patterns.training_patterns).lower() for pattern in compute_intensive_patterns):
            return 'ml.c5.2xlarge'  # Compute optimized
        
        # Default to general purpose
        return 'ml.m5.xlarge'

    def _determine_instance_count(self, patterns: PatternAnalysis) -> int:
        """Determine instance count based on distributed training patterns."""
        if patterns.distributed_training:
            return 2  # Start with 2 instances for distributed training
        return 1

    def _extract_hyperparameters(self, analysis: AnalysisReport) -> Dict[str, str]:
        """Extract hyperparameters from analysis."""
        # This would be enhanced to extract actual hyperparameters from code
        return {
            'epochs': '10',
            'batch_size': '32',
            'learning_rate': '0.001'
        }