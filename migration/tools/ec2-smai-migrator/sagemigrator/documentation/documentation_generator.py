"""
Documentation Generator for SageBridge

Generates comprehensive documentation for migration artifacts including:
- README files with quick start instructions
- Migration guides explaining architectural decisions
- Troubleshooting documentation for common issues
- Deployment status tracking and monitoring guides
- Cost optimization recommendations and best practices
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models.analysis import AnalysisReport, RiskLevel
from ..models.artifacts import MigrationArtifacts, DocumentationPackage


class DocumentationGenerator:
    """Generates comprehensive documentation for SageMaker migration artifacts"""
    
    def __init__(self):
        """Initialize the documentation generator"""
        self.templates_dir = Path(__file__).parent / "templates"
        
    def generate_documentation_package(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> DocumentationPackage:
        """
        Generate complete documentation package for migration artifacts
        
        Args:
            analysis: Source code analysis report
            artifacts: Generated migration artifacts
            
        Returns:
            DocumentationPackage with all generated documentation
        """
        return DocumentationPackage(
            readme_files=self._generate_readme_files(analysis, artifacts),
            migration_guides=self._generate_migration_guides(analysis, artifacts),
            troubleshooting_docs=self._generate_troubleshooting_docs(analysis, artifacts),
            api_documentation=self._generate_api_documentation(analysis, artifacts),
            deployment_guides=self._generate_deployment_guides(analysis, artifacts)
        )
    
    def _generate_readme_files(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate README files with quick start instructions"""
        readme_content = self._create_main_readme(analysis, artifacts)
        project_readme = self._create_project_readme(analysis, artifacts)
        
        return {
            "README.md": readme_content,
            "PROJECT_README.md": project_readme
        }
    
    def _generate_migration_guides(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate migration guides explaining architectural decisions"""
        migration_guide = self._create_migration_guide(analysis, artifacts)
        architecture_guide = self._create_architecture_guide(analysis, artifacts)
        
        return {
            "MIGRATION_GUIDE.md": migration_guide,
            "ARCHITECTURE_GUIDE.md": architecture_guide
        }
    
    def _generate_troubleshooting_docs(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate troubleshooting documentation for common issues"""
        troubleshooting_guide = self._create_troubleshooting_guide(analysis, artifacts)
        common_issues = self._create_common_issues_guide(analysis, artifacts)
        
        return {
            "TROUBLESHOOTING.md": troubleshooting_guide,
            "COMMON_ISSUES.md": common_issues
        }
    
    def _generate_api_documentation(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate API documentation"""
        api_reference = self._create_api_reference(analysis, artifacts)
        
        return {
            "API_REFERENCE.md": api_reference
        }
    
    def _generate_deployment_guides(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> Dict[str, str]:
        """Generate deployment status tracking and monitoring guides"""
        deployment_guide = self._create_deployment_guide(analysis, artifacts)
        monitoring_guide = self._create_monitoring_guide(analysis, artifacts)
        cost_optimization = self._create_cost_optimization_guide(analysis, artifacts)
        
        return {
            "DEPLOYMENT_GUIDE.md": deployment_guide,
            "MONITORING_GUIDE.md": monitoring_guide,
            "COST_OPTIMIZATION.md": cost_optimization
        }
    
    def _create_main_readme(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create the main README file with quick start instructions"""
        project_name = Path(analysis.source_info.path).name
        
        readme_content = f"""# {project_name} - SageMaker Migration

This project has been migrated from EC2/local execution to Amazon SageMaker using SageBridge.

## 🎯 Migration Overview

**Original Setup:** {analysis.source_info.estimated_complexity.title()} EC2/local training with {analysis.source_info.python_files} Python files
**Migrated To:** Production-ready SageMaker MLOps pipeline with automated training, evaluation, and deployment

### Key Benefits
- **Scalability**: Auto-scaling training and inference
- **Cost Optimization**: Pay-per-use, spot instances support
- **MLOps**: Automated pipeline with CI/CD integration
- **Monitoring**: Built-in CloudWatch metrics and logging
- **Security**: IAM roles, encryption, VPC support
- **Collaboration**: Shared model registry and infrastructure

## 🚀 Quick Start

### Prerequisites
```bash
# Install dependencies
pip install sagemaker boto3 torch

# Configure AWS credentials
aws configure
```

### 1. Deploy Infrastructure
```bash
# Deploy CloudFormation stack
python infrastructure/scripts/deploy.py --region us-east-1

# Run the training pipeline
python pipeline/pipeline.py
```

### 2. Monitor Training
```bash
# Check pipeline status
aws sagemaker list-pipeline-executions --pipeline-name {project_name.lower()}-pipeline

# View in SageMaker console
https://console.aws.amazon.com/sagemaker/home#/pipelines
```

## 📁 Project Structure

```
{project_name}/
├── training/           # SageMaker training scripts
│   ├── train.py       # Main training script
│   ├── model.py       # Model definition
│   └── requirements.txt
├── inference/          # SageMaker inference code
│   ├── inference.py   # Custom inference handler
│   └── requirements.txt
├── pipeline/           # MLOps pipeline
│   ├── pipeline.py    # Pipeline definition
│   ├── preprocessing.py
│   └── evaluation.py
├── infrastructure/     # Infrastructure as Code
│   ├── cloudformation/
│   ├── iam/
│   └── scripts/
├── tests/             # Comprehensive test suite
│   ├── unit/
│   ├── integration/
│   └── performance/
└── docs/              # Documentation
    ├── MIGRATION_GUIDE.md
    ├── TROUBLESHOOTING.md
    └── DEPLOYMENT_GUIDE.md
```

## 🔧 Configuration

### Training Configuration
- **Instance Type**: ml.m5.large (configurable)
- **Framework**: PyTorch {self._get_framework_version(artifacts)}
- **Distributed Training**: {'Enabled' if analysis.patterns.distributed_training else 'Disabled'}

### Pipeline Configuration
- **Processing**: ml.m5.large
- **Training**: ml.m5.large  
- **Model Approval**: {'Automatic' if analysis.risks.overall_risk == RiskLevel.LOW else 'Manual'}

## 📊 Migration Results

### Risk Assessment
- **Overall Risk**: {analysis.risks.overall_risk.value.title()}
- **Estimated Effort**: {analysis.risks.estimated_effort_hours} hours
- **High Risk Items**: {len(analysis.risks.high_risk_items)}
- **Problematic Dependencies**: {len(analysis.dependencies.problematic_packages)}

### Generated Artifacts
- **Training Scripts**: {len(artifacts.training_scripts)}
- **Infrastructure Templates**: {len(artifacts.infrastructure.cloudformation_templates)}
- **Test Files**: {len(artifacts.testing_suite.unit_tests) + len(artifacts.testing_suite.integration_tests)}

## 🔗 Quick Links

- [Migration Guide](docs/MIGRATION_GUIDE.md) - Detailed migration explanation
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Step-by-step deployment
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Cost Optimization](docs/COST_OPTIMIZATION.md) - Cost reduction strategies
- [Monitoring Guide](docs/MONITORING_GUIDE.md) - Observability setup

## 🆘 Support

If you encounter issues:
1. Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
2. Review CloudWatch logs for your training jobs
3. Validate IAM permissions and resource access

---

Generated by SageBridge v{artifacts.metadata.get('sagebridge_version', '0.1.0')} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return readme_content
    
    def _create_project_readme(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create a project-specific README with technical details"""
        project_name = Path(analysis.source_info.path).name
        
        return f"""# {project_name} Technical Documentation

## Architecture Overview

This project implements a complete MLOps pipeline on Amazon SageMaker with the following components:

### Training Pipeline
- **Entry Point**: `training/train.py`
- **Model Definition**: `training/model.py`
- **Dependencies**: See `training/requirements.txt`

### Inference Pipeline  
- **Handler**: `inference/inference.py`
- **Model Loading**: Supports both state_dict and TorchScript formats
- **Dependencies**: See `inference/requirements.txt`

### MLOps Pipeline
- **Definition**: `pipeline/pipeline.py`
- **Preprocessing**: `pipeline/preprocessing.py`
- **Evaluation**: `pipeline/evaluation.py`

## Key Migration Changes

### Environment Variables
Original code used hard-coded paths. SageMaker provides:
- `SM_CHANNEL_TRAINING`: Training data path
- `SM_MODEL_DIR`: Model output directory
- `SM_NUM_GPUS`: Number of available GPUs

### Hyperparameters
SageMaker passes hyperparameters via command line arguments automatically.

### Data Loading
- **Before**: Local file paths
- **After**: S3 paths via SageMaker channels

### Model Saving
- **Before**: Local filesystem
- **After**: `/opt/ml/model/` for SageMaker model artifacts

## Dependencies Analysis

### Compatible Packages
{self._format_list(analysis.dependencies.compatible_packages)}

### Problematic Packages (Replaced)
{self._format_dependency_replacements(analysis.dependencies)}

## Testing Strategy

### Unit Tests
- Training component validation
- Model architecture verification
- Data preprocessing validation

### Integration Tests
- End-to-end pipeline execution
- Inference endpoint testing
- Performance benchmarking

### Property-Based Tests
- Model consistency across inputs
- Pipeline robustness validation
- Infrastructure compliance checks

## Performance Considerations

### Instance Selection
- **Development**: ml.m5.large (CPU, cost-effective)
- **Production**: ml.p3.2xlarge (GPU, high performance)
- **Large Scale**: ml.p3.8xlarge (Multi-GPU)

### Cost Optimization
- Spot instances for training jobs
- Auto-scaling for inference endpoints
- Lifecycle policies for S3 storage

## Security Implementation

### IAM Roles
- Least privilege access policies
- Separate roles for training and inference
- Cross-account access controls

### Data Encryption
- S3 bucket encryption at rest
- In-transit encryption for training
- KMS key management

## Monitoring and Observability

### CloudWatch Metrics
- Training job performance
- Resource utilization
- Pipeline execution status
- Endpoint performance

### Logging
- Structured logging for all components
- CloudWatch integration
- Error tracking and alerting

---

For deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
"""
    
    def _create_migration_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create detailed migration guide explaining architectural decisions"""
        project_name = Path(analysis.source_info.path).name
        
        return f"""# {project_name} Migration Guide

This guide explains the architectural decisions and changes made during the EC2 to SageMaker migration.

## 🎯 Migration Strategy

### Analysis Results
- **Source Complexity**: {analysis.source_info.estimated_complexity.title()}
- **Total Files**: {analysis.source_info.total_files} ({analysis.source_info.python_files} Python)
- **Lines of Code**: {analysis.source_info.total_lines:,}
- **Risk Level**: {analysis.risks.overall_risk.value.title()}

### Migration Approach
Based on the analysis, we implemented a **{self._get_migration_strategy(analysis)}** migration strategy.

## 🔄 Key Architectural Changes

### 1. Training Script Transformation

#### Before (EC2/Local)
```python
# Hard-coded paths and configurations
data_dir = "./data"
model_save_path = "./models/model.pth"
batch_size = 64
epochs = 10
```

#### After (SageMaker)
```python
# SageMaker environment integration
data_dir = os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data/training')
model_dir = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')
batch_size = args.batch_size  # From hyperparameters
epochs = args.epochs
```

### 2. Dependency Management

#### Problematic Dependencies Resolved
{self._create_dependency_resolution_table(analysis.dependencies)}

### 3. Infrastructure as Code

#### Generated Components
- **CloudFormation Templates**: {len(artifacts.infrastructure.cloudformation_templates)}
- **IAM Policies**: {len(artifacts.infrastructure.iam_policies)}
- **Deployment Scripts**: {len(artifacts.infrastructure.deployment_scripts)}

### 4. MLOps Pipeline Implementation

#### Pipeline Components
1. **Data Preprocessing**: Automated data preparation and validation
2. **Training**: Scalable training with hyperparameter optimization
3. **Evaluation**: Automated model evaluation with quality gates
4. **Registration**: Conditional model registration based on performance
5. **Deployment**: Automated endpoint deployment with monitoring

## 🏗️ Architecture Decisions

### Decision 1: Training Instance Selection
**Choice**: ml.m5.large for development, ml.p3.2xlarge for production
**Rationale**: {self._get_instance_rationale(analysis)}

### Decision 2: Model Saving Strategy
**Choice**: Dual format saving (state_dict + TorchScript)
**Rationale**: Ensures compatibility with both custom and managed inference containers

### Decision 3: Pipeline Orchestration
**Choice**: SageMaker Pipelines with conditional steps
**Rationale**: Native integration with SageMaker services and automatic scaling

### Decision 4: Security Implementation
**Choice**: Least privilege IAM roles with resource-specific permissions
**Rationale**: Follows AWS security best practices and compliance requirements

## 🔧 Implementation Details

### Error Prevention Measures
{self._create_error_prevention_list(analysis)}

### Testing Strategy
- **Unit Tests**: {len(artifacts.testing_suite.unit_tests)} test files
- **Integration Tests**: {len(artifacts.testing_suite.integration_tests)} test files
- **Property Tests**: {len(artifacts.testing_suite.property_tests)} test files

### Monitoring Implementation
- CloudWatch metrics for all pipeline components
- Custom metrics for business KPIs
- Automated alerting for failures and performance degradation

## 📊 Migration Impact

### Performance Improvements
- **Scalability**: Automatic scaling based on demand
- **Reliability**: Built-in retry logic and error handling
- **Observability**: Comprehensive monitoring and logging

### Cost Considerations
- **Training**: Pay-per-use with spot instance support
- **Inference**: Auto-scaling endpoints with cost optimization
- **Storage**: Lifecycle policies for data management

### Operational Benefits
- **Automation**: Reduced manual intervention
- **Collaboration**: Shared infrastructure and model registry
- **Compliance**: Built-in security and governance

## 🚀 Next Steps

### Immediate Actions
1. Deploy infrastructure using provided CloudFormation templates
2. Execute initial pipeline run to validate migration
3. Set up monitoring and alerting

### Future Enhancements
1. Implement hyperparameter tuning
2. Add A/B testing capabilities
3. Integrate with CI/CD pipelines
4. Implement multi-region deployment

## 📚 References

- [SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/)
- [MLOps Best Practices](https://docs.aws.amazon.com/sagemaker/latest/dg/best-practices.html)
- [Cost Optimization Guide](docs/COST_OPTIMIZATION.md)

---

Migration completed on {datetime.now().strftime('%Y-%m-%d')} using SageBridge v{artifacts.metadata.get('sagebridge_version', '0.1.0')}
"""
    
    def _create_architecture_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create architecture guide with system design details"""
        return f"""# Architecture Guide

## System Overview

This document describes the architecture of the migrated SageMaker system.

## High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   SageMaker     │    │   Inference     │
│                 │    │   Pipeline      │    │   Endpoints     │
│  ┌───────────┐  │    │                 │    │                 │
│  │    S3     │  │───▶│  ┌───────────┐  │───▶│  ┌───────────┐  │
│  │   Data    │  │    │  │ Training  │  │    │  │ Real-time │  │
│  └───────────┘  │    │  │   Jobs    │  │    │  │Inference  │  │
│                 │    │  └───────────┘  │    │  └───────────┘  │
│  ┌───────────┐  │    │                 │    │                 │
│  │   Code    │  │    │  ┌───────────┐  │    │  ┌───────────┐  │
│  │Repository │  │    │  │   Model   │  │    │  │   Batch   │  │
│  └───────────┘  │    │  │ Registry  │  │    │  │Transform  │  │
└─────────────────┘    │  └───────────┘  │    │  └───────────┘  │
                       └─────────────────┘    └─────────────────┘
```

## Component Architecture

### Training Pipeline
- **Preprocessing**: Data validation and transformation
- **Training**: Model training with hyperparameter optimization
- **Evaluation**: Model performance assessment
- **Registration**: Conditional model registration

### Inference Architecture
- **Model Loading**: Supports multiple model formats
- **Request Processing**: Handles various input formats
- **Response Generation**: Structured output with metadata
- **Monitoring**: Performance and health metrics

### Infrastructure Components
- **IAM Roles**: Least privilege access control
- **S3 Buckets**: Data and artifact storage
- **CloudWatch**: Monitoring and logging
- **VPC**: Network security and isolation

## Data Flow

### Training Data Flow
1. Raw data uploaded to S3
2. Preprocessing job validates and transforms data
3. Training job consumes processed data
4. Model artifacts stored in S3
5. Evaluation job assesses model quality
6. Approved models registered in Model Registry

### Inference Data Flow
1. Client sends request to endpoint
2. Inference container loads model
3. Request processed and prediction generated
4. Response returned with metadata
5. Metrics logged to CloudWatch

## Security Architecture

### Access Control
- Service-linked roles for SageMaker
- Resource-based policies for S3
- VPC endpoints for secure communication

### Data Protection
- Encryption at rest (S3, EBS)
- Encryption in transit (TLS)
- KMS key management

### Network Security
- VPC isolation
- Security groups
- Private subnets for training

## Scalability Design

### Horizontal Scaling
- Multi-instance training
- Auto-scaling inference endpoints
- Distributed data processing

### Vertical Scaling
- Instance type optimization
- GPU utilization for training
- Memory optimization for inference

## Monitoring and Observability

### Metrics Collection
- Training job metrics
- Inference endpoint metrics
- Infrastructure metrics
- Custom business metrics

### Logging Strategy
- Structured logging
- Centralized log aggregation
- Log retention policies

### Alerting
- Performance degradation alerts
- Error rate monitoring
- Cost threshold notifications

## Disaster Recovery

### Backup Strategy
- Model artifact versioning
- Code repository backups
- Configuration backups

### Recovery Procedures
- Model rollback capabilities
- Infrastructure recreation
- Data recovery processes

---

For implementation details, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
"""
    
    def _create_troubleshooting_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create comprehensive troubleshooting guide"""
        return f"""# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with your SageMaker migration.

## 🚨 Common Issues and Solutions

### 1. Training Job Failures

#### Issue: Permission Denied Errors
**Symptoms:**
- Training job fails with "Access Denied" errors
- Cannot read from S3 buckets
- Cannot write model artifacts

**Solution:**
```bash
# Check IAM role permissions
aws iam get-role --role-name SageMakerExecutionRole
aws iam list-attached-role-policies --role-name SageMakerExecutionRole

# Verify S3 bucket permissions
aws s3 ls s3://your-bucket-name/
```

**Prevention:**
- Use the generated IAM policies in `infrastructure/iam/`
- Ensure bucket policies allow SageMaker access

#### Issue: Dependency Installation Failures
**Symptoms:**
- Training job fails during package installation
- "Package not found" errors
- Version conflict errors

**Solution:**
```bash
# Check requirements.txt for problematic packages
cat training/requirements.txt

# Test locally with SageMaker local mode
python -c "
from sagemaker.pytorch import PyTorch
estimator = PyTorch(
    entry_point='train.py',
    source_dir='training',
    instance_type='local'
)
"
```

**Prevention:**
- Use the generated requirements.txt files
- Test with SageMaker local mode before deploying

### 2. Pipeline Execution Issues

#### Issue: Pipeline Step Failures
**Symptoms:**
- Pipeline execution stops at specific step
- Step shows "Failed" status
- No clear error message in console

**Solution:**
```bash
# Get detailed pipeline execution info
aws sagemaker describe-pipeline-execution --pipeline-execution-arn <arn>

# Check CloudWatch logs for specific step
aws logs describe-log-groups --log-group-name-prefix /aws/sagemaker/

# Get step execution details
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn <arn>
```

#### Issue: Data Not Found Errors
**Symptoms:**
- "No such file or directory" errors
- Empty dataset errors
- S3 path not found

**Solution:**
```bash
# Verify S3 data paths
aws s3 ls s3://your-bucket/data/training/

# Check pipeline parameter values
aws sagemaker describe-pipeline --pipeline-name <pipeline-name>

# Validate data preprocessing step
python pipeline/preprocessing.py --dry-run
```

### 3. Inference Endpoint Issues

#### Issue: Endpoint Creation Failures
**Symptoms:**
- Endpoint stuck in "Creating" status
- "InsufficientCapacity" errors
- Model loading failures

**Solution:**
```bash
# Check endpoint configuration
aws sagemaker describe-endpoint-config --endpoint-config-name <config-name>

# Try different instance type
aws sagemaker update-endpoint --endpoint-name <name> --endpoint-config-name <new-config>

# Check model artifacts
aws s3 ls s3://your-bucket/models/
```

#### Issue: Inference Errors
**Symptoms:**
- 500 Internal Server Error
- Model prediction failures
- Timeout errors

**Solution:**
```bash
# Check endpoint logs
aws logs filter-log-events --log-group-name /aws/sagemaker/Endpoints/<endpoint-name>

# Test inference locally
python -c "
from inference.inference import model_fn, input_fn, predict_fn
model = model_fn('./model')
data = input_fn('test_input', 'application/json')
result = predict_fn(data, model)
print(result)
"
```

### 4. Cost and Performance Issues

#### Issue: Unexpected High Costs
**Symptoms:**
- Higher than expected AWS bills
- Training jobs running longer than expected
- Endpoints not auto-scaling down

**Solution:**
```bash
# Check running resources
aws sagemaker list-training-jobs --status-equals InProgress
aws sagemaker list-endpoints --status-equals InService

# Review cost allocation tags
aws ce get-cost-and-usage --time-period Start=2024-01-01,End=2024-01-31 --granularity MONTHLY

# Implement cost controls
python infrastructure/scripts/cost_monitoring.py
```

**Prevention:**
- Use spot instances for training
- Implement auto-scaling for endpoints
- Set up cost alerts and budgets

## 🔍 Diagnostic Commands

### Training Diagnostics
```bash
# List recent training jobs
aws sagemaker list-training-jobs --sort-by CreationTime --sort-order Descending --max-items 10

# Get training job details
aws sagemaker describe-training-job --training-job-name <job-name>

# Check training metrics
aws cloudwatch get-metric-statistics --namespace AWS/SageMaker --metric-name TrainingLoss --dimensions Name=TrainingJobName,Value=<job-name> --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z --period 300 --statistics Average
```

### Pipeline Diagnostics
```bash
# List pipeline executions
aws sagemaker list-pipeline-executions --pipeline-name <pipeline-name>

# Get execution details
aws sagemaker describe-pipeline-execution --pipeline-execution-arn <arn>

# List execution steps
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn <arn>
```

### Endpoint Diagnostics
```bash
# List endpoints
aws sagemaker list-endpoints

# Get endpoint details
aws sagemaker describe-endpoint --endpoint-name <endpoint-name>

# Check endpoint metrics
aws cloudwatch get-metric-statistics --namespace AWS/SageMaker --metric-name Invocations --dimensions Name=EndpointName,Value=<endpoint-name> --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z --period 300 --statistics Sum
```

## 🛠️ Debug Mode

### Enable Debug Mode
Add these environment variables to your training script:
```python
import os
os.environ['SAGEMAKER_DEBUG'] = '1'
os.environ['PYTHONPATH'] = '/opt/ml/code'
```

### Local Testing
```bash
# Test training script locally
cd training
python train.py --epochs 1 --batch-size 32 --dry-run

# Test inference handler locally
cd inference
python -c "
from inference import model_fn, input_fn, predict_fn, output_fn
model = model_fn('./model')
print('Model loaded successfully')
"
```

## 📞 Getting Help

### AWS Support Resources
- [SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/)
- [SageMaker Troubleshooting](https://docs.aws.amazon.com/sagemaker/latest/dg/troubleshooting.html)
- [AWS Support Center](https://console.aws.amazon.com/support/)

### Community Resources
- [SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples)
- [AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/amazon-sagemaker)

### Emergency Procedures
1. **Stop all running resources** to prevent cost accumulation
2. **Check CloudWatch logs** for error details
3. **Review IAM permissions** for access issues
4. **Contact AWS Support** for critical production issues

---

For deployment guidance, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
"""
    
    def _create_common_issues_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create guide for common migration-specific issues"""
        return f"""# Common Migration Issues

This guide addresses issues specific to EC2 to SageMaker migrations.

## Migration-Specific Issues

### 1. Dependency Compatibility

#### Problematic Packages Detected
{self._create_problematic_packages_section(analysis.dependencies)}

#### Resolution Strategy
- **torchvision**: Replaced with manual data download
- **seaborn**: Replaced with matplotlib-only visualizations
- **custom packages**: Containerized with custom Docker images

### 2. Path and Environment Issues

#### Common Path Problems
```python
# ❌ Hard-coded paths (won't work in SageMaker)
data_path = "./data/train.csv"
model_path = "./models/model.pth"

# ✅ SageMaker environment paths
data_path = os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data/training')
model_path = os.path.join(os.environ.get('SM_MODEL_DIR', '/opt/ml/model'), 'model.pth')
```

### 3. Hyperparameter Handling

#### Before Migration
```python
# ❌ Hard-coded hyperparameters
batch_size = 64
learning_rate = 0.001
epochs = 100
```

#### After Migration
```python
# ✅ SageMaker hyperparameter integration
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--batch-size', type=int, default=64)
parser.add_argument('--learning-rate', type=float, default=0.001)
parser.add_argument('--epochs', type=int, default=100)
args = parser.parse_args()
```

### 4. Model Saving and Loading

#### TorchScript Compatibility Issues
```python
# ✅ Dual model saving for compatibility
def save_model(model, model_dir):
    # Save state dict for custom containers
    torch.save(model.state_dict(), os.path.join(model_dir, 'model.pth'))
    
    # Save TorchScript for managed containers
    try:
        traced_model = torch.jit.trace(model, example_input)
        traced_model.save(os.path.join(model_dir, 'model.pt'))
    except Exception as e:
        print(f"TorchScript saving failed: {{e}}")
```

## Risk-Specific Guidance

### High Risk Items
{self._create_risk_guidance(analysis.risks.high_risk_items, "high")}

### Medium Risk Items  
{self._create_risk_guidance(analysis.risks.medium_risk_items, "medium")}

## Pattern-Specific Issues

### Distributed Training Migration
{self._create_distributed_training_guidance(analysis.patterns)}

### Custom Metrics Migration
{self._create_custom_metrics_guidance(analysis.patterns)}

### Visualization Code Migration
{self._create_visualization_guidance(analysis.patterns)}

## Quick Fixes

### Fix 1: Import Errors
```bash
# Add to requirements.txt
sagemaker>=2.0
boto3>=1.26
```

### Fix 2: Permission Issues
```bash
# Update IAM role with required permissions
aws iam attach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

### Fix 3: Data Loading Issues
```python
# Use SageMaker data channels
def load_data():
    train_dir = os.environ.get('SM_CHANNEL_TRAINING')
    if train_dir:
        return pd.read_csv(os.path.join(train_dir, 'train.csv'))
    else:
        # Fallback for local testing
        return pd.read_csv('./data/train.csv')
```

---

For comprehensive troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
"""
    
    def _create_api_reference(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create API reference documentation"""
        return f"""# API Reference

This document provides API reference for the migrated SageMaker components.

## Training Script API

### Entry Point: `training/train.py`

#### Command Line Arguments
```bash
python train.py [OPTIONS]
```

**Options:**
- `--batch-size` (int): Training batch size (default: 64)
- `--epochs` (int): Number of training epochs (default: 10)
- `--learning-rate` (float): Learning rate (default: 0.001)
- `--model-dir` (str): Model output directory (default: /opt/ml/model)
- `--train` (str): Training data directory (default: /opt/ml/input/data/training)

#### Environment Variables
- `SM_MODEL_DIR`: Model artifacts output directory
- `SM_CHANNEL_TRAINING`: Training data input directory
- `SM_NUM_GPUS`: Number of available GPUs
- `SM_HOSTS`: List of hosts in distributed training
- `SM_CURRENT_HOST`: Current host name

### Model Definition: `training/model.py`

#### Classes
```python
class Model(nn.Module):
    \"\"\"Main model class\"\"\"
    
    def __init__(self, **kwargs):
        \"\"\"Initialize model with hyperparameters\"\"\"
        
    def forward(self, x):
        \"\"\"Forward pass\"\"\"
        
    def save_model(self, model_dir: str):
        \"\"\"Save model artifacts\"\"\"
```

## Inference API

### Entry Point: `inference/inference.py`

#### Required Functions
```python
def model_fn(model_dir: str):
    \"\"\"Load model from artifacts directory\"\"\"
    
def input_fn(request_body: str, content_type: str):
    \"\"\"Parse input data\"\"\"
    
def predict_fn(input_data, model):
    \"\"\"Generate predictions\"\"\"
    
def output_fn(prediction, accept: str):
    \"\"\"Format output response\"\"\"
```

#### Supported Content Types
- `application/json`: JSON input/output
- `text/csv`: CSV input/output
- `application/x-npy`: NumPy array input

#### Response Format
```json
{{
    "predictions": [...],
    "model_version": "1.0",
    "timestamp": "2024-01-01T00:00:00Z"
}}
```

## Pipeline API

### Pipeline Definition: `pipeline/pipeline.py`

#### Main Function
```python
def create_pipeline(
    role: str,
    bucket: str,
    region: str,
    **kwargs
) -> Pipeline:
    \"\"\"Create SageMaker pipeline\"\"\"
```

#### Pipeline Parameters
- `ProcessingInstanceType`: Instance type for preprocessing
- `TrainingInstanceType`: Instance type for training
- `ModelApprovalStatus`: Model approval status
- `AccuracyThreshold`: Minimum accuracy for approval

### Preprocessing: `pipeline/preprocessing.py`

#### Main Function
```python
def preprocess_data(
    input_path: str,
    output_path: str,
    **kwargs
):
    \"\"\"Preprocess training data\"\"\"
```

### Evaluation: `pipeline/evaluation.py`

#### Main Function
```python
def evaluate_model(
    model_path: str,
    test_data_path: str,
    output_path: str
):
    \"\"\"Evaluate model performance\"\"\"
```

#### Evaluation Metrics
```json
{{
    "accuracy": 0.95,
    "precision": 0.94,
    "recall": 0.96,
    "f1_score": 0.95,
    "confusion_matrix": [[...]]
}}
```

## Infrastructure API

### Deployment Script: `infrastructure/scripts/deploy.py`

#### Command Line Interface
```bash
python deploy.py [OPTIONS]
```

**Options:**
- `--region` (str): AWS region (default: us-east-1)
- `--stack-name` (str): CloudFormation stack name
- `--run-pipeline` (bool): Execute pipeline after deployment
- `--dry-run` (bool): Validate without deploying

#### Functions
```python
def deploy_infrastructure(
    region: str,
    stack_name: str,
    parameters: Dict[str, str]
) -> str:
    \"\"\"Deploy CloudFormation stack\"\"\"
    
def create_pipeline(
    role_arn: str,
    bucket_name: str
) -> str:
    \"\"\"Create SageMaker pipeline\"\"\"
```

## Configuration API

### Configuration Files

#### `config/training.yaml`
```yaml
training:
  instance_type: ml.m5.large
  instance_count: 1
  volume_size: 30
  max_run: 3600
  
hyperparameters:
  batch_size: 64
  epochs: 10
  learning_rate: 0.001
```

#### `config/inference.yaml`
```yaml
inference:
  instance_type: ml.m5.large
  initial_instance_count: 1
  max_concurrent_transforms: 1
  
endpoint:
  auto_scaling:
    min_capacity: 1
    max_capacity: 10
    target_value: 70.0
```

## Error Codes

### Training Errors
- `TRAIN_001`: Data loading failure
- `TRAIN_002`: Model initialization failure
- `TRAIN_003`: Training convergence failure
- `TRAIN_004`: Model saving failure

### Inference Errors
- `INFER_001`: Model loading failure
- `INFER_002`: Input parsing failure
- `INFER_003`: Prediction failure
- `INFER_004`: Output formatting failure

### Pipeline Errors
- `PIPE_001`: Step execution failure
- `PIPE_002`: Parameter validation failure
- `PIPE_003`: Resource allocation failure
- `PIPE_004`: Approval workflow failure

## Examples

### Training Job Execution
```python
from sagemaker.pytorch import PyTorch

estimator = PyTorch(
    entry_point='train.py',
    source_dir='training',
    role=role,
    instance_type='ml.m5.large',
    framework_version='2.0.0',
    hyperparameters={{
        'batch-size': 64,
        'epochs': 10
    }}
)

estimator.fit({{'training': 's3://bucket/data/'}})
```

### Inference Endpoint
```python
from sagemaker.pytorch import PyTorchModel

model = PyTorchModel(
    model_data='s3://bucket/model.tar.gz',
    role=role,
    entry_point='inference.py',
    source_dir='inference',
    framework_version='2.0.0'
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large'
)

result = predictor.predict(data)
```

### Pipeline Execution
```python
from sagemaker.workflow.pipeline import Pipeline

pipeline = create_pipeline(role, bucket, region)
execution = pipeline.start()
execution.wait()
```

---

For implementation examples, see the generated code in each component directory.
"""
    
    def _create_deployment_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create deployment guide with step-by-step instructions"""
        project_name = Path(analysis.source_info.path).name
        
        return f"""# Deployment Guide

This guide provides step-by-step instructions for deploying your migrated SageMaker system.

## 🚀 Deployment Overview

### Prerequisites
- AWS CLI configured with appropriate permissions
- Python 3.8+ with pip
- Docker (for local testing)
- Sufficient AWS service limits

### Deployment Strategy
Based on your risk assessment ({analysis.risks.overall_risk.value}), we recommend a **{self._get_deployment_strategy(analysis)}** deployment approach.

## 📋 Pre-Deployment Checklist

### ✅ AWS Account Setup
- [ ] AWS CLI configured (`aws configure`)
- [ ] Sufficient service limits for SageMaker
- [ ] S3 bucket created for artifacts
- [ ] IAM permissions for SageMaker operations

### ✅ Local Environment
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] Docker installed and running
- [ ] AWS credentials configured
- [ ] Region selected and configured

### ✅ Code Validation
- [ ] Training script tested locally
- [ ] Inference handler validated
- [ ] Pipeline definition syntax checked
- [ ] Infrastructure templates validated

## 🏗️ Step-by-Step Deployment

### Step 1: Infrastructure Deployment

#### 1.1 Deploy CloudFormation Stack
```bash
cd infrastructure
python scripts/deploy.py \\
    --region us-east-1 \\
    --stack-name {project_name.lower()}-sagemaker \\
    --validate-only
```

#### 1.2 Verify Infrastructure
```bash
# Check stack status
aws cloudformation describe-stacks --stack-name {project_name.lower()}-sagemaker

# Verify IAM role creation
aws iam get-role --role-name SageMakerExecutionRole-{project_name}

# Check S3 bucket
aws s3 ls s3://{project_name.lower()}-sagemaker-artifacts/
```

### Step 2: Data Preparation

#### 2.1 Upload Training Data
```bash
# Create data structure
aws s3 mb s3://{project_name.lower()}-sagemaker-artifacts/data/

# Upload training data
aws s3 cp ./data/ s3://{project_name.lower()}-sagemaker-artifacts/data/training/ --recursive

# Verify upload
aws s3 ls s3://{project_name.lower()}-sagemaker-artifacts/data/training/
```

#### 2.2 Upload Code Artifacts
```bash
# Package training code
tar -czf training.tar.gz training/

# Upload to S3
aws s3 cp training.tar.gz s3://{project_name.lower()}-sagemaker-artifacts/code/

# Package inference code
tar -czf inference.tar.gz inference/
aws s3 cp inference.tar.gz s3://{project_name.lower()}-sagemaker-artifacts/code/
```

### Step 3: Pipeline Deployment

#### 3.1 Create Pipeline
```bash
cd pipeline
python pipeline.py \\
    --role-arn arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole-{project_name} \\
    --bucket {project_name.lower()}-sagemaker-artifacts \\
    --region us-east-1 \\
    --create-only
```

#### 3.2 Validate Pipeline
```bash
# List pipelines
aws sagemaker list-pipelines

# Describe pipeline
aws sagemaker describe-pipeline --pipeline-name {project_name.lower()}-training-pipeline
```

### Step 4: Initial Training Run

#### 4.1 Execute Pipeline
```bash
# Start pipeline execution
python pipeline.py \\
    --role-arn arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole-{project_name} \\
    --bucket {project_name.lower()}-sagemaker-artifacts \\
    --region us-east-1 \\
    --execute
```

#### 4.2 Monitor Execution
```bash
# Check execution status
aws sagemaker list-pipeline-executions --pipeline-name {project_name.lower()}-training-pipeline

# Monitor in console
echo "Monitor at: https://console.aws.amazon.com/sagemaker/home?region=us-east-1#/pipelines"
```

### Step 5: Model Deployment

#### 5.1 Approve Model (if manual approval required)
```bash
# List model packages
aws sagemaker list-model-packages --model-package-group-name {project_name.lower()}-model-group

# Approve model
aws sagemaker update-model-package \\
    --model-package-arn <model-package-arn> \\
    --model-approval-status Approved
```

#### 5.2 Deploy Endpoint
```bash
# Deploy endpoint
python scripts/deploy_endpoint.py \\
    --model-package-arn <model-package-arn> \\
    --endpoint-name {project_name.lower()}-endpoint \\
    --instance-type ml.m5.large
```

### Step 6: Validation and Testing

#### 6.1 Run Test Suite
```bash
# Run unit tests
python -m pytest tests/unit/ -v

# Run integration tests
python -m pytest tests/integration/ -v

# Run endpoint tests
python tests/test_endpoint.py --endpoint-name {project_name.lower()}-endpoint
```

#### 6.2 Performance Testing
```bash
# Run load tests
python tests/load_test.py \\
    --endpoint-name {project_name.lower()}-endpoint \\
    --concurrent-requests 10 \\
    --duration 300
```

## 📊 Deployment Validation

### Health Checks
```bash
# Check training job status
aws sagemaker list-training-jobs --status-equals Completed --max-items 5

# Check endpoint health
aws sagemaker describe-endpoint --endpoint-name {project_name.lower()}-endpoint

# Check pipeline status
aws sagemaker list-pipeline-executions --pipeline-name {project_name.lower()}-training-pipeline --max-items 5
```

### Monitoring Setup
```bash
# Create CloudWatch dashboard
python scripts/create_dashboard.py --project-name {project_name.lower()}

# Set up alarms
python scripts/create_alarms.py --endpoint-name {project_name.lower()}-endpoint
```

## 🔧 Configuration Management

### Environment-Specific Configurations

#### Development Environment
```yaml
# config/dev.yaml
training:
  instance_type: ml.m5.large
  instance_count: 1
  
inference:
  instance_type: ml.t2.medium
  initial_instance_count: 1
```

#### Production Environment
```yaml
# config/prod.yaml
training:
  instance_type: ml.p3.2xlarge
  instance_count: 2
  
inference:
  instance_type: ml.m5.large
  initial_instance_count: 2
  auto_scaling:
    enabled: true
    min_capacity: 2
    max_capacity: 10
```

### Parameter Management
```bash
# Store parameters in Systems Manager
aws ssm put-parameter \\
    --name "/{project_name.lower()}/training/instance-type" \\
    --value "ml.m5.large" \\
    --type "String"
```

## 🚨 Rollback Procedures

### Emergency Rollback
```bash
# Stop current pipeline execution
aws sagemaker stop-pipeline-execution --pipeline-execution-arn <execution-arn>

# Rollback to previous model version
python scripts/rollback_model.py --endpoint-name {project_name.lower()}-endpoint --version previous

# Delete problematic resources
aws cloudformation delete-stack --stack-name {project_name.lower()}-sagemaker
```

### Gradual Rollback
```bash
# Update endpoint with previous model
aws sagemaker update-endpoint \\
    --endpoint-name {project_name.lower()}-endpoint \\
    --endpoint-config-name previous-config

# Monitor rollback
aws sagemaker describe-endpoint --endpoint-name {project_name.lower()}-endpoint
```

## 📈 Post-Deployment Tasks

### Monitoring Setup
1. Configure CloudWatch dashboards
2. Set up alerting for failures and performance issues
3. Implement cost monitoring and budgets
4. Set up log aggregation and analysis

### Optimization
1. Analyze training job performance and optimize instance types
2. Implement hyperparameter tuning
3. Set up A/B testing for model versions
4. Optimize inference endpoint auto-scaling

### Maintenance
1. Schedule regular model retraining
2. Implement data drift monitoring
3. Set up automated testing pipelines
4. Plan for disaster recovery testing

## 🔗 Next Steps

### Immediate Actions
- [ ] Set up monitoring and alerting
- [ ] Configure cost budgets and alerts
- [ ] Document operational procedures
- [ ] Train team on new system

### Future Enhancements
- [ ] Implement hyperparameter tuning
- [ ] Add A/B testing capabilities
- [ ] Integrate with CI/CD pipelines
- [ ] Implement multi-region deployment

---

For troubleshooting deployment issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
For cost optimization, see [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md)
"""
    
    def _create_monitoring_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create monitoring and observability guide"""
        project_name = Path(analysis.source_info.path).name
        
        return f"""# Monitoring Guide

This guide covers monitoring, observability, and alerting for your SageMaker deployment.

## 📊 Monitoring Overview

### Key Metrics to Monitor
- **Training Jobs**: Loss, accuracy, resource utilization
- **Pipeline Executions**: Success rate, execution time, step failures
- **Inference Endpoints**: Latency, throughput, error rate
- **Infrastructure**: Costs, resource utilization, security events

### Monitoring Tools
- **CloudWatch**: Metrics, logs, and alarms
- **SageMaker Studio**: Built-in monitoring dashboards
- **X-Ray**: Distributed tracing (optional)
- **Cost Explorer**: Cost analysis and optimization

## 🎯 Training Job Monitoring

### Key Training Metrics
```python
# Custom metrics in training script
import boto3

cloudwatch = boto3.client('cloudwatch')

def log_metric(metric_name, value, unit='None'):
    cloudwatch.put_metric_data(
        Namespace='SageMaker/Training/{project_name}',
        MetricData=[
            {{
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Dimensions': [
                    {{
                        'Name': 'TrainingJobName',
                        'Value': os.environ.get('SM_TRAINING_JOB_NAME', 'local')
                    }}
                ]
            }}
        ]
    )

# Log training metrics
log_metric('TrainingLoss', loss.item(), 'None')
log_metric('TrainingAccuracy', accuracy, 'Percent')
log_metric('LearningRate', current_lr, 'None')
```

### Training Job Alarms
```bash
# Create alarm for training job failures
aws cloudwatch put-metric-alarm \\
    --alarm-name "{project_name}-TrainingJobFailures" \\
    --alarm-description "Alert on training job failures" \\
    --metric-name TrainingJobsFailed \\
    --namespace AWS/SageMaker \\
    --statistic Sum \\
    --period 300 \\
    --threshold 1 \\
    --comparison-operator GreaterThanOrEqualToThreshold \\
    --evaluation-periods 1
```

### Training Logs
```bash
# View training logs
aws logs filter-log-events \\
    --log-group-name /aws/sagemaker/TrainingJobs \\
    --start-time $(date -d '1 hour ago' +%s)000 \\
    --filter-pattern "ERROR"
```

## 🔄 Pipeline Monitoring

### Pipeline Metrics Dashboard
```python
# Create CloudWatch dashboard for pipeline
import boto3

cloudwatch = boto3.client('cloudwatch')

dashboard_body = {{
    "widgets": [
        {{
            "type": "metric",
            "properties": {{
                "metrics": [
                    ["AWS/SageMaker", "PipelineExecutionSuccess", "PipelineName", "{project_name.lower()}-training-pipeline"],
                    [".", "PipelineExecutionFailure", ".", "."]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "us-east-1",
                "title": "Pipeline Executions"
            }}
        }}
    ]
}}

cloudwatch.put_dashboard(
    DashboardName='{project_name}-Pipeline-Dashboard',
    DashboardBody=json.dumps(dashboard_body)
)
```

### Pipeline Step Monitoring
```bash
# Monitor pipeline step execution
aws sagemaker list-pipeline-execution-steps \\
    --pipeline-execution-arn <execution-arn> \\
    --query 'PipelineExecutionSteps[?StepStatus==`Failed`]'
```

### Pipeline Alarms
```bash
# Alarm for pipeline failures
aws cloudwatch put-metric-alarm \\
    --alarm-name "{project_name}-PipelineFailures" \\
    --alarm-description "Alert on pipeline failures" \\
    --metric-name PipelineExecutionFailure \\
    --namespace AWS/SageMaker \\
    --statistic Sum \\
    --period 300 \\
    --threshold 1 \\
    --comparison-operator GreaterThanOrEqualToThreshold \\
    --dimensions Name=PipelineName,Value={project_name.lower()}-training-pipeline
```

## 🎯 Inference Endpoint Monitoring

### Endpoint Metrics
```python
# Custom endpoint metrics
def log_inference_metrics(prediction_time, input_size):
    cloudwatch.put_metric_data(
        Namespace='SageMaker/Inference/{project_name}',
        MetricData=[
            {{
                'MetricName': 'PredictionLatency',
                'Value': prediction_time,
                'Unit': 'Milliseconds'
            }},
            {{
                'MetricName': 'InputSize',
                'Value': input_size,
                'Unit': 'Bytes'
            }}
        ]
    )
```

### Endpoint Health Checks
```python
# Automated endpoint health check
import requests
import json

def health_check_endpoint(endpoint_name):
    runtime = boto3.client('sagemaker-runtime')
    
    try:
        # Send test request
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps({{"test": "data"}})
        )
        
        # Log success metric
        log_metric('EndpointHealthCheck', 1, 'Count')
        return True
        
    except Exception as e:
        # Log failure metric
        log_metric('EndpointHealthCheck', 0, 'Count')
        log_metric('EndpointErrors', 1, 'Count')
        return False
```

### Endpoint Alarms
```bash
# High latency alarm
aws cloudwatch put-metric-alarm \\
    --alarm-name "{project_name}-HighLatency" \\
    --alarm-description "Alert on high inference latency" \\
    --metric-name ModelLatency \\
    --namespace AWS/SageMaker \\
    --statistic Average \\
    --period 300 \\
    --threshold 1000 \\
    --comparison-operator GreaterThanThreshold \\
    --dimensions Name=EndpointName,Value={project_name.lower()}-endpoint

# High error rate alarm
aws cloudwatch put-metric-alarm \\
    --alarm-name "{project_name}-HighErrorRate" \\
    --alarm-description "Alert on high error rate" \\
    --metric-name Model4XXErrors \\
    --namespace AWS/SageMaker \\
    --statistic Sum \\
    --period 300 \\
    --threshold 10 \\
    --comparison-operator GreaterThanThreshold \\
    --dimensions Name=EndpointName,Value={project_name.lower()}-endpoint
```

## 💰 Cost Monitoring

### Cost Tracking
```python
# Cost tracking function
def track_costs():
    ce = boto3.client('ce')
    
    response = ce.get_cost_and_usage(
        TimePeriod={{
            'Start': '2024-01-01',
            'End': '2024-01-31'
        }},
        Granularity='MONTHLY',
        Metrics=['BlendedCost'],
        GroupBy=[
            {{
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }}
        ],
        Filter={{
            'Dimensions': {{
                'Key': 'SERVICE',
                'Values': ['Amazon SageMaker']
            }}
        }}
    )
    
    return response['ResultsByTime']
```

### Cost Alarms
```bash
# Monthly cost alarm
aws budgets create-budget \\
    --account-id $(aws sts get-caller-identity --query Account --output text) \\
    --budget '{{
        "BudgetName": "{project_name}-SageMaker-Budget",
        "BudgetLimit": {{
            "Amount": "1000",
            "Unit": "USD"
        }},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
        "CostFilters": {{
            "Service": ["Amazon SageMaker"]
        }}
    }}'
```

## 📈 Performance Monitoring

### Model Performance Tracking
```python
# Model performance monitoring
def track_model_performance(predictions, actuals):
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    
    accuracy = accuracy_score(actuals, predictions)
    precision = precision_score(actuals, predictions, average='weighted')
    recall = recall_score(actuals, predictions, average='weighted')
    
    # Log performance metrics
    log_metric('ModelAccuracy', accuracy, 'Percent')
    log_metric('ModelPrecision', precision, 'Percent')
    log_metric('ModelRecall', recall, 'Percent')
    
    # Alert if performance degrades
    if accuracy < 0.85:  # Threshold from analysis
        send_alert('Model performance degraded', {{
            'accuracy': accuracy,
            'threshold': 0.85
        }})
```

### Data Drift Monitoring
```python
# Simple data drift detection
def detect_data_drift(current_data, reference_data):
    from scipy import stats
    
    # Statistical test for drift
    statistic, p_value = stats.ks_2samp(reference_data, current_data)
    
    # Log drift metric
    log_metric('DataDriftPValue', p_value, 'None')
    
    # Alert if significant drift detected
    if p_value < 0.05:
        send_alert('Data drift detected', {{
            'p_value': p_value,
            'statistic': statistic
        }})
```

## 🚨 Alerting and Notifications

### SNS Topic Setup
```bash
# Create SNS topic for alerts
aws sns create-topic --name {project_name}-alerts

# Subscribe email to topic
aws sns subscribe \\
    --topic-arn arn:aws:sns:us-east-1:ACCOUNT:{project_name}-alerts \\
    --protocol email \\
    --notification-endpoint your-email@example.com
```

### Alert Functions
```python
def send_alert(message, details=None):
    sns = boto3.client('sns')
    
    alert_message = {{
        'timestamp': datetime.now().isoformat(),
        'project': '{project_name}',
        'message': message,
        'details': details or {{}}
    }}
    
    sns.publish(
        TopicArn='arn:aws:sns:us-east-1:ACCOUNT:{project_name}-alerts',
        Message=json.dumps(alert_message, indent=2),
        Subject=f'{project_name} Alert: {{message}}'
    )
```

## 📊 Custom Dashboards

### Comprehensive Dashboard
```python
# Create comprehensive monitoring dashboard
dashboard_config = {{
    "widgets": [
        # Training metrics
        {{
            "type": "metric",
            "properties": {{
                "metrics": [
                    ["SageMaker/Training/{project_name}", "TrainingLoss"],
                    [".", "TrainingAccuracy"]
                ],
                "title": "Training Metrics"
            }}
        }},
        # Pipeline metrics
        {{
            "type": "metric", 
            "properties": {{
                "metrics": [
                    ["AWS/SageMaker", "PipelineExecutionSuccess", "PipelineName", "{project_name.lower()}-training-pipeline"],
                    [".", "PipelineExecutionFailure", ".", "."]
                ],
                "title": "Pipeline Status"
            }}
        }},
        # Endpoint metrics
        {{
            "type": "metric",
            "properties": {{
                "metrics": [
                    ["AWS/SageMaker", "Invocations", "EndpointName", "{project_name.lower()}-endpoint"],
                    [".", "ModelLatency", ".", "."],
                    [".", "Model4XXErrors", ".", "."]
                ],
                "title": "Endpoint Performance"
            }}
        }}
    ]
}}

cloudwatch.put_dashboard(
    DashboardName='{project_name}-Comprehensive-Dashboard',
    DashboardBody=json.dumps(dashboard_config)
)
```

## 🔍 Log Analysis

### Centralized Logging
```python
# Structured logging setup
import logging
import json

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log(self, level, message, **kwargs):
        log_entry = {{
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'project': '{project_name}',
            **kwargs
        }}
        self.logger.info(json.dumps(log_entry))

# Usage
logger = StructuredLogger('sagemaker-{project_name.lower()}')
logger.log('INFO', 'Training started', epoch=1, batch_size=64)
```

### Log Queries
```bash
# Query logs with CloudWatch Insights
aws logs start-query \\
    --log-group-name /aws/sagemaker/TrainingJobs \\
    --start-time $(date -d '1 hour ago' +%s) \\
    --end-time $(date +%s) \\
    --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc'
```

## 🔧 Monitoring Automation

### Automated Monitoring Setup
```python
# Automated monitoring setup script
def setup_monitoring():
    # Create alarms
    create_training_alarms()
    create_pipeline_alarms()
    create_endpoint_alarms()
    create_cost_alarms()
    
    # Create dashboards
    create_training_dashboard()
    create_pipeline_dashboard()
    create_endpoint_dashboard()
    
    # Set up notifications
    setup_sns_notifications()
    
    print("Monitoring setup complete!")

if __name__ == "__main__":
    setup_monitoring()
```

---

For troubleshooting monitoring issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
For cost optimization strategies, see [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md)
"""
    
    def _create_cost_optimization_guide(
        self, 
        analysis: AnalysisReport, 
        artifacts: MigrationArtifacts
    ) -> str:
        """Create cost optimization recommendations and best practices"""
        project_name = Path(analysis.source_info.path).name
        
        return f"""# Cost Optimization Guide

This guide provides strategies and best practices for optimizing costs in your SageMaker deployment.

## 💰 Cost Overview

### Current Configuration Costs (Estimated)
Based on your migration analysis:
- **Training**: ~${self._estimate_training_costs(analysis)}/month
- **Inference**: ~${self._estimate_inference_costs(analysis)}/month  
- **Storage**: ~${self._estimate_storage_costs(analysis)}/month
- **Total Estimated**: ~${self._estimate_total_costs(analysis)}/month

### Cost Optimization Potential
With recommended optimizations: **{self._calculate_savings_potential(analysis)}% cost reduction**

## 🎯 Training Cost Optimization

### 1. Instance Type Optimization

#### Current Recommendation
```python
# Based on your workload analysis
TRAINING_INSTANCES = {{
    'development': 'ml.m5.large',      # $0.115/hour
    'production': 'ml.p3.2xlarge',    # $3.825/hour
    'large_scale': 'ml.p3.8xlarge'    # $15.30/hour
}}
```

#### Cost-Optimized Alternatives
```python
# Spot instances for development
pytorch_estimator = PyTorch(
    # ... other parameters
    use_spot_instances=True,
    max_wait=3600,  # 1 hour max wait
    max_run=1800,   # 30 minutes max run
    spot_interruption_behavior='StopTraining'
)

# Savings: Up to 70% on training costs
```

### 2. Spot Instance Strategy
```python
# Implement spot instance with checkpointing
def create_spot_estimator():
    return PyTorch(
        entry_point='train.py',
        source_dir='training',
        role=role,
        instance_type='ml.p3.2xlarge',
        instance_count=1,
        use_spot_instances=True,
        max_wait=7200,  # 2 hours max wait
        max_run=3600,   # 1 hour max run
        checkpoint_s3_uri='s3://bucket/checkpoints/',
        checkpoint_local_path='/opt/ml/checkpoints'
    )

# Expected savings: 50-70% on training costs
```

### 3. Training Job Optimization
```python
# Optimize training duration
OPTIMIZATION_STRATEGIES = {{
    'early_stopping': {{
        'patience': 5,
        'min_delta': 0.001,
        'estimated_savings': '20-30%'
    }},
    'learning_rate_scheduling': {{
        'strategy': 'reduce_on_plateau',
        'estimated_savings': '10-20%'
    }},
    'batch_size_optimization': {{
        'current': 64,
        'optimized': 128,
        'estimated_savings': '15-25%'
    }}
}}
```

## 🚀 Inference Cost Optimization

### 1. Auto-Scaling Configuration
```python
# Implement intelligent auto-scaling
auto_scaling_config = {{
    'min_capacity': 1,
    'max_capacity': 10,
    'target_value': 70.0,  # CPU utilization target
    'scale_in_cooldown': 300,  # 5 minutes
    'scale_out_cooldown': 60   # 1 minute
}}

# Configure auto-scaling
application_autoscaling = boto3.client('application-autoscaling')
application_autoscaling.register_scalable_target(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{project_name.lower()}-endpoint/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    MinCapacity=auto_scaling_config['min_capacity'],
    MaxCapacity=auto_scaling_config['max_capacity']
)

# Expected savings: 40-60% on inference costs
```

### 2. Instance Type Right-Sizing
```python
# Instance type recommendations based on workload
INFERENCE_INSTANCES = {{
    'low_traffic': {{
        'instance_type': 'ml.t2.medium',
        'cost_per_hour': 0.0464,
        'use_case': '<100 requests/hour'
    }},
    'medium_traffic': {{
        'instance_type': 'ml.m5.large', 
        'cost_per_hour': 0.115,
        'use_case': '100-1000 requests/hour'
    }},
    'high_traffic': {{
        'instance_type': 'ml.c5.xlarge',
        'cost_per_hour': 0.204,
        'use_case': '>1000 requests/hour'
    }}
}}
```

### 3. Batch Transform for Batch Inference
```python
# Use batch transform for non-real-time inference
def create_batch_transform():
    transformer = model.transformer(
        instance_count=1,
        instance_type='ml.m5.large',
        output_path='s3://bucket/batch-output/',
        max_concurrent_transforms=4,
        max_payload=100  # MB
    )
    
    # Cost comparison:
    # Real-time endpoint: $0.115/hour * 24 hours = $2.76/day
    # Batch transform: $0.115/hour * 2 hours = $0.23/day
    # Savings: 92% for batch workloads
    
    return transformer
```

## 💾 Storage Cost Optimization

### 1. S3 Lifecycle Policies
```python
# Implement intelligent data lifecycle
lifecycle_config = {{
    'Rules': [
        {{
            'ID': 'TrainingDataLifecycle',
            'Status': 'Enabled',
            'Filter': {{'Prefix': 'data/training/'}},
            'Transitions': [
                {{
                    'Days': 30,
                    'StorageClass': 'STANDARD_IA'  # 40% cheaper
                }},
                {{
                    'Days': 90,
                    'StorageClass': 'GLACIER'      # 80% cheaper
                }},
                {{
                    'Days': 365,
                    'StorageClass': 'DEEP_ARCHIVE' # 95% cheaper
                }}
            ]
        }},
        {{
            'ID': 'ModelArtifactsLifecycle',
            'Status': 'Enabled',
            'Filter': {{'Prefix': 'models/'}},
            'Transitions': [
                {{
                    'Days': 90,
                    'StorageClass': 'STANDARD_IA'
                }}
            ]
        }}
    ]
}}

# Apply lifecycle policy
s3.put_bucket_lifecycle_configuration(
    Bucket=bucket_name,
    LifecycleConfiguration=lifecycle_config
)

# Expected savings: 50-70% on storage costs
```

### 2. Data Compression
```python
# Implement data compression
def compress_training_data():
    import gzip
    import pickle
    
    # Compress training data
    with gzip.open('training_data.pkl.gz', 'wb') as f:
        pickle.dump(training_data, f)
    
    # Typical compression ratios:
    # Text data: 60-80% reduction
    # Numerical data: 30-50% reduction
    # Image data: 10-30% reduction
```

## 📊 Cost Monitoring and Budgets

### 1. Cost Budgets
```python
# Set up cost budgets
def create_cost_budget():
    budgets = boto3.client('budgets')
    
    budget = {{
        'BudgetName': f'{project_name}-SageMaker-Budget',
        'BudgetLimit': {{
            'Amount': '1000',  # Adjust based on your needs
            'Unit': 'USD'
        }},
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostFilters': {{
            'Service': ['Amazon SageMaker'],
            'TagKey': ['Project'],
            'TagValue': [project_name]
        }}
    }}
    
    # Create budget with alerts at 50%, 80%, and 100%
    budgets.create_budget(
        AccountId=account_id,
        Budget=budget,
        NotificationsWithSubscribers=[
            {{
                'Notification': {{
                    'NotificationType': 'ACTUAL',
                    'ComparisonOperator': 'GREATER_THAN',
                    'Threshold': 50
                }},
                'Subscribers': [{{
                    'SubscriptionType': 'EMAIL',
                    'Address': 'your-email@example.com'
                }}]
            }}
        ]
    )
```

### 2. Cost Tracking Dashboard
```python
# Create cost tracking dashboard
def create_cost_dashboard():
    cost_widgets = [
        {{
            'type': 'metric',
            'properties': {{
                'metrics': [
                    ['AWS/Billing', 'EstimatedCharges', 'ServiceName', 'AmazonSageMaker'],
                ],
                'period': 86400,  # Daily
                'stat': 'Maximum',
                'region': 'us-east-1',
                'title': 'Daily SageMaker Costs'
            }}
        }},
        {{
            'type': 'metric',
            'properties': {{
                'metrics': [
                    ['AWS/SageMaker', 'TrainingJobsRunning'],
                    ['AWS/SageMaker', 'EndpointsInService']
                ],
                'title': 'Active Resources'
            }}
        }}
    ]
    
    cloudwatch.put_dashboard(
        DashboardName=f'{project_name}-Cost-Dashboard',
        DashboardBody=json.dumps({{'widgets': cost_widgets}})
    )
```

## 🔧 Advanced Cost Optimization

### 1. Multi-Model Endpoints
```python
# Deploy multiple models on single endpoint
def create_multi_model_endpoint():
    from sagemaker.multidatamodel import MultiDataModel
    
    mdm = MultiDataModel(
        name=f'{project_name.lower()}-multi-model',
        model_data_prefix='s3://bucket/multi-model/',
        image_uri=image_uri,
        role=role
    )
    
    predictor = mdm.deploy(
        initial_instance_count=1,
        instance_type='ml.m5.large'
    )
    
    # Cost savings: 50-70% when hosting multiple models
    return predictor
```

### 2. Serverless Inference
```python
# Use serverless inference for variable workloads
def create_serverless_endpoint():
    serverless_config = {{
        'MemorySizeInMB': 2048,
        'MaxConcurrency': 10
    }}
    
    model.deploy(
        serverless_inference_config=serverless_config,
        endpoint_name=f'{project_name.lower()}-serverless'
    )
    
    # Cost model: Pay per request
    # No charges when not in use
    # Ideal for <100 requests/hour
```

### 3. Reserved Instances
```python
# Reserved instance strategy for predictable workloads
RESERVED_INSTANCE_STRATEGY = {{
    'training': {{
        'instance_type': 'ml.m5.large',
        'term': '1_year',
        'savings': '20-40%',
        'use_case': 'Regular retraining jobs'
    }},
    'inference': {{
        'instance_type': 'ml.m5.large', 
        'term': '1_year',
        'savings': '30-50%',
        'use_case': 'Always-on endpoints'
    }}
}}
```

## 📈 Cost Optimization Roadmap

### Phase 1: Immediate Optimizations (Week 1)
- [ ] Enable spot instances for training
- [ ] Implement auto-scaling for endpoints
- [ ] Set up cost budgets and alerts
- [ ] Apply S3 lifecycle policies

**Expected Savings: 30-40%**

### Phase 2: Advanced Optimizations (Month 1)
- [ ] Right-size instance types based on metrics
- [ ] Implement batch transform for batch workloads
- [ ] Optimize training job duration
- [ ] Implement data compression

**Expected Savings: 50-60%**

### Phase 3: Strategic Optimizations (Month 2-3)
- [ ] Evaluate multi-model endpoints
- [ ] Consider serverless inference
- [ ] Implement reserved instances for predictable workloads
- [ ] Optimize data storage and retention

**Expected Savings: 60-70%**

## 🎯 Cost Optimization Checklist

### Training Optimization
- [ ] Use spot instances for development and testing
- [ ] Implement checkpointing for fault tolerance
- [ ] Optimize batch sizes and learning rates
- [ ] Use early stopping to prevent overtraining
- [ ] Right-size instance types based on workload

### Inference Optimization
- [ ] Implement auto-scaling for variable traffic
- [ ] Use batch transform for batch inference
- [ ] Consider serverless for low-traffic endpoints
- [ ] Optimize model size and inference code
- [ ] Use multi-model endpoints when appropriate

### Storage Optimization
- [ ] Implement S3 lifecycle policies
- [ ] Compress training data and model artifacts
- [ ] Delete unnecessary intermediate files
- [ ] Use appropriate storage classes
- [ ] Implement data retention policies

### Monitoring and Governance
- [ ] Set up cost budgets and alerts
- [ ] Create cost tracking dashboards
- [ ] Implement resource tagging strategy
- [ ] Regular cost reviews and optimization
- [ ] Automated resource cleanup

## 💡 Cost Optimization Tips

### Best Practices
1. **Start Small**: Begin with smaller instance types and scale up as needed
2. **Monitor Continuously**: Set up alerts and review costs weekly
3. **Use Spot Instances**: For non-critical workloads, use spot instances
4. **Optimize Data**: Compress and lifecycle your data appropriately
5. **Right-Size Resources**: Match instance types to actual workload requirements

### Common Pitfalls to Avoid
1. **Over-Provisioning**: Don't use larger instances than necessary
2. **Always-On Endpoints**: Use auto-scaling or serverless for variable traffic
3. **Data Hoarding**: Implement proper data lifecycle management
4. **Ignoring Spot Interruptions**: Implement proper checkpointing
5. **No Cost Monitoring**: Set up budgets and alerts from day one

---

For implementation guidance, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
For monitoring cost metrics, see [MONITORING_GUIDE.md](MONITORING_GUIDE.md)
"""
    
    # Helper methods for documentation generation
    
    def _get_framework_version(self, artifacts: MigrationArtifacts) -> str:
        """Extract framework version from artifacts"""
        # Look for framework version in requirements or default to 2.0.0
        for req_file in artifacts.training_scripts.values():
            if 'torch' in req_file and '>=' in req_file:
                # Extract version from requirements
                return "2.0.0"  # Default for now
        return "2.0.0"
    
    def _format_list(self, items: List[str]) -> str:
        """Format list items as markdown bullets"""
        if not items:
            return "- None detected"
        return "\n".join(f"- {item}" for item in items)
    
    def _format_dependency_replacements(self, dependencies: 'DependencyAnalysis') -> str:
        """Format dependency replacements as markdown"""
        if not dependencies.sagemaker_alternatives:
            return "- No problematic packages detected"
        
        replacements = []
        for old_pkg, new_pkg in dependencies.sagemaker_alternatives.items():
            replacements.append(f"- **{old_pkg}** → {new_pkg}")
        
        return "\n".join(replacements)
    
    def _get_migration_strategy(self, analysis: AnalysisReport) -> str:
        """Determine migration strategy based on analysis"""
        if analysis.risks.overall_risk == RiskLevel.LOW:
            return "automated"
        elif analysis.risks.overall_risk == RiskLevel.MEDIUM:
            return "guided"
        else:
            return "manual"
    
    def _create_dependency_resolution_table(self, dependencies: 'DependencyAnalysis') -> str:
        """Create dependency resolution table"""
        if not dependencies.problematic_packages:
            return "No problematic dependencies detected."
        
        table = "| Package | Issue | Resolution |\n|---------|-------|------------|\n"
        for pkg in dependencies.problematic_packages:
            resolution = dependencies.sagemaker_alternatives.get(pkg, "Manual resolution required")
            table += f"| {pkg} | Compatibility | {resolution} |\n"
        
        return table
    
    def _get_instance_rationale(self, analysis: AnalysisReport) -> str:
        """Get rationale for instance type selection"""
        if analysis.patterns.distributed_training:
            return "Multi-GPU support required for distributed training patterns"
        elif analysis.source_info.estimated_complexity == "complex":
            return "Higher compute capacity needed for complex model architecture"
        else:
            return "Cost-optimized selection for moderate complexity workload"
    
    def _create_error_prevention_list(self, analysis: AnalysisReport) -> str:
        """Create error prevention measures list"""
        measures = [
            "- Embedded model definitions in evaluation scripts",
            "- Automatic tar.gz extraction for SageMaker artifacts", 
            "- Execution role detection with CloudFormation fallbacks",
            "- Retry logic for transient failures"
        ]
        
        if analysis.dependencies.problematic_packages:
            measures.append("- Dependency replacement for SageMaker compatibility")
        
        if analysis.patterns.distributed_training:
            measures.append("- Distributed training configuration validation")
            
        return "\n".join(measures)
    
    def _create_problematic_packages_section(self, dependencies: 'DependencyAnalysis') -> str:
        """Create section about problematic packages"""
        if not dependencies.problematic_packages:
            return "No problematic packages detected in your migration."
        
        section = "The following packages were identified as problematic:\n\n"
        for pkg in dependencies.problematic_packages:
            alternative = dependencies.sagemaker_alternatives.get(pkg, "Manual resolution")
            section += f"- **{pkg}**: {alternative}\n"
        
        return section
    
    def _create_risk_guidance(self, risk_items: List[str], risk_level: str) -> str:
        """Create guidance for risk items"""
        if not risk_items:
            return f"No {risk_level} risk items identified."
        
        guidance = f"### {risk_level.title()} Risk Items\n\n"
        for item in risk_items:
            guidance += f"- **{item}**: Requires careful attention during migration\n"
        
        return guidance
    
    def _create_distributed_training_guidance(self, patterns: 'PatternAnalysis') -> str:
        """Create guidance for distributed training migration"""
        if not patterns.distributed_training:
            return "No distributed training patterns detected."
        
        return """### Distributed Training Migration
- Convert DataParallel to SageMaker distributed training
- Update communication backend configuration
- Modify data loading for multi-node setup
- Test with SageMaker distributed training instances"""
    
    def _create_custom_metrics_guidance(self, patterns: 'PatternAnalysis') -> str:
        """Create guidance for custom metrics migration"""
        if not patterns.custom_metrics:
            return "No custom metrics detected."
        
        return """### Custom Metrics Migration
- Integrate custom metrics with CloudWatch
- Update metric logging for SageMaker format
- Configure metric collection in training scripts
- Set up CloudWatch dashboards for custom metrics"""
    
    def _create_visualization_guidance(self, patterns: 'PatternAnalysis') -> str:
        """Create guidance for visualization code migration"""
        if not patterns.visualization_usage:
            return "No visualization code detected."
        
        return """### Visualization Code Migration
- Replace seaborn with matplotlib-only implementations
- Remove interactive plotting for training environments
- Save plots to S3 instead of displaying
- Use CloudWatch for metric visualization"""
    
    def _get_deployment_strategy(self, analysis: AnalysisReport) -> str:
        """Get deployment strategy based on risk level"""
        if analysis.risks.overall_risk == RiskLevel.LOW:
            return "automated"
        elif analysis.risks.overall_risk == RiskLevel.MEDIUM:
            return "phased"
        else:
            return "manual"
    
    def _estimate_training_costs(self, analysis: AnalysisReport) -> str:
        """Estimate monthly training costs"""
        # Simple cost estimation based on complexity
        if analysis.source_info.estimated_complexity == "simple":
            return "50-100"
        elif analysis.source_info.estimated_complexity == "moderate":
            return "100-300"
        else:
            return "300-800"
    
    def _estimate_inference_costs(self, analysis: AnalysisReport) -> str:
        """Estimate monthly inference costs"""
        # Simple cost estimation
        return "100-500"
    
    def _estimate_storage_costs(self, analysis: AnalysisReport) -> str:
        """Estimate monthly storage costs"""
        # Simple cost estimation based on file count
        if analysis.source_info.total_files < 10:
            return "10-50"
        else:
            return "50-200"
    
    def _estimate_total_costs(self, analysis: AnalysisReport) -> str:
        """Estimate total monthly costs"""
        training = int(self._estimate_training_costs(analysis).split('-')[1])
        inference = int(self._estimate_inference_costs(analysis).split('-')[1])
        storage = int(self._estimate_storage_costs(analysis).split('-')[1])
        total = training + inference + storage
        return str(total)
    
    def _calculate_savings_potential(self, analysis: AnalysisReport) -> str:
        """Calculate potential cost savings percentage"""
        if analysis.risks.overall_risk == RiskLevel.LOW:
            return "60-70"
        elif analysis.risks.overall_risk == RiskLevel.MEDIUM:
            return "40-60"
        else:
            return "30-50"